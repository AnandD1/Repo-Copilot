"""Build review units from parsed diffs for granular code review."""

from typing import List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from .diff_parser import FileDiff, Hunk, DiffLine, LineType
from .pr_fetcher import PRData


class ReviewUnitType(Enum):
    """Type of review unit."""
    FILE = "file"          # Review entire file
    HUNK = "hunk"          # Review single hunk
    MULTI_HUNK = "multi_hunk"  # Review multiple related hunks
    LOGICAL_CHANGE = "logical"  # Review logical change (e.g., function modification)


@dataclass
class ReviewContext:
    """Context information for a review unit."""
    # File context
    file_path: str
    old_file_path: Optional[str] = None
    
    # Line ranges
    old_line_start: Optional[int] = None
    old_line_end: Optional[int] = None
    new_line_start: Optional[int] = None
    new_line_end: Optional[int] = None
    
    # Change counts
    additions: int = 0
    deletions: int = 0
    
    # Content
    added_lines: List[str] = field(default_factory=list)
    removed_lines: List[str] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    
    # Metadata
    is_new_file: bool = False
    is_deleted_file: bool = False
    is_renamed: bool = False
    language: Optional[str] = None


@dataclass
class ReviewUnit:
    """
    A unit of code to review.
    
    Each unit represents a focused portion of changes that can be
    reviewed independently with relevant context.
    """
    # Unit identification
    unit_id: str  # Unique identifier
    unit_type: ReviewUnitType
    
    # Review context
    context: ReviewContext
    
    # PR metadata
    pr_number: int
    pr_title: str
    repo_full_name: str
    
    # Hunk references (for reconstruction)
    hunk_indices: List[int] = field(default_factory=list)
    
    # Derived data
    complexity_score: float = 0.0  # Estimated complexity (0-1)
    priority: int = 1  # Review priority (1=high, 5=low)
    
    def get_diff_snippet(self, max_lines: int = 50) -> str:
        """
        Get a formatted diff snippet for this review unit.
        
        Args:
            max_lines: Maximum lines to include
        
        Returns:
            Formatted diff string
        """
        lines = []
        
        # Add file header
        lines.append(f"File: {self.context.file_path}")
        if self.context.new_line_start and self.context.new_line_end:
            lines.append(f"Lines: {self.context.new_line_start}-{self.context.new_line_end}")
        lines.append(f"Changes: +{self.context.additions} -{self.context.deletions}")
        lines.append("")
        
        # Add changes
        total_lines = 0
        
        # Show removed lines
        if self.context.removed_lines and total_lines < max_lines:
            lines.append("Removed:")
            for line in self.context.removed_lines[:max_lines - total_lines]:
                lines.append(f"- {line}")
                total_lines += 1
        
        # Show added lines
        if self.context.added_lines and total_lines < max_lines:
            if self.context.removed_lines:
                lines.append("")
            lines.append("Added:")
            for line in self.context.added_lines[:max_lines - total_lines]:
                lines.append(f"+ {line}")
                total_lines += 1
        
        return "\n".join(lines)


class ReviewUnitBuilder:
    """Build review units from PR data and parsed diffs."""
    
    def __init__(self, pr_data: PRData, file_diffs: List[FileDiff]):
        """
        Initialize builder.
        
        Args:
            pr_data: PR metadata
            file_diffs: Parsed file diffs
        """
        self.pr_data = pr_data
        self.file_diffs = file_diffs
        self.units: List[ReviewUnit] = []
    
    def build_all_units(
        self,
        strategy: str = "per_hunk",
        max_hunk_size: int = 100
    ) -> List[ReviewUnit]:
        """
        Build all review units based on strategy.
        
        Args:
            strategy: Strategy to use - "per_file", "per_hunk", "smart"
            max_hunk_size: Maximum lines per hunk before splitting
        
        Returns:
            List of ReviewUnit objects
        """
        self.units = []
        
        if strategy == "per_file":
            self._build_per_file_units()
        elif strategy == "per_hunk":
            self._build_per_hunk_units(max_hunk_size)
        elif strategy == "smart":
            self._build_smart_units(max_hunk_size)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Calculate complexity and priority
        self._calculate_metrics()
        
        return self.units
    
    def _build_per_file_units(self):
        """Build one review unit per file."""
        for file_idx, file_diff in enumerate(self.file_diffs):
            # Skip binary files
            if file_diff.is_binary:
                continue
            
            # Collect all lines from all hunks
            all_added = []
            all_removed = []
            all_context = []
            
            old_start = None
            old_end = None
            new_start = None
            new_end = None
            
            for hunk in file_diff.hunks:
                all_added.extend([line.content for line in hunk.added_lines])
                all_removed.extend([line.content for line in hunk.removed_lines])
                all_context.extend([line.content for line in hunk.context_lines])
                
                # Track line ranges
                if old_start is None or hunk.old_start < old_start:
                    old_start = hunk.old_start
                if old_end is None or hunk.old_start + hunk.old_count > old_end:
                    old_end = hunk.old_start + hunk.old_count
                if new_start is None or hunk.new_start < new_start:
                    new_start = hunk.new_start
                if new_end is None or hunk.new_start + hunk.new_count > new_end:
                    new_end = hunk.new_start + hunk.new_count
            
            context = ReviewContext(
                file_path=file_diff.new_path,
                old_file_path=file_diff.old_path if file_diff.is_renamed else None,
                old_line_start=old_start,
                old_line_end=old_end,
                new_line_start=new_start,
                new_line_end=new_end,
                additions=file_diff.total_additions,
                deletions=file_diff.total_deletions,
                added_lines=all_added,
                removed_lines=all_removed,
                context_lines=all_context,
                is_new_file=file_diff.is_new,
                is_deleted_file=file_diff.is_deleted,
                is_renamed=file_diff.is_renamed,
                language=self._detect_language(file_diff.new_path)
            )
            
            unit = ReviewUnit(
                unit_id=f"file_{file_idx}_{file_diff.new_path}",
                unit_type=ReviewUnitType.FILE,
                context=context,
                pr_number=self.pr_data.number,
                pr_title=self.pr_data.title,
                repo_full_name=self.pr_data.repo_full_name,
                hunk_indices=list(range(len(file_diff.hunks)))
            )
            
            self.units.append(unit)
    
    def _build_per_hunk_units(self, max_hunk_size: int):
        """Build one review unit per hunk."""
        for file_idx, file_diff in enumerate(self.file_diffs):
            # Skip binary files
            if file_diff.is_binary:
                continue
            
            for hunk_idx, hunk in enumerate(file_diff.hunks):
                # Check if hunk is too large
                if len(hunk.lines) > max_hunk_size:
                    # Split large hunks
                    self._split_large_hunk(file_diff, file_idx, hunk_idx, hunk, max_hunk_size)
                else:
                    # Create single unit for this hunk
                    unit = self._create_hunk_unit(file_diff, file_idx, hunk_idx, hunk)
                    self.units.append(unit)
    
    def _create_hunk_unit(
        self,
        file_diff: FileDiff,
        file_idx: int,
        hunk_idx: int,
        hunk: Hunk
    ) -> ReviewUnit:
        """Create a review unit for a single hunk."""
        context = ReviewContext(
            file_path=file_diff.new_path,
            old_file_path=file_diff.old_path if file_diff.is_renamed else None,
            old_line_start=hunk.old_start,
            old_line_end=hunk.old_start + hunk.old_count - 1,
            new_line_start=hunk.new_start,
            new_line_end=hunk.new_start + hunk.new_count - 1,
            additions=hunk.additions_count,
            deletions=hunk.deletions_count,
            added_lines=[line.content for line in hunk.added_lines],
            removed_lines=[line.content for line in hunk.removed_lines],
            context_lines=[line.content for line in hunk.context_lines],
            is_new_file=file_diff.is_new,
            is_deleted_file=file_diff.is_deleted,
            is_renamed=file_diff.is_renamed,
            language=self._detect_language(file_diff.new_path)
        )
        
        unit_id = f"hunk_{file_idx}_{hunk_idx}_{file_diff.new_path}"
        
        return ReviewUnit(
            unit_id=unit_id,
            unit_type=ReviewUnitType.HUNK,
            context=context,
            pr_number=self.pr_data.number,
            pr_title=self.pr_data.title,
            repo_full_name=self.pr_data.repo_full_name,
            hunk_indices=[hunk_idx]
        )
    
    def _split_large_hunk(
        self,
        file_diff: FileDiff,
        file_idx: int,
        hunk_idx: int,
        hunk: Hunk,
        max_size: int
    ):
        """Split a large hunk into smaller review units."""
        current_lines = []
        current_added = []
        current_removed = []
        current_context = []
        part_num = 0
        
        for line in hunk.lines:
            current_lines.append(line)
            
            if line.line_type == LineType.ADDED:
                current_added.append(line.content)
            elif line.line_type == LineType.REMOVED:
                current_removed.append(line.content)
            else:
                current_context.append(line.content)
            
            # Check if we should create a unit
            if len(current_lines) >= max_size:
                self._create_split_unit(
                    file_diff, file_idx, hunk_idx, part_num,
                    current_lines, current_added, current_removed, current_context
                )
                
                # Reset for next part
                current_lines = []
                current_added = []
                current_removed = []
                current_context = []
                part_num += 1
        
        # Create unit for remaining lines
        if current_lines:
            self._create_split_unit(
                file_diff, file_idx, hunk_idx, part_num,
                current_lines, current_added, current_removed, current_context
            )
    
    def _create_split_unit(
        self,
        file_diff: FileDiff,
        file_idx: int,
        hunk_idx: int,
        part_num: int,
        lines: List[DiffLine],
        added: List[str],
        removed: List[str],
        context: List[str]
    ):
        """Create a review unit from split hunk part."""
        # Find line ranges
        old_lines = [l.old_line_no for l in lines if l.old_line_no is not None]
        new_lines = [l.new_line_no for l in lines if l.new_line_no is not None]
        
        review_context = ReviewContext(
            file_path=file_diff.new_path,
            old_file_path=file_diff.old_path if file_diff.is_renamed else None,
            old_line_start=min(old_lines) if old_lines else None,
            old_line_end=max(old_lines) if old_lines else None,
            new_line_start=min(new_lines) if new_lines else None,
            new_line_end=max(new_lines) if new_lines else None,
            additions=len(added),
            deletions=len(removed),
            added_lines=added,
            removed_lines=removed,
            context_lines=context,
            is_new_file=file_diff.is_new,
            is_deleted_file=file_diff.is_deleted,
            is_renamed=file_diff.is_renamed,
            language=self._detect_language(file_diff.new_path)
        )
        
        unit_id = f"hunk_{file_idx}_{hunk_idx}_part{part_num}_{file_diff.new_path}"
        
        unit = ReviewUnit(
            unit_id=unit_id,
            unit_type=ReviewUnitType.HUNK,
            context=review_context,
            pr_number=self.pr_data.number,
            pr_title=self.pr_data.title,
            repo_full_name=self.pr_data.repo_full_name,
            hunk_indices=[hunk_idx]
        )
        
        self.units.append(unit)
    
    def _build_smart_units(self, max_hunk_size: int):
        """
        Build units using smart grouping.
        
        Groups related hunks (e.g., in same function) into single units.
        Falls back to per-hunk for unrelated changes.
        """
        for file_idx, file_diff in enumerate(self.file_diffs):
            if file_diff.is_binary:
                continue
            
            # For now, use per-hunk strategy
            # TODO: Implement AST-based grouping for related hunks
            for hunk_idx, hunk in enumerate(file_diff.hunks):
                if len(hunk.lines) > max_hunk_size:
                    self._split_large_hunk(file_diff, file_idx, hunk_idx, hunk, max_hunk_size)
                else:
                    unit = self._create_hunk_unit(file_diff, file_idx, hunk_idx, hunk)
                    self.units.append(unit)
    
    def _calculate_metrics(self):
        """Calculate complexity and priority for each unit."""
        for unit in self.units:
            # Complexity based on change size and type
            change_size = unit.context.additions + unit.context.deletions
            
            # Base complexity on size (normalized to 0-1)
            complexity = min(change_size / 100.0, 1.0)
            
            # Increase complexity for new/deleted files
            if unit.context.is_new_file or unit.context.is_deleted_file:
                complexity *= 1.5
            
            # Increase complexity for certain file types
            if unit.context.language in ['python', 'javascript', 'typescript', 'java']:
                complexity *= 1.2
            
            unit.complexity_score = min(complexity, 1.0)
            
            # Priority based on complexity (inverse)
            if unit.complexity_score > 0.7:
                unit.priority = 1  # High priority
            elif unit.complexity_score > 0.4:
                unit.priority = 2  # Medium priority
            else:
                unit.priority = 3  # Low priority
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.md': 'markdown',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sql': 'sql',
        }
        
        import os
        _, ext = os.path.splitext(file_path)
        return ext_map.get(ext.lower())
    
    def get_high_priority_units(self) -> List[ReviewUnit]:
        """Get units with priority 1 (high)."""
        return [u for u in self.units if u.priority == 1]
    
    def get_units_by_file(self, file_path: str) -> List[ReviewUnit]:
        """Get all units for a specific file."""
        return [u for u in self.units if u.context.file_path == file_path]
    
    def get_units_by_language(self, language: str) -> List[ReviewUnit]:
        """Get all units for a specific language."""
        return [u for u in self.units if u.context.language == language]
