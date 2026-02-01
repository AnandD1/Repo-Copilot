"""Node 5: HITL Gate - Human-in-the-loop approval."""

from typing import Dict, Any
from datetime import datetime

from .state import WorkflowState, HITLDecision, HITLAction


class HITLGate:
    """Human-in-the-loop gate for review approval."""
    
    def __init__(self, auto_approve: bool = False):
        """Initialize HITL gate.
        
        Args:
            auto_approve: If True, automatically approve all reviews (for testing/web)
        """
        self.auto_approve = auto_approve
    
    def format_review_summary(self, state: WorkflowState) -> str:
        """
        Format a human-readable review summary.
        
        Args:
            state: Current workflow state
            
        Returns:
            Formatted summary string
        """
        lines = []
        
        lines.append("=" * 80)
        lines.append(f"PR REVIEW SUMMARY - {state.repo_name} #{state.pr_number}")
        lines.append("=" * 80)
        lines.append("")
        
        # Guardrail status
        if state.guardrail_result:
            if state.guardrail_result.passed:
                lines.append("✓ Guardrail Checks: PASSED")
            else:
                lines.append("✗ Guardrail Checks: FAILED")
                lines.append("\nBlocked Reasons:")
                for reason in state.guardrail_result.blocked_reasons:
                    lines.append(f"  - {reason}")
            
            if state.guardrail_result.warnings:
                lines.append("\nWarnings:")
                for warning in state.guardrail_result.warnings:
                    lines.append(f"  ⚠ {warning}")
            lines.append("")
        
        # Review issues
        lines.append(f"\nREVIEW ISSUES ({len(state.review_issues)} total)")
        lines.append("-" * 80)
        
        if not state.review_issues:
            lines.append("No issues found. Code looks good! ✓")
        else:
            # Group by severity
            by_severity = {}
            for issue in state.review_issues:
                # Handle both enum and string
                severity = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(issue)
            
            for severity in ["blocker", "major", "minor", "nit"]:
                issues = by_severity.get(severity, [])
                if issues:
                    lines.append(f"\n{severity.upper()} ({len(issues)}):")
                    for i, issue in enumerate(issues, 1):
                        # Handle both enum and string for category
                        category = issue.category.value if hasattr(issue.category, 'value') else str(issue.category)
                        lines.append(f"\n  {i}. [{category}] {issue.file_path}:{issue.line_number}")
                        lines.append(f"     {issue.explanation}")
                        lines.append(f"     💡 {issue.suggestion}")
                        if issue.evidence_references:
                            lines.append(f"     📎 Evidence: {', '.join(issue.evidence_references[:3])}")
        
        # Fix plan
        lines.append("\n")
        lines.append(f"\nFIX PLAN ({len(state.fix_tasks)} tasks)")
        lines.append("-" * 80)
        
        if not state.fix_tasks:
            lines.append("No fix tasks generated.")
        else:
            for i, task in enumerate(state.fix_tasks, 1):
                lines.append(f"\n{i}. {task.title} [{task.effort_estimate}]")
                lines.append(f"   Why: {task.why_it_matters}")
                lines.append(f"   Files: {', '.join(task.affected_files)}")
                lines.append(f"   Approach: {task.suggested_approach}")
                lines.append(f"   Related issues: {len(task.related_issues)}")
        
        lines.append("\n")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def request_human_decision(self, state: WorkflowState) -> HITLDecision:
        """
        Request human decision via console input.
        
        Args:
            state: Current workflow state
            
        Returns:
            HITLDecision with user's choice
        """
        # Print summary
        summary = self.format_review_summary(state)
        print(summary)
        
        # Request decision
        print("\n" + "=" * 80)
        print("HUMAN DECISION REQUIRED")
        print("=" * 80)
        print("\nOptions:")
        print("  1. approve       - Approve and publish review")
        print("  2. edit          - Edit review before publishing")
        print("  3. reject        - Reject and stop")
        print("  4. summary_only  - Post only a summary (no detailed issues)")
        print()
        
        # Get input
        while True:
            choice = input("Your decision [1-4]: ").strip().lower()
            
            if choice in ["1", "approve"]:
                return HITLDecision(
                    action=HITLAction.APPROVE,
                    feedback="Approved for publishing"
                )
            elif choice in ["2", "edit"]:
                edited_content = input("\nEnter edited review content (or press Enter to skip): ").strip()
                return HITLDecision(
                    action=HITLAction.EDIT,
                    edited_content=edited_content if edited_content else None,
                    feedback="User requested edits"
                )
            elif choice in ["3", "reject"]:
                feedback = input("\nReason for rejection (optional): ").strip()
                return HITLDecision(
                    action=HITLAction.REJECT,
                    feedback=feedback if feedback else "Rejected by user"
                )
            elif choice in ["4", "summary_only"]:
                return HITLDecision(
                    action=HITLAction.POST_SUMMARY_ONLY,
                    feedback="Post summary only"
                )
            else:
                print("Invalid choice. Please enter 1-4 or the action name.")
    
    def __call__(self, state: WorkflowState) -> Dict[str, Any]:
        """
        LangGraph node function: request human approval.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updates to state (hitl_decision)
        """
        print(f"\n👤 HITL Gate: Requesting human approval...")
        
        # Auto-approve if enabled
        if self.auto_approve:
            print("  ⚡ Auto-approve enabled - skipping human input")
            return {
                "hitl_decision": HITLDecision(
                    action=HITLAction.APPROVE,
                    feedback="Auto-approved for web interface"
                )
            }
        
        # For web interface: check if decision already provided
        if state.hitl_decision:
            print(f"  ✓ Decision already provided: {state.hitl_decision.action}")
            return {}
        
        # No decision yet - pause workflow and wait for web UI
        print("  ⏸️  Pausing workflow - awaiting decision from web interface...")
        
        # Use LangGraph interrupt to pause execution
        from langgraph.types import interrupt
        
        # Format summary for display
        summary = self.format_review_summary(state)
        
        # Interrupt execution and return summary to UI
        # The interrupt will pause here until workflow.update_state() is called with hitl_decision
        interrupt({
            "type": "hitl_decision_required",
            "summary": summary,
            "issues_count": len(state.review_issues),
            "tasks_count": len(state.fix_tasks),
            "guardrails_passed": state.guardrail_result.passed if state.guardrail_result else True,
            "blocked_reasons": state.guardrail_result.blocked_reasons if state.guardrail_result else []
        })
        
        # After resume, the decision should be in state
        # Return empty dict as state was already updated
        return {}
