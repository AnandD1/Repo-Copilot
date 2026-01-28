"""Fetch pull request data from GitHub API."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from config.settings import settings


@dataclass
class PRFile:
    """Represents a file changed in a PR."""
    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str]  # Unified diff patch
    previous_filename: Optional[str] = None  # For renamed files
    sha: Optional[str] = None
    blob_url: Optional[str] = None
    raw_url: Optional[str] = None


@dataclass
class PRData:
    """Complete pull request data."""
    # Basic info
    number: int
    title: str
    description: str
    state: str  # open, closed, merged
    
    # Author info
    author: str
    author_association: str
    
    # Branch info
    base_branch: str
    head_branch: str
    base_sha: str
    head_sha: str
    
    # Repository info
    repo_owner: str
    repo_name: str
    repo_full_name: str
    
    # Timing
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Changes
    files: List[PRFile] = None
    commits_count: int = 0
    changed_files_count: int = 0
    additions: int = 0
    deletions: int = 0
    
    # Labels and reviewers
    labels: List[str] = None
    requested_reviewers: List[str] = None
    reviews: List[Dict[str, Any]] = None
    
    # URLs
    html_url: str = None
    diff_url: str = None
    patch_url: str = None
    
    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.labels is None:
            self.labels = []
        if self.requested_reviewers is None:
            self.requested_reviewers = []
        if self.reviews is None:
            self.reviews = []


class PRFetcher:
    """Fetch pull request data from GitHub."""
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize PR fetcher.
        
        Args:
            github_token: GitHub API token (uses settings if not provided)
        """
        self.github_token = github_token or settings.github_token
        
        if not self.github_token:
            raise ValueError("GitHub token required. Set GITHUB_TOKEN in .env file")
        
        self.github = Github(self.github_token)
    
    def fetch_pr(
        self,
        repo_full_name: str,
        pr_number: int,
        include_reviews: bool = False
    ) -> PRData:
        """
        Fetch complete PR data.
        
        Args:
            repo_full_name: Repository in format "owner/repo"
            pr_number: PR number
            include_reviews: Whether to fetch review comments
        
        Returns:
            PRData object with all PR information
        """
        repo = self.github.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # Extract repo owner and name
        owner, name = repo_full_name.split('/')
        
        # Fetch files
        files = self._fetch_files(pr)
        
        # Fetch reviews if requested
        reviews = []
        if include_reviews:
            reviews = self._fetch_reviews(pr)
        
        # Build PRData
        pr_data = PRData(
            number=pr.number,
            title=pr.title,
            description=pr.body or "",
            state=pr.state,
            author=pr.user.login,
            author_association=pr.author_association,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            base_sha=pr.base.sha,
            head_sha=pr.head.sha,
            repo_owner=owner,
            repo_name=name,
            repo_full_name=repo_full_name,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
            files=files,
            commits_count=pr.commits,
            changed_files_count=pr.changed_files,
            additions=pr.additions,
            deletions=pr.deletions,
            labels=[label.name for label in pr.labels],
            requested_reviewers=[reviewer.login for reviewer in pr.requested_reviewers],
            reviews=reviews,
            html_url=pr.html_url,
            diff_url=pr.diff_url,
            patch_url=pr.patch_url
        )
        
        return pr_data
    
    def _fetch_files(self, pr: PullRequest) -> List[PRFile]:
        """Fetch all changed files in the PR."""
        files = []
        
        for file in pr.get_files():
            pr_file = PRFile(
                filename=file.filename,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                changes=file.changes,
                patch=file.patch,
                previous_filename=file.previous_filename,
                sha=file.sha,
                blob_url=file.blob_url,
                raw_url=file.raw_url
            )
            files.append(pr_file)
        
        return files
    
    def _fetch_reviews(self, pr: PullRequest) -> List[Dict[str, Any]]:
        """Fetch all review comments."""
        reviews = []
        
        # Get review comments
        for review in pr.get_reviews():
            review_data = {
                'id': review.id,
                'user': review.user.login,
                'state': review.state,  # APPROVED, CHANGES_REQUESTED, COMMENTED
                'body': review.body,
                'submitted_at': review.submitted_at,
            }
            reviews.append(review_data)
        
        # Get inline comments
        for comment in pr.get_review_comments():
            comment_data = {
                'id': comment.id,
                'user': comment.user.login,
                'path': comment.path,
                'position': comment.position,
                'original_position': comment.original_position,
                'line': comment.line,
                'original_line': comment.original_line,
                'body': comment.body,
                'created_at': comment.created_at,
                'in_reply_to_id': comment.in_reply_to_id,
            }
            reviews.append(comment_data)
        
        return reviews
    
    def fetch_file_content(
        self,
        repo_full_name: str,
        file_path: str,
        ref: str
    ) -> str:
        """
        Fetch content of a specific file at a specific commit.
        
        Args:
            repo_full_name: Repository in format "owner/repo"
            file_path: Path to file in repo
            ref: Git reference (SHA, branch, tag)
        
        Returns:
            File content as string
        """
        repo = self.github.get_repo(repo_full_name)
        
        try:
            file_content = repo.get_contents(file_path, ref=ref)
            return file_content.decoded_content.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Could not fetch file {file_path} at {ref}: {e}")
    
    def fetch_pr_diff(
        self,
        repo_full_name: str,
        pr_number: int
    ) -> str:
        """
        Fetch the complete unified diff for a PR.
        
        Args:
            repo_full_name: Repository in format "owner/repo"
            pr_number: PR number
        
        Returns:
            Complete unified diff as string
        """
        repo = self.github.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # Fetch the diff URL content
        import requests
        response = requests.get(
            pr.diff_url,
            headers={'Authorization': f'token {self.github_token}'}
        )
        response.raise_for_status()
        
        return response.text
    
    def close(self):
        """Close the GitHub client."""
        self.github.close()
