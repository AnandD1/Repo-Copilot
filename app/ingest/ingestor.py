"""Main ingestion orchestrator."""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from app.ingest.loader import RepositoryLoader, LoadMethod, RepositoryInfo
from app.ingest.filter import FileFilter, FileInfo
from app.ingest.language_detector import LanguageDetector
from config.settings import settings


@dataclass
class IngestionResult:
    """Result of repository ingestion."""
    repo_info: RepositoryInfo
    filtered_files: List[FileInfo]
    total_files: int
    total_size_mb: float
    language_stats: dict
    
    def __str__(self):
        """String representation of ingestion result."""
        return f"""
Ingestion Result:
  Repository: {self.repo_info.full_name}
  Branch: {self.repo_info.default_branch}
  Local Path: {self.repo_info.local_path}
  
  Files Processed:
    Total files: {self.total_files}
    Total size: {self.total_size_mb} MB
  
  Languages Detected:
{self._format_languages()}
        """.strip()
    
    def _format_languages(self) -> str:
        """Format language statistics."""
        lines = []
        for lang, count in list(self.language_stats.items())[:10]:
            lines.append(f"    {lang}: {count} file(s)")
        return "\n".join(lines)


class RepositoryIngestor:
    """
    Main orchestrator for repository ingestion.
    
    Coordinates loading, filtering, and language detection.
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        Initialize the repository ingestor.
        
        Args:
            github_token: GitHub API token
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude
        """
        self.loader = RepositoryLoader(github_token=github_token)
        self.file_filter = FileFilter(
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns
        )
        self.language_detector = LanguageDetector()
    
    def ingest_repository(
        self,
        repo_url: str,
        method: LoadMethod = LoadMethod.API,
        branch: Optional[str] = None
    ) -> IngestionResult:
        """
        Ingest a complete repository.
        
        This method:
        1. Loads the repository from GitHub
        2. Filters files based on patterns
        3. Detects programming languages
        4. Returns a complete ingestion result
        
        Args:
            repo_url: GitHub repository URL
            method: Load method (API or CLONE)
            branch: Specific branch to ingest
        
        Returns:
            IngestionResult with all processed data
        """
        print(f"\n{'='*60}")
        print(f"Starting Repository Ingestion")
        print(f"{'='*60}\n")
        
        # Step 1: Load repository
        print("Step 1: Loading repository...")
        repo_info = self.loader.load_repository(
            repo_url=repo_url,
            method=method,
            branch=branch
        )
        print(f"✓ Repository loaded: {repo_info.full_name}")
        
        # Step 2: Filter files
        print(f"\nStep 2: Filtering files...")
        filtered_files = self.file_filter.filter_files(repo_info.local_path)
        print(f"✓ Filtered {len(filtered_files)} files")
        
        # Step 3: Detect languages
        print(f"\nStep 3: Detecting languages...")
        for file_info in filtered_files:
            lang_id = self.language_detector.detect_language(file_info.path)
            if lang_id:
                lang_info = self.language_detector.get_language_info(lang_id)
                file_info.language = lang_info.name if lang_info else None
        
        # Get statistics
        stats = self.file_filter.get_statistics(filtered_files)
        language_stats = self.language_detector.get_language_statistics(
            [f.path for f in filtered_files]
        )
        print(f"✓ Detected {len(language_stats)} languages")
        
        # Create result
        result = IngestionResult(
            repo_info=repo_info,
            filtered_files=filtered_files,
            total_files=stats['total_files'],
            total_size_mb=stats['total_size_mb'],
            language_stats=language_stats
        )
        
        print(f"\n{'='*60}")
        print(f"Ingestion Complete!")
        print(f"{'='*60}\n")
        print(result)
        
        return result
    
    def cleanup(self, result: IngestionResult) -> None:
        """
        Clean up downloaded repository.
        
        Args:
            result: Ingestion result with repository info
        """
        self.loader.cleanup(result.repo_info)
    
    def get_code_files(self, result: IngestionResult) -> List[FileInfo]:
        """
        Get only code files (programming languages) from ingestion result.
        
        Args:
            result: Ingestion result
        
        Returns:
            List of code files
        """
        return [
            f for f in result.filtered_files
            if self.language_detector.is_code_file(f.path)
        ]
    
    def get_files_by_language(
        self,
        result: IngestionResult,
        language: str
    ) -> List[FileInfo]:
        """
        Get files of a specific language.
        
        Args:
            result: Ingestion result
            language: Language name (e.g., 'Python', 'JavaScript')
        
        Returns:
            List of files in that language
        """
        return [
            f for f in result.filtered_files
            if f.language == language
        ]


def main():
    """Example usage of RepositoryIngestor."""
    # Initialize ingestor
    ingestor = RepositoryIngestor()
    
    # Ingest a repository
    result = ingestor.ingest_repository(
        repo_url="https://github.com/pallets/flask",
        method=LoadMethod.API
    )
    
    # Get code files only
    code_files = ingestor.get_code_files(result)
    print(f"\n✓ Code files: {len(code_files)}")
    
    # Show sample Python files
    python_files = ingestor.get_files_by_language(result, "Python")
    print(f"\n✓ Python files: {len(python_files)}")
    print(f"\n  Sample Python files:")
    for file in python_files[:10]:
        print(f"    - {file.relative_path}")
    
    # Note: Remember to cleanup when done
    # ingestor.cleanup(result)


if __name__ == "__main__":
    main()
