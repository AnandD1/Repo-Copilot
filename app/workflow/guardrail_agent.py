"""Node 4: Guardrail Agent - Validate outputs and run safety checks."""

import re
from typing import Dict, Any, List
from pydantic import ValidationError

from .state import WorkflowState, GuardrailResult, ReviewIssue, FixTask


class GuardrailAgent:
    """Agent responsible for validating outputs and running safety checks."""
    
    def __init__(self):
        """Initialize guardrail agent."""
        # Secret patterns to detect
        self.secret_patterns = [
            (r'[A-Za-z0-9]{20,}', "Potential API key or token"),
            (r'sk-[A-Za-z0-9]{32,}', "OpenAI API key pattern"),
            (r'ghp_[A-Za-z0-9]{36,}', "GitHub personal access token"),
            (r'AIza[A-Za-z0-9_-]{35}', "Google API key"),
            (r'AKIA[A-Z0-9]{16}', "AWS access key"),
            (r'-----BEGIN (RSA |DSA |EC )?PRIVATE KEY-----', "Private key"),
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        ]
        
        # Prompt injection patterns
        self.injection_patterns = [
            r'ignore (all )?previous instructions',
            r'disregard (all )?previous',
            r'forget (all )?previous',
            r'you are now',
            r'new instructions:',
            r'system prompt:',
            r'override prompt',
        ]
    
    def check_schema_validation(
        self,
        issues: List[ReviewIssue],
        tasks: List[FixTask]
    ) -> tuple[bool, List[str]]:
        """
        Validate that all issues and tasks conform to Pydantic schemas.
        
        Returns:
            (passed, errors)
        """
        errors = []
        
        # Validate issues
        for i, issue in enumerate(issues):
            try:
                # Re-validate to ensure all fields are correct
                ReviewIssue.model_validate(issue.model_dump())
            except ValidationError as e:
                errors.append(f"Issue {i} schema validation failed: {e}")
        
        # Validate tasks
        for i, task in enumerate(tasks):
            try:
                FixTask.model_validate(task.model_dump())
            except ValidationError as e:
                errors.append(f"Task {i} schema validation failed: {e}")
        
        return len(errors) == 0, errors
    
    def check_secret_scanning(
        self,
        issues: List[ReviewIssue],
        tasks: List[FixTask]
    ) -> tuple[bool, List[str]]:
        """
        Scan for potential secrets in output.
        
        Returns:
            (passed, blocked_reasons)
        """
        blocked = []
        
        # Collect all text to scan
        text_to_scan = []
        for issue in issues:
            text_to_scan.append(issue.explanation)
            text_to_scan.append(issue.suggestion)
            text_to_scan.extend(issue.evidence_references)
        
        for task in tasks:
            text_to_scan.append(task.title)
            text_to_scan.append(task.suggested_approach)
        
        combined_text = " ".join(text_to_scan)
        
        # Check for secret patterns
        for pattern, description in self.secret_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                # Filter out common false positives
                real_matches = [m for m in matches if not self._is_false_positive(m)]
                if real_matches:
                    blocked.append(f"Potential secret detected: {description}")
        
        return len(blocked) == 0, blocked
    
    def check_prompt_injection(
        self,
        issues: List[ReviewIssue],
        tasks: List[FixTask]
    ) -> tuple[bool, List[str]]:
        """
        Check for prompt injection attempts in retrieved content.
        
        Returns:
            (passed, warnings)
        """
        warnings = []
        
        # Collect evidence references (these come from repo content)
        evidence_text = []
        for issue in issues:
            evidence_text.extend(issue.evidence_references)
        
        combined_text = " ".join(evidence_text).lower()
        
        # Check for injection patterns
        for pattern in self.injection_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                warnings.append(f"Potential prompt injection pattern detected: {pattern}")
        
        # Don't block on warnings, just log them
        return True, warnings
    
    def check_no_evidence_rule(
        self,
        issues: List[ReviewIssue]
    ) -> tuple[bool, List[str]]:
        """
        Enforce "no evidence = no issue" rule.
        
        Returns:
            (passed, blocked_reasons)
        """
        blocked = []
        
        for i, issue in enumerate(issues):
            if not issue.evidence_references or len(issue.evidence_references) == 0:
                blocked.append(
                    f"Issue {i} ({issue.category} in {issue.file_path}:{issue.line_number}) "
                    f"has no evidence references - violates 'no evidence = no issue' rule"
                )
        
        return len(blocked) == 0, blocked
    
    def _is_false_positive(self, match: str) -> bool:
        """Check if a secret match is likely a false positive."""
        # Common false positives
        false_positive_patterns = [
            r'^example',
            r'^test',
            r'^dummy',
            r'^placeholder',
            r'^your[_-]',
            r'^my[_-]',
        ]
        
        for pattern in false_positive_patterns:
            if re.match(pattern, match, re.IGNORECASE):
                return True
        
        return False
    
    def run_all_checks(
        self,
        issues: List[ReviewIssue],
        tasks: List[FixTask]
    ) -> GuardrailResult:
        """
        Run all guardrail checks.
        
        Args:
            issues: Review issues to check
            tasks: Fix tasks to check
            
        Returns:
            GuardrailResult with pass/fail and details
        """
        all_blocked = []
        all_warnings = []
        checks_performed = []
        
        # 1. Schema validation
        schema_pass, schema_errors = self.check_schema_validation(issues, tasks)
        checks_performed.append("schema_validation")
        if not schema_pass:
            all_blocked.extend(schema_errors)
        
        # 2. Secret scanning
        secret_pass, secret_blocked = self.check_secret_scanning(issues, tasks)
        checks_performed.append("secret_scanning")
        if not secret_pass:
            all_blocked.extend(secret_blocked)
        
        # 3. Prompt injection detection
        injection_pass, injection_warnings = self.check_prompt_injection(issues, tasks)
        checks_performed.append("prompt_injection_guard")
        if injection_warnings:
            all_warnings.extend(injection_warnings)
        
        # 4. Evidence enforcement
        evidence_pass, evidence_blocked = self.check_no_evidence_rule(issues)
        checks_performed.append("evidence_enforcement")
        if not evidence_pass:
            all_blocked.extend(evidence_blocked)
        
        # Overall pass if no blockers
        passed = len(all_blocked) == 0
        
        return GuardrailResult(
            passed=passed,
            blocked_reasons=all_blocked,
            warnings=all_warnings,
            checks_performed=checks_performed
        )
    
    def __call__(self, state: WorkflowState) -> Dict[str, Any]:
        """
        LangGraph node function: run guardrail checks.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updates to state (guardrail_result)
        """
        print("\n🛡️ Guardrail Agent: Running safety checks...")
        
        try:
            result = self.run_all_checks(
                issues=state.review_issues,
                tasks=state.fix_tasks
            )
            
            print(f"  Checks performed: {', '.join(result.checks_performed)}")
            
            if result.passed:
                print(f"  ✓ All guardrail checks passed")
                if result.warnings:
                    print(f"  ⚠ {len(result.warnings)} warnings:")
                    for warning in result.warnings:
                        print(f"    - {warning}")
            else:
                print(f"  ✗ Guardrail checks FAILED:")
                for reason in result.blocked_reasons:
                    print(f"    - {reason}")
            
            return {
                "guardrail_result": result,
                "current_node": "guardrail"
            }
            
        except Exception as e:
            error_msg = f"Guardrail check failed: {e}"
            print(f"  ✗ {error_msg}")
            
            # Create failed result
            result = GuardrailResult(
                passed=False,
                blocked_reasons=[error_msg],
                warnings=[],
                checks_performed=["error"]
            )
            
            return {
                "guardrail_result": result,
                "current_node": "guardrail",
                "errors": state.errors + [error_msg]
            }
