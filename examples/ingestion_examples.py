"""Example script demonstrating repository ingestion."""

from app.ingest.ingestor import RepositoryIngestor
from app.ingest.loader import LoadMethod


def example_basic_ingestion():
    """Basic repository ingestion example."""
    print("="*70)
    print("Example 1: Basic Repository Ingestion")
    print("="*70)
    
    # Create ingestor
    ingestor = RepositoryIngestor()
    
    # Ingest a small repository
    result = ingestor.ingest_repository(
        repo_url="https://github.com/pallets/flask",
        method=LoadMethod.API
    )
    
    print(f"\n✓ Successfully ingested {result.total_files} files")
    
    # Don't forget to cleanup
    # ingestor.cleanup(result)
    
    return result


def example_filter_by_language():
    """Example showing how to filter files by language."""
    print("\n" + "="*70)
    print("Example 2: Filter Files by Language")
    print("="*70)
    
    ingestor = RepositoryIngestor()
    
    result = ingestor.ingest_repository(
        repo_url="https://github.com/django/django",
        method=LoadMethod.API
    )
    
    # Get Python files only
    python_files = ingestor.get_files_by_language(result, "Python")
    
    print(f"\n✓ Found {len(python_files)} Python files")
    print(f"\n  Sample Python files:")
    for file in python_files[:5]:
        print(f"    - {file.relative_path}")
    
    return result


def example_code_files_only():
    """Example showing how to get only code files."""
    print("\n" + "="*70)
    print("Example 3: Code Files Only")
    print("="*70)
    
    ingestor = RepositoryIngestor()
    
    result = ingestor.ingest_repository(
        repo_url="https://github.com/fastapi/fastapi",
        method=LoadMethod.API
    )
    
    # Get only code files (exclude docs, config, etc.)
    code_files = ingestor.get_code_files(result)
    
    print(f"\n✓ Total files: {result.total_files}")
    print(f"✓ Code files: {len(code_files)}")
    print(f"✓ Percentage: {len(code_files)/result.total_files*100:.1f}%")
    
    return result


def example_custom_patterns():
    """Example with custom include/exclude patterns."""
    print("\n" + "="*70)
    print("Example 4: Custom File Patterns")
    print("="*70)
    
    # Create ingestor with custom patterns
    ingestor = RepositoryIngestor(
        include_patterns=["src/**/*.py", "tests/**/*.py"],  # Python files only
        exclude_patterns=["**/test_*.py"]  # Exclude test files
    )
    
    result = ingestor.ingest_repository(
        repo_url="https://github.com/psf/requests",
        method=LoadMethod.API
    )
    
    print(f"\n✓ Filtered to {result.total_files} files with custom patterns")
    
    return result


def main():
    """Run all examples."""
    print("\n" + "🚀"*35)
    print("Repo_Copilot - Repository Ingestion Examples")
    print("🚀"*35 + "\n")
    
    # Run examples (commented out to avoid actually downloading)
    # Uncomment the ones you want to try
    
    # Example 1: Basic ingestion
    # result1 = example_basic_ingestion()
    
    # Example 2: Filter by language
    # result2 = example_filter_by_language()
    
    # Example 3: Code files only
    # result3 = example_code_files_only()
    
    # Example 4: Custom patterns
    # result4 = example_custom_patterns()
    
    print("\n" + "="*70)
    print("Examples Complete!")
    print("="*70)
    print("\nTo run these examples, uncomment the function calls in main()")
    print("Note: Make sure you have set your GITHUB_TOKEN in .env for higher rate limits")


if __name__ == "__main__":
    main()
