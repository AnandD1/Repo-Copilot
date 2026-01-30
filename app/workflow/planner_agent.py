"""Node 3: Patch Planner Agent - Generate fix plan from issues."""

import json
from typing import Dict, Any, List
from collections import defaultdict
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from .state import WorkflowState, ReviewIssue, FixTask, EffortEstimate


PLANNER_PROMPT = """You are a technical lead creating a fix plan for code review issues.

You have identified the following issues in a pull request:

{issues_summary}

## Your Task

Group related issues into logical fix tasks. Each task should:
1. Have a clear, actionable title
2. Explain why it matters (impact on code quality/security/performance)
3. List all affected files
4. Provide a suggested approach to fix
5. Estimate effort: S (small, <1hr), M (medium, 1-4hrs), L (large, >4hrs)

Group issues by:
- Theme (e.g., "Error handling improvements", "Security fixes", "Style consistency")
- File or module
- Related functionality

Output a JSON array of fix tasks:

[
  {{
    "task_id": "task_1",
    "title": "Add error handling for missing keys",
    "why_it_matters": "Prevents runtime KeyError exceptions that could crash the application",
    "affected_files": ["src/app.py", "src/utils.py"],
    "suggested_approach": "Use dict.get() with defaults or add try-except blocks around dict access",
    "effort_estimate": "S",
    "related_issues": [0, 1, 3]
  }}
]

The "related_issues" field should contain the indices (0-based) of issues from the input list.

Now create the fix plan:
"""


class PatchPlannerAgent:
    """Agent responsible for creating a fix plan from review issues."""
    
    def __init__(self, model_name: str = "qwen2.5-coder:7b-instruct"):
        """
        Initialize patch planner agent with LLM.
        
        Args:
            model_name: Ollama model name
        """
        self.llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.2,
            num_predict=2048,
        )
        self.prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    
    def create_fix_plan(self, issues: List[ReviewIssue]) -> List[FixTask]:
        """
        Create a fix plan from review issues.
        
        Args:
            issues: List of review issues
            
        Returns:
            List of fix tasks
        """
        if not issues:
            return []
        
        # Format issues summary
        issues_summary = self._format_issues(issues)
        
        # Invoke LLM
        try:
            chain = self.prompt | self.llm
            response = chain.invoke({"issues_summary": issues_summary})
            
            # Parse JSON response
            response_text = response.content if hasattr(response, 'content') else str(response)
            tasks_data = self._extract_json(response_text)
            
            # Convert to FixTask objects
            tasks = []
            for task_dict in tasks_data:
                try:
                    task = FixTask(**task_dict)
                    tasks.append(task)
                except Exception as e:
                    print(f"Failed to parse task: {e}")
                    continue
            
            return tasks
            
        except Exception as e:
            print(f"Fix planning failed: {e}")
            # Fallback: create simple tasks by file
            return self._create_fallback_plan(issues)
    
    def _format_issues(self, issues: List[ReviewIssue]) -> str:
        """Format issues as numbered list for LLM."""
        lines = []
        for i, issue in enumerate(issues):
            lines.append(f"\n{i}. [{issue.severity.upper()}] {issue.category}")
            lines.append(f"   File: {issue.file_path}:{issue.line_number}")
            lines.append(f"   Issue: {issue.explanation}")
            lines.append(f"   Suggestion: {issue.suggestion}")
            if issue.evidence_references:
                lines.append(f"   Evidence: {', '.join(issue.evidence_references)}")
        
        return "\n".join(lines)
    
    def _extract_json(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON array from LLM response."""
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON array in text
        import re
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return []
    
    def _create_fallback_plan(self, issues: List[ReviewIssue]) -> List[FixTask]:
        """Create simple fallback plan grouped by severity and file."""
        # Group by severity and file
        groups = defaultdict(list)
        for i, issue in enumerate(issues):
            key = (issue.severity, issue.file_path)
            groups[key].append(i)
        
        tasks = []
        for task_id, ((severity, file_path), issue_indices) in enumerate(groups.items(), 1):
            related_issues = [issues[i] for i in issue_indices]
            # Handle both enum and string for categories
            categories = {
                (issue.category.value if hasattr(issue.category, 'value') else str(issue.category))
                for issue in related_issues
            }
            
            tasks.append(FixTask(
                task_id=f"task_{task_id}",
                title=f"Fix {severity} issues in {file_path}",
                why_it_matters=f"Resolve {len(issue_indices)} {severity} issues ({', '.join(categories)})",
                affected_files=[file_path],
                suggested_approach=f"Address {len(issue_indices)} issues in this file",
                effort_estimate=EffortEstimate.SMALL if len(issue_indices) <= 2 else EffortEstimate.MEDIUM,
                related_issues=issue_indices
            ))
        
        return tasks
    
    def __call__(self, state: WorkflowState) -> Dict[str, Any]:
        """
        LangGraph node function: create fix plan.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updates to state (fix_tasks)
        """
        print(f"\n🔧 Patch Planner Agent: Creating fix plan from {len(state.review_issues)} issues...")
        
        if not state.review_issues:
            print("  No issues to plan for.")
            return {
                "fix_tasks": [],
                "current_node": "planner"
            }
        
        try:
            tasks = self.create_fix_plan(state.review_issues)
            print(f"  ✓ Created {len(tasks)} fix tasks")
            
            for task in tasks:
                # Handle both enum and string for effort_estimate
                effort_str = task.effort_estimate.value if hasattr(task.effort_estimate, 'value') else str(task.effort_estimate)
                print(f"    - {task.title} ({effort_str}, {len(task.related_issues)} issues)")
            
            return {
                "fix_tasks": tasks,
                "current_node": "planner"
            }
            
        except Exception as e:
            error_msg = f"Patch planning failed: {e}"
            print(f"  ✗ {error_msg}")
            return {
                "fix_tasks": [],
                "current_node": "planner",
                "errors": state.errors + [error_msg]
            }
