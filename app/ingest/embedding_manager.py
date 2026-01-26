"""Embedding manager for coordinating embedding generation and caching."""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

from app.ingest.embedder import Embedder, EmbeddingResult
from app.ingest.chunk_manager import ChunkingResult
from app.ingest.chunker import Chunk


@dataclass
class EmbeddingMetadata:
    """Extended metadata for embeddings including chunk metadata."""
    # Chunk metadata
    chunk_id: str
    chunk_index: int
    repo: str
    branch: str
    file_path: str
    language: Optional[str]
    start_line: int
    end_line: int
    chunk_type: str
    symbol: Optional[str]
    imports: Optional[str]
    
    # Embedding metadata
    embedding_model: str
    embedding_dimension: int
    token_count: int
    content_hash: str  # For cache validation


@dataclass
class EmbeddingManagerResult:
    """Result of embedding manager operation."""
    embeddings: List[EmbeddingResult]
    metadata: List[EmbeddingMetadata]
    total_embeddings: int
    total_tokens: int
    cached_embeddings: int
    new_embeddings: int
    failed_embeddings: int
    
    def __str__(self):
        """String representation."""
        return f"""
Embedding Manager Result:
  Total embeddings: {self.total_embeddings}
  New embeddings: {self.new_embeddings}
  Cached embeddings: {self.cached_embeddings}
  Failed: {self.failed_embeddings}
  Total tokens: {self.total_tokens:,}
  Model: {self.metadata[0].embedding_model if self.metadata else 'N/A'}
        """.strip()


class EmbeddingManager:
    """
    Manages embedding generation with caching and coordination.
    
    Features:
    - Embedding generation coordination
    - Cache management to avoid re-embedding
    - Metadata tracking
    - Progress monitoring
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True,
        batch_size: int = 100
    ):
        """
        Initialize embedding manager.
        
        Args:
            cache_dir: Directory for caching embeddings
            use_cache: Whether to use cache
            batch_size: Batch size for embedding generation
        """
        self.cache_dir = cache_dir or Path("./embedding_cache")
        self.use_cache = use_cache
        self.batch_size = batch_size
        
        if self.use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.embedder = Embedder(batch_size=batch_size)
    
    def embed_chunks(self, chunks: List[Chunk]) -> EmbeddingManagerResult:
        """
        Generate embeddings for chunks with caching.
        
        Args:
            chunks: List of chunks to embed
        
        Returns:
            EmbeddingManagerResult with embeddings and metadata
        """
        print(f"\n{'='*60}")
        print(f"Embedding Manager")
        print(f"{'='*60}")
        print(f"Total chunks: {len(chunks)}")
        print(f"Cache enabled: {self.use_cache}")
        
        embeddings = []
        metadata_list = []
        cached_count = 0
        new_count = 0
        
        # Create chunk lookup by chunk_id for alignment
        chunk_by_id = {chunk.metadata.chunk_id: chunk for chunk in chunks}
        
        # Separate cached and non-cached chunks
        chunks_to_embed = []
        
        for chunk in chunks:
            content_hash = self._hash_content(chunk.content)
            
            # Try to load from cache
            if self.use_cache:
                cached_embedding = self._load_from_cache(
                    chunk.metadata.repo,
                    chunk.metadata.branch,
                    chunk.metadata.chunk_id,
                    content_hash,
                    self.embedder.model
                )
                if cached_embedding:
                    embeddings.append(cached_embedding)
                    metadata_list.append(self._create_metadata(chunk, cached_embedding, content_hash))
                    cached_count += 1
                    continue
            
            chunks_to_embed.append(chunk)
        
        print(f"Cached: {cached_count}, To embed: {len(chunks_to_embed)}")
        
        # Generate new embeddings
        if chunks_to_embed:
            new_embeddings_list = self.embedder.embed_chunks(chunks_to_embed)
            
            # Map embeddings by chunk_id (not zip order)
            embedding_by_id = {emb.chunk_id: emb for emb in new_embeddings_list}
            
            # Align embeddings with original chunks using chunk_id
            for chunk in chunks_to_embed:
                embedding = embedding_by_id.get(chunk.metadata.chunk_id)
                if embedding:
                    content_hash = self._hash_content(chunk.content)
                    
                    # Cache the embedding
                    if self.use_cache:
                        self._save_to_cache(
                            chunk.metadata.repo,
                            chunk.metadata.branch,
                            chunk.metadata.chunk_id,
                            content_hash,
                            embedding
                        )
                    
                    embeddings.append(embedding)
                    metadata_list.append(self._create_metadata(chunk, embedding, content_hash))
                    new_count += 1
                else:
                    print(f"Warning: No embedding generated for {chunk.metadata.chunk_id}")
        
        # Get statistics
        stats = self.embedder.get_statistics()
        
        result = EmbeddingManagerResult(
            embeddings=embeddings,
            metadata=metadata_list,
            total_embeddings=len(embeddings),
            total_tokens=sum(e.token_count for e in embeddings),
            cached_embeddings=cached_count,
            new_embeddings=new_count,
            failed_embeddings=stats['failed_chunks']
        )
        
        print(f"\n{'='*60}")
        print(f"Embedding Complete")
        print(f"{'='*60}")
        print(result)
        
        return result
    
    def embed_chunking_result(self, chunking_result: ChunkingResult) -> EmbeddingManagerResult:
        """
        Generate embeddings for all chunks in chunking result.
        
        Args:
            chunking_result: Result from chunk manager
        
        Returns:
            EmbeddingManagerResult
        """
        return self.embed_chunks(chunking_result.chunks)
    
    def _create_metadata(
        self,
        chunk: Chunk,
        embedding: EmbeddingResult,
        content_hash: str
    ) -> EmbeddingMetadata:
        """Create extended metadata for embedding."""
        return EmbeddingMetadata(
            chunk_id=chunk.metadata.chunk_id,
            chunk_index=chunk.metadata.chunk_index,
            repo=chunk.metadata.repo,
            branch=chunk.metadata.branch,
            file_path=chunk.metadata.file_path,
            language=chunk.metadata.language,
            start_line=chunk.metadata.start_line,
            end_line=chunk.metadata.end_line,
            chunk_type=chunk.metadata.chunk_type.value,
            symbol=chunk.metadata.symbol,
            imports=chunk.metadata.imports,
            embedding_model=embedding.model,
            embedding_dimension=embedding.dimension,
            token_count=embedding.token_count,
            content_hash=content_hash
        )
    
    def _hash_content(self, content: str) -> str:
        """Generate hash of content for cache validation."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _get_cache_path(self, repo: str, branch: str, chunk_id: str, model: str) -> Path:
        """Get cache file path for chunk including repo, branch, and model."""
        # Create safe filename components
        safe_repo = repo.replace('/', '_').replace('\\', '_')
        safe_branch = branch.replace('/', '_').replace('\\', '_')
        safe_id = chunk_id.replace('/', '_').replace('\\', '_').replace('::', '_')
        # Use first 8 chars of model hash to keep filename reasonable
        model_hash = hashlib.sha256(model.encode('utf-8')).hexdigest()[:8]
        
        # Combine all components: repo_branch_chunkid_modelhash.json
        filename = f"{safe_repo}_{safe_branch}_{safe_id}_{model_hash}.json"
        return self.cache_dir / filename
    
    def _save_to_cache(
        self,
        repo: str,
        branch: str,
        chunk_id: str,
        content_hash: str,
        embedding: EmbeddingResult
    ):
        """Save embedding to cache with model and dimension validation."""
        cache_path = self._get_cache_path(repo, branch, chunk_id, embedding.model)
        
        cache_data = {
            'chunk_id': chunk_id,
            'repo': repo,
            'branch': branch,
            'content_hash': content_hash,
            'model': embedding.model,
            'dimension': embedding.dimension,
            'embedding': embedding.embedding,
            'token_count': embedding.token_count
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            print(f"Warning: Could not save cache for {chunk_id}: {e}")
    
    def _load_from_cache(
        self,
        repo: str,
        branch: str,
        chunk_id: str,
        content_hash: str,
        model: str
    ) -> Optional[EmbeddingResult]:
        """Load embedding from cache if valid (checks model, dimension, content)."""
        cache_path = self._get_cache_path(repo, branch, chunk_id, model)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
            
            # Validate content hash
            if cache_data.get('content_hash') != content_hash:
                return None
            
            # Validate model
            if cache_data.get('model') != model:
                return None
            
            # Validate dimension exists
            dimension = cache_data.get('dimension')
            if dimension is None:
                return None
            
            # Validate embedding vector dimension matches metadata
            embedding_vector = cache_data.get('embedding', [])
            if len(embedding_vector) != dimension:
                print(f"Warning: Cached dimension mismatch for {chunk_id}")
                return None
            
            return EmbeddingResult(
                chunk_id=cache_data['chunk_id'],
                embedding=embedding_vector,
                token_count=cache_data['token_count'],
                model=cache_data['model'],
                dimension=dimension
            )
        
        except Exception as e:
            print(f"Warning: Could not load cache for {chunk_id}: {e}")
            return None
    
    def clear_cache(self):
        """Clear all cached embeddings."""
        if self.cache_dir.exists():
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            print("✓ Cache cleared")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.cache_dir.exists():
            return {
                'cache_enabled': self.use_cache,
                'cached_files': 0,
                'cache_size_mb': 0
            }
        
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_enabled': self.use_cache,
            'cached_files': len(cache_files),
            'cache_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir)
        }


def main():
    """Example usage of EmbeddingManager."""
    from app.ingest.ingestor import RepositoryIngestor
    from app.ingest.chunk_manager import ChunkManager
    from app.ingest.loader import LoadMethod
    
    print("="*70)
    print("Example: Embedding Manager with Caching")
    print("="*70)
    
    # Ingest and chunk repository
    ingestor = RepositoryIngestor()
    ingestion_result = ingestor.ingest_repository(
        repo_url="https://github.com/pallets/flask",
        method=LoadMethod.API
    )
    
    chunk_manager = ChunkManager(
        repo_name=ingestion_result.repo_info.full_name,
        branch=ingestion_result.repo_info.default_branch
    )
    chunking_result = chunk_manager.chunk_ingestion_result(ingestion_result)
    
    # Create embedding manager
    embedding_manager = EmbeddingManager(
        cache_dir=Path("./embedding_cache"),
        use_cache=True,
        batch_size=50
    )
    
    # First run - generate embeddings
    print("\n" + "="*70)
    print("First Run (Generate Embeddings)")
    print("="*70)
    
    # Test with subset
    test_chunks = chunking_result.chunks[:10]
    result1 = embedding_manager.embed_chunks(test_chunks)
    
    # Second run - use cache
    print("\n" + "="*70)
    print("Second Run (Use Cache)")
    print("="*70)
    
    result2 = embedding_manager.embed_chunks(test_chunks)
    
    # Show cache statistics
    cache_stats = embedding_manager.get_cache_statistics()
    print(f"\nCache Statistics:")
    print(f"  Cached files: {cache_stats['cached_files']}")
    print(f"  Cache size: {cache_stats['cache_size_mb']} MB")
    print(f"  Cache dir: {cache_stats['cache_dir']}")
    
    # Show sample metadata
    if result2.metadata:
        print(f"\nSample Metadata:")
        meta = result2.metadata[0]
        print(f"  File: {meta.file_path}")
        print(f"  Lines: {meta.start_line}-{meta.end_line}")
        print(f"  Language: {meta.language}")
        print(f"  Symbol: {meta.symbol}")
        print(f"  Type: {meta.chunk_type}")
        print(f"  Model: {meta.embedding_model}")


if __name__ == "__main__":
    main()
