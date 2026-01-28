"""Local context retriever for same-file code context."""

import hashlib
from pathlib import Path
from typing import Optional

from ..pr_review.pr_fetcher import PRFetcher
from .evidence import Evidence, EvidenceType


class LocalContextRetriever:
    """Retrieves code context from the same file being reviewed.
    
    Caches file content by {commit_sha}:{file_path} to avoid repeated GitHub API calls.
    Handles new files (no base SHA) and deleted files (no head SHA) gracefully.
    """
    
    def __init__(self, pr_fetcher: PRFetcher):
        """Initialize retriever with PR fetcher for GitHub API access.
        
        Args:
            pr_fetcher: PRFetcher instance for accessing file content
        """
        self.pr_fetcher = pr_fetcher
        self._cache: dict[str, str] = {}  # {sha:path -> file_content}
    
    def _cache_key(self, sha: str, file_path: str) -> str:
        """Generate cache key for file content.
        
        Args:
            sha: Commit SHA
            file_path: File path relative to repo root
            
        Returns:
            Cache key string
        """
        return f"{sha}:{file_path}"
    
    def _get_file_content(
        self,
        owner: str,
        repo: str,
        file_path: str,
        sha: str,
    ) -> Optional[str]:
        """Get file content with caching.
        
        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            file_path: File path relative to repo root
            sha: Commit SHA
            
        Returns:
            File content as string, or None if file doesn't exist at that SHA
        """
        cache_key = self._cache_key(sha, file_path)
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Fetch from GitHub
        try:
            content = self.pr_fetcher.fetch_file_content(
                owner=owner,
                repo=repo,
                file_path=file_path,
                ref=sha,
            )
            self._cache[cache_key] = content
            return content
        except Exception:
            # File doesn't exist at this SHA (new or deleted file)
            return None
    
    def retrieve(
        self,
        owner: str,
        repo: str,
        file_path: str,
        head_sha: str,
        target_line: int,
        context_lines: int = 10,
    ) -> list[Evidence]:
        """Retrieve local context around a specific line.
        
        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            file_path: File path being reviewed
            head_sha: PR head commit SHA
            target_line: Line number to get context around (1-indexed)
            context_lines: Number of lines before and after target
            
        Returns:
            List with single Evidence object containing local context,
            or empty list if file doesn't exist or target_line is invalid
        """
        # Get file content
        content = self._get_file_content(owner, repo, file_path, head_sha)
        if content is None:
            return []
        
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Validate target line
        if target_line < 1 or target_line > total_lines:
            return []
        
        # Calculate line range (1-indexed, inclusive)
        start_line = max(1, target_line - context_lines)
        end_line = min(total_lines, target_line + context_lines)
        
        # Extract snippet (convert to 0-indexed for slicing)
        snippet_lines = lines[start_line - 1 : end_line]
        snippet_content = "\n".join(snippet_lines)
        
        # Generate snippet ID
        snippet_hash = hashlib.md5(snippet_content.encode()).hexdigest()[:8]
        snippet_id = f"local_{file_path.replace('/', '_')}_{start_line}_{snippet_hash}"
        
        evidence = Evidence(
            evidence_type=EvidenceType.LOCAL_CONTEXT,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=snippet_content,
            similarity_score=1.0,  # Perfect match (same file)
            snippet_id=snippet_id,
        )
        
        return [evidence]
    
    def clear_cache(self):
        """Clear file content cache."""
        self._cache.clear()
