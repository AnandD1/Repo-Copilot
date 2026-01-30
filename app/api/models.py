"""Pydantic models for API requests and responses."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ReviewRequest(BaseModel):
    """Request to start a code review."""
    repo_url: str = Field(..., description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    pr_number: int = Field(..., description="Pull request number", gt=0)
    github_token: Optional[str] = Field(None, description="GitHub personal access token")


class HITLDecisionRequest(BaseModel):
    """HITL decision from user."""
    run_id: str = Field(..., description="Workflow run ID")
    action: str = Field(..., description="One of: approve, edit, reject, summary_only")
    feedback: Optional[str] = Field(None, description="Optional feedback text")
    edited_issues: Optional[List[Dict[str, Any]]] = Field(None, description="Edited issues if action is edit")


class WorkflowStatus(BaseModel):
    """Status of a workflow run."""
    run_id: str
    status: str
    current_node: Optional[str] = None
    created_at: datetime
    repo_full_name: str
    pr_number: int
    awaiting_hitl: bool = False
    completed: bool = False
    error: Optional[str] = None


class ReviewIssueResponse(BaseModel):
    """Single review issue."""
    severity: str
    category: str
    file_path: str
    line_number: int
    description: str
    suggestion: Optional[str] = None
    evidence_snippet: Optional[str] = None


class FixTaskResponse(BaseModel):
    """Single fix task."""
    description: str
    rationale: str
    affected_files: List[str]
    suggested_approach: str
    effort_estimate: str
    related_issue_indices: List[int]


class GuardrailResponse(BaseModel):
    """Guardrail check results."""
    passed: bool
    failed_checks: List[str]
    warnings: List[str]


class ReviewSummaryResponse(BaseModel):
    """Complete review summary."""
    run_id: str
    repo_full_name: str
    pr_number: int
    issues: List[ReviewIssueResponse]
    fix_tasks: List[FixTaskResponse]
    guardrail_result: GuardrailResponse
    awaiting_hitl: bool
    posted_comment_url: Optional[str] = None
    persisted: bool
