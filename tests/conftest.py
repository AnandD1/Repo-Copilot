"""Test configuration."""

import pytest


@pytest.fixture
def sample_repo_path(tmp_path):
    """Create a sample repository structure for testing."""
    repo_path = tmp_path / "sample_repo"
    repo_path.mkdir()
    
    # Create directory structure
    (repo_path / "src").mkdir()
    (repo_path / "src" / "app").mkdir()
    (repo_path / "tests").mkdir()
    (repo_path / "node_modules").mkdir()
    
    # Create sample files
    (repo_path / "src" / "main.py").write_text("print('hello')")
    (repo_path / "src" / "app" / "utils.py").write_text("def util(): pass")
    (repo_path / "tests" / "test_main.py").write_text("def test(): pass")
    (repo_path / "node_modules" / "package.json").write_text("{}")
    (repo_path / "README.md").write_text("# Readme")
    
    return repo_path
