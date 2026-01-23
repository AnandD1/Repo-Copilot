"""Test script for ingesting a real GitHub repository."""

from app.ingest.ingestor import RepositoryIngestor
from app.ingest.loader import LoadMethod


def test_my_repo():
    """Test ingestion with your actual GitHub repository."""
    
    # REPLACE WITH YOUR REPO URL
    REPO_URL = "https://github.com/AnandD1/ScratchYOLO.git"
    
    print("\n" + "="*70)
    print("TESTING REPOSITORY INGESTION")
    print("="*70)
    print(f"\nRepository: {REPO_URL}")
    print("\nStarting ingestion...\n")
    
    # Create ingestor
    ingestor = RepositoryIngestor()
    
    try:
        # Ingest repository (using API method - faster)
        result = ingestor.ingest_repository(
            repo_url=REPO_URL,
            method=LoadMethod.API
        )
        
        # Display results
        print("\n" + "="*70)
        print("INGESTION RESULTS")
        print("="*70)
        
        print(f"\nRepository Info:")
        print(f"  Name: {result.repo_info.full_name}")
        print(f"  Branch: {result.repo_info.default_branch}")
        print(f"  URL: {result.repo_info.url}")
        print(f"  Local Path: {result.repo_info.local_path}")
        
        print(f"\nFile Statistics:")
        print(f"  Total Files: {result.total_files}")
        print(f"  Total Size: {result.total_size_mb} MB")
        
        print(f"\nLanguages Detected:")
        for lang, count in result.language_stats.items():
            print(f"  {lang}: {count} file(s)")
        
        # Get code files only
        code_files = ingestor.get_code_files(result)
        print(f"\nCode Files (programming languages only): {len(code_files)}")
        
        # Show first 20 files
        print(f"\nFirst 20 Files:")
        for i, file in enumerate(result.filtered_files[:20], 1):
            lang = file.language or "Unknown"
            size_kb = file.size_bytes / 1024
            print(f"  {i:2}. [{lang:12}] {file.relative_path} ({size_kb:.1f} KB)")
        
        if len(result.filtered_files) > 20:
            print(f"  ... and {len(result.filtered_files) - 20} more files")
        
        # Test filtering by language
        if result.language_stats:
            top_language = list(result.language_stats.keys())[0]
            lang_files = ingestor.get_files_by_language(result, top_language)
            print(f"\n{top_language} Files: {len(lang_files)}")
            for file in lang_files[:5]:
                print(f"  - {file.relative_path}")
            if len(lang_files) > 5:
                print(f"  ... and {len(lang_files) - 5} more")
        
        print("\n" + "="*70)
        print("✅ INGESTION TEST SUCCESSFUL!")
        print("="*70)
        
        print(f"\n📁 Files downloaded to: {result.repo_info.local_path}")
        print(f"\n💡 Tip: Check the 'temp_repos' folder to see all downloaded files")
        
        # Ask about cleanup
        print("\n" + "="*70)
        cleanup = input("\nDo you want to delete the downloaded files? (y/n): ").lower()
        if cleanup == 'y':
            ingestor.cleanup(result)
            print("✅ Cleaned up successfully!")
        else:
            print("📁 Files kept for inspection")
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ INGESTION FAILED!")
        print("="*70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n💡 Common issues:")
        print("  1. Check if GITHUB_TOKEN is set in .env file")
        print("  2. Verify the repository URL is correct")
        print("  3. Ensure the repository is public or you have access")


if __name__ == "__main__":
    print("\n" + "="*35)
    print("Repo_Copilot - Real Repository Ingestion Test")
    print("="*35)
    
    test_my_repo()
