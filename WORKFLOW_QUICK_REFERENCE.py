"""Quick reference guide for Phase 4 workflow usage."""

# ============================================================================
# PHASE 4 - MULTI-AGENT WORKFLOW QUICK REFERENCE
# ============================================================================

"""
This guide provides quick examples for using the Phase 4 multi-agent workflow.
"""

# ----------------------------------------------------------------------------
# Example 1: Basic Workflow Execution
# ----------------------------------------------------------------------------

from app.workflow import WorkflowState, create_review_workflow, run_workflow
from datetime import datetime

# Create initial state
state = WorkflowState(
    run_id="my_review_001",
    repo_owner="owner",
    repo_name="repo",
    repo_id="owner_repo_main",
    pr_number=123,
    pr_sha="abc123def456",
    diff_hash="hash789",
    hunks=[
        {
            "hunk_id": "file.py:10",
            "file_path": "src/file.py",
            "old_line_start": 10,
            "old_line_end": 15,
            "new_line_start": 10,
            "new_line_end": 18,
            "added_lines": ["    new_code()"],
            "removed_lines": ["    old_code()"],
            "context_lines": ["def function():", "    # Context"],
        }
    ],
)

# Run workflow
workflow = create_review_workflow()
final = run_workflow(state, workflow)

# Check results
print(f"Issues: {len(final['review_issues'])}")
print(f"Tasks: {len(final['fix_tasks'])}")


# ----------------------------------------------------------------------------
# Example 2: Integration with Phase 2 (PR Fetcher)
# ----------------------------------------------------------------------------

from app.pr_review import quick_prepare_review
from app.workflow import WorkflowState, create_review_workflow, run_workflow

# Fetch and parse PR
session = quick_prepare_review(
    repo_url="https://github.com/owner/repo.git",
    pr_number=123
)

# Convert to workflow hunks
hunks = []
for unit in session.units[:5]:  # First 5 hunks
    hunks.append({
        "hunk_id": f"{unit.context.file_path}:{unit.context.new_line_start}",
        "file_path": unit.context.file_path,
        "old_line_start": unit.context.old_line_start or 0,
        "old_line_end": unit.context.old_line_end or 0,
        "new_line_start": unit.context.new_line_start or 0,
        "new_line_end": unit.context.new_line_end or 0,
        "added_lines": unit.context.added_lines,
        "removed_lines": unit.context.removed_lines,
        "context_lines": unit.context.context_lines,
    })

# Create and run workflow
state = WorkflowState(
    run_id=f"pr_{session.pr_data.number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    repo_owner="owner",
    repo_name="repo",
    repo_id="owner_repo_main",
    pr_number=session.pr_data.number,
    pr_sha=session.pr_data.head_sha,
    diff_hash="hash",
    hunks=hunks,
)

final = run_workflow(state)


# ----------------------------------------------------------------------------
# Example 3: Custom Agent Configuration
# ----------------------------------------------------------------------------

from app.workflow import (
    RetrieverAgent,
    ReviewerAgent,
    PatchPlannerAgent,
    GuardrailAgent,
    HITLGate,
    PublisherNotifier,
    PersistenceAgent,
)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Create custom agents with different configs
reviewer = ReviewerAgent(model_name="qwen2.5-coder:7b-instruct")
planner = PatchPlannerAgent(model_name="qwen2.5-coder:7b-instruct")
persistence = PersistenceAgent(storage_dir="./custom_runs")

# Build custom workflow
workflow = StateGraph(WorkflowState)
workflow.add_node("retriever", RetrieverAgent())
workflow.add_node("reviewer", reviewer)
workflow.add_node("planner", planner)
workflow.add_node("guardrail", GuardrailAgent())
workflow.add_node("hitl", HITLGate())
workflow.add_node("publish", PublisherNotifier())
workflow.add_node("persistence", persistence)

# ... define edges and compile


# ----------------------------------------------------------------------------
# Example 4: Accessing Workflow Results
# ----------------------------------------------------------------------------

final_state = run_workflow(initial_state)

# Access review issues
for issue in final_state['review_issues']:
    print(f"[{issue.severity.value}] {issue.category.value}")
    print(f"  {issue.file_path}:{issue.line_number}")
    print(f"  {issue.explanation}")
    print(f"  Suggestion: {issue.suggestion}")
    print(f"  Evidence: {issue.evidence_references}")
    print()

# Access fix tasks
for task in final_state['fix_tasks']:
    print(f"Task: {task.title} [{task.effort_estimate.value}]")
    print(f"  Why: {task.why_it_matters}")
    print(f"  Files: {task.affected_files}")
    print(f"  Approach: {task.suggested_approach}")
    print()

# Check guardrail results
if final_state['guardrail_result']:
    result = final_state['guardrail_result']
    print(f"Guardrails: {'PASSED' if result.passed else 'FAILED'}")
    if result.blocked_reasons:
        print(f"Blocked: {result.blocked_reasons}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")

# Check HITL decision
if final_state['hitl_decision']:
    decision = final_state['hitl_decision']
    print(f"Decision: {decision.action.value}")
    print(f"Feedback: {decision.feedback}")

# Check publication
if final_state['posted_comment_url']:
    print(f"Comment posted: {final_state['posted_comment_url']}")

# Check persistence
if final_state['persisted']:
    print(f"State saved: {final_state['persistence_path']}")


# ----------------------------------------------------------------------------
# Example 5: Programmatic HITL Decision (No User Input)
# ----------------------------------------------------------------------------

from app.workflow.state import HITLDecision, HITLAction

# Create workflow with auto-approve
class AutoApproveHITL:
    """HITL gate that auto-approves for testing."""
    
    def __call__(self, state):
        # Auto-approve without user input
        decision = HITLDecision(
            action=HITLAction.APPROVE,
            feedback="Auto-approved for testing"
        )
        return {
            "hitl_decision": decision,
            "current_node": "hitl"
        }

# Use in custom workflow
from langgraph.graph import StateGraph

workflow = StateGraph(WorkflowState)
# ... add other nodes ...
workflow.add_node("hitl", AutoApproveHITL())  # Custom HITL
# ... continue workflow setup


# ----------------------------------------------------------------------------
# Example 6: Error Handling
# ----------------------------------------------------------------------------

try:
    final_state = run_workflow(initial_state)
    
    # Check for errors
    if final_state.get('errors'):
        print(f"Workflow completed with {len(final_state['errors'])} errors:")
        for error in final_state['errors']:
            print(f"  - {error}")
    
    # Check if persisted
    if not final_state.get('persisted'):
        print("Warning: Workflow state not persisted")
    
except Exception as e:
    print(f"Workflow failed: {e}")
    import traceback
    traceback.print_exc()


# ----------------------------------------------------------------------------
# Example 7: Loading Persisted State
# ----------------------------------------------------------------------------

import json
from pathlib import Path

# Load persisted state
with open("workflow_runs/run_id_timestamp.json") as f:
    state_dict = json.load(f)

# Reconstruct WorkflowState
from app.workflow import WorkflowState

loaded_state = WorkflowState(**state_dict)

# Access results
print(f"Loaded run: {loaded_state.run_id}")
print(f"Issues: {len(loaded_state.review_issues)}")
print(f"Tasks: {len(loaded_state.fix_tasks)}")


# ----------------------------------------------------------------------------
# Example 8: Batch Processing Multiple PRs
# ----------------------------------------------------------------------------

prs = [
    {"repo": "owner/repo1", "pr_number": 1},
    {"repo": "owner/repo2", "pr_number": 2},
    {"repo": "owner/repo3", "pr_number": 3},
]

workflow = create_review_workflow()
results = []

for pr_info in prs:
    # Fetch PR and create state
    # ... (use Phase 2 integration)
    
    # Run workflow
    final = run_workflow(state, workflow)
    results.append(final)
    
    print(f"✓ PR {pr_info['pr_number']}: {len(final['review_issues'])} issues")

# Aggregate results
total_issues = sum(len(r['review_issues']) for r in results)
print(f"\nTotal issues across {len(prs)} PRs: {total_issues}")


# ============================================================================
# CONFIGURATION TIPS
# ============================================================================

"""
1. LLM Model Selection:
   - Default: qwen2.5-coder:7b-instruct (good balance)
   - Faster: qwen2.5-coder:3b (lower quality)
   - Better: qwen2.5-coder:14b (slower, needs more RAM)

2. Temperature Settings:
   - Reviewer: 0.1 (deterministic, consistent reviews)
   - Planner: 0.2 (slightly creative task grouping)
   - Lower = more consistent, Higher = more creative

3. Retrieval Tuning:
   - top_k for similar code: 3-5 (balance coverage vs noise)
   - Reranking: Always use for better relevance
   - Local context: 3 chunks (sufficient for most cases)

4. Guardrail Strictness:
   - Enable all checks for production
   - Disable secret scanning for internal repos (if needed)
   - Prompt injection: Warning-only by default

5. HITL Options:
   - Console: Good for testing, manual review
   - Auto-approve: For CI/CD integration (careful!)
   - Web UI: Future Phase 5 (better UX)

6. Persistence:
   - Keep all runs for auditing
   - Clean old runs periodically (cronjob)
   - Archive to S3/blob storage for long-term

7. Performance:
   - Limit hunks for large PRs (e.g., top 10 most changed)
   - Parallel agent execution (future optimization)
   - Cache retrieval bundles for re-runs
"""


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

"""
Issue: "No module named 'langgraph'"
Solution: pip install langgraph

Issue: "Ollama connection refused"
Solution: Start Ollama server: ollama serve

Issue: "Qdrant connection failed"
Solution: Start Qdrant: docker run -p 6333:6333 qdrant/qdrant

Issue: "No retrieval results"
Solution: Ensure repository is ingested (Phase 1)

Issue: "LLM returns invalid JSON"
Solution: Lower temperature or use more powerful model

Issue: "Too many issues found"
Solution: Adjust guardrail thresholds or prompt tuning

Issue: "Workflow hangs at HITL"
Solution: Provide input at console prompt (or use auto-approve for testing)
"""
