"""Qdrant vector store for embeddings."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
)

from app.ingest.embedder import EmbeddingResult
from app.ingest.embedding_manager import EmbeddingMetadata
from config.settings import settings


class QdrantVectorStore:
    """
    Qdrant vector store for code embeddings.
    
    Features:
    - Efficient vector similarity search with HNSW
    - Full metadata storage for PR review
    - Automatic collection creation
    - Filtering by repo, branch, file, language
    - Payload indexing for fast filtered searches
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            url: Qdrant server URL (uses settings if not provided)
            api_key: Qdrant API key for cloud (uses settings if not provided)
            collection_name: Collection name (uses settings if not provided)
        """
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.collection_name = collection_name or settings.qdrant_collection_name
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60,
            prefer_grpc=False  # Use REST API for better compatibility
        )
        
        # Initialize collection
        self._init_collection()
    
    def _init_collection(self):
        """Initialize Qdrant collection with proper configuration."""
        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)
        
        if not collection_exists:
            # Create collection with vector configuration
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,  # 3072 for Gemini
                    distance=Distance.COSINE
                )
            )
            
            # Create payload indexes for fast filtering
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="chunk_id",
                field_schema="keyword"
            )
            
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="repo",
                field_schema="keyword"
            )
            
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="branch",
                field_schema="keyword"
            )
            
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="file_path",
                field_schema="keyword"
            )
            
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="language",
                field_schema="keyword"
            )
            
            print(f"✓ Created Qdrant collection '{self.collection_name}'")
        else:
            print(f"✓ Using existing Qdrant collection '{self.collection_name}'")
    
    def insert_embeddings(
        self,
        embeddings: List[EmbeddingResult],
        metadata_list: List[EmbeddingMetadata],
        contents: List[str],
        upsert: bool = True
    ) -> int:
        """
        Insert embeddings into Qdrant.
        
        Args:
            embeddings: List of embedding results
            metadata_list: List of embedding metadata
            contents: List of chunk contents
            upsert: If True, update existing points with same chunk_id
        
        Returns:
            Number of points inserted
        """
        if (not embeddings) or (len(embeddings) != len(metadata_list)) or (len(embeddings) != len(contents)):
            raise ValueError("Embeddings, metadata, and contents must have same length")
        
        # Prepare points for upload
        points = []
        
        for emb, meta, content in zip(embeddings, metadata_list, contents):
            # Validate dimension
            if len(emb.embedding) != settings.embedding_dimension:
                print(f"Warning: Skipping {meta.chunk_id} - dimension mismatch")
                continue
            
            # Create payload with all metadata
            payload = {
                "chunk_id": meta.chunk_id,
                "chunk_index": meta.chunk_index,
                "repo": meta.repo,
                "branch": meta.branch,
                "file_path": meta.file_path,
                "language": meta.language,
                "start_line": meta.start_line,
                "end_line": meta.end_line,
                "chunk_type": meta.chunk_type,
                "symbol": meta.symbol,
                "imports": meta.imports,
                "embedding_model": meta.embedding_model,
                "embedding_dimension": meta.embedding_dimension,
                "token_count": meta.token_count,
                "content_hash": meta.content_hash,
                "content": content,
                "created_at": datetime.now().isoformat()
            }
            
            # Use chunk_id as deterministic point ID for upsert
            # This ensures same chunk_id always maps to same point
            point_id = str(uuid4()) if not upsert else self._chunk_id_to_uuid(meta.chunk_id)
            
            points.append(PointStruct(
                id=point_id,
                vector=emb.embedding,
                payload=payload
            ))
        
        if not points:
            return 0
        
        # Upsert points (inserts new or updates existing)
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return len(points)
    
    def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings using cosine similarity.
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            repo: Filter by repository name
            branch: Filter by branch name
            file_path: Filter by file path (substring match)
            language: Filter by programming language
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            List of results with metadata and similarity scores
        """
        if len(query_embedding) != settings.embedding_dimension:
            raise ValueError(f"Query embedding must be {settings.embedding_dimension}D")
        
        # Build filter conditions
        must_conditions = []
        
        if repo:
            must_conditions.append(
                FieldCondition(key="repo", match=MatchValue(value=repo))
            )
        
        if branch:
            must_conditions.append(
                FieldCondition(key="branch", match=MatchValue(value=branch))
            )
        
        if file_path:
            must_conditions.append(
                FieldCondition(key="file_path", match=MatchValue(value=file_path))
            )
        
        if language:
            must_conditions.append(
                FieldCondition(key="language", match=MatchValue(value=language))
            )
        
        # Create filter
        search_filter = Filter(must=must_conditions) if must_conditions else None
        
        # Search using query_points (newer API)
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=search_filter,
            limit=limit,
            score_threshold=min_similarity if min_similarity > 0 else None,
            with_payload=True
        )
        
        # Convert to dict format
        results = []
        for point in search_results.points:
            result = dict(point.payload)
            result['similarity'] = point.score
            result['id'] = point.id
            results.append(result)
        
        return results
    
    def get_by_chunk_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a chunk by its chunk_id.
        
        Args:
            chunk_id: Unique chunk identifier
        
        Returns:
            Chunk data or None if not found
        """
        # Search by chunk_id in payload
        search_results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
            ),
            limit=1
        )
        
        if search_results[0]:
            point = search_results[0][0]
            result = dict(point.payload)
            result['id'] = point.id
            return result
        
        return None
    
    def delete_by_repo(self, repo: str, branch: Optional[str] = None) -> int:
        """
        Delete all chunks for a repository.
        
        Args:
            repo: Repository name
            branch: Optional branch name (deletes all branches if None)
        
        Returns:
            Number of points deleted (estimated)
        """
        # Build filter
        must_conditions = [
            FieldCondition(key="repo", match=MatchValue(value=repo))
        ]
        
        if branch:
            must_conditions.append(
                FieldCondition(key="branch", match=MatchValue(value=branch))
            )
        
        # Count points before deletion
        count_result = self.client.count(
            collection_name=self.collection_name,
            count_filter=Filter(must=must_conditions)
        )
        
        # Delete points
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(must=must_conditions)
        )
        
        return count_result.count
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dictionary with statistics
        """
        # Get collection info
        collection_info = self.client.get_collection(self.collection_name)
        
        # Get sample points to analyze
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=1000,  # Sample first 1000
            with_payload=True
        )
        
        points = scroll_result[0]
        
        # Aggregate statistics
        by_repo = {}
        by_language = {}
        
        for point in points:
            repo = point.payload.get('repo')
            language = point.payload.get('language')
            
            if repo:
                by_repo[repo] = by_repo.get(repo, 0) + 1
            
            if language:
                by_language[language] = by_language.get(language, 0) + 1
        
        return {
            'total_chunks': collection_info.points_count,
            'vector_dimension': collection_info.config.params.vectors.size,
            'by_repo': dict(sorted(by_repo.items(), key=lambda x: x[1], reverse=True)),
            'by_language': dict(sorted(by_language.items(), key=lambda x: x[1], reverse=True)),
            'indexed_vectors': collection_info.indexed_vectors_count,
            'status': collection_info.status
        }
    
    def _chunk_id_to_uuid(self, chunk_id: str) -> str:
        """
        Convert chunk_id to deterministic UUID for upsert.
        Uses MD5 hash of chunk_id to generate consistent UUID.
        """
        import hashlib
        from uuid import UUID
        hash_bytes = hashlib.md5(chunk_id.encode('utf-8')).digest()
        # Convert to UUID format (MD5 produces 16 bytes, perfect for UUID)
        return str(UUID(bytes=hash_bytes))
    
    def close(self):
        """Close Qdrant client connection."""
        self.client.close()
        print("✓ Qdrant client closed")


def main():
    """Example usage of QdrantVectorStore."""
    from app.ingest.ingestor import RepositoryIngestor
    from app.ingest.chunk_manager import ChunkManager
    from app.ingest.embedding_manager import EmbeddingManager
    from app.ingest.loader import LoadMethod
    
    print("="*70)
    print("Example: Qdrant Vector Store")
    print("="*70)
    
    # Ingest and embed repository
    print("\n1. Ingesting repository...")
    ingestor = RepositoryIngestor()
    ingestion_result = ingestor.ingest_repository(
        repo_url="https://github.com/pallets/flask",
        method=LoadMethod.API
    )
    
    print("\n2. Chunking files...")
    chunk_manager = ChunkManager(
        repo_name=ingestion_result.repo_info.full_name,
        branch=ingestion_result.repo_info.default_branch
    )
    chunking_result = chunk_manager.chunk_ingestion_result(ingestion_result)
    
    print("\n3. Generating embeddings...")
    embedding_manager = EmbeddingManager(use_cache=True)
    
    # Test with small subset
    test_chunks = chunking_result.chunks[:10]
    embedding_result = embedding_manager.embed_chunks(test_chunks)
    
    print("\n4. Storing in Qdrant...")
    vector_store = QdrantVectorStore()
    
    # Extract contents from chunks
    contents = [chunk.content for chunk in test_chunks]
    
    points_inserted = vector_store.insert_embeddings(
        embedding_result.embeddings,
        embedding_result.metadata,
        contents,
        upsert=True
    )
    
    print(f"✓ Inserted {points_inserted} embeddings")
    
    print("\n5. Testing similarity search...")
    if embedding_result.embeddings:
        # Use first embedding as query
        query_vector = embedding_result.embeddings[0].embedding
        
        results = vector_store.similarity_search(
            query_embedding=query_vector,
            limit=5,
            repo=ingestion_result.repo_info.full_name
        )
        
        print(f"\nTop 5 similar chunks:")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. {result['file_path']} (lines {result['start_line']}-{result['end_line']})")
            print(f"     Similarity: {result['similarity']:.4f}")
            print(f"     Symbol: {result['symbol']}")
    
    print("\n6. Collection statistics:")
    stats = vector_store.get_statistics()
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Indexed vectors: {stats['indexed_vectors']}")
    print(f"  Status: {stats['status']}")
    
    vector_store.close()


if __name__ == "__main__":
    main()
