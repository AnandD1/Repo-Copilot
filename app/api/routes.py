"""FastAPI routes for PR review system."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.api.orchestrator import WorkflowOrchestrator
from config.settings import Settings

router = APIRouter()

# Global orchestrator instance
orchestrator = WorkflowOrchestrator()


class IngestRequest(BaseModel):
    """Request model for repository ingestion."""
    repo_url: str = Field(..., description="GitHub repository URL")


class PRFetchRequest(BaseModel):
    """Request model for PR fetch and parse."""
    repo_url: str = Field(..., description="GitHub repository URL")
    pr_number: int = Field(..., description="Pull request number", gt=0)
    github_token: Optional[str] = Field(None, description="GitHub token (optional)")


class ExecuteWorkflowRequest(BaseModel):
    """Request model for workflow execution (Phase 3-6)."""
    repo_url: str = Field(..., description="GitHub repository URL")
    pr_number: int = Field(..., description="Pull request number", gt=0)
    pr_data: Dict[str, Any] = Field(..., description="PR data from Phase 2")
    review_units: List[Dict[str, Any]] = Field(..., description="Review units from Phase 2")
    github_token: Optional[str] = Field(None, description="GitHub token (optional)")
    run_evaluation: bool = Field(False, description="Run evaluation metrics")


class PRReviewRequest(BaseModel):
    """Request model for PR review."""
    repo_url: str = Field(..., description="GitHub repository URL")
    pr_number: int = Field(..., description="Pull request number", gt=0)
    github_token: Optional[str] = Field(None, description="GitHub token (optional)")
    run_evaluation: bool = Field(False, description="Run evaluation metrics")


class PRReviewResponse(BaseModel):
    """Response model for PR review."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str = "1.0.0"
    services: Dict[str, str]


@router.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "service": "Repo-Copilot PR Review API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    settings = Settings()
    
    # Check Qdrant connection
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        client.get_collections()
        qdrant_status = "healthy"
    except Exception as e:
        qdrant_status = f"unhealthy: {str(e)}"
    
    # Check Ollama connection
    try:
        import requests
        response = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        ollama_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        ollama_status = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        services={
            "qdrant": qdrant_status,
            "ollama": ollama_status,
            "github": "configured" if settings.github_token else "not configured",
            "slack": "configured" if settings.slack_enabled else "disabled"
        }
    )


@router.post("/review", response_model=PRReviewResponse)
async def review_pr(request: PRReviewRequest):
    """
    Run PR review workflow.
    
    This endpoint executes the complete workflow:
    1. Ingestion - Clone and embed repository
    2. PR Fetch - Get PR data from GitHub
    3. Retrieval - Find relevant context
    4. Review - Analyze changes with agents
    5. Guardrails - Validate review quality
    6. HITL - Human-in-the-loop decision
    7. Publish - Post comments and notifications
    8. Evaluation - Optional metrics calculation
    """
    try:
        result = await orchestrator.run_full_workflow(
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            github_token=request.github_token,
            run_evaluation=request.run_evaluation
        )
        
        if result['success']:
            return PRReviewResponse(
                success=True,
                message=f"PR review complete for {result['repo_owner']}/{result['repo_name']} #{result['pr_number']}",
                data=result
            )
        else:
            return PRReviewResponse(
                success=False,
                message="PR review failed",
                error=result.get('error', 'Unknown error'),
                data=result
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/cleanup", response_model=Dict[str, str])
async def cleanup_all():
    """Force cleanup of all temporary resources."""
    try:
        orchestrator.cleanup_manager.full_cleanup()
        orchestrator.current_repo_id = None
        
        return {
            "status": "success",
            "message": "All resources cleaned successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )


@router.get("/status", response_model=Dict[str, Any])
async def get_status():
    """Get current orchestrator status."""
    return {
        "current_repo": orchestrator.current_repo_id,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/ingest", response_model=Dict[str, Any])
async def ingest_repository(request: IngestRequest):
    """
    Step 1: Ingest repository and create embeddings.
    
    This is the first step of the workflow. It:
    - Parses the GitHub URL
    - Checks if repo is already ingested
    - Cleans up old repos if switching repos
    - Clones and embeds the repository
    """
    try:
        result = await orchestrator.run_ingestion_only(
            repo_url=request.repo_url
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/fetch-pr", response_model=Dict[str, Any])
async def fetch_pr(request: PRFetchRequest):
    """Fetch and parse a pull request (Phase 2)."""
    try:
        result = await orchestrator.run_pr_fetch_only(
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            github_token=request.github_token
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-workflow", response_model=Dict[str, Any])
async def execute_workflow(request: ExecuteWorkflowRequest):
    """Execute workflow agents (Phase 3-6: Retrieval → Review → Guardrails → HITL → Publish → Persist)."""
    try:
        result = await orchestrator.run_workflow_execution(
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            pr_data=request.pr_data,
            review_units=request.review_units,
            github_token=request.github_token,
            run_evaluation=request.run_evaluation
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class HITLDecisionRequest(BaseModel):
    """Request model for HITL decision."""
    run_id: str = Field(..., description="Workflow run ID")
    action: str = Field(..., description="HITL action: approve, edit, reject, post_summary_only")
    edited_content: Optional[str] = Field(None, description="Edited review content")
    feedback: Optional[str] = Field(None, description="User feedback")


@router.post("/hitl-decision", response_model=Dict[str, Any])
async def submit_hitl_decision(request: HITLDecisionRequest):
    """Submit HITL decision and resume workflow."""
    try:
        result = await orchestrator.resume_workflow_with_hitl(
            run_id=request.run_id,
            action=request.action,
            edited_content=request.edited_content,
            feedback=request.feedback
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow-status/{run_id}", response_model=Dict[str, Any])
async def get_workflow_status(run_id: str):
    """Get current workflow status."""
    try:
        result = await orchestrator.get_workflow_status(run_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    """Fetch and parse a pull request (Phase 2)."""
    try:
        result = await orchestrator.run_pr_fetch_only(
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            github_token=request.github_token
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-workflow", response_model=Dict[str, Any])
async def execute_workflow(request: ExecuteWorkflowRequest):
    """
    Step 2: Fetch and parse PR.
    
    This is the second step of the workflow. It:
    - Fetches PR data from GitHub
    - Parses diffs into hunks
    - Builds review units
    """
    try:
        result = await orchestrator.run_pr_fetch_only(
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            github_token=request.github_token
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PR fetch failed: {str(e)}"
        )
