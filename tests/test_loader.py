"""Tests for repository loader."""

import pytest
from pathlib import Path
from app.ingest.loader import RepositoryLoader, LoadMethod


class TestRepositoryLoader:
    """Tests for RepositoryLoader class."""
    
    def test_parse_repo_url_full_https(self):
        """Test parsing full HTTPS URL."""
        loader = RepositoryLoader()
        owner, repo = loader._parse_repo_url("https://github.com/openai/openai-python")
        assert owner == "openai"
        assert repo == "openai-python"
    
    def test_parse_repo_url_short_format(self):
        """Test parsing short format (owner/repo)."""
        loader = RepositoryLoader()
        owner, repo = loader._parse_repo_url("pallets/flask")
        assert owner == "pallets"
        assert repo == "flask"
    
    def test_parse_repo_url_with_git_extension(self):
        """Test parsing URL with .git extension."""
        loader = RepositoryLoader()
        owner, repo = loader._parse_repo_url("https://github.com/django/django.git")
        assert owner == "django"
        assert repo == "django"
    
    def test_parse_repo_url_invalid(self):
        """Test parsing invalid URL raises error."""
        loader = RepositoryLoader()
        with pytest.raises(ValueError):
            loader._parse_repo_url("invalid-url")
    
    def test_parse_repo_url_http(self):
        """Test parsing HTTP URL."""
        loader = RepositoryLoader()
        owner, repo = loader._parse_repo_url("http://github.com/user/project")
        assert owner == "user"
        assert repo == "project"
