"""Node 1: Retriever Agent - Retrieve relevant context for each hunk."""

from typing import Dict, Any, List

from .state import WorkflowState, RetrievalBundle


class RetrieverAgent:
    """Agent responsible for retrieving relevant context for code review."""
    
    def __init__(self):
        """Initialize retriever agent."""
        # Simplified initialization - full RAG integration in future
        # For now, works without vector store (empty retrievals)
        self.vector_store = None
        try:
            from app.storage import QdrantVectorStore
            from app.ingest.embedder import Embedder
            self.vector_store = QdrantVectorStore()
            self.embedder = Embedder()
        except Exception as e:
            print(f"  ⚠ Vector store not available: {e}")
            print(f"  ⚠ Retriever will return empty contexts")
    
    def retrieve_for_hunk(
        self,
        hunk: Dict[str, Any],
        repo_id: str,
        style_guide_chunks: List[Dict[str, Any]] = None
    ) -> RetrievalBundle:
        """
        Retrieve context for a single hunk.
        
        Args:
            hunk: Hunk dictionary with file_path, added_lines, removed_lines, etc.
            repo_id: Repository identifier for vector search
            style_guide_chunks: Optional pre-loaded style guide chunks
            
        Returns:
            RetrievalBundle with local, similar, and convention context
        """
        file_path = hunk.get("file_path", "")
        hunk_id = hunk.get("hunk_id", f"{file_path}:{hunk.get('new_line_start', 0)}")
        
        # Extract the code change for querying
        added_lines = hunk.get("added_lines", [])
        removed_lines = hunk.get("removed_lines", [])
        context_lines = hunk.get("context_lines", [])
        
        # Combine for query
        query_text = "\n".join(added_lines + removed_lines[:3])  # Focus on added + some removed
        
        # Simplified retrieval for demo
        # TODO: Integrate full RAG retrieval when vector store is populated
        local_results = []
        similar_results = []
        convention_results = []
        
        # Only attempt retrieval if vector store is available
        if self.vector_store and query_text.strip():
            try:
                query_embedding = self.embedder.embed_text(query_text)
                
                # Search in vector store
                search_results = self.vector_store.similarity_search(
                    query_embedding=query_embedding.embedding,
                    limit=5,
                    repo=repo_id,
                    min_similarity=0.7,
                )
                
                # Format results
                for result in search_results[:3]:
                    similar_results.append({
                        "content": result.get("content", ""),
                        "metadata": {
                            "file_path": result.get("file_path", ""),
                            "start_line": result.get("start_line", 0),
                            "end_line": result.get("end_line", 0),
                            "similarity": result.get("similarity", 0.0),
                        }
                    })
            except Exception as e:
                print(f"  ⚠ Retrieval failed for {hunk_id}: {e}")
        
        # Build bundle
        bundle = RetrievalBundle(
            hunk_id=hunk_id,
            local_context=local_results,
            similar_code=similar_results,
            conventions=convention_results,
            total_chunks=len(local_results) + len(similar_results) + len(convention_results)
        )
        
        return bundle
    
    def __call__(self, state: WorkflowState) -> Dict[str, Any]:
        """
        LangGraph node function: retrieve context for all hunks.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updates to state (retrieval_bundles)
        """
        print(f"\n🔍 Retriever Agent: Processing {len(state.hunks)} hunks...")
        
        retrieval_bundles = {}
        
        for hunk in state.hunks:
            try:
                bundle = self.retrieve_for_hunk(
                    hunk=hunk,
                    repo_id=state.repo_id
                )
                retrieval_bundles[bundle.hunk_id] = bundle
                print(f"  ✓ Retrieved {bundle.total_chunks} chunks for {bundle.hunk_id}")
            except Exception as e:
                error_msg = f"Retrieval failed for hunk {hunk.get('hunk_id', 'unknown')}: {e}"
                print(f"  ✗ {error_msg}")
                state.errors.append(error_msg)
        
        return {
            "retrieval_bundles": retrieval_bundles,
            "current_node": "retriever"
        }
