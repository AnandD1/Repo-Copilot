"""End-to-end test of the complete Repo Copilot system.

Tests all components:
1. Conventions extraction and storage
2. Code ingestion, chunking, embedding
3. Vector storage in Qdrant
4. PR fetching and diff parsing
5. Three retrievers (local, similar, conventions)
6. BGE reranker
7. LangGraph orchestrator
8. Evidence-based review generation

Usage:
    python test_end_to_end.py https://github.com/owner/repo.git PR_NUMBER
    python test_end_to_end.py https://github.com/AnandD1/ScratchYOLO.git 2
"""

import sys
import re
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from app.conventions.conventions_manager import ConventionsManager
from app.conventions.conventions_store import ConventionsVectorStore
from app.ingest.chunker import CodeChunker
from app.ingest.embedder import Embedder
from app.ingest.filter import FileInfo
from app.storage.vector_store import QdrantVectorStore
from app.pr_review.pr_fetcher import PRFetcher
from app.pr_review.diff_parser import DiffParser
from app.pr_review.review_units import ReviewUnitBuilder
from app.rag import (
    LocalContextRetriever,
    SimilarCodeRetriever,
    ConventionsRetriever,
    BGEReranker,
    ReviewOrchestrator,
    ReviewRequest,
)


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse GitHub URL to extract owner and repo.
    
    Args:
        url: GitHub URL (e.g., https://github.com/owner/repo.git)
        
    Returns:
        Tuple of (owner, repo)
    """
    # Remove .git suffix if present
    url = url.rstrip('.git')
    
    # Extract owner/repo from URL
    pattern = r'github\.com[:/]([^/]+)/([^/]+)'
    match = re.search(pattern, url)
    
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")
    
    return match.group(1), match.group(2)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_conventions(repo_path: str, owner: str, repo: str) -> ConventionsVectorStore:
    """Test conventions extraction and storage.
    
    Args:
        repo_path: Path to local repository
        owner: GitHub repository owner
        repo: GitHub repository name
        
    Returns:
        ConventionsVectorStore instance
    """
    print_section("PHASE 1: CONVENTIONS EXTRACTION & STORAGE")
    
    # Initialize conventions manager
    conventions_store = ConventionsVectorStore()
    embedder = Embedder()
    conventions_manager = ConventionsManager(
        vector_store=conventions_store,
        embedder=embedder,
    )
    
    # Process conventions
    print(f"📁 Scanning repository: {repo_path}")
    from pathlib import Path
    conventions_manager.process_repository_conventions(
        repo_path=Path(repo_path),
        repo_name=f"{owner}/{repo}",
        branch="main",
    )
    
    # Test search
    print("\n🔍 Testing conventions search...")
    test_query_result = embedder.embed_text("variable naming conventions")
    test_query_embedding = test_query_result.embedding  # Extract embedding vector
    results = conventions_store.search_conventions(
        query_embedding=test_query_embedding,
        limit=3,
    )
    
    print(f"✓ Found {len(results)} relevant conventions")
    for i, result in enumerate(results, 1):
        # Debug: print available keys
        if i == 1:
            print(f"  Available keys in result: {list(result.keys())}")
        
        # Handle different result structures
        category = result.get('category', 'unknown')
        rule_text = result.get('rule_text', result.get('text', 'N/A'))
        score = result.get('similarity', result.get('score', 0.0))
        
        print(f"  {i}. [{category}] {rule_text[:80]}... (score: {score:.3f})")
    
    return conventions_store


def test_code_ingestion(repo_path: str, owner: str, repo: str) -> QdrantVectorStore:
    """Test code ingestion, chunking, embedding, and storage.
    
    Args:
        repo_path: Path to local repository
        owner: GitHub repository owner
        repo: GitHub repository name
        
    Returns:
        QdrantVectorStore instance
    """
    print_section("PHASE 2A: CODE INGESTION, CHUNKING & EMBEDDING")
    
    # Initialize components
    repo_full_name = f"{owner}/{repo}"
    chunker = CodeChunker(repo_name=repo_full_name, branch="main")
    embedder = Embedder()
    vector_store = QdrantVectorStore()
    
    # Find Python files
    print(f"📁 Scanning for Python files in: {repo_path}")
    repo_path_obj = Path(repo_path)
    python_files = list(repo_path_obj.rglob("*.py"))
    
    # Limit to first 10 files for testing
    python_files = python_files[:10]
    print(f"✓ Found {len(python_files)} Python files (processing first 10)")
    
    # Process files
    all_chunks = []
    all_embeddings = []
    all_metadata = []
    
    for file_path in python_files:
        try:
            relative_path = file_path.relative_to(repo_path_obj)
            print(f"\n  Processing: {relative_path}")
            
            # Read file
            content = file_path.read_text(encoding='utf-8')
            
            # Create FileInfo with Path objects
            file_info = FileInfo(
                path=file_path,  # Already a Path object
                relative_path=relative_path,  # Already a Path object
                size_bytes=len(content),
                extension=file_path.suffix,
                language="python",
            )
            
            # Chunk - chunker will read file from path
            chunks = chunker.chunk_file(file_info)
            print(f"    → {len(chunks)} chunks")
            
            # Embed chunks
            for chunk in chunks:
                try:
                    embedding_result = embedder.embed_text(chunk.content)
                    all_embeddings.append(embedding_result)  # EmbeddingResult object is fine
                    
                    # Create metadata for storage
                    from app.ingest.embedding_manager import EmbeddingMetadata
                    metadata = EmbeddingMetadata(
                        chunk_id=chunk.metadata.chunk_id,
                        chunk_index=chunk.metadata.chunk_index,
                        repo=repo_full_name,
                        branch="main",
                        file_path=str(relative_path),
                        language="python",
                        start_line=chunk.metadata.start_line,
                        end_line=chunk.metadata.end_line,
                        chunk_type=chunk.metadata.chunk_type.value,
                        symbol=chunk.metadata.symbol,
                        imports=chunk.metadata.imports,
                        embedding_model=settings.embedding_model,
                        embedding_dimension=settings.embedding_dimension,
                        token_count=chunk.token_count,
                        content_hash=f"test_{chunk.metadata.chunk_id}",
                    )
                    all_metadata.append(metadata)
                except Exception as embed_error:
                    print(f"      ⚠ Embedding error: {embed_error}")
                    continue
            
            all_chunks.extend(chunks)
            
        except Exception as e:
            print(f"    ⚠ Error: {e}")
            continue
    
    print(f"\n✓ Total chunks created: {len(all_chunks)}")
    
    # Store in Qdrant
    print("\n💾 Storing embeddings in Qdrant...")
    contents = [chunk.content for chunk in all_chunks]
    
    if all_embeddings and len(all_embeddings) == len(all_metadata):
        count = vector_store.insert_embeddings(
            embeddings=all_embeddings,
            metadata_list=all_metadata,
            contents=contents[:len(all_embeddings)],
        )
        print(f"✓ Stored {count} embeddings in Qdrant")
    else:
        print(f"⚠ Mismatch: {len(all_embeddings)} embeddings vs {len(all_metadata)} metadata")
    
    return vector_store


def test_pr_fetching(owner: str, repo: str, pr_number: int) -> tuple:
    """Test PR fetching and diff parsing.
    
    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
        pr_number: PR number to fetch
        
    Returns:
        Tuple of (PRData, list of FileDiff, list of ReviewUnit)
    """
    print_section("PHASE 2B: PR FETCHING & DIFF PARSING")
    
    # Fetch PR
    print(f"🔗 Fetching PR #{pr_number} from {owner}/{repo}")
    pr_fetcher = PRFetcher(github_token=settings.github_token)
    repo_full_name = f"{owner}/{repo}"
    pr_data = pr_fetcher.fetch_pr(repo_full_name=repo_full_name, pr_number=pr_number)
    
    print(f"✓ PR Title: {pr_data.title}")
    print(f"✓ Files changed: {len(pr_data.files)}")
    print(f"✓ Base SHA: {pr_data.base_sha[:8]}")
    print(f"✓ Head SHA: {pr_data.head_sha[:8]}")
    
    # Add owner/repo properties for compatibility with retrievers
    pr_data.owner = pr_data.repo_owner
    pr_data.repo = pr_data.repo_name
    
    # Parse diffs
    print("\n📝 Parsing diffs...")
    diff_parser = DiffParser()
    all_file_diffs = []
    
    for pr_file in pr_data.files:
        print(f"  Checking file: {pr_file.filename}, status: {pr_file.status}")
        if pr_file.patch:
            print(f"    Patch size: {len(pr_file.patch)} chars")
            # GitHub patch may not have file headers, add them
            full_patch = f"--- a/{pr_file.filename}\n+++ b/{pr_file.filename}\n{pr_file.patch}"
            file_diffs = diff_parser.parse_diff(full_patch)
            all_file_diffs.extend(file_diffs)
            
            for file_diff in file_diffs:
                print(f"\n  File: {file_diff.new_path}")
                print(f"    Hunks: {len(file_diff.hunks)}")
                for hunk in file_diff.hunks:
                    added = len(hunk.added_lines)
                    removed = len(hunk.removed_lines)
                    print(f"      @@ {hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@ (+{added}, -{removed})")
        else:
            print(f"    No patch data (binary file or other reason)")
    
    # Build review units
    print("\n🔨 Building review units...")
    unit_builder = ReviewUnitBuilder(pr_data=pr_data, file_diffs=all_file_diffs)
    review_units = unit_builder.build_all_units(strategy="smart")
    
    print(f"✓ Created {len(review_units)} review units")
    for unit in review_units[:3]:  # Show first 3
        print(f"  - {unit.context.file_path} (priority: {unit.priority}, complexity: {unit.complexity_score:.2f})")
    
    return pr_data, all_file_diffs, review_units


def test_retrievers(
    pr_data,
    review_units,
    pr_fetcher: PRFetcher,
    vector_store: QdrantVectorStore,
    conventions_store: ConventionsVectorStore,
) -> tuple:
    """Test all three retrievers.
    
    Args:
        pr_data: PRData object
        review_units: List of ReviewUnit objects
        pr_fetcher: PRFetcher instance
        vector_store: QdrantVectorStore instance
        conventions_store: ConventionsVectorStore instance
        
    Returns:
        Tuple of (local_retriever, similar_retriever, conventions_retriever, embedder)
    """
    print_section("PHASE 3A: RETRIEVER TESTING")
    
    # Initialize retrievers
    embedder = Embedder()
    local_retriever = LocalContextRetriever(pr_fetcher)
    similar_retriever = SimilarCodeRetriever(vector_store, embedder)
    conventions_retriever = ConventionsRetriever(conventions_store, embedder)
    
    # Get first review unit for testing
    if not review_units:
        print("⚠ No review units to test")
        return local_retriever, similar_retriever, conventions_retriever, embedder
    
    test_unit = review_units[0]
    print(f"🧪 Testing with: {test_unit.context.file_path}")
    # Get code snippet from diff
    code_snippet = test_unit.get_diff_snippet(max_lines=20)
    print(f"   Code snippet preview: {code_snippet[:100]}...")
    
    # For search, use added lines as query
    query_text = "\n".join(test_unit.context.added_lines[:10]) if test_unit.context.added_lines else "code review"
    
    # Test LocalContextRetriever
    print("\n1️⃣ LocalContextRetriever")
    local_evidence = local_retriever.retrieve(
        owner=pr_data.owner,
        repo=pr_data.repo,
        file_path=test_unit.context.file_path,
        head_sha=pr_data.head_sha,
        target_line=test_unit.context.new_line_start or 1,
        context_lines=5,
    )
    print(f"   ✓ Found {len(local_evidence)} local context evidence")
    for evidence in local_evidence:
        print(f"     [{evidence.evidence_type.value}] {evidence.file_path}:{evidence.start_line}-{evidence.end_line}")
    
    # Test SimilarCodeRetriever
    print("\n2️⃣ SimilarCodeRetriever")
    similar_evidence = similar_retriever.retrieve(
        query=query_text,
        top_k=3,
        repo=pr_data.repo,
        min_similarity=0.5,
    )
    print(f"   ✓ Found {len(similar_evidence)} similar code snippets")
    for evidence in similar_evidence:
        print(f"     [{evidence.evidence_type.value}] {evidence.file_path}:{evidence.start_line}-{evidence.end_line} (score: {evidence.similarity_score:.3f})")
    
    # Test ConventionsRetriever
    print("\n3️⃣ ConventionsRetriever")
    convention_evidence = conventions_retriever.retrieve(
        query=query_text,
        top_k=2,
        language="python",
        min_similarity=0.5,
    )
    print(f"   ✓ Found {len(convention_evidence)} relevant conventions")
    for evidence in convention_evidence:
        print(f"     [{evidence.evidence_type.value}] {evidence.content[:80]}... (score: {evidence.similarity_score:.3f})")
    
    return local_retriever, similar_retriever, conventions_retriever, embedder


def test_reranker_and_orchestrator(
    pr_data,
    review_units,
    local_retriever: LocalContextRetriever,
    similar_retriever: SimilarCodeRetriever,
    conventions_retriever: ConventionsRetriever,
):
    """Test BGE reranker and full orchestrator.
    
    Args:
        pr_data: PRData object
        review_units: List of ReviewUnit objects
        local_retriever: LocalContextRetriever instance
        similar_retriever: SimilarCodeRetriever instance
        conventions_retriever: ConventionsRetriever instance
    """
    print_section("PHASE 3B: RERANKER & ORCHESTRATOR")
    
    # Initialize reranker
    print("🔄 Initializing BGE reranker...")
    reranker = BGEReranker()
    print("✓ Reranker ready")
    
    # Initialize orchestrator
    print("\n🎭 Initializing ReviewOrchestrator...")
    orchestrator = ReviewOrchestrator(
        local_retriever=local_retriever,
        similar_retriever=similar_retriever,
        conventions_retriever=conventions_retriever,
        reranker=reranker,
    )
    print("✓ Orchestrator ready")
    
    # Test with first review unit
    if not review_units:
        print("⚠ No review units to test")
        return
    
    test_unit = review_units[0]
    print(f"\n🧪 Generating review for: {test_unit.context.file_path}")
    
    # Get code snippet and query text
    code_snippet = test_unit.get_diff_snippet(max_lines=30)
    query_text = "\n".join(test_unit.context.added_lines[:20]) if test_unit.context.added_lines else code_snippet
    
    # Create review request
    request = ReviewRequest(
        file_path=test_unit.context.file_path,
        code_snippet=query_text,
        owner=pr_data.owner,
        repo=pr_data.repo,
        head_sha=pr_data.head_sha,
        target_line=test_unit.context.new_line_start or 1,
        language="python",
    )
    
    # Execute review
    print("\n⚙️ Executing LangGraph workflow...")
    print("   Step 1: Retrieve local context")
    print("   Step 2: Retrieve similar code")
    print("   Step 3: Retrieve conventions")
    print("   Step 4: Rerank evidence")
    print("   Step 5: Generate review with Ollama")
    print("   Step 6: Validate citations")
    
    start_time = time.time()
    response = orchestrator.review(request)
    elapsed = time.time() - start_time
    
    print(f"\n✓ Review completed in {elapsed:.2f} seconds")
    
    # Display results
    print("\n" + "─" * 80)
    print("📊 REVIEW RESULTS")
    print("─" * 80)
    
    print(f"\n📝 Raw LLM Response:")
    print(response.raw_response)
    
    print(f"\n🎯 Validated Claims: {len(response.claims)}")
    for i, claim in enumerate(response.claims, 1):
        print(f"\n{i}. {claim.format_with_citations()}")
        print(f"   Severity: {claim.severity}")
        print(f"   Evidence count: {len(claim.evidence)}")
    
    print(f"\n📚 Total Evidence Gathered: {len(response.evidence)}")
    print("\nEvidence breakdown:")
    from collections import Counter
    evidence_types = Counter(e.evidence_type.value for e in response.evidence)
    for etype, count in evidence_types.items():
        print(f"  - {etype}: {count}")


def main():
    """Main test execution."""
    # Parse arguments
    if len(sys.argv) < 3:
        print("Usage: python test_end_to_end.py <github_url> <pr_number>")
        print("\nExample:")
        print("  python test_end_to_end.py https://github.com/AnandD1/ScratchYOLO.git 2")
        sys.exit(1)
    
    github_url = sys.argv[1]
    pr_number = int(sys.argv[2])
    
    # Parse GitHub URL
    owner, repo = parse_github_url(github_url)
    
    print("\n" + "=" * 80)
    print("  🚀 REPO COPILOT - END-TO-END SYSTEM TEST")
    print("=" * 80)
    print(f"\n📍 Repository: {owner}/{repo}")
    print(f"📍 PR Number: {pr_number}")
    print(f"📍 GitHub URL: {github_url}")
    
    # Check if repo is cloned locally
    temp_repos_dir = Path(__file__).parent / "temp_repos"
    repo_path = temp_repos_dir / repo
    
    if not repo_path.exists():
        print(f"\n⚠️  Repository not found locally at: {repo_path}")
        print("Please clone it first:")
        print(f"  cd {temp_repos_dir}")
        print(f"  git clone {github_url}")
        sys.exit(1)
    
    print(f"✓ Local repo path: {repo_path}")
    
    try:
        # Phase 1: Conventions
        conventions_store = test_conventions(str(repo_path), owner, repo)
        
        # Phase 2A: Code ingestion
        vector_store = test_code_ingestion(str(repo_path), owner, repo)
        
        # Phase 2B: PR fetching
        pr_data, file_diffs, review_units = test_pr_fetching(owner, repo, pr_number)
        
        # Phase 3A: Retrievers
        pr_fetcher = PRFetcher(github_token=settings.github_token)
        local_retriever, similar_retriever, conventions_retriever, embedder = test_retrievers(
            pr_data,
            review_units,
            pr_fetcher,
            vector_store,
            conventions_store,
        )
        
        # Phase 3B: Orchestrator
        test_reranker_and_orchestrator(
            pr_data,
            review_units,
            local_retriever,
            similar_retriever,
            conventions_retriever,
        )
        
        print("\n" + "=" * 80)
        print("  ✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
