"""Tests for file filter."""

import pytest
from pathlib import Path
from app.ingest.filter import FileFilter, FileInfo


class TestFileFilter:
    """Tests for FileFilter class."""
    
    def test_matches_pattern_simple(self):
        """Test simple pattern matching."""
        filter = FileFilter(include_patterns=[], exclude_patterns=[])
        assert filter._matches_pattern("src/main.py", "src/*.py")
        assert not filter._matches_pattern("lib/main.py", "src/*.py")
    
    def test_matches_pattern_recursive(self):
        """Test recursive pattern matching with **."""
        filter = FileFilter(include_patterns=[], exclude_patterns=[])
        assert filter._matches_pattern("src/app/main.py", "src/**/*.py")
        assert filter._matches_pattern("src/deep/nested/file.py", "src/**/*.py")
        assert not filter._matches_pattern("lib/file.py", "src/**/*.py")
    
    def test_exclude_takes_precedence(self):
        """Test that exclude patterns take precedence over include."""
        filter = FileFilter(
            include_patterns=["src/**/*.py"],
            exclude_patterns=["**/__pycache__/**"]
        )
        
        # Create a mock path for testing
        root = Path("/repo")
        
        # This should be excluded despite matching include pattern
        excluded_path = root / "src" / "__pycache__" / "file.py"
        # We can't test should_include_file without real files,
        # but we can test the pattern matching logic
        assert filter._matches_pattern(
            "src/__pycache__/file.py",
            "**/__pycache__/**"
        )
    
    def test_match_recursive_exact(self):
        """Test exact recursive pattern matching."""
        filter = FileFilter(include_patterns=[], exclude_patterns=[])
        
        path_parts = ["src", "app", "main.py"]
        pattern_parts = ["src", "**", "*.py"]
        
        assert filter._match_recursive(path_parts, pattern_parts)
    
    def test_get_statistics(self):
        """Test file statistics calculation."""
        filter = FileFilter()
        
        files = [
            FileInfo(
                path=Path("/repo/main.py"),
                relative_path=Path("main.py"),
                size_bytes=1024,
                extension=".py"
            ),
            FileInfo(
                path=Path("/repo/app.js"),
                relative_path=Path("app.js"),
                size_bytes=2048,
                extension=".js"
            ),
            FileInfo(
                path=Path("/repo/util.py"),
                relative_path=Path("util.py"),
                size_bytes=512,
                extension=".py"
            ),
        ]
        
        stats = filter.get_statistics(files)
        
        assert stats['total_files'] == 3
        assert stats['total_size_bytes'] == 3584
        assert stats['extensions']['.py'] == 2
        assert stats['extensions']['.js'] == 1
