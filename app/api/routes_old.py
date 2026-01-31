"""FastAPI routes for PR review system."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.api.orchestrator import WorkflowOrchestrator
from config.settings import Settings

router = APIRouter()
# Global orchestrator instance
orchestrator = WorkflowOrchestrator()


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
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
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
    if url.startswith('https://github.com/'):
        url = url.replace('https://github.com/', '')
    elif url.startswith('http://github.com/'):
        url = url.replace('http://github.com/', '')
    elif url.startswith('git@github.com:'):
        url = url.replace('git@github.com:', '')
    
    # Split and validate
    parts = url.split('/')
    if len(parts) >= 2:
        owner = parts[0].strip()
        repo = parts[1].strip()
        if owner and repo:
            return owner, repo
    
    raise ValueError(f"Invalid GitHub URL format: {repo_url}. Expected format: https://github.com/owner/repo")


async def run_workflow_background(run_id: str, state: WorkflowState) -> None:
    """Run workflow in background and pause at HITL."""
    try:
        active_workflows[run_id] = {
            "state": state,
            "status": "running",
            "awaiting_hitl": False,
            "hitl_decision": None,
            "created_at": datetime.now(),
            "paused": False
        }
        
        print(f"🚀 Starting workflow {run_id} in background...")
        
        # Import agents
        from ..workflow.retriever_agent import RetrieverAgent
        from ..workflow.reviewer_agent import ReviewerAgent
        from ..workflow.planner_agent import PatchPlannerAgent
        from ..workflow.guardrail_agent import GuardrailAgent
        from ..workflow.publisher_notifier import PublisherNotifier
        from ..workflow.persistence_agent import PersistenceAgent
        
        # Run agents sequentially until HITL
        retriever = RetrieverAgent()
        reviewer = ReviewerAgent()
        planner = PatchPlannerAgent()
        guardrail = GuardrailAgent()
        
        # Execute phases
        state_dict: Dict[str, Any] = state.model_dump()
        
        # Phase 1: Retrieval
        ret_result = retriever(WorkflowState(**state_dict))
        state_dict.update(ret_result)
        active_workflows[run_id]["state"] = WorkflowState(**state_dict)
        
        # Phase 2: Review
        rev_result = reviewer(WorkflowState(**state_dict))
        state_dict.update(rev_result)
        active_workflows[run_id]["state"] = WorkflowState(**state_dict)
        
        # Phase 3: Planning
        plan_result = planner(WorkflowState(**state_dict))
        state_dict.update(plan_result)
        active_workflows[run_id]["state"] = WorkflowState(**state_dict)
        
        # Phase 4: Guardrails
        guard_result = guardrail(WorkflowState(**state_dict))
        state_dict.update(guard_result)
        active_workflows[run_id]["state"] = WorkflowState(**state_dict)
        
        # Phase 5: HITL - PAUSE HERE
        active_workflows[run_id]["status"] = "awaiting_hitl"
        active_workflows[run_id]["awaiting_hitl"] = True
        active_workflows[run_id]["paused"] = True
        
        # Wait for HITL decision
        while run_id in active_workflows and active_workflows[run_id]["paused"]:
            await asyncio.sleep(1)
        
        # Get HITL decision and continue
        hitl_decision = active_workflows[run_id].get("hitl_decision")
        if hitl_decision:
            state_dict["hitl_decision"] = hitl_decision
            
            # Phase 6: Publishing (if approved)
            if hitl_decision["action"] in [HITLAction.APPROVE, HITLAction.POST_SUMMARY_ONLY]:
                publisher = PublisherNotifier()
                pub_result = publisher(WorkflowState(**state_dict))
                state_dict.update(pub_result)
            
            # Phase 7: Persistence
            persistence = PersistenceAgent()
            pers_result = persistence(WorkflowState(**state_dict))
            state_dict.update(pers_result)
        
        # Update final state
        active_workflows[run_id]["state"] = WorkflowState(**state_dict)
        active_workflows[run_id]["status"] = "completed"
        active_workflows[run_id]["awaiting_hitl"] = False
        print(f"✅ Workflow {run_id} completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Workflow {run_id} failed: {error_msg}")
        import traceback
        traceback.print_exc()
        
        if run_id in active_workflows:
            active_workflows[run_id]["status"] = "error"
            active_workflows[run_id]["error"] = error_msg
        else:
            # Workflow was deleted while running
            print(f"⚠️ Workflow {run_id} was deleted during execution")


@router.post("/review/start")
async def start_review(request: ReviewRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Start a new code review workflow."""
    try:
        # Parse GitHub URL
        try:
            owner, repo = extract_repo_info(request.repo_url)
            repo_full_name = f"{owner}/{repo}"
            print(f"✓ Parsed repo: {repo_full_name}")
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        
        # Set GitHub token if provided
        if request.github_token:
            os.environ["GITHUB_TOKEN"] = request.github_token
        elif not os.environ.get("GITHUB_TOKEN"):
            raise HTTPException(
                status_code=400, 
                detail="GitHub token required. Provide via request or set GITHUB_TOKEN environment variable."
            )
        
        # Prepare review using Phase 2
        print(f"📥 Fetching PR #{request.pr_number} from {repo_full_name}...")
        try:
            session = quick_prepare_review(
                repo_full_name=repo_full_name,
                pr_number=request.pr_number
            )
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to fetch PR: {error_msg}")
            # Extract meaningful error from GitHub API response
            if "404" in error_msg:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Repository or PR not found. Check: 1) Repository '{repo_full_name}' exists and is accessible, 2) PR #{request.pr_number} exists, 3) GitHub token has correct permissions."
                )
            elif "401" in error_msg or "403" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail="GitHub authentication failed. Check your GitHub token permissions."
                )
            else:
                raise HTTPException(status_code=500, detail=f"Failed to fetch PR: {error_msg}")
        
        if not session or not session.review_units:
            raise HTTPException(
                status_code=400, 
                detail=f"No code changes found in PR #{request.pr_number}. The PR may be empty or only contain non-reviewable changes."
            )
        
        # Convert review units to workflow hunks (as dictionaries matching WorkflowState schema)
        hunks = []
        for unit in session.review_units:
            # Each ReviewUnit represents a reviewable chunk of changes
            # Convert to hunk dictionary format for workflow
            hunk_dict = {
                "file_path": unit.context.file_path,
                "old_start": unit.context.old_line_start or 0,
                "old_count": unit.context.deletions,
                "new_start": unit.context.new_line_start or 0,
                "new_count": unit.context.additions,
                "lines": unit.context.added_lines + unit.context.removed_lines,
                "change_type": "modified"
            }
            
            # Determine change type
            if unit.context.is_new_file:
                hunk_dict["change_type"] = "added"
            elif unit.context.is_deleted_file:
                hunk_dict["change_type"] = "deleted"
            elif unit.context.is_renamed:
                hunk_dict["change_type"] = "renamed"
            
            hunks.append(hunk_dict)
        
        # Generate diff hash for tracking
        diff_hash = hashlib.md5(str(hunks).encode()).hexdigest()[:12]
        
        # Create workflow state
        run_id = f"{repo}_{session.pr_data.number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        state = WorkflowState(
            run_id=run_id,
            repo_owner=owner,
            repo_name=repo,
            repo_id=f"{owner}_{repo}",
            pr_number=session.pr_data.number,
            pr_sha=session.pr_data.head_sha,
            diff_hash=diff_hash,
            hunks=hunks
        )
        
        # Start workflow in background
        background_tasks.add_task(run_workflow_background, run_id, state)
        
        return {
            "run_id": run_id,
            "repo_full_name": repo_full_name,
            "pr_number": session.pr_data.number,
            "status": "started",
            "hunks_count": len(hunks)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # URL parsing errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = str(e)
        print(f"❌ Unexpected error in start_review: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_msg}")


@router.get("/review/{run_id}/status")
async def get_status(run_id: str) -> WorkflowStatus:
    """Get current status of a workflow run."""
    if run_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    workflow = active_workflows[run_id]
    state = workflow["state"]
    
    return WorkflowStatus(
        run_id=run_id,
        status=workflow["status"],
        current_node=workflow.get("current_node"),
        created_at=workflow["created_at"],
        repo_full_name=f"{state.repo_owner}/{state.repo_name}",
        pr_number=state.pr_number,
        awaiting_hitl=workflow["awaiting_hitl"],
        completed=workflow["status"] == "completed",
        error=workflow.get("error")
    )


@router.get("/review/{run_id}/summary")
async def get_review_summary(run_id: str) -> ReviewSummaryResponse:
    """Get review summary with issues and tasks."""
    if run_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    workflow = active_workflows[run_id]
    state = workflow["state"]
    
    # Convert issues
    issues = []
    for issue in state.review_issues:
        issues.append(ReviewIssueResponse(
            severity=issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
            category=issue.category.value if hasattr(issue.category, 'value') else str(issue.category),
            file_path=issue.file_path,
            line_number=issue.line_number,
            description=issue.explanation,
            suggestion=issue.suggestion,
            evidence_snippet=issue.evidence_references[0] if issue.evidence_references else None
        ))
    
    # Convert fix tasks
    fix_tasks = []
    for task in state.fix_tasks:
        fix_tasks.append(FixTaskResponse(
            description=task.title,
            rationale=task.why_it_matters,
            affected_files=task.affected_files,
            suggested_approach=task.suggested_approach,
            effort_estimate=task.effort_estimate.value if hasattr(task.effort_estimate, 'value') else str(task.effort_estimate),
            related_issue_indices=task.related_issues
        ))
    
    # Convert guardrail result
    guardrail = GuardrailResponse(
        passed=state.guardrail_result.passed if state.guardrail_result else True,
        failed_checks=state.guardrail_result.blocked_reasons if state.guardrail_result else [],
        warnings=state.guardrail_result.warnings if state.guardrail_result else []
    )
    
    return ReviewSummaryResponse(
        run_id=run_id,
        repo_full_name=f"{state.repo_owner}/{state.repo_name}",
        pr_number=state.pr_number,
        issues=issues,
        fix_tasks=fix_tasks,
        guardrail_result=guardrail,
        awaiting_hitl=workflow["awaiting_hitl"],
        posted_comment_url=state.posted_comment_url,
        persisted=state.persisted
    )


@router.post("/review/{run_id}/hitl-decision")
async def submit_hitl_decision(run_id: str, decision: HITLDecisionRequest) -> Dict[str, str]:
    """Submit HITL decision to continue workflow."""
    if run_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    workflow = active_workflows[run_id]
    
    if not workflow["awaiting_hitl"]:
        raise HTTPException(status_code=400, detail="Workflow is not awaiting HITL decision")
    
    # Map action string to HITLAction enum
    action_map = {
        "approve": HITLAction.APPROVE,
        "edit": HITLAction.EDIT,
        "reject": HITLAction.REJECT,
        "summary_only": HITLAction.POST_SUMMARY_ONLY
    }
    
    if decision.action not in action_map:
        raise HTTPException(status_code=400, detail=f"Invalid action: {decision.action}")
    
    # Store decision and resume workflow
    workflow["hitl_decision"] = {
        "action": action_map[decision.action],
        "feedback": decision.feedback,
        "edited_issues": decision.edited_issues
    }
    workflow["paused"] = False
    
    return {
        "status": "decision_accepted",
        "run_id": run_id,
        "action": decision.action
    }


@router.get("/review/{run_id}/view", response_class=HTMLResponse)
async def view_review(run_id: str, request: Request):
    """Render review page with HITL interface."""
    if run_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    workflow = active_workflows[run_id]
    state = workflow["state"]
    
    return templates.TemplateResponse("review.html", {
        "request": request,
        "run_id": run_id,
        "repo_full_name": f"{state.repo_owner}/{state.repo_name}",
        "pr_number": state.pr_number,
        "awaiting_hitl": workflow["awaiting_hitl"],
        "status": workflow["status"]
    })
