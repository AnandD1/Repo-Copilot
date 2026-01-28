"""Conventions retriever using project rules index."""

import hashlib
from typing import Optional

from ..conventions.conventions_store import ConventionsVectorStore
from ..ingest.embedder import Embedder
from .evidence import Evidence, EvidenceType


class ConventionsRetriever:
    """Retrieves relevant project conventions and rules.
    
    Uses existing conventions vector store.
    Returns conventions as Evidence objects for consistency.
    """
    
    def __init__(
        self,
        conventions_store: ConventionsVectorStore,
        embedder: Embedder,
    ):
        """Initialize retriever with conventions store and embedder.
        
        Args:
            conventions_store: ConventionsVectorStore instance
            embedder: Embedder instance for query embedding
        """
        self.conventions_store = conventions_store
        self.embedder = embedder
    
    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
        language: Optional[str] = None,
        min_similarity: float = 0.6,
    ) -> list[Evidence]:
        """Retrieve relevant conventions.
        
        Args:
            query: Code snippet or description to find conventions for
            top_k: Maximum number of conventions to return
            category: Filter by category (e.g., "style", "security")
            language: Filter by programming language
            min_similarity: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            List of Evidence objects containing conventions
        """
        # Embed query
        query_embedding = self.embedder.embed_text(query)
        
        # Search conventions store
        results = self.conventions_store.search_conventions(
            query_embedding=query_embedding.embedding,  # Extract embedding vector
            limit=top_k,
            category=category,
            language=language,
            min_similarity=min_similarity,
        )
        
        # Convert to Evidence objects
        evidence_list = []
        
        for result in results:
            # Result structure is flat (no nested metadata)
            rule_text = result.get("rule_text", "")
            source_file = result.get("source_file", "CONVENTIONS.md")
            category_str = result.get("category", "general")
            similarity_score = result.get("similarity", 0.0)
            
            # For conventions, we use the source file as file_path
            # Line numbers represent the convention's position in source
            start_line = result.get("line_number", 1)
            end_line = start_line
            
            # Generate snippet ID
            snippet_hash = hashlib.md5(rule_text.encode()).hexdigest()[:8]
            snippet_id = f"convention_{category_str}_{snippet_hash}"
            
            # Format content with category prefix
            formatted_content = f"[{category_str.upper()}] {rule_text}"
            
            evidence = Evidence(
                evidence_type=EvidenceType.CONVENTION,
                file_path=source_file,
                start_line=start_line,
                end_line=end_line,
                content=formatted_content,
                similarity_score=similarity_score,
                snippet_id=snippet_id,
            )
            
            evidence_list.append(evidence)
        
        return evidence_list
