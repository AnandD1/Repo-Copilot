"""Test Slack notification integration (Phase 6)."""

import os
from datetime import datetime

from app.notifications import SlackNotifier
from app.workflow.state import (
    WorkflowState,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    FixTask,
    EffortEstimate
)
from config.settings import Settings


def create_sample_state() -> WorkflowState:
    """Create a sample workflow state with review issues."""
    
    # Create sample review issues
    issues = [
        ReviewIssue(
            severity=IssueSeverity.BLOCKER,
            category=IssueCategory.SECURITY,
            file_path="src/auth/login.py",
            line_number=45,
            explanation="Potential SQL injection vulnerability detected. User input is directly concatenated into SQL query without parameterization.",
            suggestion="Use parameterized queries with placeholders (e.g., cursor.execute('SELECT * FROM users WHERE email = ?', (email,)))",
            evidence_references=["OWASP Top 10 - A03:2021 Injection", "CWE-89: SQL Injection"]
        ),
        ReviewIssue(
            severity=IssueSeverity.MAJOR,
            category=IssueCategory.CORRECTNESS,
            file_path="src/api/handlers.py",
            line_number=112,
            explanation="Missing error handling for database connection failure. This could cause unhandled exceptions in production.",
            suggestion="Wrap database calls in try-except block and return appropriate error responses",
            evidence_references=["Python Best Practices - Exception Handling"]
        ),
        ReviewIssue(
            severity=IssueSeverity.MAJOR,
            category=IssueCategory.PERFORMANCE,
            file_path="src/utils/data_processor.py",
            line_number=78,
            explanation="Inefficient list comprehension inside loop. O(n²) complexity could cause performance issues with large datasets.",
            suggestion="Move list comprehension outside the loop or use set operations for O(n) complexity",
            evidence_references=["Python Performance Tips", "Big O Complexity Guide"]
        ),
        ReviewIssue(
            severity=IssueSeverity.MINOR,
            category=IssueCategory.TEST,
            file_path="tests/test_api.py",
            line_number=23,
            explanation="Test coverage missing for edge case: empty request body",
            suggestion="Add test case for handling empty/malformed request bodies",
            evidence_references=[]
        ),
        ReviewIssue(
            severity=IssueSeverity.NIT,
            category=IssueCategory.STYLE,
            file_path="src/models/user.py",
            line_number=15,
            explanation="Variable name 'usr_data' doesn't follow naming conventions",
            suggestion="Rename to 'user_data' for better readability",
            evidence_references=["PEP 8 - Python Style Guide"]
        ),
    ]
    
    # Create fix tasks
    fix_tasks = [
        FixTask(
            task_id="FIX-001",
            title="Fix SQL Injection Vulnerability",
            why_it_matters="Critical security issue that could allow attackers to access or modify database",
            affected_files=["src/auth/login.py"],
            suggested_approach="Replace string concatenation with parameterized queries using cursor.execute() with placeholders",
            effort_estimate=EffortEstimate.SMALL,
            related_issues=[0]
        ),
        FixTask(
            task_id="FIX-002",
            title="Add Error Handling for Database Operations",
            why_it_matters="Prevents unhandled exceptions and improves application reliability",
            affected_files=["src/api/handlers.py", "src/utils/db.py"],
            suggested_approach="Add try-except blocks around all database calls with proper error logging and user-friendly error responses",
            effort_estimate=EffortEstimate.MEDIUM,
            related_issues=[1]
        ),
        FixTask(
            task_id="FIX-003",
            title="Optimize Data Processing Performance",
            why_it_matters="Improves performance for large datasets and reduces server load",
            affected_files=["src/utils/data_processor.py"],
            suggested_approach="Refactor nested loops to use set operations or dictionary lookups",
            effort_estimate=EffortEstimate.SMALL,
            related_issues=[2]
        ),
    ]
    
    # Create workflow state
    state = WorkflowState(
        run_id="test_run_20260130_120000",
        repo_owner="AnandD1",
        repo_name="ScratchYOLO",
        repo_id="AnandD1_ScratchYOLO_main",
        pr_number=42,
        pr_sha="abc123def456",
        diff_hash="hash_xyz789",
        hunks=[
            {
                "hunk_id": "hunk_1",
                "file_path": "src/auth/login.py",
                "old_start": 40,
                "new_start": 40,
                "old_lines": 10,
                "new_lines": 12,
                "changes": "+    query = 'SELECT * FROM users WHERE email = ' + email"
            },
            {
                "hunk_id": "hunk_2",
                "file_path": "src/api/handlers.py",
                "old_start": 110,
                "new_start": 110,
                "old_lines": 5,
                "new_lines": 8,
                "changes": "+    result = db.query(sql)"
            },
        ],
        review_issues=issues,
        fix_tasks=fix_tasks,
        notification_sent=False,
        persisted=False
    )
    
    return state


def test_slack_notification_simple():
    """Test simple Slack notification."""
    print("\n" + "=" * 80)
    print("TEST 1: Simple Slack Notification")
    print("=" * 80)
    
    # Get Slack webhook URL from environment or use default
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/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")
    channel = "#anandprojects"
    
    # Create notifier
    notifier = SlackNotifier(webhook_url=webhook_url, channel=channel)
    
    # Send simple message
    message = f"🧪 Test notification from Repo-Copilot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    success = notifier.send_simple_notification(message)
    
    if success:
        print("✓ Simple notification sent successfully!")
    else:
        print("✗ Failed to send simple notification")
    
    return success


def test_slack_notification_full():
    """Test full PR review notification with all features."""
    print("\n" + "=" * 80)
    print("TEST 2: Full PR Review Notification")
    print("=" * 80)
    
    # Get Slack webhook URL from environment or use default
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/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")
    channel = "#anandprojects"
    
    # Create notifier
    notifier = SlackNotifier(webhook_url=webhook_url, channel=channel)
    
    # Create sample state
    state = create_sample_state()
    
    # Define URLs
    pr_url = f"https://github.com/{state.repo_owner}/{state.repo_name}/pull/{state.pr_number}"
    comment_url = f"{pr_url}#issuecomment-123456789"
    hitl_url = f"http://localhost:8000/review/{state.run_id}"
    
    # Send notification
    print(f"\nSending notification for PR #{state.pr_number}...")
    print(f"  Issues: {len(state.review_issues)}")
    print(f"  Fix Tasks: {len(state.fix_tasks)}")
    
    success = notifier.send_pr_review_notification(
        state=state,
        pr_url=pr_url,
        comment_url=comment_url,
        hitl_url=hitl_url
    )
    
    if success:
        print("\n✓ Full PR review notification sent successfully!")
        print(f"  → Check {channel} channel in Slack")
    else:
        print("\n✗ Failed to send PR review notification")
    
    return success


def test_slack_notification_no_issues():
    """Test notification when no issues are found."""
    print("\n" + "=" * 80)
    print("TEST 3: Notification with No Issues (Clean PR)")
    print("=" * 80)
    
    # Get Slack webhook URL from environment or use default
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/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")
    channel = "#anandprojects"
    
    # Create notifier
    notifier = SlackNotifier(webhook_url=webhook_url, channel=channel)
    
    # Create state with no issues
    state = WorkflowState(
        run_id="test_run_clean_20260130_120000",
        repo_owner="AnandD1",
        repo_name="ScratchYOLO",
        repo_id="AnandD1_ScratchYOLO_main",
        pr_number=43,
        pr_sha="clean123",
        diff_hash="hash_clean",
        hunks=[{"hunk_id": "h1", "file_path": "README.md"}],
        review_issues=[],  # No issues!
        fix_tasks=[],
        notification_sent=False,
        persisted=False
    )
    
    # Define URLs
    pr_url = f"https://github.com/{state.repo_owner}/{state.repo_name}/pull/{state.pr_number}"
    comment_url = f"{pr_url}#issuecomment-clean"
    
    # Send notification
    print(f"\nSending clean PR notification for PR #{state.pr_number}...")
    
    success = notifier.send_pr_review_notification(
        state=state,
        pr_url=pr_url,
        comment_url=comment_url,
        hitl_url=None
    )
    
    if success:
        print("\n✓ Clean PR notification sent successfully!")
        print(f"  → Check {channel} channel in Slack")
    else:
        print("\n✗ Failed to send clean PR notification")
    
    return success


def test_with_settings():
    """Test using Settings configuration."""
    print("\n" + "=" * 80)
    print("TEST 4: Notification Using Settings Configuration")
    print("=" * 80)
    
    # Create settings with Slack config
    settings = Settings(
        slack_webhook_url="https://hooks.slack.com/services/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",
        slack_channel="#anandprojects",
        slack_enabled=True
    )
    
    print(f"\nSettings loaded:")
    print(f"  Slack Enabled: {settings.slack_enabled}")
    print(f"  Slack Channel: {settings.slack_channel}")
    print(f"  Webhook URL: {settings.slack_webhook_url[:50]}...")
    
    # Create notifier from settings
    if settings.slack_enabled and settings.slack_webhook_url:
        notifier = SlackNotifier(
            webhook_url=settings.slack_webhook_url,
            channel=settings.slack_channel
        )
        
        # Create sample state
        state = create_sample_state()
        
        # Send notification
        pr_url = f"https://github.com/{state.repo_owner}/{state.repo_name}/pull/{state.pr_number}"
        
        success = notifier.send_pr_review_notification(
            state=state,
            pr_url=pr_url,
            comment_url=f"{pr_url}#comment",
            hitl_url=f"{settings.hitl_base_url}/review/{state.run_id}"
        )
        
        if success:
            print("\n✓ Notification sent using Settings configuration!")
        else:
            print("\n✗ Failed to send notification")
        
        return success
    else:
        print("\n✗ Slack not enabled in settings")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PHASE 6: Slack Notification Tests")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {}
    
    # Test 1: Simple notification
    try:
        results["simple"] = test_slack_notification_simple()
    except Exception as e:
        print(f"\n✗ Test 1 failed with error: {e}")
        results["simple"] = False
    
    # Test 2: Full PR review notification
    try:
        results["full"] = test_slack_notification_full()
    except Exception as e:
        print(f"\n✗ Test 2 failed with error: {e}")
        results["full"] = False
    
    # Test 3: No issues notification
    try:
        results["no_issues"] = test_slack_notification_no_issues()
    except Exception as e:
        print(f"\n✗ Test 3 failed with error: {e}")
        results["no_issues"] = False
    
    # Test 4: Settings-based notification
    try:
        results["settings"] = test_with_settings()
    except Exception as e:
        print(f"\n✗ Test 4 failed with error: {e}")
        results["settings"] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 All tests passed! Slack notifications are working correctly.")
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed. Please check the errors above.")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
