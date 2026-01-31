"""Test evaluation framework - Phase 7."""

import time
import hashlib
from datetime import datetime
from pathlib import Path

from app.evaluation import Evaluator, SyntheticPRGenerator
from app.workflow import WorkflowState, create_review_workflow, run_workflow
from config.settings import Settings


def run_workflow_for_pr(synthetic_pr, settings):
    """
    Run workflow for a synthetic PR.
    
    Returns:
        Tuple of (WorkflowState, latency_seconds)
    """
    start_time = time.time()
    
    # Create hunk from synthetic PR
    hunk = synthetic_pr.to_hunk()
    
    # Build workflow state
    run_id = f"eval_{synthetic_pr.pr_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    diff_hash = hashlib.md5(str(hunk).encode()).hexdigest()[:12]
    
    initial_state = WorkflowState(
        run_id=run_id,
        repo_owner="Evaluation",
        repo_name="SyntheticPR",
        repo_id="Evaluation_SyntheticPR_main",
        pr_number=int(synthetic_pr.pr_id.split('_')[1]),
        pr_sha="synthetic",
        diff_hash=diff_hash,
        hunks=[hunk]
    )
    
    # Create and run workflow
    workflow = create_review_workflow(
        github_token=settings.github_token,
        settings=settings
    )
    
    # Run workflow (auto-approve for evaluation)
    final_state = run_workflow(initial_state, workflow)
    
    end_time = time.time()
    latency = end_time - start_time
    
    # Convert dict to WorkflowState if needed
    if isinstance(final_state, dict):
        final_state = WorkflowState(**final_state)
    
    return final_state, latency


def main():
    """Run evaluation."""
    print("\n" + "=" * 80)
    print("PHASE 7: EVALUATION - Testing PR Review System")
    print("=" * 80)
    
    # Load settings
    settings = Settings()
    settings.slack_enabled = False  # Disable Slack for evaluation
    
    print(f"\n📋 Configuration:")
    print(f"  Ollama Model: {settings.ollama_model}")
    print(f"  Embedding Model: {settings.embedding_model}")
    print(f"  Qdrant Collection: {settings.qdrant_collection_name}")
    print(f"  Slack: Disabled for evaluation")
    
    # Create evaluator
    evaluator = Evaluator(settings=settings)
    
    # Optional: Manual usefulness ratings (1-5)
    # You can manually rate each PR after reviewing the output
    manual_ratings = {
        # 'eval_001': 5,  # Excellent - found SQL injection
        # 'eval_002': 4,  # Good - found error handling issue
        # 'eval_009': 5,  # Excellent - correctly found no issues
        # etc...
    }
    
    # Define workflow runner
    def workflow_runner(synthetic_pr):
        return run_workflow_for_pr(synthetic_pr, settings)
    
    # Run evaluation
    report = evaluator.run_evaluation(
        workflow_runner=workflow_runner,
        manual_ratings=manual_ratings
    )
    
    # Save report
    output_dir = Path("evaluation_results")
    output_dir.mkdir(exist_ok=True)
    
    report_file = output_dir / f"evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report.save(report_file)
    
    # Generate summary
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    print(f"\n✅ Evaluated {report.total_prs} synthetic PRs")
    print(f"\n📊 Performance Metrics:")
    print(f"  • Groundedness: {report.avg_groundedness:.1%} - Issues with valid evidence")
    print(f"  • Precision: {report.avg_precision:.1%} - Valid vs nonsense comments")
    print(f"  • Usefulness: {report.avg_usefulness:.1f}/5.0 - Reviewer satisfaction")
    print(f"  • Consistency: {report.avg_consistency:.1%} - Adherence to standards")
    print(f"  • Latency: {report.avg_latency:.1f}s avg ({report.latency_pass_rate:.0%} < 60s)")
    
    print(f"\n🎯 Overall Score: {report.avg_overall:.1%}")
    
    if report.avg_overall >= 0.8:
        print("\n🎉 Excellent! System performing at high quality.")
    elif report.avg_overall >= 0.6:
        print("\n✅ Good! System is production-ready with room for improvement.")
    elif report.avg_overall >= 0.4:
        print("\n⚠️  Fair. System needs optimization before production.")
    else:
        print("\n❌ Poor. Significant improvements needed.")
    
    print(f"\n📁 Full report saved to: {report_file}")
    
    # Category breakdown
    print(f"\n📂 Performance by Category:")
    categories = {}
    for detail in report.per_pr_details:
        cat = detail['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(detail['metrics']['overall_score'])
    
    for cat, scores in sorted(categories.items()):
        avg_score = sum(scores) / len(scores)
        print(f"  {cat:12s}: {avg_score:.1%} ({len(scores)} PRs)")
    
    print("\n" + "=" * 80)
    
    return report


if __name__ == "__main__":
    main()
