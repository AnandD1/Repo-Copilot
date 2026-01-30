"""Configuration settings for Repo_Copilot."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # GitHub API
    github_token: Optional[str] = None
    
    # Legacy Google Gemini API (no longer used, kept for backward compatibility)
    google_api_key: Optional[str] = None
    
    # Slack Notifications (Phase 6)
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_enabled: bool = True
    
    # Qdrant Vector Database
    qdrant_url: str = "http://localhost:6333"  # Qdrant server URL
    qdrant_api_key: Optional[str] = None  # Optional for cloud Qdrant
    qdrant_collection_name: str = "code_embeddings"  # Collection name
    
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
    
    # Chunking settings - Code files
    code_chunk_target_tokens: int = 900
    code_chunk_max_tokens: int = 1200
    code_chunk_overlap_tokens: int = 120
    
    # Chunking settings - Markdown/Docs
    doc_chunk_target_tokens: int = 1100
    doc_chunk_max_tokens: int = 1500
    doc_chunk_overlap_tokens: int = 150
    
    # Chunking settings - Config files
    config_chunk_target_tokens: int = 700
    config_chunk_max_tokens: int = 1000
    config_chunk_overlap_tokens: int = 80
    config_whole_file_max_tokens: int = 1200
    
    # Embedding settings
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimension: int = 1024  # BGE-large dimension
    embedding_device: str = "cpu"  # "cpu" or "cuda" for GPU acceleration
    embedding_normalize: bool = True  # Normalize embeddings for cosine similarity
    
    # Ollama LLM settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b-instruct"
    ollama_temperature: float = 0.1  # Low temperature for code review
    
    # HITL (Human-in-the-Loop) settings
    hitl_base_url: str = "http://localhost:8000"  # Base URL for HITL web interface
    
    # Notification settings (Phase 6)
    notification_enabled: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
