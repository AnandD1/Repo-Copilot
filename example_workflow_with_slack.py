"""Example: Running PR review workflow with Slack notifications (Phase 6)."""

import hashlib
from datetime import datetime

from app.workflow import WorkflowState, create_review_workflow, run_workflow
from app.pr_review import quick_prepare_review
from config.settings import Settings


def generate_run_id(repo_name: str, pr_number: int) -> str:
    """Generate unique run ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{repo_name}_PR{pr_number}_{timestamp}"


def generate_diff_hash(hunks: list) -> str:
    """Generate hash of diff for tracking."""
    content = str(hunks)
    return hashlib.md5(content.encode()).hexdigest()[:12]


def main():
    """Run workflow with Slack notifications enabled."""
    
    print("=" * 80)
    print("PHASE 6: PR Review Workflow with Slack Notifications")
    print("=" * 80)
    
    # Load settings (includes Slack config from .env)
    settings = Settings()
    
    print("\n📋 Settings Loaded:")
    print(f"  Slack Enabled: {settings.slack_enabled}")
    print(f"  Slack Channel: {settings.slack_channel}")
    print(f"  Webhook URL: {settings.slack_webhook_url[:50] if settings.slack_webhook_url else 'Not configured'}...")
    print(f"  HITL Base URL: {settings.hitl_base_url}")
    
    # Example repo and PR
    repo_full_name = "AnandD1/ScratchYOLO"
    pr_number = 2
    
    print(f"\n🔍 Preparing review for: {repo_full_name} PR#{pr_number}")
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
        for unit in session.review_units:
            hunks.append({
                'hunk_id': f'hunk_{len(hunks)}',
                'file_path': unit.context.file_path,
                'old_start': 1,
                'new_start': 1,
                'old_lines': 10,
                'new_lines': 10,
                'changes': unit.code_snippet[:200]
            })
        
        # Create initial workflow state
        initial_state = WorkflowState(
            run_id=generate_run_id(repo_name, pr_number),
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_id=f"{repo_owner}_{repo_name}_main",
            pr_number=pr_number,
            pr_sha=session.pr_data.head_sha,
            diff_hash=generate_diff_hash(hunks),
            hunks=hunks
        )
        
        print(f"\n✓ Initial state created:")
        print(f"  Run ID: {initial_state.run_id}")
        print(f"  Repo: {initial_state.repo_owner}/{initial_state.repo_name}")
        print(f"  Hunks: {len(initial_state.hunks)}")
        
        # Create workflow graph with settings (enables Slack notifications)
        print(f"\n🔧 Creating workflow with Slack notifications enabled...")
        workflow = create_review_workflow(
            github_token=settings.github_token,
            settings=settings  # Pass settings for Slack integration
        )
        
        print(f"✓ Workflow created")
        
        # Run the workflow
        print(f"\n🚀 Running multi-agent workflow...")
        print("=" * 80)
        
        final_state = run_workflow(workflow, initial_state)
        
        print("\n" + "=" * 80)
        print("✅ WORKFLOW COMPLETE")
        print("=" * 80)
        
        # Display results
        print(f"\n📊 Results:")
        print(f"  Issues found: {len(final_state.review_issues)}")
        print(f"  Fix tasks: {len(final_state.fix_tasks)}")
        print(f"  Comment posted: {final_state.posted_comment_url or 'N/A'}")
        print(f"  Slack notification sent: {'✓ Yes' if final_state.notification_sent else '✗ No'}")
        print(f"  Persisted: {'✓ Yes' if final_state.persisted else '✗ No'}")
        
        if final_state.notification_sent:
            print(f"\n🎉 SUCCESS! Slack notification sent to {settings.slack_channel}")
            print(f"   Check your Slack channel to see the PR review summary!")
        
        if final_state.errors:
            print(f"\n⚠️  Errors encountered:")
            for error in final_state.errors:
                print(f"  - {error}")
        
        # Show where results are persisted
        if final_state.persistence_path:
            print(f"\n💾 Results saved to: {final_state.persistence_path}")
        
        return final_state
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    final_state = main()
    
    if final_state:
        print("\n" + "=" * 80)
        print("🎊 Phase 6 Demo Complete!")
        print("=" * 80)
        print(f"\nKey Features Demonstrated:")
        print(f"  ✅ Full workflow execution")
        print(f"  ✅ Slack notification integration")
        print(f"  ✅ Settings-based configuration")
        print(f"  ✅ Automatic notification sending")
        print(f"\nNext Steps:")
        print(f"  1. Check {Settings().slack_channel or '#anandprojects'} in Slack")
        print(f"  2. Review the notification content")
        print(f"  3. Click the links in the notification")
        print(f"  4. Use this pattern for all PR reviews!")
        print("=" * 80)
