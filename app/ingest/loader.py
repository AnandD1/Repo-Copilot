"""Repository loader for fetching code from GitHub."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

import requests
from github import Github, Repository
from git import Repo as GitRepo

from config.settings import settings


class LoadMethod(Enum):
    """Method to use for loading repository."""
    CLONE = "clone"  # Git clone (for large repos or full history)
    API = "api"      # GitHub Contents API (faster, no git history)


@dataclass
class RepositoryInfo:
    """Information about a loaded repository."""
    owner: str
    name: str
    full_name: str
    default_branch: str
    url: str
    local_path: Path
    load_method: LoadMethod
    languages: Optional[Dict[str, int]] = None


class RepositoryLoader:
    """
    Loads repository content from GitHub.
    
    Supports two methods:
    1. Clone: Full git clone (includes history, larger download)
    2. API: GitHub Contents API (faster, no history, better for analysis)
    """
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the repository loader.
        
        Args:
            github_token: GitHub API token for authenticated requests (optional)
        """
        self.github_token = github_token or settings.github_token
        self.github_client = Github(self.github_token) if self.github_token else Github()
        self.temp_dir = Path(settings.temp_clone_directory)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def load_repository(
        self,
        repo_url: str,
        method: LoadMethod = LoadMethod.API,
        target_path: Optional[Path] = None,
        branch: Optional[str] = None
    ) -> RepositoryInfo:
        """
        Load a repository from GitHub.
        
        Args:
            repo_url: GitHub repository URL (e.g., "https://github.com/owner/repo")
            method: Method to use for loading (CLONE or API)
            target_path: Target directory path (if None, uses temp directory)
            branch: Specific branch to load (if None, uses default branch)
        
        Returns:
            RepositoryInfo object with repository metadata and local path
        
        Raises:
            ValueError: If repository URL is invalid
            Exception: If loading fails
        """
        owner, repo_name = self._parse_repo_url(repo_url)
        
        # Get repository metadata from GitHub API
        repo = self.github_client.get_repo(f"{owner}/{repo_name}")
        branch = branch or repo.default_branch
        
        # Determine local path
        if target_path is None:
            target_path = self.temp_dir / f"{owner}_{repo_name}"
        else:
            target_path = Path(target_path)
        
        # Clean existing directory if it exists
        if target_path.exists():
            shutil.rmtree(target_path)
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Load repository using selected method
        if method == LoadMethod.CLONE:
            self._clone_repository(repo.clone_url, target_path, branch)
        else:  # LoadMethod.API
            self._download_via_api(repo, target_path, branch)
        
        # Get language statistics
        languages = repo.get_languages()
        
        return RepositoryInfo(
            owner=owner,
            name=repo_name,
            full_name=repo.full_name,
            default_branch=repo.default_branch,
            url=repo.html_url,
            local_path=target_path,
            load_method=method,
            languages=languages
        )
    
    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        Parse GitHub repository URL to extract owner and repo name.
        
        Args:
            repo_url: GitHub repository URL
        
        Returns:
            Tuple of (owner, repo_name)
        
        Raises:
            ValueError: If URL format is invalid
        """
        # Handle different URL formats:
        # - https://github.com/owner/repo
        # - github.com/owner/repo
        # - owner/repo
        
        repo_url = repo_url.strip().rstrip('/')
        
        if repo_url.startswith('http://') or repo_url.startswith('https://'):
            # Extract from full URL
            parts = repo_url.split('github.com/')[-1].split('/')
        else:
            # Handle "owner/repo" format
            parts = repo_url.split('/')
        
        if len(parts) >= 2:
            owner = parts[-2]
            repo_name = parts[-1].replace('.git', '')
            return owner, repo_name
        
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
    
    def _clone_repository(self, clone_url: str, target_path: Path, branch: str) -> None:
        """
        Clone repository using git.
        
        Args:
            clone_url: Git clone URL
            target_path: Local directory to clone into
            branch: Branch to checkout
        """
        print(f"Cloning repository to {target_path}...")
        
        # Clone with depth=1 for faster download (shallow clone)
        GitRepo.clone_from(
            clone_url,
            target_path,
            branch=branch,
            depth=1,
            single_branch=True
        )
        
        print(f"✓ Repository cloned successfully")
    
    def _download_via_api(
        self,
        repo: Repository.Repository,
        target_path: Path,
        branch: str
    ) -> None:
        """
        Download repository contents using GitHub Contents API.
        
        This method recursively downloads all files from the repository.
        It's faster than cloning and doesn't include git history.
        
        Args:
            repo: PyGithub Repository object
            target_path: Local directory to download into
            branch: Branch to download from
        """
        print(f"Downloading repository via GitHub API to {target_path}...")
        
        def download_contents(contents, current_path: Path):
            """Recursively download repository contents."""
            for content in contents:
                local_file_path = current_path / content.name
                
                if content.type == "dir":
                    # Create directory and recurse
                    local_file_path.mkdir(parents=True, exist_ok=True)
                    dir_contents = repo.get_contents(content.path, ref=branch)
                    download_contents(dir_contents, local_file_path)
                else:
                    # Download file
                    try:
                        file_content = repo.get_contents(content.path, ref=branch)
                        
                        # Handle binary files
                        if file_content.encoding == "base64":
                            import base64
                            decoded_content = base64.b64decode(file_content.content)
                            local_file_path.write_bytes(decoded_content)
                        else:
                            # Text file
                            local_file_path.write_text(
                                file_content.decoded_content.decode('utf-8'),
                                encoding='utf-8'
                            )
                    except Exception as e:
                        print(f"Warning: Could not download {content.path}: {e}")
        
        # Start recursive download from root
        root_contents = repo.get_contents("", ref=branch)
        download_contents(root_contents, target_path)
        
        print(f"✓ Repository downloaded successfully")
    
    def cleanup(self, repo_info: RepositoryInfo) -> None:
        """
        Clean up downloaded repository files.
        
        Args:
            repo_info: Repository information with local path
        """
        if repo_info.local_path.exists():
            shutil.rmtree(repo_info.local_path)
            print(f"✓ Cleaned up {repo_info.local_path}")
    
    def list_files(self, repo_info: RepositoryInfo) -> List[Path]:
        """
        List all files in the loaded repository.
        
        Args:
            repo_info: Repository information with local path
        
        Returns:
            List of file paths
        """
        files = []
        for file_path in repo_info.local_path.rglob('*'):
            if file_path.is_file():
                files.append(file_path)
        return files


def main():
    """Example usage of RepositoryLoader."""
    # Example: Load a repository
    loader = RepositoryLoader()
    
    # Using API method (faster, recommended for analysis)
    repo_info = loader.load_repository(
        repo_url="https://github.com/openai/openai-python",
        method=LoadMethod.API
    )
    
    print(f"\n✓ Loaded repository: {repo_info.full_name}")
    print(f"  Branch: {repo_info.default_branch}")
    print(f"  Local path: {repo_info.local_path}")
    print(f"  Languages: {repo_info.languages}")
    
    # List files
    files = loader.list_files(repo_info)
    print(f"  Total files: {len(files)}")
    print(f"\n  First 10 files:")
    for file in files[:10]:
        print(f"    - {file.relative_to(repo_info.local_path)}")
    
    # Cleanup when done
    # loader.cleanup(repo_info)


if __name__ == "__main__":
    main()
