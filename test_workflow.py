"""Example script to run the Phase 4 multi-agent workflow."""

import hashlib
from datetime import datetime

from app.workflow import WorkflowState, create_review_workflow, run_workflow
from app.pr_review import quick_prepare_review


def generate_run_id(repo_name: str, pr_number: int) -> str:
    """Generate unique run ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{repo_name}_PR{pr_number}_{timestamp}"


def generate_diff_hash(hunks: list) -> str:
    """Generate hash of diff for tracking."""
    content = str(hunks)
    return hashlib.md5(content.encode()).hexdigest()[:12]


def main():
    """Run example workflow."""
    
    # Example: Use Phase 2 to prepare review
    print("=" * 80)
    print("PHASE 4: Multi-Agent Workflow Example")
    print("=" * 80)
    
    # Example repo and PR
    repo_full_name = "AnandD1/ScratchYOLO"
    pr_number = 2
    
    print(f"\nPreparing review for: {repo_full_name} PR#{pr_number}")
    print("(Using Phase 2 coordinator to fetch and parse PR...)\n")
    
    # Use Phase 2 to get PR data and hunks
    try:
        session = quick_prepare_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number
        )
        
        print(f"✓ PR data loaded: {len(session.review_units)} review units")
        
        # Extract owner/name from repo_full_name
        repo_owner, repo_name = repo_full_name.split("/")
        
        # Build hunks from review units
        hunks = []
        for i, unit in enumerate(session.review_units):
            hunk = {
                "hunk_id": f"{unit.context.file_path}:{unit.context.new_line_start}",
                "file_path": unit.context.file_path,
                "old_line_start": unit.context.old_line_start or 0,
                "old_line_end": unit.context.old_line_end or 0,
                "new_line_start": unit.context.new_line_start or 0,
                "new_line_end": unit.context.new_line_end or 0,
                "added_lines": unit.context.added_lines,
                "removed_lines": unit.context.removed_lines,
                "context_lines": unit.context.context_lines,
            }
            hunks.append(hunk)
        
        # Limit to first 3 hunks for demo
        hunks = hunks[:3]
        
        print(f"✓ Converted to {len(hunks)} hunks for workflow\n")
        
        # Create initial state
        run_id = generate_run_id(repo_name, pr_number)
        diff_hash = generate_diff_hash(hunks)
        
        initial_state = WorkflowState(
            run_id=run_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_id=f"{repo_owner}_{repo_name}_main",  # Qdrant collection name
            pr_number=pr_number,
            pr_sha=session.pr_data.head_sha,
            diff_hash=diff_hash,
            hunks=hunks,
        )
        
        print( "Initial state created:")
        print(f"  Run ID: {run_id}")
        print(f"  Repo: {repo_owner}/{repo_name}")
        print(f"  PR: #{pr_number}")
        print(f"  Hunks: {len(hunks)}")
        print()
        
        # Create and run workflow
        workflow = create_review_workflow()
        final_state = run_workflow(initial_state, workflow)
        
        # Print final results
        print("\n" + "=" * 80)
        print("WORKFLOW RESULTS")
        print("=" * 80)
        
        if final_state:
            print(f"\nFinal node: {final_state.get('current_node', 'unknown')}")
            print(f"Persisted: {final_state.get('persisted', False)}")
            
            if final_state.get('persistence_path'):
                print(f"State saved to: {final_state['persistence_path']}")
            
            if final_state.get('posted_comment_url'):
                print(f"Comment posted: {final_state['posted_comment_url']}")
            
            if final_state.get('errors'):
                print(f"\nErrors encountered: {len(final_state['errors'])}")
                for error in final_state['errors']:
                    print(f"  - {error}")
        
        print("\n" + "=" * 80)
        print("Workflow execution complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
