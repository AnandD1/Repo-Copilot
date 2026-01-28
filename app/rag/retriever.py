"""LangChain retriever combining code and conventions."""

from typing import List, Dict, Any, Optional
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from app.storage.vector_store import QdrantVectorStore
from app.conventions.conventions_store import ConventionsVectorStore
from app.ingest.embedder import Embedder


class HybridRetriever(BaseRetriever):
    """Retriever that searches both code and conventions."""
    
    code_store: QdrantVectorStore
    conventions_store: ConventionsVectorStore
    embedder: Embedder
    code_k: int = 10
    conventions_k: int = 5
    
    def __init__(
        self,
        code_store: Optional[QdrantVectorStore] = None,
        conventions_store: Optional[ConventionsVectorStore] = None,
        embedder: Optional[Embedder] = None,
        code_k: int = 10,
        conventions_k: int = 5
    ):
        """Initialize hybrid retriever.
        
        Args:
            code_store: Code vector store
            conventions_store: Conventions vector store
            embedder: Embedder for queries
            code_k: Number of code chunks to retrieve
            conventions_k: Number of conventions to retrieve
        """
        super().__init__()
        self.code_store = code_store or QdrantVectorStore()
        self.conventions_store = conventions_store or ConventionsVectorStore()
        self.embedder = embedder or Embedder()
        self.code_k = code_k
        self.conventions_k = conventions_k
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None,
        **kwargs
    ) -> List[Document]:
        """Retrieve relevant code and conventions.
        
        Args:
            query: Search query
            run_manager: Callback manager
            **kwargs: Additional retrieval parameters (repo, language, etc.)
        
        Returns:
            List of LangChain Documents
        """
        # Embed query
        query_result = self.embedder.embed_text(query)
        
        documents = []
        
        # Retrieve code chunks
        code_results = self.code_store.similarity_search(
            query_embedding=query_result.embedding,
            limit=kwargs.get('code_k', self.code_k),
            repo=kwargs.get('repo'),
            branch=kwargs.get('branch'),
            language=kwargs.get('language'),
            min_similarity=kwargs.get('min_similarity', 0.0)
        )
        
        for result in code_results:
            doc = Document(
                page_content=result['content'],
                metadata={
                    'source': 'code',
                    'file_path': result['file_path'],
                    'language': result['language'],
                    'chunk_type': result['chunk_type'],
                    'symbol': result['symbol'],
                    'start_line': result['start_line'],
                    'end_line': result['end_line'],
                    'similarity': result['similarity'],
                    'repo': result['repo'],
                    'branch': result['branch']
                }
            )
            documents.append(doc)
        
        # Retrieve conventions
        conventions_results = self.conventions_store.search_conventions(
            query_embedding=query_result.embedding,
            limit=kwargs.get('conventions_k', self.conventions_k),
            category=kwargs.get('category'),
            language=kwargs.get('language'),
            repo=kwargs.get('repo'),
            min_similarity=kwargs.get('min_similarity', 0.0)
        )
        
        for result in conventions_results:
            # Format convention as document
            content_parts = [f"Convention: {result['title']}"]
            content_parts.append(f"Category: {result['category']}")
            content_parts.append(f"Description: {result['description']}")
            
            if result.get('example_good'):
                content_parts.append(f"Good Example:\n{result['example_good']}")
            
            if result.get('example_bad'):
                content_parts.append(f"Bad Example:\n{result['example_bad']}")
            
            doc = Document(
                page_content="\n\n".join(content_parts),
                metadata={
                    'source': 'convention',
                    'convention_id': result.get('convention_id'),
                    'category': result['category'],
                    'severity': result['severity'],
                    'rule_id': result.get('rule_id'),
                    'similarity': result['similarity'],
                    'language': result.get('language'),
                    'file_source': result.get('source')
                }
            )
            documents.append(doc)
        
        return documents
    
    def get_code_context(
        self,
        file_path: str,
        repo: str,
        branch: str = "main",
        limit: int = 5
    ) -> List[Document]:
        """Get code context for a specific file.
        
        Args:
            file_path: File path to get context for
            repo: Repository name
            branch: Branch name
            limit: Maximum chunks
        
        Returns:
            List of Documents from the file
        """
        # Search by exact file path
        scroll_result = self.code_store.client.scroll(
            collection_name=self.code_store.collection_name,
            scroll_filter={
                "must": [
                    {"key": "file_path", "match": {"value": file_path}},
                    {"key": "repo", "match": {"value": repo}},
                    {"key": "branch", "match": {"value": branch}}
                ]
            },
            limit=limit,
            with_payload=True
        )
        
        documents = []
        for point in scroll_result[0]:
            doc = Document(
                page_content=point.payload['content'],
                metadata={
                    'source': 'code',
                    'file_path': point.payload['file_path'],
                    'language': point.payload['language'],
                    'start_line': point.payload['start_line'],
                    'end_line': point.payload['end_line'],
                    'symbol': point.payload.get('symbol'),
                }
            )
            documents.append(doc)
        
        return documents
    
    def close(self):
        """Close store connections."""
        self.code_store.close()
        self.conventions_store.close()
