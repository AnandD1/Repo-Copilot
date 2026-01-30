"""Node 2: Reviewer Agent - Analyze hunks and generate review issues."""

import json
from typing import Dict, Any, List
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .state import WorkflowState, ReviewIssue, IssueSeverity, IssueCategory


REVIEW_PROMPT = """You are a senior code reviewer analyzing a pull request change.

Your task is to review the code change and identify any issues. You MUST provide evidence for every issue you report.

## Code Change
File: {file_path}
Lines {old_line_start}-{old_line_end} → {new_line_start}-{new_line_end}

### Removed Lines:
{removed_lines}

### Added Lines:
{added_lines}

### Context Lines (unchanged):
{context_lines}

## Evidence Context

### Local Context (same file):
{local_context}

### Similar Code Patterns (from repository):
{similar_code}

### Project Conventions & Style Guide:
{conventions}

## Instructions

Analyze the code change and identify issues in these categories:
- **correctness**: Logic errors, bugs, incorrect implementation
- **security**: Security vulnerabilities, exposed secrets, unsafe operations
- **perf**: Performance issues, inefficient algorithms, resource leaks
- **style**: Code style violations, naming conventions, formatting
- **test**: Missing tests, inadequate test coverage
- **docs**: Missing or incorrect documentation

For each issue, you MUST:
1. Have at least one evidence reference from the provided context
2. Assign severity: blocker (must fix), major (should fix), minor (nice to fix), nit (optional)
3. Provide clear explanation and actionable suggestion
4. Reference evidence using format: [file.py:10-20] or [CONVENTION: Style Guide]

**CRITICAL RULE**: If you cannot find evidence in the provided context, DO NOT report the issue.

Output a JSON array of issues. If no issues found, return empty array [].

Example output:
[
  {{
    "severity": "major",
    "category": "correctness",
    "file_path": "src/app.py",
    "line_number": 45,
    "explanation": "Function may raise KeyError if 'user_id' key is missing from dict",
    "suggestion": "Use dict.get('user_id') with a default value or add explicit key check",
    "evidence_references": ["src/utils.py:23-28", "CONVENTION: Error Handling"]
  }}
]

Now analyze the code change and output JSON:
"""


class ReviewerAgent:
    """Agent responsible for reviewing code changes and identifying issues."""
    
    def __init__(self, model_name: str = "qwen2.5-coder:7b-instruct"):
        """
        Initialize reviewer agent with LLM.
        
        Args:
            model_name: Ollama model name
        """
        self.llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.1,
            num_predict=2048,
        )
        self.parser = JsonOutputParser()
        self.prompt = ChatPromptTemplate.from_template(REVIEW_PROMPT)
    
    def review_hunk(
        self,
        hunk: Dict[str, Any],
        retrieval_bundle: Any
    ) -> List[ReviewIssue]:
        """
        Review a single hunk with retrieved context.
        
        Args:
            hunk: Hunk dictionary
            retrieval_bundle: Retrieved context bundle
            
        Returns:
            List of ReviewIssue objects
        """
        # Format context
        local_ctx = self._format_context(retrieval_bundle.local_context, "Local Context")
        similar_ctx = self._format_context(retrieval_bundle.similar_code, "Similar Code")
        conventions_ctx = self._format_context(retrieval_bundle.conventions, "Conventions")
        
        # Prepare prompt inputs
        prompt_input = {
            "file_path": hunk.get("file_path", "unknown"),
            "old_line_start": hunk.get("old_line_start", 0),
            "old_line_end": hunk.get("old_line_end", 0),
            "new_line_start": hunk.get("new_line_start", 0),
            "new_line_end": hunk.get("new_line_end", 0),
            "removed_lines": "\n".join(hunk.get("removed_lines", [])) or "(none)",
            "added_lines": "\n".join(hunk.get("added_lines", [])) or "(none)",
            "context_lines": "\n".join(hunk.get("context_lines", [])) or "(none)",
            "local_context": local_ctx or "(none)",
            "similar_code": similar_ctx or "(none)",
            "conventions": conventions_ctx or "(none)",
        }
        
        # Invoke LLM
        try:
            chain = self.prompt | self.llm
            response = chain.invoke(prompt_input)
            
            # Parse JSON response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            issues_data = self._extract_json(response_text)
            
            # Convert to ReviewIssue objects
            issues = []
            for issue_dict in issues_data:
                try:
                    issue = ReviewIssue(**issue_dict)
                    issues.append(issue)
                except Exception as e:
                    print(f"Failed to parse issue: {e}")
                    continue
            
            return issues
            
        except Exception as e:
            print(f"Review failed for hunk: {e}")
            return []
    
    def _format_context(self, chunks: List[Dict[str, Any]], section_name: str) -> str:
        """Format retrieved chunks as readable context."""
        if not chunks:
            return ""
        
        lines = [f"## {section_name}"]
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})
            file_path = metadata.get("file_path", "unknown")
            start_line = metadata.get("start_line", 0)
            end_line = metadata.get("end_line", 0)
            
            lines.append(f"\n### Source: [{file_path}:{start_line}-{end_line}]")
            lines.append(f"```\n{content}\n```")
        
        return "\n".join(lines)
    
    def _extract_json(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON array from LLM response."""
        # Try direct parse first
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
        
        # No valid JSON found
        return []
    
    def __call__(self, state: WorkflowState) -> Dict[str, Any]:
        """
        LangGraph node function: review all hunks.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updates to state (review_issues)
        """
        print(f"\n📝 Reviewer Agent: Analyzing {len(state.hunks)} hunks...")
        
        all_issues = []
        
        for hunk in state.hunks:
            hunk_id = hunk.get("hunk_id", "unknown")
            
            # Get retrieval bundle for this hunk
            bundle = state.retrieval_bundles.get(hunk_id)
            if not bundle:
                print(f"  ⚠ No retrieval bundle for {hunk_id}, skipping...")
                continue
            
            try:
                issues = self.review_hunk(hunk, bundle)
                all_issues.extend(issues)
                print(f"  ✓ Found {len(issues)} issues in {hunk_id}")
            except Exception as e:
                error_msg = f"Review failed for {hunk_id}: {e}"
                print(f"  ✗ {error_msg}")
                state.errors.append(error_msg)
        
        print(f"\n  Total issues found: {len(all_issues)}")
        
        return {
            "review_issues": all_issues,
            "current_node": "reviewer"
        }
