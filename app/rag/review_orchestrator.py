"""LangGraph orchestrator for code review with cited evidence."""

from dataclasses import dataclass
from typing import Annotated, TypedDict
import operator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from config.settings import settings
from .evidence import Evidence, CitedClaim, EvidenceType
from .local_context_retriever import LocalContextRetriever
from .similar_code_retriever import SimilarCodeRetriever
from .conventions_retriever import ConventionsRetriever
from .reranker import BGEReranker


@dataclass
class ReviewRequest:
    """Request for code review.
    
    Attributes:
        file_path: File being reviewed
        code_snippet: Code snippet to review
        owner: GitHub repo owner
        repo: GitHub repo name
        head_sha: PR head commit SHA
        target_line: Line number being reviewed
        language: Programming language
    """
    
    file_path: str
    code_snippet: str
    owner: str
    repo: str
    head_sha: str
    target_line: int
    language: str = "python"


@dataclass
class ReviewResponse:
    """Response from code review.
    
    Attributes:
        claims: List of cited review claims
        evidence: All evidence gathered
        raw_response: Raw LLM response
    """
    
    claims: list[CitedClaim]
    evidence: list[Evidence]
    raw_response: str


class ReviewState(TypedDict):
    """State for review graph."""
    
    request: ReviewRequest
    local_evidence: list[Evidence]
    similar_evidence: list[Evidence]
    convention_evidence: list[Evidence]
    all_evidence: Annotated[list[Evidence], operator.add]
    reranked_evidence: list[Evidence]
    review_text: str
    validated_claims: list[CitedClaim]
    error: str | None


class ReviewOrchestrator:
    """LangGraph orchestrator for evidence-based code review.
    
    Workflow:
    1. Retrieve local context
    2. Retrieve similar code
    3. Retrieve conventions
    4. Rerank all evidence
    5. Generate review with LLM
    6. Validate evidence citations
    """
    
    def __init__(
        self,
        local_retriever: LocalContextRetriever,
        similar_retriever: SimilarCodeRetriever,
        conventions_retriever: ConventionsRetriever,
        reranker: BGEReranker,
    ):
        """Initialize orchestrator with retrievers and reranker.
        
        Args:
            local_retriever: LocalContextRetriever instance
            similar_retriever: SimilarCodeRetriever instance
            conventions_retriever: ConventionsRetriever instance
            reranker: BGEReranker instance
        """
        self.local_retriever = local_retriever
        self.similar_retriever = similar_retriever
        self.conventions_retriever = conventions_retriever
        self.reranker = reranker
        
        # Initialize Ollama LLM
        self.llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
        )
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(ReviewState)
        
        # Add nodes
        workflow.add_node("retrieve_local", self._retrieve_local)
        workflow.add_node("retrieve_similar", self._retrieve_similar)
        workflow.add_node("retrieve_conventions", self._retrieve_conventions)
        workflow.add_node("rerank", self._rerank)
        workflow.add_node("generate_review", self._generate_review)
        workflow.add_node("validate_citations", self._validate_citations)
        
        # Add edges
        workflow.set_entry_point("retrieve_local")
        workflow.add_edge("retrieve_local", "retrieve_similar")
        workflow.add_edge("retrieve_similar", "retrieve_conventions")
        workflow.add_edge("retrieve_conventions", "rerank")
        workflow.add_edge("rerank", "generate_review")
        workflow.add_edge("generate_review", "validate_citations")
        workflow.add_edge("validate_citations", END)
        
        return workflow.compile()
    
    def _retrieve_local(self, state: ReviewState) -> dict:
        """Retrieve local context from same file."""
        request = state["request"]
        
        local_evidence = self.local_retriever.retrieve(
            owner=request.owner,
            repo=request.repo,
            file_path=request.file_path,
            head_sha=request.head_sha,
            target_line=request.target_line,
            context_lines=10,
        )
        
        return {
            "local_evidence": local_evidence,
            "all_evidence": local_evidence,
        }
    
    def _retrieve_similar(self, state: ReviewState) -> dict:
        """Retrieve similar code from repository."""
        request = state["request"]
        
        similar_evidence = self.similar_retriever.retrieve(
            query=request.code_snippet,
            top_k=5,
            repo=request.repo,
            exclude_file=request.file_path,
            min_similarity=0.7,
        )
        
        return {
            "similar_evidence": similar_evidence,
            "all_evidence": similar_evidence,
        }
    
    def _retrieve_conventions(self, state: ReviewState) -> dict:
        """Retrieve relevant conventions."""
        request = state["request"]
        
        convention_evidence = self.conventions_retriever.retrieve(
            query=request.code_snippet,
            top_k=3,
            language=request.language,
            min_similarity=0.6,
        )
        
        return {
            "convention_evidence": convention_evidence,
            "all_evidence": convention_evidence,
        }
    
    def _rerank(self, state: ReviewState) -> dict:
        """Rerank all evidence."""
        request = state["request"]
        all_evidence = state["all_evidence"]
        
        reranked = self.reranker.rerank(
            query=request.code_snippet,
            evidence_list=all_evidence,
            top_k=10,
        )
        
        return {"reranked_evidence": reranked}
    
    def _generate_review(self, state: ReviewState) -> dict:
        """Generate review using LLM with evidence."""
        request = state["request"]
        reranked_evidence = state["reranked_evidence"]
        
        # Format evidence for LLM
        evidence_text = self._format_evidence(reranked_evidence)
        
        # Create prompt
        system_prompt = """You are a code review assistant. Review the provided code snippet using the evidence provided.

CRITICAL RULES:
1. Every claim MUST cite at least one piece of evidence using [file:line] format
2. Use evidence types: [LOCAL], [SIMILAR], [CONVENTION]
3. Format: **[SEVERITY]** claim [evidence citations]
4. Severity levels: CRITICAL, WARNING, INFO, SUGGESTION
5. Be concise and specific

Example:
**[WARNING]** Variable name 'x' is not descriptive [LOCAL: handlers.py:45-47] [CONVENTION: STYLE_GUIDE.md:12]
"""
        
        user_prompt = f"""Review this code:

File: {request.file_path}:{request.target_line}
```{request.language}
{request.code_snippet}
```

Evidence:
{evidence_text}

Provide code review with cited evidence:"""
        
        # Generate review
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        
        response = self.llm.invoke(messages)
        review_text = response.content
        
        return {"review_text": review_text}
    
    def _validate_citations(self, state: ReviewState) -> dict:
        """Validate that review has proper evidence citations."""
        review_text = state["review_text"]
        reranked_evidence = state["reranked_evidence"]
        
        # Parse review text into claims
        # Simple parsing: each line starting with **[SEVERITY]**
        claims = []
        lines = review_text.strip().split("\n")
        
        current_claim = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a new claim
            if line.startswith("**["):
                # Extract severity
                if "]**" in line:
                    severity_end = line.index("]**")
                    severity = line[3:severity_end].lower()
                    claim_text = line[severity_end + 3:].strip()
                    
                    # Find evidence citations in brackets
                    cited_evidence = self._extract_citations(claim_text, reranked_evidence)
                    
                    if cited_evidence:
                        current_claim = CitedClaim(
                            claim=claim_text,
                            severity=severity,
                            evidence=cited_evidence,
                        )
                        claims.append(current_claim)
        
        return {
            "validated_claims": claims,
            "error": None if claims else "No valid cited claims found",
        }
    
    def _format_evidence(self, evidence_list: list[Evidence]) -> str:
        """Format evidence for LLM context."""
        formatted = []
        
        for i, evidence in enumerate(evidence_list, 1):
            type_label = evidence.evidence_type.value.upper()
            score = f"{evidence.similarity_score:.2f}" if evidence.similarity_score else "N/A"
            
            formatted.append(
                f"{i}. [{type_label}] {evidence.file_path}:{evidence.start_line}-{evidence.end_line} (score: {score})\n"
                f"   {evidence.content[:200]}..."
            )
        
        return "\n\n".join(formatted)
    
    def _extract_citations(
        self,
        claim_text: str,
        evidence_list: list[Evidence],
    ) -> list[Evidence]:
        """Extract evidence citations from claim text."""
        cited = []
        
        # Simple heuristic: look for file paths in brackets
        for evidence in evidence_list:
            citation = evidence.format_citation()
            if citation in claim_text or evidence.file_path in claim_text:
                cited.append(evidence)
        
        return cited
    
    def review(self, request: ReviewRequest) -> ReviewResponse:
        """Execute code review workflow.
        
        Args:
            request: ReviewRequest object
            
        Returns:
            ReviewResponse with cited claims
        """
        # Initialize state
        initial_state: ReviewState = {
            "request": request,
            "local_evidence": [],
            "similar_evidence": [],
            "convention_evidence": [],
            "all_evidence": [],
            "reranked_evidence": [],
            "review_text": "",
            "validated_claims": [],
            "error": None,
        }
        
        # Run graph
        final_state = self.graph.invoke(initial_state)
        
        # Build response
        return ReviewResponse(
            claims=final_state["validated_claims"],
            evidence=final_state["reranked_evidence"],
            raw_response=final_state["review_text"],
        )
