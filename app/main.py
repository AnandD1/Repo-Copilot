"""Main entry point for Repo_Copilot ingestion."""

import sys
from pathlib import Path

from app.ingest.ingestor import RepositoryIngestor
from app.ingest.loader import LoadMethod
from config.settings import settings


def main():
    """
    Main entry point for repository ingestion.
    
    Usage:
        python -m app.main <github_repo_url>
    
    Example:
        python -m app.main https://github.com/openai/openai-python
    """
    if len(sys.argv) < 2:
        print("Usage: python -m app.main <github_repo_url>")
        print("\nExample:")
        print("  python -m app.main https://github.com/pallets/flask")
        return
    
    repo_url = sys.argv[1]
    
    # Optional: specify branch
    branch = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Create ingestor
    ingestor = RepositoryIngestor()
    
    try:
        # Ingest repository
        result = ingestor.ingest_repository(
            repo_url=repo_url,
            method=LoadMethod.API,  # Using API method (faster)
            branch=branch
        )
        
        # Show some insights
        print(f"\n{'='*60}")
        print(f"Additional Insights")
        print(f"{'='*60}\n")
        
        # Code files
        code_files = ingestor.get_code_files(result)
        print(f"Code files: {len(code_files)}")
        
        # Top languages
        print(f"\nTop 5 Languages:")
        for lang, count in list(result.language_stats.items())[:5]:
            print(f"  {lang}: {count} files")
        
        # Sample files
        print(f"\nSample files (first 10):")
        for file in result.filtered_files[:10]:
            lang = file.language or "Unknown"
            size_kb = file.size_bytes / 1024
            print(f"  [{lang}] {file.relative_path} ({size_kb:.1f} KB)")
        
        print(f"\n✓ Ingestion successful!")
        print(f"  Files stored at: {result.repo_info.local_path}")
        
        # Next steps message
        print(f"\n{'='*60}")
        print(f"Next Steps")
        print(f"{'='*60}")
        print(f"1. Files are ready for chunking")
        print(f"2. Use chunker to split files into manageable pieces")
        print(f"3. Generate embeddings for each chunk")
        print(f"4. Store embeddings in vector database")
        print(f"\nTo clean up: ingestor.cleanup(result)")
        
    except Exception as e:
        print(f"\n✗ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
