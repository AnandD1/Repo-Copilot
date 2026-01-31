"""Ingest package for repository ingestion."""

from .ingestor import RepositoryIngestor, IngestionResult
from .loader import LoadMethod
from .quick_ingest import quick_ingest_repo

__all__ = [
    "RepositoryIngestor",
    "IngestionResult", 
    "LoadMethod",
    "quick_ingest_repo"
]
