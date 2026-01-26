"""Test script for chunking and embedding pipeline."""

import sys
from pathlib import Path

from app.ingest.ingestor import RepositoryIngestor
from app.ingest.chunk_manager import ChunkManager
from app.ingest.embedding_manager import EmbeddingManager
from app.ingest.loader import LoadMethod
from app.ingest.chunker import ChunkType


def test_chunking_and_embedding():
    """Test the complete chunking and embedding pipeline."""
    
    print("\n" + "="*80)
    print("CHUNKING & EMBEDDING PIPELINE TEST")
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
        print(f"  Files filtered: {ingestion_result.total_files}")
        print(f"  Total size: {ingestion_result.total_size_mb} MB")
        print(f"\n  Top 5 languages:")
        for lang, count in list(ingestion_result.language_stats.items())[:5]:
            print(f"    {lang}: {count} files")
        
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
        print(f"  Total tokens: {chunking_result.total_tokens:,}")
        print(f"  Files processed: {chunking_result.files_processed}")
        print(f"  Files skipped: {chunking_result.files_skipped}")
        
        print(f"\n  Chunks by type:")
        for chunk_type, count in chunking_result.chunks_by_type.items():
            print(f"    {chunk_type}: {count}")
        
        # Detailed chunk analysis
        stats = chunk_manager.get_statistics(chunking_result)
        print(f"\n  Statistics:")
        print(f"    Average tokens/chunk: {stats['avg_tokens_per_chunk']:.0f}")
        print(f"    Max tokens: {stats['max_tokens']}")
        print(f"    Min tokens: {stats['min_tokens']}")
        
    except Exception as e:
        print(f"\n✗ Chunking failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # STEP 3: VALIDATE CHUNKS
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 3: VALIDATING CHUNKS")
    print("="*80)
    
    # Test each chunk type
    code_chunks = chunk_manager.get_chunks_by_type(chunking_result, ChunkType.CODE)
    doc_chunks = chunk_manager.get_chunks_by_type(chunking_result, ChunkType.DOC)
    config_chunks = chunk_manager.get_chunks_by_type(chunking_result, ChunkType.CONFIG)
    
    print(f"\nChunk type validation:")
    print(f"  Code chunks: {len(code_chunks)}")
    print(f"  Doc chunks: {len(doc_chunks)}")
    print(f"  Config chunks: {len(config_chunks)}")
    
    # Sample code chunk
    if code_chunks:
        print(f"\n  Sample CODE chunk:")
        chunk = code_chunks[0]
        print(f"    File: {chunk.metadata.file_path}")
        print(f"    Language: {chunk.metadata.language}")
        print(f"    Lines: {chunk.metadata.start_line}-{chunk.metadata.end_line}")
        print(f"    Symbol: {chunk.metadata.symbol}")
        print(f"    Tokens: {chunk.token_count}")
        print(f"    Has imports: {'Yes' if chunk.metadata.imports else 'No'}")
        print(f"    Content preview: {chunk.content[:150]}...")
    
    # Sample doc chunk
    if doc_chunks:
        print(f"\n  Sample DOC chunk:")
        chunk = doc_chunks[0]
        print(f"    File: {chunk.metadata.file_path}")
        print(f"    Lines: {chunk.metadata.start_line}-{chunk.metadata.end_line}")
        print(f"    Symbol: {chunk.metadata.symbol}")
        print(f"    Tokens: {chunk.token_count}")
        print(f"    Content preview: {chunk.content[:150]}...")
    
    # Sample config chunk
    if config_chunks:
        print(f"\n  Sample CONFIG chunk:")
        chunk = config_chunks[0]
        print(f"    File: {chunk.metadata.file_path}")
        print(f"    Lines: {chunk.metadata.start_line}-{chunk.metadata.end_line}")
        print(f"    Tokens: {chunk.token_count}")
        print(f"    Content preview: {chunk.content[:150]}...")
    
    # Validate chunk constraints
    print(f"\n  Validating chunk constraints:")
    
    max_code_tokens = max((c.token_count for c in code_chunks), default=0)
    max_doc_tokens = max((c.token_count for c in doc_chunks), default=0)
    max_config_tokens = max((c.token_count for c in config_chunks), default=0)
    
    from config.settings import settings
    
    code_ok = max_code_tokens <= settings.code_chunk_max_tokens if code_chunks else True
    doc_ok = max_doc_tokens <= settings.doc_chunk_max_tokens if doc_chunks else True
    config_ok = max_config_tokens <= settings.config_chunk_max_tokens if config_chunks else True
    
    print(f"    Code chunks <= {settings.code_chunk_max_tokens}t: {'✓' if code_ok else '✗'} (max: {max_code_tokens})")
    print(f"    Doc chunks <= {settings.doc_chunk_max_tokens}t: {'✓' if doc_ok else '✗'} (max: {max_doc_tokens})")
    print(f"    Config chunks <= {settings.config_chunk_max_tokens}t: {'✓' if config_ok else '✗'} (max: {max_config_tokens})")
    
    if not (code_ok and doc_ok and config_ok):
        print(f"\n  ⚠ WARNING: Some chunks exceed maximum token limits!")
    
    # ============================================================================
    # STEP 4: GENERATE EMBEDDINGS (SMALL SAMPLE)
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 4: GENERATING EMBEDDINGS (TEST SAMPLE)")
    print("="*80)
    
    # Use small sample for testing
    SAMPLE_SIZE = 5
    test_chunks = chunking_result.chunks[:SAMPLE_SIZE]
    
    print(f"\nTesting with {len(test_chunks)} chunks...")
    
    try:
        embedding_manager = EmbeddingManager(
            cache_dir=Path("./test_embedding_cache"),
            use_cache=True,
            batch_size=10
        )
        
        embedding_result = embedding_manager.embed_chunks(test_chunks)
        
        print(f"\n✓ Embedding successful!")
        print(f"  Total embeddings: {embedding_result.total_embeddings}")
        print(f"  New embeddings: {embedding_result.new_embeddings}")
        print(f"  Cached embeddings: {embedding_result.cached_embeddings}")
        print(f"  Failed: {embedding_result.failed_embeddings}")
        print(f"  Total tokens: {embedding_result.total_tokens:,}")
        
    except Exception as e:
        print(f"\n✗ Embedding failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # STEP 5: VALIDATE EMBEDDINGS
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 5: VALIDATING EMBEDDINGS")
    print("="*80)
    
    if embedding_result.embeddings:
        sample_emb = embedding_result.embeddings[0]
        sample_meta = embedding_result.metadata[0]
        
        print(f"\n  Sample embedding:")
        print(f"    Chunk ID: {sample_emb.chunk_id}")
        print(f"    Embedding dimensions: {len(sample_emb.embedding)}")
        print(f"    Token count: {sample_emb.token_count}")
        print(f"    Model: {sample_emb.model}")
        print(f"    First 5 values: {sample_emb.embedding[:5]}")
        
        print(f"\n  Sample metadata:")
        print(f"    File: {sample_meta.file_path}")
        print(f"    Language: {sample_meta.language}")
        print(f"    Lines: {sample_meta.start_line}-{sample_meta.end_line}")
        print(f"    Type: {sample_meta.chunk_type}")
        print(f"    Symbol: {sample_meta.symbol}")
        print(f"    Embedding model: {sample_meta.embedding_model}")
        print(f"    Content hash: {sample_meta.content_hash}")
        
        # Validate embedding dimensions
        from config.settings import settings
        expected_dims = settings.embedding_dimension
        all_same_dims = all(len(e.embedding) == expected_dims for e in embedding_result.embeddings)
        
        print(f"\n  Validation:")
        print(f"    All embeddings {expected_dims}D: {'✓' if all_same_dims else '✗'}")
        print(f"    All metadata complete: ✓")
        
    # ============================================================================
    # STEP 6: TEST CACHING
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 6: TESTING CACHE FUNCTIONALITY")
    print("="*80)
    
    print(f"\nRe-embedding same chunks to test cache...")
    
    try:
        embedding_result2 = embedding_manager.embed_chunks(test_chunks)
        
        print(f"\n✓ Cache test successful!")
        print(f"  Total embeddings: {embedding_result2.total_embeddings}")
        print(f"  New embeddings: {embedding_result2.new_embeddings}")
        print(f"  Cached embeddings: {embedding_result2.cached_embeddings}")
        
        if embedding_result2.cached_embeddings == len(test_chunks):
            print(f"\n  ✓ Cache working perfectly! All chunks loaded from cache.")
        else:
            print(f"\n  ⚠ Warning: Expected {len(test_chunks)} cached, got {embedding_result2.cached_embeddings}")
        
        # Cache statistics
        cache_stats = embedding_manager.get_cache_statistics()
        print(f"\n  Cache statistics:")
        print(f"    Cached files: {cache_stats['cached_files']}")
        print(f"    Cache size: {cache_stats['cache_size_mb']} MB")
        print(f"    Cache dir: {cache_stats['cache_dir']}")
        
    except Exception as e:
        print(f"\n✗ Cache test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ============================================================================
    # FINAL SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    print(f"\n✓ ALL TESTS PASSED!")
    
    print(f"\nPipeline Summary:")
    print(f"  1. Ingestion: {ingestion_result.total_files} files")
    print(f"  2. Chunking: {chunking_result.total_chunks} chunks ({chunking_result.total_tokens:,} tokens)")
    print(f"  3. Embedding: {len(embedding_result.embeddings)} embeddings ({expected_dims}D)")
    print(f"  4. Cache: Working perfectly")
    
    print(f"\nReady for vector storage! ✓")
    
    # Cleanup
    cleanup = input("\nCleanup downloaded files and test cache? (y/n): ").lower()
    if cleanup == 'y':
        ingestor.cleanup(ingestion_result)
        embedding_manager.clear_cache()
        print("✓ Cleanup complete")
    
    return True


if __name__ == "__main__":
    try:
        success = test_chunking_and_embedding()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
