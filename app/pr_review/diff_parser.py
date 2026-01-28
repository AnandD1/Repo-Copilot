"""Parse unified diffs into structured hunks."""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class LineType(Enum):
    """Type of line in a diff."""
    CONTEXT = "context"  # Unchanged line
    ADDED = "added"      # Added line (+)
    REMOVED = "removed"  # Removed line (-)


@dataclass
class DiffLine:
    """A single line in a diff."""
    line_type: LineType
    content: str
    old_line_no: Optional[int] = None  # Line number in old file (before)
    new_line_no: Optional[int] = None  # Line number in new file (after)


@dataclass
class Hunk:
    """
    A hunk represents a contiguous change block in a diff.
    
    Example hunk header:
    @@ -10,5 +12,7 @@ function_name
    
    This means:
    - Old file: starting at line 10, 5 lines
    - New file: starting at line 12, 7 lines
    """
    # Header information
    old_start: int  # Starting line in old file
    old_count: int  # Number of lines in old file
    new_start: int  # Starting line in new file
    new_count: int  # Number of lines in new file
    header_context: str = ""  # Context after @@ (function/class name)
    
    # Lines in this hunk
    lines: List[DiffLine] = field(default_factory=list)
    
    @property
    def added_lines(self) -> List[DiffLine]:
        """Get only added lines."""
        return [line for line in self.lines if line.line_type == LineType.ADDED]
    
    @property
    def removed_lines(self) -> List[DiffLine]:
        """Get only removed lines."""
        return [line for line in self.lines if line.line_type == LineType.REMOVED]
    
    @property
    def context_lines(self) -> List[DiffLine]:
        """Get only context lines."""
        return [line for line in self.lines if line.line_type == LineType.CONTEXT]
    
    @property
    def old_line_range(self) -> Tuple[int, int]:
        """Get line range in old file (start, end)."""
        return (self.old_start, self.old_start + self.old_count - 1)
    
    @property
    def new_line_range(self) -> Tuple[int, int]:
        """Get line range in new file (start, end)."""
        return (self.new_start, self.new_start + self.new_count - 1)
    
    @property
    def additions_count(self) -> int:
        """Count of added lines."""
        return len(self.added_lines)
    
    @property
    def deletions_count(self) -> int:
        """Count of removed lines."""
        return len(self.removed_lines)
    
    def get_added_line_numbers(self) -> List[int]:
        """Get list of line numbers for added lines (in new file)."""
        return [line.new_line_no for line in self.added_lines if line.new_line_no]
    
    def get_removed_line_numbers(self) -> List[int]:
        """Get list of line numbers for removed lines (in old file)."""
        return [line.old_line_no for line in self.removed_lines if line.old_line_no]


@dataclass
class FileDiff:
    """Represents all changes to a single file."""
    # File paths
    old_path: str  # Path in old version (before)
    new_path: str  # Path in new version (after)
    
    # File status
    is_new: bool = False      # File was added
    is_deleted: bool = False  # File was deleted
    is_renamed: bool = False  # File was renamed
    is_binary: bool = False   # Binary file
    
    # Hunks in this file
    hunks: List[Hunk] = field(default_factory=list)
    
    @property
    def total_additions(self) -> int:
        """Total lines added across all hunks."""
        return sum(hunk.additions_count for hunk in self.hunks)
    
    @property
    def total_deletions(self) -> int:
        """Total lines deleted across all hunks."""
        return sum(hunk.deletions_count for hunk in self.hunks)
    
    @property
    def all_added_lines(self) -> List[DiffLine]:
        """Get all added lines from all hunks."""
        return [line for hunk in self.hunks for line in hunk.added_lines]
    
    @property
    def all_removed_lines(self) -> List[DiffLine]:
        """Get all removed lines from all hunks."""
        return [line for hunk in self.hunks for line in hunk.removed_lines]


class DiffParser:
    """Parse unified diff format into structured data."""
    
    # Regex patterns
    FILE_HEADER_OLD = re.compile(r'^--- (.+?)(?:\t.*)?$')
    FILE_HEADER_NEW = re.compile(r'^\+\+\+ (.+?)(?:\t.*)?$')
    HUNK_HEADER = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$')
    BINARY_DIFF = re.compile(r'^Binary files .+ differ$')
    
    @staticmethod
    def parse_diff(diff_text: str) -> List[FileDiff]:
        """
        Parse unified diff into structured FileDiff objects.
        
        Args:
            diff_text: Unified diff text (from git diff or PR patch)
        
        Returns:
            List of FileDiff objects, one per file
        """
        if not diff_text or not diff_text.strip():
            return []
        
        lines = diff_text.split('\n')
        file_diffs = []
        current_file = None
        current_hunk = None
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for binary file
            if DiffParser.BINARY_DIFF.match(line):
                # Binary files - create minimal FileDiff
                if current_file:
                    file_diffs.append(current_file)
                current_file = FileDiff(
                    old_path="binary",
                    new_path="binary",
                    is_binary=True
                )
                file_diffs.append(current_file)
                current_file = None
                i += 1
                continue
            
            # Check for old file header (--- a/path)
            old_match = DiffParser.FILE_HEADER_OLD.match(line)
            if old_match:
                # Save previous file if exists
                if current_file:
                    if current_hunk:
                        current_file.hunks.append(current_hunk)
                        current_hunk = None
                    file_diffs.append(current_file)
                
                old_path = old_match.group(1)
                # Remove a/ or b/ prefix if present
                old_path = old_path.replace('a/', '', 1)
                
                # Next line should be new file header
                i += 1
                if i < len(lines):
                    new_match = DiffParser.FILE_HEADER_NEW.match(lines[i])
                    if new_match:
                        new_path = new_match.group(1)
                        new_path = new_path.replace('b/', '', 1)
                        
                        # Determine file status
                        is_new = old_path == '/dev/null'
                        is_deleted = new_path == '/dev/null'
                        is_renamed = old_path != new_path and not is_new and not is_deleted
                        
                        current_file = FileDiff(
                            old_path=old_path if not is_new else new_path,
                            new_path=new_path if not is_deleted else old_path,
                            is_new=is_new,
                            is_deleted=is_deleted,
                            is_renamed=is_renamed
                        )
                i += 1
                continue
            
            # Check for hunk header (@@ -10,5 +12,7 @@)
            hunk_match = DiffParser.HUNK_HEADER.match(line)
            if hunk_match and current_file:
                # Save previous hunk if exists
                if current_hunk:
                    current_file.hunks.append(current_hunk)
                
                old_start = int(hunk_match.group(1))
                old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                header_context = hunk_match.group(5).strip()
                
                current_hunk = Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    header_context=header_context
                )
                i += 1
                continue
            
            # Parse hunk content lines
            if current_hunk and line:
                if line.startswith('+') and not line.startswith('+++'):
                    # Added line
                    content = line[1:]  # Remove + prefix
                    diff_line = DiffLine(
                        line_type=LineType.ADDED,
                        content=content,
                        new_line_no=current_hunk.new_start + len([
                            l for l in current_hunk.lines 
                            if l.line_type in (LineType.ADDED, LineType.CONTEXT)
                        ])
                    )
                    current_hunk.lines.append(diff_line)
                
                elif line.startswith('-') and not line.startswith('---'):
                    # Removed line
                    content = line[1:]  # Remove - prefix
                    diff_line = DiffLine(
                        line_type=LineType.REMOVED,
                        content=content,
                        old_line_no=current_hunk.old_start + len([
                            l for l in current_hunk.lines 
                            if l.line_type in (LineType.REMOVED, LineType.CONTEXT)
                        ])
                    )
                    current_hunk.lines.append(diff_line)
                
                elif line.startswith(' '):
                    # Context line (unchanged)
                    content = line[1:]  # Remove space prefix
                    old_line_no = current_hunk.old_start + len([
                        l for l in current_hunk.lines 
                        if l.line_type in (LineType.REMOVED, LineType.CONTEXT)
                    ])
                    new_line_no = current_hunk.new_start + len([
                        l for l in current_hunk.lines 
                        if l.line_type in (LineType.ADDED, LineType.CONTEXT)
                    ])
                    diff_line = DiffLine(
                        line_type=LineType.CONTEXT,
                        content=content,
                        old_line_no=old_line_no,
                        new_line_no=new_line_no
                    )
                    current_hunk.lines.append(diff_line)
            
            i += 1
        
        # Save last file and hunk
        if current_hunk and current_file:
            current_file.hunks.append(current_hunk)
        if current_file:
            file_diffs.append(current_file)
        
        return file_diffs
    
    @staticmethod
    def parse_file_patch(patch: str, filename: str) -> FileDiff:
        """
        Parse a single file's patch into FileDiff.
        
        Args:
            patch: Patch text for one file
            filename: Name of the file
        
        Returns:
            FileDiff object
        """
        if not patch or not patch.strip():
            return FileDiff(old_path=filename, new_path=filename)
        
        # Add minimal diff headers if not present
        if not patch.startswith('---'):
            patch = f"--- a/{filename}\n+++ b/{filename}\n{patch}"
        
        file_diffs = DiffParser.parse_diff(patch)
        
        if file_diffs:
            return file_diffs[0]
        
        return FileDiff(old_path=filename, new_path=filename)
