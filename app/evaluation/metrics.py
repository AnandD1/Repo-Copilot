"""Evaluation metrics for PR reviews."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time


@dataclass
class MetricsResult:
    """Results from evaluation metrics."""
    
    # Groundedness metrics
    groundedness_score: float  # 0-1: % of issues with valid evidence
    total_issues: int
    issues_with_evidence: int
    
    # Precision metrics
    precision_score: float  # 0-1: % of valid comments
    total_comments: int
    valid_comments: int
    nonsense_comments: int
    
    # Usefulness metrics
    usefulness_score: float  # 1-5 average rating
    
    # Consistency metrics
    consistency_score: float  # 0-1: adherence to style guide
    style_violations: int
    style_checks_passed: int
    
    # Latency metrics
    latency_seconds: float
    meets_latency_target: bool  # < 60s
    
    # Overall
    overall_score: float  # Weighted average
    
    # Optional fields with defaults
    usefulness_ratings: List[int] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'groundedness': {
                'score': self.groundedness_score,
                'issues_with_evidence': f"{self.issues_with_evidence}/{self.total_issues}"
            },
            'precision': {
                'score': self.precision_score,
                'valid_comments': f"{self.valid_comments}/{self.total_comments}",
                'nonsense_comments': self.nonsense_comments
            },
            'usefulness': {
                'score': self.usefulness_score,
                'ratings': self.usefulness_ratings,
                'average': sum(self.usefulness_ratings) / len(self.usefulness_ratings) if self.usefulness_ratings else 0
            },
            'consistency': {
                'score': self.consistency_score,
                'violations': self.style_violations,
                'passed': self.style_checks_passed
            },
            'latency': {
                'seconds': self.latency_seconds,
                'meets_target': self.meets_latency_target,
                'target': '< 60s'
            },
            'overall_score': self.overall_score
        }


class EvaluationMetrics:
    """Calculate evaluation metrics for PR reviews."""
    
    @staticmethod
    def calculate_groundedness(
        review_issues: List[Any],
        expected_evidence: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate groundedness: % of issues with valid evidence references.
        
        Args:
            review_issues: List of ReviewIssue objects
            expected_evidence: Ground truth evidence references
            
        Returns:
            Dict with groundedness metrics
        """
        if not review_issues:
            return {
                'score': 1.0,  # No issues = perfect groundedness
                'total': 0,
                'with_evidence': 0
            }
        
        issues_with_evidence = 0
        for issue in review_issues:
            if hasattr(issue, 'evidence_references') and issue.evidence_references:
                # Check if any evidence reference is valid
                has_valid_evidence = any(
                    any(expected in ref for expected in expected_evidence)
                    for ref in issue.evidence_references
                ) if expected_evidence else True
                
                if has_valid_evidence or len(issue.evidence_references) > 0:
                    issues_with_evidence += 1
        
        score = issues_with_evidence / len(review_issues)
        
        return {
            'score': score,
            'total': len(review_issues),
            'with_evidence': issues_with_evidence
        }
    
    @staticmethod
    def calculate_precision(
        review_issues: List[Any],
        expected_issues: List[Dict[str, Any]],
        manual_labels: Optional[List[bool]] = None
    ) -> Dict[str, Any]:
        """
        Calculate precision: how many comments are valid vs nonsense.
        
        Args:
            review_issues: List of ReviewIssue objects
            expected_issues: Expected issues from ground truth
            manual_labels: Optional manual validity labels (True = valid)
            
        Returns:
            Dict with precision metrics
        """
        if not review_issues:
            if expected_issues:
                # Missed all expected issues
                return {'score': 0.0, 'total': 0, 'valid': 0, 'nonsense': 0}
            else:
                # Correctly found no issues
                return {'score': 1.0, 'total': 0, 'valid': 0, 'nonsense': 0}
        
        # If manual labels provided, use them
        if manual_labels:
            valid = sum(manual_labels)
            nonsense = len(manual_labels) - valid
            score = valid / len(manual_labels) if manual_labels else 0
        else:
            # Auto-evaluate based on expected issues
            valid = 0
            for issue in review_issues:
                # Check if issue matches expected severity/category
                issue_severity = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
                issue_category = issue.category.value if hasattr(issue.category, 'value') else str(issue.category)
                
                for expected in expected_issues:
                    if (expected.get('severity') == issue_severity or 
                        expected.get('category') == issue_category):
                        valid += 1
                        break
            
            nonsense = len(review_issues) - valid
            score = valid / len(review_issues) if review_issues else 0
        
        return {
            'score': score,
            'total': len(review_issues),
            'valid': valid,
            'nonsense': nonsense
        }
    
    @staticmethod
    def calculate_usefulness(
        ratings: List[int]
    ) -> Dict[str, Any]:
        """
        Calculate usefulness from reviewer ratings (1-5 scale).
        
        Args:
            ratings: List of ratings from 1-5
            
        Returns:
            Dict with usefulness metrics
        """
        if not ratings:
            return {'score': 3.0, 'ratings': [], 'count': 0}
        
        # Validate ratings
        valid_ratings = [r for r in ratings if 1 <= r <= 5]
        
        if not valid_ratings:
            return {'score': 3.0, 'ratings': [], 'count': 0}
        
        score = sum(valid_ratings) / len(valid_ratings)
        
        return {
            'score': score,
            'ratings': valid_ratings,
            'count': len(valid_ratings)
        }
    
    @staticmethod
    def calculate_consistency(
        review_issues: List[Any],
        expected_severity: str
    ) -> Dict[str, Any]:
        """
        Calculate consistency: adherence to style guide and severity standards.
        
        Args:
            review_issues: List of ReviewIssue objects
            expected_severity: Expected highest severity level
            
        Returns:
            Dict with consistency metrics
        """
        if not review_issues:
            return {'score': 1.0, 'violations': 0, 'passed': 1}
        
        severity_order = ['blocker', 'major', 'minor', 'nit', 'none']
        
        violations = 0
        passed = 0
        
        for issue in review_issues:
            issue_severity = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
            
            # Check severity appropriateness
            if expected_severity in severity_order and issue_severity in severity_order:
                expected_idx = severity_order.index(expected_severity)
                actual_idx = severity_order.index(issue_severity)
                
                # Allow some tolerance (within 1 level)
                if abs(expected_idx - actual_idx) <= 1:
                    passed += 1
                else:
                    violations += 1
            else:
                passed += 1
        
        score = passed / (passed + violations) if (passed + violations) > 0 else 1.0
        
        return {
            'score': score,
            'violations': violations,
            'passed': passed
        }
    
    @staticmethod
    def calculate_latency(
        start_time: float,
        end_time: float,
        target_seconds: float = 60.0
    ) -> Dict[str, Any]:
        """
        Calculate latency metrics.
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            target_seconds: Target latency in seconds (default 60s)
            
        Returns:
            Dict with latency metrics
        """
        latency = end_time - start_time
        meets_target = latency <= target_seconds
        
        return {
            'seconds': latency,
            'meets_target': meets_target,
            'target': target_seconds
        }
    
    @staticmethod
    def calculate_overall(
        groundedness: float,
        precision: float,
        usefulness: float,
        consistency: float,
        latency_met: bool
    ) -> float:
        """
        Calculate overall score with weighted average.
        
        Weights:
        - Groundedness: 25%
        - Precision: 30%
        - Usefulness: 20%
        - Consistency: 15%
        - Latency: 10%
        """
        weights = {
            'groundedness': 0.25,
            'precision': 0.30,
            'usefulness': 0.20,
            'consistency': 0.15,
            'latency': 0.10
        }
        
        # Normalize usefulness from 1-5 to 0-1
        usefulness_normalized = (usefulness - 1) / 4
        
        # Latency as binary 0 or 1
        latency_score = 1.0 if latency_met else 0.0
        
        overall = (
            groundedness * weights['groundedness'] +
            precision * weights['precision'] +
            usefulness_normalized * weights['usefulness'] +
            consistency * weights['consistency'] +
            latency_score * weights['latency']
        )
        
        return overall
