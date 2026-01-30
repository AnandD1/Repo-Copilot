# Phase 6: Slack Notifications - Quick Reference

## Quick Test (No Dependencies Required)

```bash
cd D:\LLM\PROJECT\Repo_Copilot
python test_slack_simple.py
```

This will send 3 test notifications to `#anandprojects`:
1. Simple text message
2. Rich PR review with issues
3. Clean PR with no issues

## Configuration

**Webhook URL**: `https://hooks.slack.com/services/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`
**Channel**: `#anandprojects`
**Status**: ✅ Already configured in `.env`

## What Gets Sent

Every PR review notification includes:

### 1. Header & Summary
- PR title and number
- Number of changes reviewed
- Total issues found
- Fix tasks generated

### 2. Severity Breakdown
- 🔴 Blockers
- 🟠 Major
- 🟡 Minor
- 🔵 Nit

### 3. Top 5 Issues
- Issue type and location
- Detailed explanation
- Suggested fix

### 4. Links
- GitHub PR link
- Review comment link
- HITL approval page link

### 5. Evidence
- References to standards (OWASP, CWE, PEP 8, etc.)
- Best practice guides

### 6. Recommendations
- Critical actions needed
- Security considerations
- Test coverage suggestions

## Usage in Code

### Option 1: Automatic (Integrated in Workflow)
```python
from app.workflow import create_review_workflow, run_workflow
from config.settings import Settings

settings = Settings()  # Auto-loads from .env
workflow = create_review_workflow(settings=settings)
final_state = run_workflow(workflow, initial_state)
# ✅ Notification sent automatically!
```

### Option 2: Manual
```python
from app.notifications import SlackNotifier
from config.settings import Settings

settings = Settings()
notifier = SlackNotifier(
    webhook_url=settings.slack_webhook_url,
    channel=settings.slack_channel
)

# Simple message
notifier.send_simple_notification("Hello Slack!")

# Full PR review
notifier.send_pr_review_notification(
    state=workflow_state,
    pr_url="https://github.com/owner/repo/pull/123",
    comment_url="...",
    hitl_url="..."
)
```

## Files Modified

| File | Changes |
|------|---------|
| `app/notifications/slack_notifier.py` | ✨ NEW - Slack notification service |
| `app/workflow/publisher_notifier.py` | ✅ Integrated Slack notifications |
| `config/settings.py` | ✅ Added Slack settings |
| `.env` | ✅ Added your webhook URL and channel |
| `test_slack_simple.py` | ✨ NEW - Standalone test |
| `test_slack_notifications.py` | ✨ NEW - Full integration test |

## Environment Variables

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/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
SLACK_CHANNEL=#anandprojects
SLACK_ENABLED=true
```

## Features

✅ Rich Slack Blocks formatting
✅ Severity-based color coding
✅ Top 5 issues display
✅ Evidence references
✅ Links to PR, comments, HITL
✅ Context-aware recommendations
✅ Handles clean PRs (no issues)
✅ Error handling and fallbacks
✅ Simple text notifications
✅ Channel override support

## Color Coding

- 🔴 **Red**: Blocker issues present
- 🟠 **Orange**: Major issues present  
- 🟡 **Yellow**: Minor issues only
- 🟢 **Green**: No issues (clean PR)

## Next Steps to Test

1. **Run the simple test**:
   ```bash
   python test_slack_simple.py
   ```

2. **Check `#anandprojects` in Slack** - you should see 3 notifications

3. **Run a real PR review** through the workflow to see it in action

## Support

- Full documentation: `PHASE6_IMPLEMENTATION.md`
- Test files: `test_slack_simple.py`, `test_slack_notifications.py`
- Source code: `app/notifications/slack_notifier.py`
