"""File filtering for repository ingestion."""

import fnmatch
from pathlib import Path
from typing import List, Set, Optional
from dataclasses import dataclass

from config.settings import settings


@dataclass
class FileInfo:
    """Information about a filtered file."""
    path: Path
    relative_path: Path
    size_bytes: int
    extension: str
    language: Optional[str] = None


class FileFilter:
    """
    Filters repository files based on include/exclude patterns.
    
    Supports glob patterns for flexible file selection.
    """
    
    def __init__(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_file_size_kb: Optional[int] = None
    ):
        """
        Initialize file filter.
        
        Args:
            include_patterns: List of glob patterns to include
            exclude_patterns: List of glob patterns to exclude
            max_file_size_kb: Maximum file size in KB (files larger are skipped)
        """
        self.include_patterns = include_patterns or settings.include_patterns
        self.exclude_patterns = exclude_patterns or settings.exclude_patterns
        self.max_file_size_bytes = (max_file_size_kb or settings.max_file_size_kb) * 1024
    
    def should_include_file(self, file_path: Path, root_path: Path) -> bool:
        """
        Determine if a file should be included based on patterns.
        
        Args:
            file_path: Absolute path to the file
            root_path: Root path of the repository
        
        Returns:
            True if file should be included, False otherwise
        """
        if not file_path.is_file():
            return False
        
        # Get relative path for pattern matching
        try:
            relative_path = file_path.relative_to(root_path)
        except ValueError:
            return False
        
        relative_path_str = str(relative_path).replace('\\', '/')
        
        # Check file size
        try:
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size_bytes:
                return False
        except OSError:
            return False
        
        # Check exclude patterns first (takes precedence)
        for pattern in self.exclude_patterns:
            if self._matches_pattern(relative_path_str, pattern):
                return False
        
        # If no include patterns specified, include all (except excluded)
        if not self.include_patterns:
            return True
        
        # Check include patterns
        for pattern in self.include_patterns:
            if self._matches_pattern(relative_path_str, pattern):
                return True
        
        return False
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if path matches a glob pattern.
        
        Supports ** for recursive matching.
        
        Args:
            path: File path to check
            pattern: Glob pattern
        
        Returns:
            True if path matches pattern
        """
        # Handle ** patterns for recursive matching
        if '**' in pattern:
            # Convert ** to * for fnmatch
            pattern_parts = pattern.split('/')
            path_parts = path.split('/')
            
            # Try to match pattern with path
            return self._match_recursive(path_parts, pattern_parts)
        else:
            return fnmatch.fnmatch(path, pattern)
    
    def _match_recursive(self, path_parts: List[str], pattern_parts: List[str]) -> bool:
        """
        Match path against pattern with ** support.
        
        Args:
            path_parts: Parts of the path split by /
            pattern_parts: Parts of the pattern split by /
        
        Returns:
            True if matches
        """
        while pattern_parts:
            if not path_parts:
                return False
            
            pattern_part = pattern_parts[0]
            
            if pattern_part == '**':
                # ** matches zero or more path segments
                if len(pattern_parts) == 1:
                    return True
                
                # Try matching the rest of the pattern at different positions
                for i in range(len(path_parts)):
                    if self._match_recursive(path_parts[i:], pattern_parts[1:]):
                        return True
                return False
            else:
                # Regular pattern matching
                if not fnmatch.fnmatch(path_parts[0], pattern_part):
                    return False
                path_parts = path_parts[1:]
                pattern_parts = pattern_parts[1:]
        
        return len(path_parts) == 0
    
    def filter_files(self, root_path: Path) -> List[FileInfo]:
        """
        Filter all files in a directory tree.
        
        Args:
            root_path: Root directory to filter
        
        Returns:
            List of FileInfo objects for included files
        """
        filtered_files = []
        
        for file_path in root_path.rglob('*'):
            if self.should_include_file(file_path, root_path):
                try:
                    relative_path = file_path.relative_to(root_path)
                    size_bytes = file_path.stat().st_size
                    extension = file_path.suffix.lower()
                    
                    file_info = FileInfo(
                        path=file_path,
                        relative_path=relative_path,
                        size_bytes=size_bytes,
                        extension=extension
                    )
                    filtered_files.append(file_info)
                except (OSError, ValueError) as e:
                    print(f"Warning: Could not process {file_path}: {e}")
        
        return filtered_files
    
    def get_statistics(self, files: List[FileInfo]) -> dict:
        """
        Get statistics about filtered files.
        
        Args:
            files: List of FileInfo objects
        
        Returns:
            Dictionary with statistics
        """
        total_size = sum(f.size_bytes for f in files)
        extensions = {}
        
        for file in files:
            ext = file.extension or 'no_extension'
            extensions[ext] = extensions.get(ext, 0) + 1
        
        return {
            'total_files': len(files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'extensions': dict(sorted(extensions.items(), key=lambda x: x[1], reverse=True))
        }


def main():
    """Example usage of FileFilter."""
    from pathlib import Path
    
    # Example: Filter files in a repository
    repo_path = Path("./temp_repos/some_repo")
    
    filter = FileFilter()
    files = filter.filter_files(repo_path)
    
    print(f"\n✓ Filtered {len(files)} files")
    
    stats = filter.get_statistics(files)
    print(f"\nStatistics:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Total size: {stats['total_size_mb']} MB")
    print(f"\n  Files by extension:")
    for ext, count in list(stats['extensions'].items())[:10]:
        print(f"    {ext}: {count}")
    
    print(f"\n  Sample files:")
    for file in files[:10]:
        print(f"    - {file.relative_path} ({file.size_bytes} bytes)")


if __name__ == "__main__":
    main()
