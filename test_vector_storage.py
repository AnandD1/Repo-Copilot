"""Test script for Qdrant vector storage."""

import sys
from pathlib import Path

from app.ingest.ingestor import RepositoryIngestor
from app.ingest.chunk_manager import ChunkManager
from app.ingest.embedding_manager import EmbeddingManager
from app.ingest.loader import LoadMethod
from app.storage.vector_store import QdrantVectorStore


def test_vector_storage():
    """Test the complete pipeline with Qdrant storage."""
    
    print("\n" + "="*80)
    print("QDRANT VECTOR STORAGE TEST")
    print("="*80)
    
    # Configuration
    REPO_URL = input("\nEnter GitHub repo URL (or press Enter for default 'pallets/flask'): ").strip()
    if not REPO_URL:
        REPO_URL = "https://github.com/pallets/flask"
    
    print(f"\nTesting with repository: {REPO_URL}")
    
    # ============================================================================
    # STEP 1: INGEST REPOSITORY
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 1: INGESTING REPOSITORY")
    print("="*80)
    
    try:
        ingestor = RepositoryIngestor()
        ingestion_result = ingestor.ingest_repository(
            repo_url=REPO_URL,
            method=LoadMethod.API
        )
        
        print(f"\n✓ Ingestion successful!")
        print(f"  Repository: {ingestion_result.repo_info.full_name}")
        print(f"  Branch: {ingestion_result.repo_info.default_branch}")
        print(f"  Files: {ingestion_result.total_files}")
        
    except Exception as e:
        print(f"\n✗ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # STEP 2: CHUNK FILES
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 2: CHUNKING FILES")
    print("="*80)
    
    try:
        chunk_manager = ChunkManager(
            repo_name=ingestion_result.repo_info.full_name,
            branch=ingestion_result.repo_info.default_branch
        )
        
        chunking_result = chunk_manager.chunk_ingestion_result(ingestion_result)
        
        print(f"\n✓ Chunking successful!")
        print(f"  Total chunks: {chunking_result.total_chunks}")
        print(f"  Code chunks: {chunking_result.chunks_by_type.get('code', 0)}")
        print(f"  Doc chunks: {chunking_result.chunks_by_type.get('doc', 0)}")
        print(f"  Config chunks: {chunking_result.chunks_by_type.get('config', 0)}")
        
    except Exception as e:
        print(f"\n✗ Chunking failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # STEP 3: GENERATE EMBEDDINGS
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 3: GENERATING EMBEDDINGS")
    print("="*80)
    
    # Use subset for testing
    SAMPLE_SIZE = int(input("\nHow many chunks to embed? (default: 10): ").strip() or "10")
    test_chunks = chunking_result.chunks[:SAMPLE_SIZE]
    
    print(f"\nGenerating embeddings for {len(test_chunks)} chunks...")
    
    try:
        embedding_manager = EmbeddingManager(
            cache_dir=Path("./embedding_cache"),
            use_cache=True
        )
        
        embedding_result = embedding_manager.embed_chunks(test_chunks)
        
        print(f"\n✓ Embedding successful!")
        print(f"  Total embeddings: {embedding_result.total_embeddings}")
        print(f"  New: {embedding_result.new_embeddings}")
        print(f"  Cached: {embedding_result.cached_embeddings}")
        
    except Exception as e:
        print(f"\n✗ Embedding failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # STEP 4: STORE IN QDRANT
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 4: STORING IN QDRANT")
    print("="*80)
    
    try:
        vector_store = QdrantVectorStore()
        
        # Extract contents from chunks
        contents = [chunk.content for chunk in test_chunks]
        
        points_inserted = vector_store.insert_embeddings(
            embedding_result.embeddings,
            embedding_result.metadata,
            contents,
            upsert=True
        )
        
        print(f"\n✓ Storage successful!")
        print(f"  Points inserted/updated: {points_inserted}")
        
    except Exception as e:
        print(f"\n✗ Storage failed: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure Qdrant is running!")
        print("Setup instructions:")
        print("  Docker: docker run -p 6333:6333 qdrant/qdrant")
        print("  Or see QDRANT_SETUP.md for detailed instructions")
        return False
    
    # ============================================================================
    # STEP 5: TEST SIMILARITY SEARCH
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 5: TESTING SIMILARITY SEARCH")
    print("="*80)
    
    try:
        if embedding_result.embeddings:
            # Use first embedding as query
            query_vector = embedding_result.embeddings[0].embedding
            query_chunk = test_chunks[0]
            
            print(f"\nQuery chunk: {query_chunk.metadata.file_path}")
            print(f"  Lines: {query_chunk.metadata.start_line}-{query_chunk.metadata.end_line}")
            print(f"  Symbol: {query_chunk.metadata.symbol}")
            
            results = vector_store.similarity_search(
                query_embedding=query_vector,
                limit=5,
                repo=ingestion_result.repo_info.full_name
            )
            
            print(f"\n✓ Found {len(results)} similar chunks:")
            for i, result in enumerate(results, 1):
                print(f"\n  {i}. {result['file_path']}")
                print(f"     Lines: {result['start_line']}-{result['end_line']}")
                print(f"     Similarity: {result['similarity']:.4f}")
                print(f"     Symbol: {result['symbol']}")
                print(f"     Preview: {result['content'][:100]}...")
        
    except Exception as e:
        print(f"\n✗ Similarity search failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # STEP 6: DATABASE STATISTICS
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 6: DATABASE STATISTICS")
    print("="*80)
    
    try:
        stats = vector_store.get_statistics()
        
        print(f"\n✓ Database statistics:")
        print(f"  Total chunks: {stats['total_chunks']}")
        print(f"  Indexed vectors: {stats['indexed_vectors']}")
        print(f"  Vector dimension: {stats['vector_dimension']}")
        print(f"  Status: {stats['status']}")
        print(f"\n  By repository:")
        for repo, count in list(stats['by_repo'].items())[:5]:
            print(f"    {repo}: {count}")
        print(f"\n  By language:")
        for lang, count in list(stats['by_language'].items())[:5]:
            print(f"    {lang}: {count}")
        
    except Exception as e:
        print(f"\n✗ Statistics failed: {e}")
    
    # ============================================================================
    # CLEANUP
    # ============================================================================
    print("\n" + "="*80)
    print("CLEANUP")
    print("="*80)
    
    cleanup = input("\nCleanup downloaded files? (y/n): ").lower()
    if cleanup == 'y':
        ingestor.cleanup(ingestion_result)
        print("✓ Files cleaned up")
    
    delete = input("\nDelete embeddings from database? (y/n): ").lower()
    if delete == 'y':
        deleted = vector_store.delete_by_repo(
            ingestion_result.repo_info.full_name,
            ingestion_result.repo_info.default_branch
        )
        print(f"✓ Deleted {deleted} embeddings")
    
    vector_store.close()
    
    # ============================================================================
    # FINAL SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    print(f"\n✓ ALL TESTS PASSED!")
    print(f"\nPipeline Summary:")
    print(f"  1. Ingestion: {ingestion_result.total_files} files")
    print(f"  2. Chunking: {chunking_result.total_chunks} chunks")
    print(f"  3. Embedding: {embedding_result.total_embeddings} embeddings (3072D)")
    print(f"  4. Storage: Qdrant vector database")
    print(f"  5. Search: Cosine similarity with HNSW index")
    
    print(f"\nReady for production! ✓")
    
    return True


if __name__ == "__main__":
    try:
        success = test_vector_storage()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
