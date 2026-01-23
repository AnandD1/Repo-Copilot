"""Configuration settings for Repo_Copilot."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # GitHub API
    github_token: Optional[str] = None
    
    # OpenAI API
    openai_api_key: Optional[str] = None
    
    # ChromaDB
    chroma_persist_directory: str = "./chroma_db"
    
    # Ingestion settings
    temp_clone_directory: str = "./temp_repos"
    max_file_size_kb: int = 1024  # Skip files larger than 1MB
    
    # File filtering patterns
    include_patterns: List[str] = [
        # Code directories
        "src/**",
        "app/**",
        "lib/**",
        "tests/**",
        "docs/**",
        
        # Root documentation & guides
        "README*",
        "CONTRIBUTING*",
        "STYLE_GUIDE*",
        "*.md",  # All markdown files in root
        
        # Dependency files
        "requirements*.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        
        # Configuration files
        ".ruff.toml",
        "ruff.toml",
        ".black",
        ".pylintrc",
        ".flake8",
        "tox.ini",
        ".editorconfig",
        ".prettierrc*",
        ".eslintrc*",
        "tsconfig.json",
        "Makefile",
        
        # CI/CD
        ".github/**/*.yml",
        ".github/**/*.yaml",
        ".gitlab-ci.yml",
        "Jenkinsfile",
    ]
    
    exclude_patterns: List[str] = [
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
        "**/.git/**",
        "**/venv/**",
        "**/env/**",
        "**/__pycache__/**",
        "**/*.min.js",
        "**/*.min.css",
        "**/coverage/**",
        "**/.next/**",
        "**/.nuxt/**",
        "**/target/**",  # Rust/Java build
        "**/.pytest_cache/**",
        "**/htmlcov/**",
    ]
    
    # Chunking settings
    chunk_size: int = 1000  # characters
    chunk_overlap: int = 200  # characters
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
