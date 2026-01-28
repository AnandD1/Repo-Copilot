"""BGE Reranker for combining and scoring evidence from multiple retrievers."""

from typing import Optional
from sentence_transformers import CrossEncoder

from .evidence import Evidence


class BGEReranker:
    """Cross-encoder reranker using BGE model.
    
    Takes candidates from multiple retrievers and reranks them
    based on relevance to the query using a cross-encoder model.
    """
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """Initialize reranker with cross-encoder model.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        self.model_name = model_name
        self.model: Optional[CrossEncoder] = None
    
    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self.model is None:
            print(f"Loading reranker model: {self.model_name}")
            self.model = CrossEncoder(self.model_name)
            print(f"✓ Reranker model loaded")
    
    def rerank(
        self,
        query: str,
        evidence_list: list[Evidence],
        top_k: Optional[int] = None,
    ) -> list[Evidence]:
        """Rerank evidence candidates using cross-encoder.
        
        Args:
            query: Query text (e.g., code snippet being reviewed)
            evidence_list: List of Evidence objects from retrievers
            top_k: Return top K results after reranking (None = return all)
            
        Returns:
            Reranked list of Evidence objects with updated similarity scores
        """
        if not evidence_list:
            return []
        
        # Load model on first use
        self._load_model()
        
        # Prepare query-document pairs for cross-encoder
        pairs = [(query, evidence.content) for evidence in evidence_list]
        
        # Get reranking scores
        scores = self.model.predict(pairs)
        
        # Update evidence objects with new scores
        reranked_evidence = []
        for evidence, score in zip(evidence_list, scores):
            # Normalize score to [0, 1] range (cross-encoder returns logits)
            # Use sigmoid to convert to probability
            normalized_score = 1 / (1 + pow(2.71828, -score))  # sigmoid
            
            # Create new Evidence with updated score
            updated_evidence = Evidence(
                evidence_type=evidence.evidence_type,
                file_path=evidence.file_path,
                start_line=evidence.start_line,
                end_line=evidence.end_line,
                content=evidence.content,
                similarity_score=normalized_score,
                snippet_id=evidence.snippet_id,
            )
            
            reranked_evidence.append((updated_evidence, normalized_score))
        
        # Sort by reranked score (descending)
        reranked_evidence.sort(key=lambda x: x[1], reverse=True)
        
        # Extract Evidence objects
        result = [evidence for evidence, _ in reranked_evidence]
        
        # Return top K if specified
        if top_k is not None:
            result = result[:top_k]
        
        return result
