"""Similar code retriever using vector search over repository index."""

import hashlib
from typing import Optional

from ..storage.vector_store import QdrantVectorStore
from ..ingest.embedder import Embedder
from .evidence import Evidence, EvidenceType


class SimilarCodeRetriever:
    """Retrieves similar code snippets using vector search.
    
    Uses existing Qdrant vector store with code embeddings.
    Deduplicates results by chunk_id to avoid redundant evidence.
    """
    
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        embedder: Embedder,
    ):
        """Initialize retriever with vector store and embedder.
        
        Args:
            vector_store: Qdrant vector store instance
            embedder: Embedder instance for query embedding
        """
        self.vector_store = vector_store
        self.embedder = embedder
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        repo: Optional[str] = None,
        exclude_file: Optional[str] = None,
        min_similarity: float = 0.7,
    ) -> list[Evidence]:
        """Retrieve similar code snippets.
        
        Args:
            query: Code snippet or description to search for
            top_k: Maximum number of results
            repo: Filter by repository name
            exclude_file: Exclude results from this file path
            min_similarity: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            List of Evidence objects sorted by similarity score
        """
        # Embed query
        query_embedding = self.embedder.embed_text(query)
        
        # Search vector store
        results = self.vector_store.similarity_search(
            query_embedding=query_embedding.embedding,  # Extract embedding vector
            limit=top_k * 2,  # Get extra for deduplication
            repo=repo,
            min_similarity=min_similarity,
        )
        
        # Convert to Evidence objects with deduplication
        evidence_list = []
        seen_chunk_ids = set()
        
        for result in results:
            chunk_id = result.get("chunk_id", "")
            file_path = result.get("file_path", "")
            
            # Skip duplicates
            if chunk_id in seen_chunk_ids:
                continue
            
            # Skip if from excluded file
            if exclude_file and file_path == exclude_file:
                continue
            
            seen_chunk_ids.add(chunk_id)
            
            # Extract metadata
            content = result.get("content", "")
            start_line = result.get("start_line", 1)
            end_line = result.get("end_line", start_line)
            similarity_score = result.get("similarity", 0.0)
            
            # Generate snippet ID from chunk_id
            snippet_hash = hashlib.md5(chunk_id.encode()).hexdigest()[:8]
            snippet_id = f"similar_{snippet_hash}"
            
            evidence = Evidence(
                evidence_type=EvidenceType.SIMILAR_CODE,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=content,
                similarity_score=similarity_score,
                snippet_id=snippet_id,
            )
            
            evidence_list.append(evidence)
            
            # Stop when we have enough
            if len(evidence_list) >= top_k:
                break
        
        return evidence_list
