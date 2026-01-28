"""Test conventions memory system."""

from pathlib import Path
from app.conventions import ConventionsManager
from app.rag import HybridRetriever, PRReviewChain


def test_conventions_extraction():
    """Test extracting conventions from Repo_Copilot itself."""
    
    print("\n" + "="*80)
    print("CONVENTIONS MEMORY TEST")
    print("="*80)
    
    repo_path = Path("d:/LLM/PROJECT/ScratchYOLO")
    
    # Process conventions
    print("\n1. Extracting conventions...")
    manager = ConventionsManager()
    
    result = manager.process_repository_conventions(
        repo_path=repo_path,
        repo_name="Repo_Copilot",
        branch="main"
    )
    
    print("\n✓ Extracted {result.total_conventions} conventions")
    print("\nBy Category:")
    for category, count in result.by_category.items():
        print(f"  {category}: {count}")
    
    print("\nBy Severity:")
    for severity, count in result.by_severity.items():
        print(f"  {severity}: {count}")
    
    # Test retrieval
    print("\n2. Testing convention retrieval...")
    
    queries = [
        "function naming conventions",
        "code formatting rules",
        "testing requirements",
        "documentation standards"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        conventions = manager.get_relevant_conventions(query, limit=3)
        
        for i, conv in enumerate(conventions, 1):
            print(f"  {i}. [{conv.category}] {conv.title}")
            print(f"     Source: {conv.source}")
            print(f"     Similarity: {conv.metadata.get('similarity', 0):.3f}")
    
    # Get statistics
    print("\n3. Conventions statistics:")
    stats = manager.get_statistics()
    print(f"  Total: {stats['total_conventions']}")
    print(f"  Categories: {list(stats['by_category'].keys())}")
    print(f"  Severities: {list(stats['by_severity'].keys())}")
    
    manager.close()
    
    print("\n✓ Conventions test complete!")


def test_rag_pr_review():
    """Test RAG-based PR review with conventions."""
    
    print("\n" + "="*80)
    print("RAG PR REVIEW TEST")
    print("="*80)
    
    # Initialize retriever
    print("\n1. Initializing hybrid retriever...")
    retriever = HybridRetriever(
        code_k=5,
        conventions_k=3
    )
    
    # Initialize review chain
    print("2. Building LangGraph chain...")
    chain = PRReviewChain(retriever)
    
    # Simulate PR review
    print("\n3. Reviewing PR...")
    
    result = chain.review_pr(
        changed_files=[
            "app/storage/vector_store.py",
            "app/conventions/conventions_store.py"
        ],
        repo="Repo_Copilot",
        branch="main",
        language="python",
        pr_description="Added conventions memory system with separate Qdrant collection"
    )
    
    print("\n✓ Review complete!")
    print("\nReview Comments:")
    for comment in result["review_comments"][:5]:
        if comment.strip():
            print(f"\n{comment}")
    
    print(f"\n\nConventions Used: {len(result['conventions_used'])}")
    print(f"Context Retrieved: {result['context_retrieved']} chunks")
    
    retriever.close()
    
    print("\n✓ RAG test complete!")


if __name__ == "__main__":
    import sys
    
    try:
        # Test conventions extraction
        test_conventions_extraction()
        
        # Test RAG PR review
        print("\n" + "="*80)
        do_rag_test = input("\nRun RAG PR review test? (requires API key) (y/n): ").lower()
        if do_rag_test == 'y':
            test_rag_pr_review()
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED!")
        print("="*80)
        
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
