"""Qdrant vector store for conventions."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4, UUID

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from config.settings import settings
from .conventions_ingestor import Convention


class ConventionsVectorStore:
    """Separate Qdrant collection for conventions memory."""
    
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: str = "conventions_index"
    ):
        """Initialize conventions vector store.
        
        Args:
            url: Qdrant server URL (uses settings if not provided)
            api_key: Qdrant API key for cloud (uses settings if not provided)
            collection_name: Collection name for conventions
        """
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.collection_name = collection_name
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60,
            prefer_grpc=False
        )
        
        # Initialize collection
        self._init_collection()
    
    def _init_collection(self):
        """Initialize conventions collection."""
        collections = self.client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)
        
        if not collection_exists:
            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE
                )
            )
            
            # Create payload indexes
            for field in ["category", "severity", "language", "source", "rule_id", "repo", "branch"]:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword"
                )
            
            print(f"✓ Created conventions collection '{self.collection_name}'")
        else:
            print(f"✓ Using existing conventions collection '{self.collection_name}'")
    
    def insert_conventions(
        self,
        conventions: List[Convention],
        embeddings: List[List[float]],
        repo: str,
        branch: str,
        upsert: bool = True
    ) -> int:
        """Insert conventions with embeddings.
        
        Args:
            conventions: List of Convention objects
            embeddings: List of embedding vectors
            repo: Repository name
            branch: Branch name
            upsert: If True, update existing conventions
        
        Returns:
            Number of points inserted
        """
        if (not conventions) or (len(conventions) != len(embeddings)):
            raise ValueError("Conventions and embeddings must have same length")
        
        points = []
        
        for convention, embedding in zip(conventions, embeddings):
            if len(embedding) != settings.embedding_dimension:
                print(f"Warning: Skipping {convention.title} - dimension mismatch")
                continue
            
            # Create unique convention ID
            convention_id = f"{repo}:{branch}:{convention.source}:{convention.rule_id or convention.title}"
            
            payload = {
                "convention_id": convention_id,
                "repo": repo,
                "branch": branch,
                "source": convention.source,
                "category": convention.category,
                "rule_id": convention.rule_id,
                "title": convention.title,
                "description": convention.description,
                "example_good": convention.example_good,
                "example_bad": convention.example_bad,
                "severity": convention.severity,
                "language": convention.language,
                "metadata": convention.metadata or {},
                "created_at": datetime.now().isoformat()
            }
            
            # Generate deterministic UUID from convention_id
            point_id = str(uuid4()) if not upsert else self._convention_id_to_uuid(convention_id)
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            ))
        
        if not points:
            return 0
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return len(points)
    
    def search_conventions(
        self,
        query_embedding: List[float],
        limit: int = 10,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        language: Optional[str] = None,
        repo: Optional[str] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Search for relevant conventions.
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            category: Filter by category
            severity: Filter by severity
            language: Filter by language
            repo: Filter by repository
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of matching conventions with scores
        """
        if len(query_embedding) != settings.embedding_dimension:
            raise ValueError(f"Query embedding must be {settings.embedding_dimension}D")
        
        # Build filters
        must_conditions = []
        
        if category:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )
        
        if severity:
            must_conditions.append(
                FieldCondition(key="severity", match=MatchValue(value=severity))
            )
        
        if language:
            must_conditions.append(
                FieldCondition(key="language", match=MatchValue(value=language))
            )
        
        if repo:
            must_conditions.append(
                FieldCondition(key="repo", match=MatchValue(value=repo))
            )
        
        search_filter = Filter(must=must_conditions) if must_conditions else None
        
        # Search
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=search_filter,
            limit=limit,
            score_threshold=min_similarity if min_similarity > 0 else None,
            with_payload=True
        )
        
        # Convert to dict
        results = []
        for point in search_results.points:
            result = dict(point.payload)
            result['similarity'] = point.score
            result['id'] = point.id
            results.append(result)
        
        return results
    
    def get_by_category(self, category: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all conventions in a category.
        
        Args:
            category: Convention category
            limit: Maximum results
        
        Returns:
            List of conventions
        """
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            ),
            limit=limit,
            with_payload=True
        )
        
        results = []
        for point in scroll_result[0]:
            result = dict(point.payload)
            result['id'] = point.id
            results.append(result)
        
        return results
    
    def delete_by_repo(self, repo: str, branch: Optional[str] = None) -> int:
        """Delete conventions for a repository.
        
        Args:
            repo: Repository name
            branch: Optional branch name
        
        Returns:
            Number of conventions deleted
        """
        must_conditions = [
            FieldCondition(key="repo", match=MatchValue(value=repo))
        ]
        
        if branch:
            must_conditions.append(
                FieldCondition(key="branch", match=MatchValue(value=branch))
            )
        
        # Count before deletion
        count_result = self.client.count(
            collection_name=self.collection_name,
            count_filter=Filter(must=must_conditions)
        )
        
        # Delete
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(must=must_conditions)
        )
        
        return count_result.count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get conventions statistics.
        
        Returns:
            Dictionary with statistics
        """
        collection_info = self.client.get_collection(self.collection_name)
        
        # Sample conventions
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=1000,
            with_payload=True
        )
        
        points = scroll_result[0]
        
        # Aggregate stats
        by_category = {}
        by_severity = {}
        by_language = {}
        by_repo = {}
        
        for point in points:
            category = point.payload.get('category')
            severity = point.payload.get('severity')
            language = point.payload.get('language')
            repo = point.payload.get('repo')
            
            if category:
                by_category[category] = by_category.get(category, 0) + 1
            if severity:
                by_severity[severity] = by_severity.get(severity, 0) + 1
            if language:
                by_language[language] = by_language.get(language, 0) + 1
            if repo:
                by_repo[repo] = by_repo.get(repo, 0) + 1
        
        return {
            'total_conventions': collection_info.points_count,
            'by_category': dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
            'by_severity': dict(sorted(by_severity.items(), key=lambda x: x[1], reverse=True)),
            'by_language': dict(sorted(by_language.items(), key=lambda x: x[1], reverse=True)),
            'by_repo': dict(sorted(by_repo.items(), key=lambda x: x[1], reverse=True)),
        }
    
    def _convention_id_to_uuid(self, convention_id: str) -> str:
        """Convert convention_id to deterministic UUID."""
        import hashlib
        hash_bytes = hashlib.md5(convention_id.encode('utf-8')).digest()
        return str(UUID(bytes=hash_bytes))
    
    def close(self):
        """Close client connection."""
        self.client.close()
        print("✓ Conventions store closed")
