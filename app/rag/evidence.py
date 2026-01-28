"""Evidence schema for cited code review claims."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EvidenceType(str, Enum):
    """Type of evidence supporting a review claim."""
    
    LOCAL_CONTEXT = "local_context"  # Same file context
    SIMILAR_CODE = "similar_code"  # Vector search from repo
    CONVENTION = "convention"  # Project conventions/rules


@dataclass
class Evidence:
    """A single piece of evidence supporting a review claim.
    
    Attributes:
        evidence_type: Type of evidence (local, similar, convention)
        file_path: Relative path from repo root (e.g., "src/app.py")
        start_line: Starting line number (1-indexed, inclusive)
        end_line: Ending line number (1-indexed, inclusive)
        content: Actual code snippet or convention text
        similarity_score: Relevance score (0.0-1.0), optional
        snippet_id: Unique identifier for traceability
    """
    
    evidence_type: EvidenceType
    file_path: str
    start_line: int
    end_line: int
    content: str
    similarity_score: Optional[float] = None
    snippet_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate evidence fields."""
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        if not self.file_path:
            raise ValueError("file_path cannot be empty")
        if not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.similarity_score is not None:
            if not 0.0 <= self.similarity_score <= 1.0:
                raise ValueError(
                    f"similarity_score must be in [0.0, 1.0], got {self.similarity_score}"
                )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "evidence_type": self.evidence_type.value,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "similarity_score": self.similarity_score,
            "snippet_id": self.snippet_id,
        }
    
    def format_citation(self) -> str:
        """Format as markdown citation link."""
        if self.start_line == self.end_line:
            return f"[{self.file_path}:{self.start_line}]"
        return f"[{self.file_path}:{self.start_line}-{self.end_line}]"


@dataclass
class CitedClaim:
    """A review comment with mandatory evidence citations.
    
    Attributes:
        claim: The review comment/suggestion
        severity: Issue severity (e.g., "critical", "warning", "info")
        evidence: List of Evidence objects supporting this claim
        confidence: LLM confidence in this claim (0.0-1.0)
    """
    
    claim: str
    severity: str
    evidence: list[Evidence] = field(default_factory=list)
    confidence: Optional[float] = None
    
    def __post_init__(self):
        """Validate cited claim."""
        if not self.claim.strip():
            raise ValueError("claim cannot be empty")
        if not self.evidence:
            raise ValueError("CitedClaim must have at least one Evidence object")
        if self.severity not in {"critical", "warning", "info", "suggestion"}:
            raise ValueError(
                f"severity must be critical/warning/info/suggestion, got '{self.severity}'"
            )
        if self.confidence is not None:
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "claim": self.claim,
            "severity": self.severity,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
        }
    
    def format_with_citations(self) -> str:
        """Format claim with evidence citations."""
        citations = ", ".join(e.format_citation() for e in self.evidence)
        return f"{self.claim}\n\n**Evidence:** {citations}"
