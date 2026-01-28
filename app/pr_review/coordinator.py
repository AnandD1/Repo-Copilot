"""High-level PR review coordinator combining all Phase 2 components."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .pr_fetcher import PRFetcher, PRData, PRFile
from .diff_parser import DiffParser, FileDiff, Hunk
from .review_units import ReviewUnitBuilder, ReviewUnit, ReviewUnitType


@dataclass
class PRReviewSession:
    """Complete PR review session data."""
    pr_data: PRData
    file_diffs: List[FileDiff]
    review_units: List[ReviewUnit]
    
    @property
    def high_priority_units(self) -> List[ReviewUnit]:
        """Get high priority review units."""
        return [u for u in self.review_units if u.priority == 1]
    
    @property
    def files_by_language(self) -> Dict[str, List[str]]:
        """Group files by programming language."""
        lang_files = {}
        for unit in self.review_units:
            if unit.context.language:
                lang = unit.context.language
                if lang not in lang_files:
                    lang_files[lang] = []
                if unit.context.file_path not in lang_files[lang]:
                    lang_files[lang].append(unit.context.file_path)
        return lang_files
    
    def get_stats(self) -> Dict[str, Any]:
        """Get review session statistics."""
        return {
            'pr_number': self.pr_data.number,
            'pr_title': self.pr_data.title,
            'total_files': len(self.file_diffs),
            'total_additions': self.pr_data.additions,
            'total_deletions': self.pr_data.deletions,
            'review_units': len(self.review_units),
            'high_priority_units': len(self.high_priority_units),
            'languages': list(self.files_by_language.keys()),
            'strategies_available': ['per_file', 'per_hunk', 'smart']
        }


class PRReviewCoordinator:
    """
    Coordinate PR review workflow.
    
    This is the main entry point for Phase 2, combining:
    - PR fetching (Step 2.1)
    - Diff parsing into hunks (Step 2.2)
    - Review unit building (Step 2.3)
    """
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize coordinator.
        
        Args:
            github_token: GitHub API token
        """
        self.fetcher = PRFetcher(github_token)
    
    def prepare_pr_review(
        self,
        repo_full_name: str,
        pr_number: int,
        strategy: str = "per_hunk",
        max_hunk_size: int = 100,
        include_reviews: bool = False
    ) -> PRReviewSession:
        """
        Complete Phase 2 workflow: Fetch → Parse → Build Units.
        
        Args:
            repo_full_name: Repository in format "owner/repo"
            pr_number: PR number
            strategy: Review unit strategy ("per_file", "per_hunk", "smart")
            max_hunk_size: Maximum lines per hunk before splitting
            include_reviews: Whether to fetch existing review comments
        
        Returns:
            PRReviewSession with all data ready for Phase 3 (retrieval + review)
        """
        # Step 2.1: Fetch PR data
        print(f"Step 2.1: Fetching PR #{pr_number} from {repo_full_name}...")
        pr_data = self.fetcher.fetch_pr(
            repo_full_name,
            pr_number,
            include_reviews=include_reviews
        )
        print(f"  ✓ Fetched PR: {pr_data.title}")
        print(f"  ✓ Files changed: {pr_data.changed_files_count}")
        print(f"  ✓ Changes: +{pr_data.additions} -{pr_data.deletions}")
        
        # Step 2.2: Parse diffs into hunks
        print(f"\nStep 2.2: Parsing diffs into hunks...")
        file_diffs = []
        
        for pr_file in pr_data.files:
            if pr_file.patch:
                file_diff = DiffParser.parse_file_patch(pr_file.patch, pr_file.filename)
                file_diffs.append(file_diff)
            elif pr_file.status in ['added', 'removed']:
                # File added/removed without patch (might be binary or too large)
                file_diff = FileDiff(
                    old_path=pr_file.filename,
                    new_path=pr_file.filename,
                    is_new=pr_file.status == 'added',
                    is_deleted=pr_file.status == 'removed'
                )
                file_diffs.append(file_diff)
        
        total_hunks = sum(len(fd.hunks) for fd in file_diffs)
        print(f"  ✓ Parsed {len(file_diffs)} files")
        print(f"  ✓ Total hunks: {total_hunks}")
        
        # Step 2.3: Build review units
        print(f"\nStep 2.3: Building review units (strategy: {strategy})...")
        builder = ReviewUnitBuilder(pr_data, file_diffs)
        review_units = builder.build_all_units(
            strategy=strategy,
            max_hunk_size=max_hunk_size
        )
        
        high_priority = len([u for u in review_units if u.priority == 1])
        print(f"  ✓ Created {len(review_units)} review units")
        print(f"  ✓ High priority: {high_priority}")
        
        # Create session
        session = PRReviewSession(
            pr_data=pr_data,
            file_diffs=file_diffs,
            review_units=review_units
        )
        
        print(f"\n✓ Phase 2 complete - Ready for review!")
        
        return session
    
    def get_file_content_at_base(
        self,
        session: PRReviewSession,
        file_path: str
    ) -> str:
        """
        Get file content at base commit (before changes).
        
        Useful for providing full context during review.
        """
        return self.fetcher.fetch_file_content(
            session.pr_data.repo_full_name,
            file_path,
            session.pr_data.base_sha
        )
    
    def get_file_content_at_head(
        self,
        session: PRReviewSession,
        file_path: str
    ) -> str:
        """
        Get file content at head commit (after changes).
        
        Useful for providing full context during review.
        """
        return self.fetcher.fetch_file_content(
            session.pr_data.repo_full_name,
            file_path,
            session.pr_data.head_sha
        )
    
    def close(self):
        """Close the coordinator and cleanup resources."""
        self.fetcher.close()


def quick_prepare_review(
    repo_full_name: str,
    pr_number: int,
    github_token: Optional[str] = None,
    strategy: str = "per_hunk"
) -> PRReviewSession:
    """
    Quick helper function to prepare a PR review in one call.
    
    Args:
        repo_full_name: Repository in format "owner/repo"
        pr_number: PR number
        github_token: GitHub API token (uses env if not provided)
        strategy: Review unit strategy
    
    Returns:
        Complete PRReviewSession ready for review
    
    Example:
        >>> session = quick_prepare_review("owner/repo", 123)
        >>> for unit in session.high_priority_units:
        ...     print(f"Review: {unit.context.file_path}")
    """
    coordinator = PRReviewCoordinator(github_token)
    session = coordinator.prepare_pr_review(repo_full_name, pr_number, strategy=strategy)
    coordinator.close()
    return session
