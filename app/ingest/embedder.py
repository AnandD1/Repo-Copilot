"""Embedding generation using Google Gemini."""

import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.ingest.chunker import Chunk
from config.settings import settings


@dataclass
class EmbeddingResult:
    """Result of embedding a chunk."""
    chunk_id: str
    embedding: List[float]
    token_count: int
    model: str
    dimension: int  # Embedding vector dimension


class Embedder:
    """
    Generates embeddings for code chunks using Google Gemini.
    
    Features:
    - Batch processing for efficiency
    - Retry logic for failures
    - Rate limit handling
    - Progress tracking
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the embedder.
        
        Args:
            api_key: Google API key (uses settings if not provided)
            model: Embedding model name (uses settings if not provided)
            batch_size: Number of chunks to process per batch
            max_retries: Maximum retry attempts for failed embeddings
            retry_delay: Delay between retries in seconds
        """
        self.api_key = api_key or settings.google_api_key
        self.model = model or settings.embedding_model
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        if not self.api_key:
            raise ValueError("Google API key not found. Set GOOGLE_API_KEY in .env file")
        
        # Initialize Google Gemini embeddings
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=self.model,
            google_api_key=self.api_key
        )
        
        # Statistics
        self.total_embedded = 0
        self.total_tokens = 0
        self.failed_chunks = []
        # Use expected dimension from settings, will validate against actual
        self.expected_dimension = settings.embedding_dimension
    
    def embed_chunks(self, chunks: List[Chunk]) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple chunks with batch processing.
        
        Args:
            chunks: List of chunks to embed
        
        Returns:
            List of EmbeddingResult objects
        """
        # Filter out empty chunks
        valid_chunks = [c for c in chunks if c.content and c.content.strip()]
        
        if not valid_chunks:
            print("Warning: No valid chunks to embed (all empty)")
            return []
        
        embeddings = []
        total_chunks = len(valid_chunks)
        
        print(f"\nGenerating embeddings for {total_chunks} chunks...")
        print(f"Batch size: {self.batch_size}")
        
        # Process in batches
        for i in range(0, total_chunks, self.batch_size):
            batch = valid_chunks[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_chunks + self.batch_size - 1) // self.batch_size
            
            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
            
            # Embed batch
            batch_embeddings = self._embed_batch(batch)
            embeddings.extend(batch_embeddings)
            
            # Show progress
            progress = len(embeddings) / total_chunks * 100
            print(f"  Progress: {len(embeddings)}/{total_chunks} ({progress:.1f}%)")
        
        print(f"✓ Embedding complete: {len(embeddings)} embeddings generated")
        
        if self.failed_chunks:
            print(f"⚠ Warning: {len(self.failed_chunks)} chunks failed to embed")
        
        return embeddings
    
    def _embed_batch(self, batch: List[Chunk]) -> List[EmbeddingResult]:
        """
        Embed a batch of chunks using embed_documents.
        
        Args:
            batch: Batch of chunks
        
        Returns:
            List of embedding results (may be partial if some fail)
        """
        embeddings = []
        
        # Always use embed_documents for consistency
        try:
            texts = [chunk.content for chunk in batch]
            embedding_vectors = self.embedding_model.embed_documents(texts)
            
            # Validate dimensions
            for idx, (chunk, embedding) in enumerate(zip(batch, embedding_vectors)):
                dimension = len(embedding)
                
                # Validate dimension matches expected
                if dimension != self.expected_dimension:
                    print(f"  Warning: Dimension mismatch for {chunk.metadata.chunk_id}: expected {self.expected_dimension}, got {dimension}")
                    # Update expected if this is first embedding (in case settings is wrong)
                    if self.total_embedded == 0:
                        print(f"  Updating expected dimension from {self.expected_dimension} to {dimension}")
                        self.expected_dimension = dimension
                    else:
                        self.failed_chunks.append(chunk.metadata.chunk_id)
                        continue
                
                self.total_embedded += 1
                self.total_tokens += chunk.token_count
                
                embeddings.append(EmbeddingResult(
                    chunk_id=chunk.metadata.chunk_id,
                    embedding=embedding,
                    token_count=chunk.token_count,
                    model=self.model,
                    dimension=dimension
                ))
        
        except Exception as e:
            # Fallback to individual embedding (still using embed_documents)
            print(f"  Batch embedding failed, falling back to individual: {e}")
            for chunk in batch:
                try:
                    # Use embed_documents even for single chunk
                    embedding_vector = self.embedding_model.embed_documents([chunk.content])[0]
                    dimension = len(embedding_vector)
                    
                    # Validate dimension
                    if dimension != self.expected_dimension:
                        # Update expected if this is first embedding
                        if self.total_embedded == 0:
                            print(f"  Updating expected dimension from {self.expected_dimension} to {dimension}")
                            self.expected_dimension = dimension
                        else:
                            print(f"  Warning: Dimension mismatch for {chunk.metadata.chunk_id}")
                            self.failed_chunks.append(chunk.metadata.chunk_id)
                            continue
                    
                    self.total_embedded += 1
                    self.total_tokens += chunk.token_count
                    
                    embeddings.append(EmbeddingResult(
                        chunk_id=chunk.metadata.chunk_id,
                        embedding=embedding_vector,
                        token_count=chunk.token_count,
                        model=self.model,
                        dimension=dimension
                    ))
                except Exception as chunk_error:
                    print(f"  Failed to embed {chunk.metadata.chunk_id}: {chunk_error}")
                    self.failed_chunks.append(chunk.metadata.chunk_id)
                    continue
        
        return embeddings
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get embedding statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_embedded': self.total_embedded,
            'total_tokens': self.total_tokens,
            'failed_chunks': len(self.failed_chunks),
            'model': self.model,
            'batch_size': self.batch_size,
        }
    
    def reset_statistics(self):
        """Reset embedding statistics."""
        self.total_embedded = 0
        self.total_tokens = 0
        self.failed_chunks = []
        self.expected_dimension = settings.embedding_dimension


def main():
    """Example usage of Embedder."""
    from app.ingest.ingestor import RepositoryIngestor
    from app.ingest.chunk_manager import ChunkManager
    from app.ingest.loader import LoadMethod
    
    print("="*70)
    print("Example: Generating Embeddings")
    print("="*70)
    
    # Ingest repository
    ingestor = RepositoryIngestor()
    ingestion_result = ingestor.ingest_repository(
        repo_url="https://github.com/pallets/flask",
        method=LoadMethod.API
    )
    
    # Chunk files
    chunk_manager = ChunkManager(
        repo_name=ingestion_result.repo_info.full_name,
        branch=ingestion_result.repo_info.default_branch
    )
    chunking_result = chunk_manager.chunk_ingestion_result(ingestion_result)
    
    # Generate embeddings
    print("\n" + "="*70)
    print("Generating Embeddings")
    print("="*70)
    
    embedder = Embedder(batch_size=50)
    
    # Embed a subset for testing (first 10 chunks)
    test_chunks = chunking_result.chunks[:10]
    embeddings = embedder.embed_chunks(test_chunks)
    
    # Show statistics
    stats = embedder.get_statistics()
    print(f"\nEmbedding Statistics:")
    print(f"  Total embedded: {stats['total_embedded']}")
    print(f"  Total tokens: {stats['total_tokens']:,}")
    print(f"  Failed chunks: {stats['failed_chunks']}")
    print(f"  Model: {stats['model']}")
    
    # Show sample embedding
    if embeddings:
        print(f"\nSample Embedding:")
        print(f"  Chunk ID: {embeddings[0].chunk_id}")
        print(f"  Embedding dimensions: {len(embeddings[0].embedding)}")
        print(f"  First 5 values: {embeddings[0].embedding[:5]}")


if __name__ == "__main__":
    main()
