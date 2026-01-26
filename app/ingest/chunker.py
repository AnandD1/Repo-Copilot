"""Code and document chunking with structure-awareness."""

import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

import tiktoken
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    Language
)

from app.ingest.filter import FileInfo
from app.ingest.language_detector import LanguageDetector
from config.settings import settings


class ChunkType(Enum):
    """Type of chunk."""
    CODE = "code"
    DOC = "doc"
    CONFIG = "config"


@dataclass
class ChunkMetadata:
    """Metadata for a code chunk."""
    repo: str
    branch: str
    file_path: str  # relative path
    language: Optional[str]
    chunk_id: str
    chunk_index: int
    start_line: int
    end_line: int
    chunk_type: ChunkType
    symbol: Optional[str] = None  # function/class name
    imports: Optional[str] = None  # import block


@dataclass
class Chunk:
    """A chunk of code or documentation."""
    content: str
    metadata: ChunkMetadata
    token_count: int


class CodeChunker:
    """
    Structure-aware chunker for code, documentation, and config files.
    
    Uses different strategies based on file type:
    - Code: Function/class boundaries with LangChain recursive splitter
    - Markdown: Section-by-section with header-based splitting
    - Config: Whole file or simple splitting
    """
    
    # Language mapping for LangChain
    LANGCHAIN_LANGUAGE_MAP = {
        'Python': Language.PYTHON,
        'JavaScript': Language.JS,
        'TypeScript': Language.TS,
        'Java': Language.JAVA,
        'C++': Language.CPP,
        'C': Language.C,
        'C#': Language.CSHARP,
        'Go': Language.GO,
        'Rust': Language.RUST,
        'Ruby': Language.RUBY,
        'PHP': Language.PHP,
        'Swift': Language.SWIFT,
        'Kotlin': Language.KOTLIN,
        'Scala': Language.SCALA,
        'HTML': Language.HTML,
        'Markdown': Language.MARKDOWN,
    }
    
    def __init__(self, repo_name: str, branch: str):
        """
        Initialize the chunker.
        
        Args:
            repo_name: Repository name (owner/repo)
            branch: Branch name
        """
        self.repo_name = repo_name
        self.branch = branch
        self.language_detector = LanguageDetector()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
    
    def chunk_file(self, file_info: FileInfo) -> List[Chunk]:
        """
        Chunk a file based on its type.
        
        Args:
            file_info: File information
        
        Returns:
            List of chunks
        """
        # Read file content
        try:
            content = file_info.path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                content = file_info.path.read_text(encoding='latin-1')
            except Exception:
                # Skip binary files
                return []
        except Exception:
            return []
        
        # Skip empty files
        if not content or not content.strip():
            return []
        
        # Determine chunk type
        chunk_type = self._get_chunk_type(file_info)
        
        # Chunk based on type
        if chunk_type == ChunkType.CODE:
            return self._chunk_code(file_info, content)
        elif chunk_type == ChunkType.DOC:
            return self._chunk_documentation(file_info, content)
        else:  # CONFIG
            return self._chunk_config(file_info, content)
    
    def _get_chunk_type(self, file_info: FileInfo) -> ChunkType:
        """Determine chunk type based on file."""
        # The ingestor sets file_info.language to the language NAME (e.g., 'Python')
        # but get_language_info expects language_id (e.g., 'python')
        # So we always detect from path to get the correct language_id
        language_id = self.language_detector.detect_language(file_info.path)
        
        if language_id:
            lang_info = self.language_detector.get_language_info(language_id)
            if lang_info:
                if lang_info.category == 'programming':
                    return ChunkType.CODE
                elif lang_info.category == 'documentation':
                    return ChunkType.DOC
        
        # Config files
        if file_info.extension in ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf']:
            return ChunkType.CONFIG
        
        # Markdown is doc
        if file_info.extension in ['.md', '.markdown']:
            return ChunkType.DOC
        
        # Default to config
        return ChunkType.CONFIG
    
    def _chunk_code(self, file_info: FileInfo, content: str) -> List[Chunk]:
        """
        Chunk code files with structure awareness.
        
        Uses LangChain's RecursiveCharacterTextSplitter with language-specific
        separators to respect function/class boundaries.
        """
        # Get LangChain language
        langchain_lang = self.LANGCHAIN_LANGUAGE_MAP.get(file_info.language)
        
        # Create splitter
        if langchain_lang:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=langchain_lang,
                chunk_size=settings.code_chunk_target_tokens,
                chunk_overlap=settings.code_chunk_overlap_tokens,
                length_function=self._count_tokens,
            )
        else:
            # Generic code splitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.code_chunk_target_tokens,
                chunk_overlap=settings.code_chunk_overlap_tokens,
                length_function=self._count_tokens,
                separators=["\n\n", "\n", " ", ""],
            )
        
        # Extract imports (keep as separate chunk)
        imports_block = self._extract_imports(content, file_info.language)
        
        # Split content
        text_chunks = splitter.split_text(content)
        
        # Safety check: if no chunks generated, return empty list
        if not text_chunks:
            return []
        
        # Create chunks with metadata
        chunks = []
        search_from = 0  # Track position in file content
        
        for idx, chunk_content in enumerate(text_chunks):
            # Skip empty or whitespace-only chunks
            if not chunk_content or not chunk_content.strip():
                continue
            
            # Calculate line numbers by finding chunk from last position
            start_line, end_line, search_from = self._find_line_numbers_from(
                content, chunk_content, search_from
            )
            
            # Try to extract symbol name (function/class)
            symbol = self._extract_symbol(chunk_content, file_info.language)
            
            # Create metadata
            metadata = ChunkMetadata(
                repo=self.repo_name,
                branch=self.branch,
                file_path=str(file_info.relative_path).replace('\\', '/'),
                language=file_info.language,
                chunk_id=f"{file_info.relative_path}::{idx}",
                chunk_index=idx,
                start_line=start_line,
                end_line=end_line,
                chunk_type=ChunkType.CODE,
                symbol=symbol,
                imports=imports_block if idx == 0 else None,
            )
            
            chunk = Chunk(
                content=chunk_content,
                metadata=metadata,
                token_count=self._count_tokens(chunk_content)
            )
            chunks.append(chunk)
        
        # Enforce hard cap: split any oversized chunks
        chunks = self._enforce_max_tokens(chunks, settings.code_chunk_max_tokens, file_info)
        
        return chunks
    
    def _chunk_documentation(self, file_info: FileInfo, content: str) -> List[Chunk]:
        """
        Chunk markdown/documentation files by headers.
        
        Uses MarkdownHeaderTextSplitter to respect section boundaries.
        """
        # Define headers to split on
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        # Create markdown splitter
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,
        )
        
        # Split by headers first
        header_splits = markdown_splitter.split_text(content)
        
        # Further split if chunks are too large
        chunks = []
        search_from = 0  # Track position in file
        
        for idx, doc in enumerate(header_splits):
            chunk_content = doc.page_content
            token_count = self._count_tokens(chunk_content)
            
            # If chunk is within limits, keep as is
            if token_count <= settings.doc_chunk_max_tokens:
                # Calculate line numbers from last position
                start_line, end_line, search_from = self._find_line_numbers_from(
                    content, chunk_content, search_from
                )
                
                metadata = ChunkMetadata(
                    repo=self.repo_name,
                    branch=self.branch,
                    file_path=str(file_info.relative_path).replace('\\', '/'),
                    language=file_info.language,
                    chunk_id=f"{file_info.relative_path}::{len(chunks)}",
                    chunk_index=len(chunks),
                    start_line=start_line,
                    end_line=end_line,
                    chunk_type=ChunkType.DOC,
                    symbol=doc.metadata.get('Header 1') or doc.metadata.get('Header 2'),
                )
                
                chunks.append(Chunk(
                    content=chunk_content,
                    metadata=metadata,
                    token_count=token_count
                ))
            else:
                # Split further
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.doc_chunk_target_tokens,
                    chunk_overlap=settings.doc_chunk_overlap_tokens,
                    length_function=self._count_tokens,
                )
                
                sub_chunks = text_splitter.split_text(chunk_content)
                # Track position within this section
                sub_search_from = search_from
                
                for sub_chunk in sub_chunks:
                    start_line, end_line, sub_search_from = self._find_line_numbers_from(
                        content, sub_chunk, sub_search_from
                    )
                    
                    metadata = ChunkMetadata(
                        repo=self.repo_name,
                        branch=self.branch,
                        file_path=str(file_info.relative_path).replace('\\', '/'),
                        language=file_info.language,
                        chunk_id=f"{file_info.relative_path}::{len(chunks)}",
                        chunk_index=len(chunks),
                        start_line=start_line,
                        end_line=end_line,
                        chunk_type=ChunkType.DOC,
                        symbol=doc.metadata.get('Header 1') or doc.metadata.get('Header 2'),
                    )
                    
                    chunks.append(Chunk(
                        content=sub_chunk,
                        metadata=metadata,
                        token_count=self._count_tokens(sub_chunk)
                    ))
                
                # Update main search position to end of this section
                search_from = sub_search_from
        
        # Enforce hard cap for doc chunks
        chunks = self._enforce_max_tokens(chunks, settings.doc_chunk_max_tokens, file_info)
        
        return chunks
    
    def _chunk_config(self, file_info: FileInfo, content: str) -> List[Chunk]:
        """
        Chunk configuration files.
        
        Keep whole file if small, otherwise split.
        """
        token_count = self._count_tokens(content)
        
        # Keep whole file if small enough
        if token_count <= settings.config_whole_file_max_tokens:
            metadata = ChunkMetadata(
                repo=self.repo_name,
                branch=self.branch,
                file_path=str(file_info.relative_path).replace('\\', '/'),
                language=file_info.language,
                chunk_id=f"{file_info.relative_path}::0",
                chunk_index=0,
                start_line=0,
                end_line=len(content.split('\n')) - 1,
                chunk_type=ChunkType.CONFIG,
            )
            
            return [Chunk(
                content=content,
                metadata=metadata,
                token_count=token_count
            )]
        
        # Split if too large
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.config_chunk_target_tokens,
            chunk_overlap=settings.config_chunk_overlap_tokens,
            length_function=self._count_tokens,
            separators=["\n\n", "\n", " ", ""],
        )
        
        text_chunks = splitter.split_text(content)
        chunks = []
        search_from = 0  # Track position in file
        
        for idx, chunk_content in enumerate(text_chunks):
            start_line, end_line, search_from = self._find_line_numbers_from(
                content, chunk_content, search_from
            )
            
            metadata = ChunkMetadata(
                repo=self.repo_name,
                branch=self.branch,
                file_path=str(file_info.relative_path).replace('\\', '/'),
                language=file_info.language,
                chunk_id=f"{file_info.relative_path}::{idx}",
                chunk_index=idx,
                start_line=start_line,
                end_line=end_line,
                chunk_type=ChunkType.CONFIG,
            )
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=metadata,
                token_count=self._count_tokens(chunk_content)
            ))
        
        # Enforce hard cap for config chunks
        chunks = self._enforce_max_tokens(chunks, settings.config_chunk_max_tokens, file_info)
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
    
    def _enforce_max_tokens(self, chunks: List[Chunk], max_tokens: int, file_info: FileInfo) -> List[Chunk]:
        """Enforce hard token limit by splitting oversized chunks."""
        result = []
        
        for chunk in chunks:
            if chunk.token_count <= max_tokens:
                result.append(chunk)
            else:
                # Chunk exceeds max, force split it
                # Use simple token-based splitting with no overlap to guarantee size
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=max_tokens,
                    chunk_overlap=0,
                    length_function=self._count_tokens,
                    separators=["\n\n", "\n", " ", ""],
                )
                
                sub_texts = splitter.split_text(chunk.content)
                sub_search_from = 0  # Track position within chunk.content
                
                for sub_idx, sub_text in enumerate(sub_texts):
                    # Update chunk_id and index
                    new_chunk_id = f"{chunk.metadata.chunk_id}_split{sub_idx}"
                    
                    # Find sub-chunk position within chunk.content
                    try:
                        sub_start_idx = chunk.content.index(sub_text, sub_search_from)
                        # Line numbers relative to chunk.content start
                        relative_start_line = chunk.content[:sub_start_idx].count('\n')
                        relative_end_line = relative_start_line + sub_text.count('\n')
                        # Update search position
                        sub_search_from = sub_start_idx + len(sub_text)
                    except ValueError:
                        # Fallback if search fails
                        relative_start_line = chunk.content[:sub_search_from].count('\n')
                        relative_end_line = relative_start_line + sub_text.count('\n')
                        sub_search_from += len(sub_text)
                    
                    # Adjust to absolute line numbers in original file
                    start_line = chunk.metadata.start_line + relative_start_line
                    end_line = chunk.metadata.start_line + relative_end_line
                    
                    new_metadata = ChunkMetadata(
                        repo=chunk.metadata.repo,
                        branch=chunk.metadata.branch,
                        file_path=chunk.metadata.file_path,
                        language=chunk.metadata.language,
                        chunk_id=new_chunk_id,
                        chunk_index=chunk.metadata.chunk_index,
                        start_line=start_line,
                        end_line=end_line,
                        chunk_type=chunk.metadata.chunk_type,
                        symbol=chunk.metadata.symbol,
                        imports=chunk.metadata.imports if sub_idx == 0 else None,
                    )
                    
                    result.append(Chunk(
                        content=sub_text,
                        metadata=new_metadata,
                        token_count=self._count_tokens(sub_text)
                    ))
        
        return result
    
    def _extract_imports(self, content: str, language: Optional[str]) -> Optional[str]:
        """Extract import block from code."""
        if not language:
            return None
        
        lines = content.split('\n')
        import_lines = []
        
        if language == 'Python':
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    import_lines.append(line)
                elif import_lines and not stripped:
                    continue
                elif import_lines:
                    break
        
        elif language in ['JavaScript', 'TypeScript']:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('export '):
                    import_lines.append(line)
                elif import_lines and not stripped:
                    continue
                elif import_lines:
                    break
        
        elif language == 'Java':
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('import '):
                    import_lines.append(line)
                elif import_lines and not stripped:
                    continue
                elif import_lines:
                    break
        
        return '\n'.join(import_lines) if import_lines else None
    
    def _extract_symbol(self, content: str, language: Optional[str]) -> Optional[str]:
        """Try to extract function/class name from chunk."""
        if not language:
            return None
        
        lines = content.split('\n')
        
        if language == 'Python':
            for line in lines:
                # Class definition
                match = re.match(r'^\s*class\s+(\w+)', line)
                if match:
                    return match.group(1)
                # Function definition
                match = re.match(r'^\s*def\s+(\w+)', line)
                if match:
                    return match.group(1)
        
        elif language in ['JavaScript', 'TypeScript']:
            for line in lines:
                # Function declaration
                match = re.match(r'^\s*function\s+(\w+)', line)
                if match:
                    return match.group(1)
                # Class definition
                match = re.match(r'^\s*class\s+(\w+)', line)
                if match:
                    return match.group(1)
                # Const/let function
                match = re.match(r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', line)
                if match:
                    return match.group(1)
        
        elif language == 'Java':
            for line in lines:
                # Class definition
                match = re.match(r'^\s*(?:public|private|protected)?\s*class\s+(\w+)', line)
                if match:
                    return match.group(1)
                # Method definition
                match = re.match(r'^\s*(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(', line)
                if match:
                    return match.group(1)
        
        return None
    
    def _find_line_numbers_from(self, full_content: str, chunk_content: str, search_from: int) -> tuple[int, int, int]:
        """
        Find start and end line numbers for chunk, searching from position.
        
        Args:
            full_content: Full file content
            chunk_content: Chunk text to find
            search_from: Character position to start searching from
        
        Returns:
            Tuple of (start_line, end_line, next_search_position)
        """
        try:
            # Find chunk starting from last known position
            start_idx = full_content.index(chunk_content, search_from)
            start_line = full_content[:start_idx].count('\n')
            end_line = start_line + chunk_content.count('\n')
            
            # Return next search position (after this chunk)
            # Use min to handle overlap: next chunk may start before this one ends
            next_search = start_idx + len(chunk_content)
            
            return start_line, end_line, next_search
        except ValueError:
            # Chunk not found from search position (shouldn't happen, but handle gracefully)
            # Fall back to estimating based on current position
            start_line = full_content[:search_from].count('\n')
            end_line = start_line + chunk_content.count('\n')
            return start_line, end_line, search_from + len(chunk_content)
