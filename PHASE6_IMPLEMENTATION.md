# Phase 6: Slack Notifications MVP - Implementation Guide

## Overview

Phase 6 adds comprehensive Slack webhook integration to send PR review summaries with detailed issue breakdowns, evidence links, and HITL approval pages.

## Features Implemented

### 1. Slack Notifier Service
**Location**: `app/notifications/slack_notifier.py`

The `SlackNotifier` class provides:
- ✅ Rich formatted notifications with Slack Blocks API
- ✅ Severity breakdown (Blocker, Major, Minor, Nit)
- ✅ Top 5 issues display
- ✅ Evidence references
- ✅ Links to PR, GitHub comments, and HITL approval page
- ✅ Recommendations based on issue types
- ✅ Color-coded attachments (red for blockers, green for clean PRs)
- ✅ Simple text notifications

### 2. Integration with Workflow
**Location**: `app/workflow/publisher_notifier.py`

Updated `PublisherNotifier` to:
- ✅ Initialize `SlackNotifier` from settings
- ✅ Send comprehensive notifications after publishing review
- ✅ Include PR summary, severity breakdown, top issues
- ✅ Provide links to GitHub PR, comments, and HITL page
- ✅ Handle errors gracefully

### 3. Configuration Settings
**Location**: `config/settings.py`

Added new settings:
```python
slack_webhook_url: Optional[str] = None
slack_channel: Optional[str] = None
slack_enabled: bool = True
hitl_base_url: str = "http://localhost:8000"
notification_enabled: bool = True
```

### 4. Environment Configuration
**Location**: `.env`

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/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
SLACK_CHANNEL=#anandprojects
SLACK_ENABLED=true
HITL_BASE_URL=http://localhost:8000
NOTIFICATION_ENABLED=true
```

## Usage

### Quick Start

1. **Configure Slack Webhook** (Already done!)
   - Webhook URL: `https://hooks.slack.com/services/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`
   - Channel: `#anandprojects`

2. **Test the Implementation**

   **Option A: Simple Standalone Test** (No dependencies)
   ```bash
   python test_slack_simple.py
   ```

   **Option B: Full Integration Test** (Requires all dependencies)
   ```bash
   python test_slack_notifications.py
   ```

3. **Use in Workflow**
   
   The Slack notifications are automatically sent when the workflow completes:
   ```python
   from app.workflow import create_review_workflow, run_workflow
   from config.settings import Settings
   
   # Settings will auto-load from .env
   settings = Settings()
   
   # Create workflow with settings
   workflow = create_review_workflow(settings=settings)
   
   # Run workflow - notifications sent automatically at the end
   final_state = run_workflow(workflow, initial_state)
   ```

### Manual Notification

Send a notification directly:
```python
from app.notifications import SlackNotifier
from config.settings import Settings

settings = Settings()
notifier = SlackNotifier(
    webhook_url=settings.slack_webhook_url,
    channel=settings.slack_channel
)

# Simple message
notifier.send_simple_notification("🎉 Deployment successful!")

# Full PR review notification
notifier.send_pr_review_notification(
    state=workflow_state,
    pr_url="https://github.com/owner/repo/pull/123",
    comment_url="https://github.com/owner/repo/pull/123#comment",
    hitl_url="http://localhost:8000/review/run_id"
)
```

## Notification Content

### Header
- 🤖 PR Review: {repo_name} #{pr_number}

### PR Summary
- Reviewed X code changes
- Found Y issue(s)
- Generated Z fix task(s)

### Severity Breakdown
- 🔴 Blockers: X
- 🟠 Major: Y
- 🟡 Minor: Z
- 🔵 Nit: W

### Top 5 Issues
Each issue includes:
- Severity emoji
- Category (SECURITY, CORRECTNESS, PERFORMANCE, etc.)
- File path and line number
- Explanation
- Suggestion

### Links Section
- View PR on GitHub
- View Review Comment
- HITL Approval Page

### Evidence References
- Unique evidence links from all issues
- Limited to top 10 references

### Recommendations
Context-aware recommendations based on:
- Blocker issues presence
- Major issues presence
- Security issues
- Test coverage
- Fix plan availability

## Color Coding

Attachment colors indicate PR status:
- **Red (danger)**: Has blocker issues
- **Orange (warning)**: Has major issues
- **Green**: Has only minor issues
- **Light Green (good)**: No issues found

## Files Created/Modified

### New Files
1. `app/notifications/__init__.py` - Package initialization
2. `app/notifications/slack_notifier.py` - SlackNotifier implementation
3. `test_slack_notifications.py` - Comprehensive test suite
4. `test_slack_simple.py` - Standalone test (no dependencies)
5. `PHASE6_IMPLEMENTATION.md` - This documentation

### Modified Files
1. `config/settings.py` - Added Slack and notification settings
2. `app/workflow/publisher_notifier.py` - Integrated Slack notifications
3. `.env` - Added Slack configuration
4. `.env.example` - Added Slack configuration template

## Testing

### Test Suite 1: Standalone (`test_slack_simple.py`)
- ✅ Test 1: Simple text message
- ✅ Test 2: Rich PR review with issues
- ✅ Test 3: Clean PR with no issues

### Test Suite 2: Full Integration (`test_slack_notifications.py`)
- ✅ Test 1: Simple notification
- ✅ Test 2: Full PR review notification
- ✅ Test 3: No issues notification
- ✅ Test 4: Settings-based notification

### Running Tests

```bash
# Simple test (recommended first)
python test_slack_simple.py

# Full test (requires dependencies)
pip install -r requirements.txt
python test_slack_notifications.py
```

## Sample Notification

When you run the tests, you'll see notifications in `#anandprojects` Slack channel with:

1. **Header**: "🤖 PR Review: ScratchYOLO #42"

2. **Summary**:
   - Reviewed 5 code changes
   - Found 5 issue(s)
   - Generated 3 fix task(s)

3. **Issue Breakdown**:
   - 🔴 Blockers: 1
   - 🟠 Major: 2
   - 🟡 Minor: 1
   - 🔵 Nit: 1

4. **Top Issues**:
   - SQL Injection in `src/auth/login.py:45`
   - Missing error handling in `src/api/handlers.py:112`
   - Performance issue in `src/utils/data_processor.py:78`

5. **Links**:
   - View PR on GitHub
   - View Review Comment
   - HITL Approval Page

6. **Evidence**:
   - OWASP Top 10 references
   - CWE identifiers
   - Best practice guides

7. **Recommendations**:
   - Critical: Blocker issues must be fixed
   - Security issues detected
   - Follow suggested fix tasks

## Architecture

```
┌─────────────────────────────────────────────┐
│         Workflow (LangGraph)                │
│                                             │
│  ┌────────────┐      ┌──────────────────┐  │
│  │  Reviewer  │─────▶│   Planner        │  │
│  └────────────┘      └──────────────────┘  │
│                              │              │
│                              ▼              │
│                      ┌──────────────────┐  │
│                      │   Guardrail      │  │
│                      └──────────────────┘  │
│                              │              │
│                              ▼              │
│                      ┌──────────────────┐  │
│                      │   HITL Gate      │  │
│                      └──────────────────┘  │
│                              │              │
│                              ▼              │
│  ┌──────────────────────────────────────┐  │
│  │   Publisher + Notifier (Phase 6)     │  │
│  │   - Format GitHub comment            │  │
│  │   - Send Slack notification ◄────────┼──┼──▶ Slack
│  │   - Build rich payload               │  │      #anandprojects
│  └──────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

## Next Steps

### Phase 7: Enhanced Notifications
- Email notifications
- Microsoft Teams integration
- Custom notification templates
- Digest mode (batch notifications)

### Phase 8: Analytics Dashboard
- Track notification delivery
- Issue trends over time
- PR review metrics
- Team performance insights

## Troubleshooting

### Webhook URL Not Working
- Verify the URL is correct
- Check that the Slack app is installed in the workspace
- Ensure the webhook has permission to post to `#anandprojects`

### Notifications Not Sending
- Check `SLACK_ENABLED=true` in `.env`
- Verify `Settings` is loaded correctly
- Check for error messages in console output

### Missing Dependencies
```bash
pip install requests pydantic pydantic-settings
```

## Security Notes

⚠️ **Important**: Never commit `.env` file to version control
- Webhook URLs are sensitive
- Use `.env.example` as template
- Add `.env` to `.gitignore`

## API Reference

### SlackNotifier

```python
class SlackNotifier:
    def __init__(self, webhook_url: str, channel: Optional[str] = None)
    
    def send_pr_review_notification(
        self,
        state: WorkflowState,
        pr_url: str,
        comment_url: Optional[str] = None,
        hitl_url: Optional[str] = None
    ) -> bool
    
    def send_simple_notification(self, message: str) -> bool
```

### Settings

```python
class Settings(BaseSettings):
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_enabled: bool = True
    hitl_base_url: str = "http://localhost:8000"
    notification_enabled: bool = True
```

## Conclusion

Phase 6 successfully implements comprehensive Slack notifications for PR reviews, providing:
- ✅ Real-time notifications to `#anandprojects`
- ✅ Rich formatting with severity breakdown
- ✅ Top 5 issues with evidence links
- ✅ Links to PR, comments, and HITL approval
- ✅ Context-aware recommendations
- ✅ Clean integration with existing workflow

The implementation is production-ready and fully tested!
