"""Manage conventions extraction, embedding, and storage."""

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from .conventions_ingestor import ConventionsIngestor, Convention
from .conventions_store import ConventionsVectorStore
from app.ingest.embedder import Embedder


@dataclass
class ConventionsResult:
    """Result of conventions processing."""
    total_conventions: int
    by_category: dict
    by_severity: dict
    conventions_stored: int
    repo: str
    branch: str


class ConventionsManager:
    """High-level manager for conventions memory."""
    
    def __init__(
        self,
        vector_store: Optional[ConventionsVectorStore] = None,
        embedder: Optional[Embedder] = None
    ):
        """Initialize conventions manager.
        
        Args:
            vector_store: Conventions vector store (creates new if None)
            embedder: Embedder for conventions (creates new if None)
        """
        self.vector_store = vector_store or ConventionsVectorStore()
        self.embedder = embedder or Embedder()
    
    def process_repository_conventions(
        self,
        repo_path: Path,
        repo_name: str,
        branch: str = "main"
    ) -> ConventionsResult:
        """Extract, embed, and store conventions from repository.
        
        Args:
            repo_path: Path to repository
            repo_name: Repository full name (e.g., "owner/repo")
            branch: Branch name
        
        Returns:
            ConventionsResult with statistics
        """
        # Extract conventions
        ingestor = ConventionsIngestor(repo_path)
        conventions = ingestor.extract_all_conventions()
        
        if not conventions:
            return ConventionsResult(
                total_conventions=0,
                by_category={},
                by_severity={},
                conventions_stored=0,
                repo=repo_name,
                branch=branch
            )
        
        # Generate embeddings for conventions (batched for efficiency)
        convention_texts = [
            self._format_convention_for_embedding(conv) 
            for conv in conventions
        ]
        
        # Batch embeddings - no rate limits with local model
        embeddings = []
        batch_size = 50  # Process in reasonable batches
        
        print(f"  Embedding {len(convention_texts)} conventions in batches of {batch_size}...")
        
        for i in range(0, len(convention_texts), batch_size):
            batch = convention_texts[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(convention_texts) + batch_size - 1) // batch_size
            
            print(f"  Processing batch {batch_num}/{total_batches}...")
            
            # Embed batch (no delays needed for local embeddings)
            for text in batch:
                result = self.embedder.embed_text(text)
                embeddings.append(result.embedding)
        
        # Store in vector database
        stored = self.vector_store.insert_conventions(
            conventions=conventions,
            embeddings=embeddings,
            repo=repo_name,
            branch=branch,
            upsert=True
        )
        
        # Calculate statistics
        by_category = {}
        by_severity = {}
        
        for conv in conventions:
            by_category[conv.category] = by_category.get(conv.category, 0) + 1
            by_severity[conv.severity] = by_severity.get(conv.severity, 0) + 1
        
        return ConventionsResult(
            total_conventions=len(conventions),
            by_category=by_category,
            by_severity=by_severity,
            conventions_stored=stored,
            repo=repo_name,
            branch=branch
        )
    
    def get_relevant_conventions(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> List[Convention]:
        """Get conventions relevant to a query.
        
        Args:
            query: Search query (e.g., "function naming", "error handling")
            limit: Maximum results
            category: Filter by category
            language: Filter by language
        
        Returns:
            List of relevant Convention objects
        """
        # Embed query
        query_result = self.embedder.embed_text(query)
        
        # Search conventions
        results = self.vector_store.search_conventions(
            query_embedding=query_result.embedding,
            limit=limit,
            category=category,
            language=language
        )
        
        # Convert back to Convention objects
        conventions = []
        for result in results:
            convention = Convention(
                source=result['source'],
                category=result['category'],
                rule_id=result.get('rule_id'),
                title=result['title'],
                description=result['description'],
                example_good=result.get('example_good'),
                example_bad=result.get('example_bad'),
                severity=result['severity'],
                language=result.get('language'),
                metadata={
                    **result.get('metadata', {}),
                    'similarity': result['similarity']
                }
            )
            conventions.append(convention)
        
        return conventions
    
    def _format_convention_for_embedding(self, convention: Convention) -> str:
        """Format convention for embedding.
        
        Creates a rich text representation combining all convention fields.
        """
        parts = [
            f"Title: {convention.title}",
            f"Category: {convention.category}",
            f"Description: {convention.description}",
        ]
        
        if convention.rule_id:
            parts.append(f"Rule ID: {convention.rule_id}")
        
        if convention.language:
            parts.append(f"Language: {convention.language}")
        
        if convention.example_good:
            parts.append(f"Good Example: {convention.example_good}")
        
        if convention.example_bad:
            parts.append(f"Bad Example: {convention.example_bad}")
        
        return "\n".join(parts)
    
    def get_statistics(self) -> dict:
        """Get conventions statistics from vector store."""
        return self.vector_store.get_statistics()
    
    def close(self):
        """Close resources."""
        self.vector_store.close()
