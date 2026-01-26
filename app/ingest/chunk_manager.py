"""Chunk manager for coordinating file chunking."""

from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.ingest.chunker import CodeChunker, Chunk, ChunkType
from app.ingest.ingestor import IngestionResult
from app.ingest.filter import FileInfo


@dataclass
class ChunkingResult:
    """Result of chunking operation."""
    chunks: List[Chunk]
    total_chunks: int
    total_tokens: int
    chunks_by_type: Dict[str, int]
    files_processed: int
    files_skipped: int
    
    def __str__(self):
        """String representation."""
        return f"""
Chunking Result:
  Total chunks: {self.total_chunks}
  Total tokens: {self.total_tokens:,}
  Files processed: {self.files_processed}
  Files skipped: {self.files_skipped}
  
  Chunks by type:
    Code: {self.chunks_by_type.get('code', 0)}
    Documentation: {self.chunks_by_type.get('doc', 0)}
    Config: {self.chunks_by_type.get('config', 0)}
        """.strip()


class ChunkManager:
    """
    Manages chunking of repository files.
    
    Coordinates the chunking process across all files and provides
    statistics about the chunking operation.
    """
    
    def __init__(self, repo_name: str, branch: str):
        """
        Initialize chunk manager.
        
        Args:
            repo_name: Repository name (owner/repo)
            branch: Branch name
        """
        self.repo_name = repo_name
        self.branch = branch
        self.chunker = CodeChunker(repo_name=repo_name, branch=branch)
    
    def chunk_files(self, files: List[FileInfo]) -> ChunkingResult:
        """
        Chunk a list of files.
        
        Args:
            files: List of FileInfo objects to chunk
        
        Returns:
            ChunkingResult with all chunks and statistics
        """
        all_chunks = []
        files_processed = 0
        files_skipped = 0
        
        print(f"\nChunking {len(files)} files...")
        
        for file_info in files:
            try:
                chunks = self.chunker.chunk_file(file_info)
                if chunks:
                    all_chunks.extend(chunks)
                    files_processed += 1
                else:
                    files_skipped += 1
            except Exception as e:
                print(f"Warning: Could not chunk {file_info.relative_path}: {e}")
                files_skipped += 1
        
        # Calculate statistics
        total_tokens = sum(chunk.token_count for chunk in all_chunks)
        chunks_by_type = {
            'code': sum(1 for c in all_chunks if c.metadata.chunk_type == ChunkType.CODE),
            'doc': sum(1 for c in all_chunks if c.metadata.chunk_type == ChunkType.DOC),
            'config': sum(1 for c in all_chunks if c.metadata.chunk_type == ChunkType.CONFIG),
        }
        
        result = ChunkingResult(
            chunks=all_chunks,
            total_chunks=len(all_chunks),
            total_tokens=total_tokens,
            chunks_by_type=chunks_by_type,
            files_processed=files_processed,
            files_skipped=files_skipped
        )
        
        print(f"✓ Chunking complete: {len(all_chunks)} chunks from {files_processed} files")
        
        return result
    
    def chunk_ingestion_result(self, ingestion_result: IngestionResult) -> ChunkingResult:
        """
        Chunk all files from an ingestion result.
        
        Args:
            ingestion_result: Result from repository ingestion
        
        Returns:
            ChunkingResult with all chunks
        """
        return self.chunk_files(ingestion_result.filtered_files)
    
    def get_chunks_by_type(self, result: ChunkingResult, chunk_type: ChunkType) -> List[Chunk]:
        """
        Get chunks of a specific type.
        
        Args:
            result: Chunking result
            chunk_type: Type of chunks to retrieve
        
        Returns:
            List of chunks of specified type
        """
        return [c for c in result.chunks if c.metadata.chunk_type == chunk_type]
    
    def get_chunks_by_language(self, result: ChunkingResult, language: str) -> List[Chunk]:
        """
        Get chunks of a specific language.
        
        Args:
            result: Chunking result
            language: Language name
        
        Returns:
            List of chunks in that language
        """
        return [c for c in result.chunks if c.metadata.language == language]
    
    def get_chunks_by_file(self, result: ChunkingResult, file_path: str) -> List[Chunk]:
        """
        Get all chunks from a specific file.
        
        Args:
            result: Chunking result
            file_path: Relative file path
        
        Returns:
            List of chunks from that file
        """
        return [c for c in result.chunks if c.metadata.file_path == file_path]
    
    def get_statistics(self, result: ChunkingResult) -> Dict:
        """
        Get detailed statistics about chunking.
        
        Args:
            result: Chunking result
        
        Returns:
            Dictionary with detailed statistics
        """
        chunks = result.chunks
        
        return {
            'total_chunks': len(chunks),
            'total_tokens': sum(c.token_count for c in chunks),
            'avg_tokens_per_chunk': sum(c.token_count for c in chunks) / len(chunks) if chunks else 0,
            'max_tokens': max((c.token_count for c in chunks), default=0),
            'min_tokens': min((c.token_count for c in chunks), default=0),
            'chunks_by_type': result.chunks_by_type,
            'files_processed': result.files_processed,
            'files_skipped': result.files_skipped,
        }


def main():
    """Example usage of ChunkManager."""
    from app.ingest.ingestor import RepositoryIngestor
    from app.ingest.loader import LoadMethod
    
    # First, ingest a repository
    print("="*70)
    print("Example: Chunking Repository Files")
    print("="*70)
    
    ingestor = RepositoryIngestor()
    ingestion_result = ingestor.ingest_repository(
        repo_url="https://github.com/pallets/flask",
        method=LoadMethod.API
    )
    
    # Create chunk manager
    chunk_manager = ChunkManager(
        repo_name=ingestion_result.repo_info.full_name,
        branch=ingestion_result.repo_info.default_branch
    )
    
    # Chunk all files
    print("\n" + "="*70)
    print("Chunking Files")
    print("="*70)
    
    chunking_result = chunk_manager.chunk_ingestion_result(ingestion_result)
    print(chunking_result)
    
    # Show statistics
    stats = chunk_manager.get_statistics(chunking_result)
    print(f"\nDetailed Statistics:")
    print(f"  Average tokens/chunk: {stats['avg_tokens_per_chunk']:.0f}")
    print(f"  Max tokens: {stats['max_tokens']}")
    print(f"  Min tokens: {stats['min_tokens']}")
    
    # Show sample chunks
    print(f"\nSample Code Chunks (first 3):")
    code_chunks = chunk_manager.get_chunks_by_type(chunking_result, ChunkType.CODE)
    for chunk in code_chunks[:3]:
        print(f"\n  File: {chunk.metadata.file_path}")
        print(f"  Lines: {chunk.metadata.start_line}-{chunk.metadata.end_line}")
        print(f"  Symbol: {chunk.metadata.symbol}")
        print(f"  Tokens: {chunk.token_count}")
        print(f"  Preview: {chunk.content[:100]}...")


if __name__ == "__main__":
    main()
