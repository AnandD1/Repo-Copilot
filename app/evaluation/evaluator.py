"""Main evaluation runner."""

import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .synthetic_pr_generator import SyntheticPR, SyntheticPRGenerator
from .metrics import EvaluationMetrics, MetricsResult
from app.workflow.state import WorkflowState
from config.settings import Settings


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    
    timestamp: datetime
    total_prs: int
    results: List[MetricsResult] = field(default_factory=list)
    per_pr_details: List[Dict[str, Any]] = field(default_factory=list)
    
    # Aggregate metrics
    avg_groundedness: float = 0.0
    avg_precision: float = 0.0
    avg_usefulness: float = 0.0
    avg_consistency: float = 0.0
    avg_latency: float = 0.0
    latency_pass_rate: float = 0.0
    avg_overall: float = 0.0
    
    def calculate_aggregates(self):
        """Calculate aggregate metrics from results."""
        if not self.results:
            return
        
        n = len(self.results)
        self.avg_groundedness = sum(r.groundedness_score for r in self.results) / n
        self.avg_precision = sum(r.precision_score for r in self.results) / n
        self.avg_usefulness = sum(r.usefulness_score for r in self.results) / n
        self.avg_consistency = sum(r.consistency_score for r in self.results) / n
        self.avg_latency = sum(r.latency_seconds for r in self.results) / n
        self.latency_pass_rate = sum(1 for r in self.results if r.meets_latency_target) / n
        self.avg_overall = sum(r.overall_score for r in self.results) / n
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_prs': self.total_prs,
            'aggregate_metrics': {
                'groundedness': self.avg_groundedness,
                'precision': self.avg_precision,
                'usefulness': self.avg_usefulness,
                'consistency': self.avg_consistency,
                'latency': self.avg_latency,
                'latency_pass_rate': self.latency_pass_rate,
                'overall_score': self.avg_overall
            },
            'per_pr_results': [r.to_dict() for r in self.results],
            'detailed_results': self.per_pr_details
        }
    
    def save(self, filepath: Path):
        """Save report to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"✓ Evaluation report saved: {filepath}")


class Evaluator:
    """Evaluate PR review system performance."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize evaluator."""
        self.settings = settings or Settings()
        self.generator = SyntheticPRGenerator()
        self.metrics = EvaluationMetrics()
    
    def evaluate_single_pr(
        self,
        synthetic_pr: SyntheticPR,
        workflow_state: WorkflowState,
        latency: float,
        manual_usefulness_rating: Optional[int] = None
    ) -> MetricsResult:
        """
        Evaluate a single PR review.
        
        Args:
            synthetic_pr: The synthetic PR
            workflow_state: Final workflow state
            latency: Time taken in seconds
            manual_usefulness_rating: Optional manual rating 1-5
            
        Returns:
            MetricsResult
        """
        review_issues = workflow_state.review_issues
        
        # Calculate groundedness
        groundedness = self.metrics.calculate_groundedness(
            review_issues,
            synthetic_pr.ground_truth_evidence
        )
        
        # Calculate precision
        precision = self.metrics.calculate_precision(
            review_issues,
            synthetic_pr.expected_issues
        )
        
        # Calculate usefulness
        if manual_usefulness_rating:
            usefulness_ratings = [manual_usefulness_rating]
        else:
            # Auto-assign based on precision
            if precision['score'] >= 0.8:
                usefulness_ratings = [5]
            elif precision['score'] >= 0.6:
                usefulness_ratings = [4]
            elif precision['score'] >= 0.4:
                usefulness_ratings = [3]
            elif precision['score'] >= 0.2:
                usefulness_ratings = [2]
            else:
                usefulness_ratings = [1]
        
        usefulness = self.metrics.calculate_usefulness(usefulness_ratings)
        
        # Calculate consistency
        consistency = self.metrics.calculate_consistency(
            review_issues,
            synthetic_pr.expected_severity
        )
        
        # Latency already calculated
        latency_met = latency <= 60.0
        
        # Calculate overall
        overall = self.metrics.calculate_overall(
            groundedness['score'],
            precision['score'],
            usefulness['score'],
            consistency['score'],
            latency_met
        )
        
        return MetricsResult(
            groundedness_score=groundedness['score'],
            total_issues=groundedness['total'],
            issues_with_evidence=groundedness['with_evidence'],
            precision_score=precision['score'],
            total_comments=precision['total'],
            valid_comments=precision['valid'],
            nonsense_comments=precision['nonsense'],
            usefulness_score=usefulness['score'],
            usefulness_ratings=usefulness['ratings'],
            consistency_score=consistency['score'],
            style_violations=consistency['violations'],
            style_checks_passed=consistency['passed'],
            latency_seconds=latency,
            meets_latency_target=latency_met,
            overall_score=overall
        )
    
    def run_evaluation(
        self,
        workflow_runner,
        manual_ratings: Optional[Dict[str, int]] = None
    ) -> EvaluationReport:
        """
        Run full evaluation on all synthetic PRs.
        
        Args:
            workflow_runner: Function that takes (synthetic_pr) -> (workflow_state, latency)
            manual_ratings: Optional dict of pr_id -> usefulness rating
            
        Returns:
            EvaluationReport
        """
        print("\n" + "=" * 80)
        print("PHASE 7: EVALUATION")
        print("=" * 80)
        print("\n🧪 Generating evaluation set...")
        
        synthetic_prs = self.generator.generate_evaluation_set()
        print(f"  ✓ Generated {len(synthetic_prs)} synthetic PRs")
        
        report = EvaluationReport(
            timestamp=datetime.now(),
            total_prs=len(synthetic_prs)
        )
        
        manual_ratings = manual_ratings or {}
        
        for i, pr in enumerate(synthetic_prs, 1):
            print(f"\n[{i}/{len(synthetic_prs)}] Evaluating {pr.pr_id}: {pr.title}")
            print(f"  Category: {pr.category}")
            print(f"  Expected: {pr.expected_severity} severity")
            
            try:
                # Run workflow
                start_time = time.time()
                workflow_state, actual_latency = workflow_runner(pr)
                end_time = time.time()
                
                # Use actual latency if provided, otherwise calculate
                latency = actual_latency if actual_latency else (end_time - start_time)
                
                print(f"  ⏱️  Latency: {latency:.2f}s {'✓' if latency <= 60 else '✗'}")
                print(f"  📊 Issues found: {len(workflow_state.review_issues)}")
                
                # Get manual rating if available
                manual_rating = manual_ratings.get(pr.pr_id)
                
                # Evaluate
                result = self.evaluate_single_pr(
                    pr,
                    workflow_state,
                    latency,
                    manual_rating
                )
                
                report.results.append(result)
                
                # Store detailed info
                report.per_pr_details.append({
                    'pr_id': pr.pr_id,
                    'title': pr.title,
                    'category': pr.category,
                    'expected_severity': pr.expected_severity,
                    'actual_issues': len(workflow_state.review_issues),
                    'latency': latency,
                    'metrics': result.to_dict()
                })
                
                print(f"  ✓ Groundedness: {result.groundedness_score:.2%}")
                print(f"  ✓ Precision: {result.precision_score:.2%}")
                print(f"  ✓ Usefulness: {result.usefulness_score:.1f}/5.0")
                print(f"  ✓ Consistency: {result.consistency_score:.2%}")
                print(f"  ✓ Overall: {result.overall_score:.2%}")
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue
        
        # Calculate aggregates
        report.calculate_aggregates()
        
        print("\n" + "=" * 80)
        print("EVALUATION COMPLETE")
        print("=" * 80)
        print(f"\n📊 Aggregate Results ({report.total_prs} PRs):")
        print(f"  Groundedness:     {report.avg_groundedness:.2%}")
        print(f"  Precision:        {report.avg_precision:.2%}")
        print(f"  Usefulness:       {report.avg_usefulness:.1f}/5.0")
        print(f"  Consistency:      {report.avg_consistency:.2%}")
        print(f"  Avg Latency:      {report.avg_latency:.2f}s")
        print(f"  Latency Pass Rate: {report.latency_pass_rate:.2%}")
        print(f"  Overall Score:    {report.avg_overall:.2%}")
        
        return report
