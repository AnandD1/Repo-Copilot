"""Slack notification service for PR reviews."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests

from app.workflow.state import WorkflowState, ReviewIssue, IssueSeverity


class SlackNotifier:
    """Send formatted PR review notifications to Slack."""
    
    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        """
        Initialize Slack notifier.
        
        Args:
            webhook_url: Slack webhook URL
            channel: Optional channel override (e.g., "#anandprojects")
        """
        self.webhook_url = webhook_url
        self.channel = channel
    
    def send_pr_review_notification(
        self,
        state: WorkflowState,
        pr_url: str,
        comment_url: Optional[str] = None,
        hitl_url: Optional[str] = None
    ) -> bool:
        """
        Send comprehensive PR review notification to Slack.
        
        Args:
            state: Workflow state with review results
            pr_url: URL to the PR
            comment_url: URL to the posted GitHub comment
            hitl_url: URL to HITL approval page
            
        Returns:
            True if notification sent successfully
        """
        try:
            # Build Slack message payload
            payload = self._build_slack_payload(state, pr_url, comment_url, hitl_url)
            
            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✓ Slack notification sent successfully")
                return True
            else:
                print(f"✗ Slack notification failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error sending Slack notification: {e}")
            return False
    
    def _build_slack_payload(
        self,
        state: WorkflowState,
        pr_url: str,
        comment_url: Optional[str],
        hitl_url: Optional[str]
    ) -> Dict[str, Any]:
        """Build Slack message payload with rich formatting."""
        
        # Get severity breakdown
        severity_counts = self._get_severity_breakdown(state.review_issues)
        total_issues = len(state.review_issues)
        
        # Get top 5 issues
        top_issues = self._get_top_issues(state.review_issues, limit=5)
        
        # Build PR summary
        pr_summary = self._build_pr_summary(state)
        
        # Determine color based on issues
        color = self._get_status_color(severity_counts)
        
        # Build blocks (Slack's rich formatting)
        blocks = []
        
        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🤖 PR Review: {state.repo_name} #{state.pr_number}",
                "emoji": True
            }
        })
        
        # PR Summary Section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*PR Summary*\n{pr_summary}"
            }
        })
        
        # Divider
        blocks.append({"type": "divider"})
        
        # Severity Breakdown
        severity_text = self._format_severity_breakdown(severity_counts, total_issues)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📊 Issue Breakdown*\n{severity_text}"
            }
        })
        
        # Top 5 Issues
        if top_issues:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔍 Top {len(top_issues)} Issues*"
                }
            })
            
            for i, issue in enumerate(top_issues, 1):
                issue_text = self._format_issue(issue, i)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": issue_text
                    }
                })
        
        # Links Section
        blocks.append({"type": "divider"})
        links_text = self._format_links(pr_url, comment_url, hitl_url)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🔗 Links*\n{links_text}"
            }
        })
        
        # Evidence section (if any issues have evidence)
        evidence_links = self._get_evidence_links(state.review_issues)
        if evidence_links:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📎 Evidence References*\n{evidence_links}"
                }
            })
        
        # Recommendations
        recommendations = self._build_recommendations(state)
        if recommendations:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*💡 Recommendations*\n{recommendations}"
                }
            })
        
        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated by Repo-Copilot • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })
        
        # Build final payload
        payload = {
            "blocks": blocks,
            "attachments": [
                {
                    "color": color,
                    "fallback": f"PR Review: {total_issues} issues found"
                }
            ]
        }
        
        # Add channel if specified
        if self.channel:
            payload["channel"] = self.channel
        
        return payload
    
    def _get_severity_breakdown(self, issues: List[ReviewIssue]) -> Dict[str, int]:
        """Count issues by severity."""
        counts = {
            "blocker": 0,
            "major": 0,
            "minor": 0,
            "nit": 0
        }
        
        for issue in issues:
            severity = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
            if severity in counts:
                counts[severity] += 1
        
        return counts
    
    def _get_top_issues(self, issues: List[ReviewIssue], limit: int = 5) -> List[ReviewIssue]:
        """Get top N issues sorted by severity."""
        severity_order = {
            "blocker": 0,
            "major": 1,
            "minor": 2,
            "nit": 3
        }
        
        sorted_issues = sorted(
            issues,
            key=lambda x: severity_order.get(
                x.severity.value if hasattr(x.severity, 'value') else str(x.severity),
                999
            )
        )
        
        return sorted_issues[:limit]
    
    def _get_status_color(self, severity_counts: Dict[str, int]) -> str:
        """Determine color based on issue severity."""
        if severity_counts["blocker"] > 0:
            return "danger"  # Red
        elif severity_counts["major"] > 0:
            return "warning"  # Orange
        elif severity_counts["minor"] > 0:
            return "#36a64f"  # Green
        else:
            return "good"  # Light green
    
    def _build_pr_summary(self, state: WorkflowState) -> str:
        """Build a summary of what the PR does."""
        lines = []
        
        # Basic stats
        total_hunks = len(state.hunks)
        total_issues = len(state.review_issues)
        
        lines.append(f"Review completed for PR #{state.pr_number}")
        lines.append(f"• Reviewed {total_hunks} code changes")
        lines.append(f"• Found {total_issues} issue(s)")
        
        if state.fix_tasks:
            lines.append(f"• Generated {len(state.fix_tasks)} fix task(s)")
        
        return "\n".join(lines)
    
    def _format_severity_breakdown(self, counts: Dict[str, int], total: int) -> str:
        """Format severity breakdown text."""
        lines = []
        
        if total == 0:
            return "✅ *No issues found!* Great work!"
        
        lines.append(f"Total Issues: *{total}*\n")
        
        if counts["blocker"] > 0:
            lines.append(f":red_circle: *Blockers*: {counts['blocker']}")
        if counts["major"] > 0:
            lines.append(f":large_orange_circle: *Major*: {counts['major']}")
        if counts["minor"] > 0:
            lines.append(f":large_yellow_circle: *Minor*: {counts['minor']}")
        if counts["nit"] > 0:
            lines.append(f":large_blue_circle: *Nit*: {counts['nit']}")
        
        return "\n".join(lines)
    
    def _format_issue(self, issue: ReviewIssue, number: int) -> str:
        """Format a single issue for Slack."""
        severity = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
        category = issue.category.value if hasattr(issue.category, 'value') else str(issue.category)
        
        # Severity emoji
        emoji = {
            "blocker": ":red_circle:",
            "major": ":large_orange_circle:",
            "minor": ":large_yellow_circle:",
            "nit": ":large_blue_circle:"
        }.get(severity, ":white_circle:")
        
        lines = [
            f"{emoji} *{number}. [{category.upper()}]* `{issue.file_path}:{issue.line_number}`",
            f"{issue.explanation[:200]}..." if len(issue.explanation) > 200 else issue.explanation,
            f"_Suggestion: {issue.suggestion[:150]}..._" if len(issue.suggestion) > 150 else f"_Suggestion: {issue.suggestion}_"
        ]
        
        return "\n".join(lines)
    
    def _format_links(
        self,
        pr_url: str,
        comment_url: Optional[str],
        hitl_url: Optional[str]
    ) -> str:
        """Format links section."""
        lines = []
        
        lines.append(f"• <{pr_url}|View PR on GitHub>")
        
        if comment_url:
            lines.append(f"• <{comment_url}|View Review Comment>")
        
        if hitl_url:
            lines.append(f"• <{hitl_url}|HITL Approval Page>")
        
        return "\n".join(lines)
    
    def _get_evidence_links(self, issues: List[ReviewIssue]) -> str:
        """Gather unique evidence references."""
        all_evidence = set()
        
        for issue in issues:
            if issue.evidence_references:
                all_evidence.update(issue.evidence_references)
        
        if not all_evidence:
            return ""
        
        # Format as bullet list
        evidence_list = sorted(all_evidence)[:10]  # Limit to 10
        return "\n".join([f"• `{ev}`" for ev in evidence_list])
    
    def _build_recommendations(self, state: WorkflowState) -> str:
        """Build recommendations for the PR."""
        lines = []
        
        # Count issues by severity
        severity_counts = self._get_severity_breakdown(state.review_issues)
        
        # Recommendations based on severity
        if severity_counts["blocker"] > 0:
            lines.append("⚠️ *Critical*: This PR has blocker issues that must be fixed before merging")
        
        if severity_counts["major"] > 0:
            lines.append("🔧 *Important*: Major issues should be addressed to maintain code quality")
        
        # Test coverage recommendation
        if any(issue.category.value == "test" if hasattr(issue.category, 'value') else str(issue.category) == "test" for issue in state.review_issues):
            lines.append("🧪 Consider adding more test coverage for the changes")
        
        # Security recommendation
        if any(issue.category.value == "security" if hasattr(issue.category, 'value') else str(issue.category) == "security" for issue in state.review_issues):
            lines.append("🔒 Security issues detected - please review carefully")
        
        # Fix plan recommendation
        if state.fix_tasks:
            lines.append(f"📋 Follow the {len(state.fix_tasks)} suggested fix task(s) in the review comment")
        
        # If no issues
        if len(state.review_issues) == 0:
            lines.append("✨ Excellent work! The code looks clean and ready to merge")
        
        return "\n".join(lines)
    
    def send_simple_notification(self, message: str) -> bool:
        """
        Send a simple text notification.
        
        Args:
            message: Simple text message to send
            
        Returns:
            True if sent successfully
        """
        try:
            payload = {"text": message}
            
            if self.channel:
                payload["channel"] = self.channel
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"✗ Error sending simple notification: {e}")
            return False
