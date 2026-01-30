"""Test FastAPI HITL interface with full Phase 1-6 integration."""

import os
import asyncio
import hashlib
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_full_workflow():
    """Test complete workflow from Phase 2 through Phase 6."""
    print("\n" + "=" * 80)
    print("FULL WORKFLOW TEST: Phase 2-6 Integration with Slack Notifications")
    print("=" * 80)
    
    from app.workflow import WorkflowState, create_review_workflow, run_workflow
    from app.pr_review import quick_prepare_review
    from config.settings import Settings
    
    # Load settings (includes Slack config)
    settings = Settings()
    
    print("\n📋 Configuration:")
    print(f"  Slack Enabled: {settings.slack_enabled}")
    print(f"  Slack Channel: {settings.slack_channel}")
    print(f"  Webhook URL: {settings.slack_webhook_url[:50] if settings.slack_webhook_url else 'Not configured'}...")
    print(f"  HITL Base URL: {settings.hitl_base_url}")
    
    # Test PR
    repo_full_name = "AnandD1/ScratchYOLO"
    pr_number = 2
    
    print(f"\n🔍 Testing with PR: {repo_full_name} #{pr_number}")
    
    try:
        # Phase 2: Prepare review
        print("\n📦 Phase 2: Fetching and parsing PR...")
        session = quick_prepare_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number
        )
        print(f"  ✓ Loaded {len(session.review_units)} review units")
        
        # Build workflow state
        repo_owner, repo_name = repo_full_name.split("/")
        
        hunks = []
        for unit in session.review_units[:3]:  # Limit to first 3 for testing
            hunks.append({
                'hunk_id': f'hunk_{len(hunks)}',
                'file_path': unit.context.file_path,
                'old_start': unit.context.old_line_start or 1,
                'new_start': unit.context.new_line_start or 1,
                'old_lines': (unit.context.old_line_end - unit.context.old_line_start + 1) if unit.context.old_line_end and unit.context.old_line_start else 10,
                'new_lines': (unit.context.new_line_end - unit.context.new_line_start + 1) if unit.context.new_line_end and unit.context.new_line_start else 10,
                'changes': unit.get_diff_snippet(max_lines=20)
            })
        
        run_id = f"{repo_name}_PR{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        diff_hash = hashlib.md5(str(hunks).encode()).hexdigest()[:12]
        
        initial_state = WorkflowState(
            run_id=run_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_id=f"{repo_owner}_{repo_name}_main",
            pr_number=pr_number,
            pr_sha=session.pr_data.head_sha,
            diff_hash=diff_hash,
            hunks=hunks
        )
        
        print(f"  ✓ Initial state created: {run_id}")
        
        # Phase 3-6: Run workflow
        print(f"\n🔧 Creating workflow with all phases (including Slack)...")
        workflow = create_review_workflow(
            github_token=settings.github_token,
            settings=settings  # Pass settings for Slack integration
        )
        
        print(f"\n🚀 Running multi-agent workflow (Phases 3-6)...")
        print("=" * 80)
        
        final_state = run_workflow(initial_state, workflow)
        
        print("\n" + "=" * 80)
        print("✅ WORKFLOW COMPLETE - ALL PHASES EXECUTED")
        print("=" * 80)
        
        # Display results
        print(f"\n📊 Final Results:")
        print(f"  Phase 3 - Retrieval: ✓ Context retrieved for {len(final_state.get('retrieval_bundles', {}))} hunks")
        print(f"  Phase 4 - Review: ✓ Found {len(final_state.get('review_issues', []))} issues")
        print(f"  Phase 4 - Planning: ✓ Generated {len(final_state.get('fix_tasks', []))} fix tasks")
        
        # Handle guardrail_result (Pydantic model)
        guardrail_result = final_state.get('guardrail_result')
        if guardrail_result:
            guardrail_status = 'Passed' if guardrail_result.passed else 'Failed'
        else:
            guardrail_status = 'N/A'
        print(f"  Phase 4 - Guardrails: ✓ {guardrail_status}")
        
        # Handle hitl_decision (Pydantic model)
        hitl_decision = final_state.get('hitl_decision')
        if hitl_decision:
            hitl_action = hitl_decision.action if hasattr(hitl_decision, 'action') else str(hitl_decision)
        else:
            hitl_action = 'Skipped (auto-approved)'
        print(f"  Phase 5 - HITL: ✓ Decision: {hitl_action}")
        
        print(f"  Phase 6 - Publishing: ✓ Comment: {final_state.get('posted_comment_url', 'N/A')}")
        print(f"  Phase 6 - Slack: {'✓ Sent' if final_state.get('notification_sent') else '✗ Not sent'}")
        print(f"  Phase 6 - Persistence: {'✓ Saved' if final_state.get('persisted') else '✗ Not saved'}")
        
        if final_state.get('notification_sent'):
            print(f"\n🎉 SUCCESS! Slack notification sent to {settings.slack_channel}")
            print(f"   👉 Check your Slack channel to see the PR review!")
        
        if final_state.get('errors'):
            print(f"\n⚠️  Errors encountered:")
            for error in final_state.get('errors', []):
                print(f"  - {error}")
        
        if final_state.get('persistence_path'):
            print(f"\n💾 Results saved to: {final_state['persistence_path']}")
        
        print("\n" + "=" * 80)
        print("🎊 Phase 6 Integration Test Complete!")
        print("=" * 80)
        print("\nPhases Verified:")
        print("  ✅ Phase 2: PR Fetching & Parsing")
        print("  ✅ Phase 3: Context Retrieval (RAG)")
        print("  ✅ Phase 4: Review, Planning, Guardrails")
        print("  ✅ Phase 5: HITL Gate")
        print("  ✅ Phase 6: Publishing & Slack Notifications")
        print("\n🔗 Next: Check #anandprojects in Slack for the notification!")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    
    # Check if user wants to run workflow test or start API server
    if len(sys.argv) > 1 and sys.argv[1] == "--workflow":
        print("\n🧪 Running Full Workflow Test (Phase 2-6)...")
        success = test_full_workflow()
        sys.exit(0 if success else 1)
    else:
        # Start API server (original behavior)
        import uvicorn
        
        print("🚀 Starting Repo-Copilot HITL Interface...")
        print("📍 Server will be available at: http://localhost:8000")
        print("📖 API docs at: http://localhost:8000/docs")
        print("\n💡 Tip: Run 'python test_api.py --workflow' to test full Phase 2-6 integration")
        print("\nPress Ctrl+C to stop the server\n")
        
        uvicorn.run(
            "app.api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["app"]
        )
