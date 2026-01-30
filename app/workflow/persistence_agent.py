"""Node 7: Persistence - Save workflow state and results."""

import json
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from .state import WorkflowState


class PersistenceAgent:
    """Agent responsible for persisting workflow state and results."""
    
    def __init__(self, storage_dir: str = "./workflow_runs"):
        """
        Initialize persistence agent.
        
        Args:
            storage_dir: Directory to store workflow runs
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_workflow_state(self, state: WorkflowState) -> str:
        """
        Save complete workflow state to disk.
        
        Args:
            state: Workflow state to save
            
        Returns:
            Path to saved file
        """
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{state.run_id}_{timestamp}.json"
        filepath = self.storage_dir / filename
        
        # Convert state to dict
        state_dict = state.model_dump(mode='json')
        
        # Add metadata
        state_dict['_metadata'] = {
            'saved_at': datetime.now().isoformat(),
            'version': '1.0',
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, indent=2, default=str)
        
        return str(filepath)
    
    def save_summary(self, state: WorkflowState) -> str:
        """
        Save a human-readable summary.
        
        Args:
            state: Workflow state
            
        Returns:
            Path to summary file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{state.run_id}_{timestamp}_summary.md"
        filepath = self.storage_dir / filename
        
        lines = []
        
        # Header
        lines.append(f"# Workflow Run Summary")
        lines.append("")
        lines.append(f"**Run ID**: {state.run_id}")
        lines.append(f"**Repository**: {state.repo_owner}/{state.repo_name}")
        lines.append(f"**PR Number**: #{state.pr_number}")
        lines.append(f"**Started**: {state.started_at.isoformat()}")
        lines.append(f"**PR SHA**: {state.pr_sha}")
        lines.append("")
        
        # Hunks processed
        lines.append(f"## Hunks Processed: {len(state.hunks)}")
        lines.append("")
        
        # Retrieval stats
        lines.append(f"## Retrieval Stats")
        lines.append("")
        total_chunks = sum(b.total_chunks for b in state.retrieval_bundles.values())
        lines.append(f"- Hunks with context: {len(state.retrieval_bundles)}")
        lines.append(f"- Total chunks retrieved: {total_chunks}")
        lines.append("")
        
        # Review issues
        lines.append(f"## Review Issues: {len(state.review_issues)}")
        lines.append("")
        if state.review_issues:
            by_severity = {}
            for issue in state.review_issues:
                # Handle both enum and string
                sev = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
                by_severity[sev] = by_severity.get(sev, 0) + 1
            
            for sev in ["blocker", "major", "minor", "nit"]:
                if sev in by_severity:
                    lines.append(f"- {sev}: {by_severity[sev]}")
            lines.append("")
        
        # Fix tasks
        lines.append(f"## Fix Tasks: {len(state.fix_tasks)}")
        lines.append("")
        if state.fix_tasks:
            for task in state.fix_tasks:
                lines.append(f"- {task.title} [{task.effort_estimate}]")
            lines.append("")
        
        # Guardrail results
        if state.guardrail_result:
            lines.append(f"## Guardrail Checks")
            lines.append("")
            lines.append(f"- **Status**: {'PASSED' if state.guardrail_result.passed else 'FAILED'}")
            lines.append(f"- **Checks**: {', '.join(state.guardrail_result.checks_performed)}")
            if state.guardrail_result.blocked_reasons:
                lines.append(f"- **Blocked**: {len(state.guardrail_result.blocked_reasons)} reasons")
            if state.guardrail_result.warnings:
                lines.append(f"- **Warnings**: {len(state.guardrail_result.warnings)}")
            lines.append("")
        
        # HITL decision
        if state.hitl_decision:
            lines.append(f"## HITL Decision")
            lines.append("")
            # Handle both enum and string
            action_str = state.hitl_decision.action.value if hasattr(state.hitl_decision.action, 'value') else str(state.hitl_decision.action)
            lines.append(f"- **Action**: {action_str}")
            if state.hitl_decision.feedback:
                lines.append(f"- **Feedback**: {state.hitl_decision.feedback}")
            lines.append(f"- **Timestamp**: {state.hitl_decision.timestamp.isoformat()}")
            lines.append("")
        
        # Publishing
        if state.posted_comment_url:
            lines.append(f"## Published")
            lines.append("")
            lines.append(f"- **Comment URL**: {state.posted_comment_url}")
            lines.append(f"- **Notification sent**: {state.notification_sent}")
            lines.append("")
        
        # Errors
        if state.errors:
            lines.append(f"## Errors ({len(state.errors)})")
            lines.append("")
            for error in state.errors:
                lines.append(f"- {error}")
            lines.append("")
        
        # Write summary
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        return str(filepath)
    
    def __call__(self, state: WorkflowState) -> Dict[str, Any]:
        """
        LangGraph node function: persist workflow state.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updates to state (persisted, persistence_path)
        """
        print(f"\n💾 Persistence Agent: Saving workflow state...")
        
        try:
            # Save full state
            state_path = self.save_workflow_state(state)
            print(f"  ✓ State saved: {state_path}")
            
            # Save summary
            summary_path = self.save_summary(state)
            print(f"  ✓ Summary saved: {summary_path}")
            
            return {
                "persisted": True,
                "persistence_path": state_path,
                "current_node": "persistence"
            }
            
        except Exception as e:
            error_msg = f"Persistence failed: {e}"
            print(f"  ✗ {error_msg}")
            
            return {
                "persisted": False,
                "persistence_path": None,
                "current_node": "persistence",
                "errors": state.errors + [error_msg]
            }
