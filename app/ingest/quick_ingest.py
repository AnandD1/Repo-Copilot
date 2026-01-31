"""Quick ingestion utility for workflow orchestration."""

from typing import Optional, Dict, Any
from pathlib import Path

from app.ingest.ingestor import RepositoryIngestor
from app.ingest.loader import LoadMethod
from app.ingest.chunker import CodeChunker
from app.ingest.embedder import Embedder
from app.ingest.embedding_manager import EmbeddingMetadata
from app.storage import QdrantVectorStore
from config.settings import Settings, settings


def quick_ingest_repo(
    repo_url: str,
    branch: Optional[str] = None,
    settings_obj: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Quick repository ingestion with chunking and embedding.
    
    Args:
        repo_url: GitHub repository URL
        branch: Branch to ingest (default: main)
        settings_obj: Settings instance
        
    Returns:
        Dict with ingestion results
    """
    settings_obj = settings_obj or Settings()
    
    # Initialize components
    ingestor = RepositoryIngestor(github_token=settings_obj.github_token)
    
    # Ingest repository
    print(f"📥 Ingesting repository: {repo_url}")
    result = ingestor.ingest_repository(
        repo_url=repo_url,
        method=LoadMethod.API,
        branch=branch or "main"
    )
    
    print(f"✓ Loaded {result.total_files} files")
    
    # Initialize chunker with repo info
    repo_name = f"{result.repo_info.owner}/{result.repo_info.name}"
    chunker = CodeChunker(repo_name=repo_name, branch=branch or "main")
    embedder = Embedder()
    vector_store = QdrantVectorStore()
    
    # Chunk and embed files
    print("✂️  Chunking code files...")
    all_chunks = []
    all_embeddings = []
    all_metadata = []
    
    for file_info in result.filtered_files:
        try:
            # Chunk file
            chunks = chunker.chunk_file(file_info)
            
            # Embed chunks
            for chunk in chunks:
                try:
                    # Generate embedding
                    embedding_result = embedder.embed_text(chunk.content)
                    
                    # Create metadata
                    metadata = EmbeddingMetadata(
                        chunk_id=chunk.metadata.chunk_id,
                        chunk_index=chunk.metadata.chunk_index,
                        repo=repo_name,
                        branch=branch or "main",
                        file_path=str(file_info.relative_path),
                        language=chunk.metadata.language,
                        start_line=chunk.metadata.start_line,
                        end_line=chunk.metadata.end_line,
                        chunk_type=chunk.metadata.chunk_type.value,
                        symbol=chunk.metadata.symbol,
                        imports=chunk.metadata.imports,
                        embedding_model=settings.embedding_model,
                        embedding_dimension=settings.embedding_dimension,
                        token_count=chunk.token_count,
                        content_hash=f"{chunk.metadata.chunk_id}_{chunk.token_count}",
                    )
                    
                    all_embeddings.append(embedding_result)
                    all_metadata.append(metadata)
                    all_chunks.append(chunk)
                    
                except Exception as embed_error:
                    print(f"⚠️  Error embedding chunk from {file_info.relative_path}: {embed_error}")
                    continue
            
        except Exception as e:
            print(f"⚠️  Error processing {file_info.relative_path}: {e}")
            continue
    
    print(f"✓ Created {len(all_chunks)} chunks")
    
    # Store in Qdrant
    print("💾 Storing embeddings in Qdrant...")
    stored_count = 0
    
    if all_embeddings and len(all_embeddings) == len(all_metadata) == len(all_chunks):
        contents = [chunk.content for chunk in all_chunks]
        stored_count = vector_store.insert_embeddings(
            embeddings=all_embeddings,
            metadata_list=all_metadata,
            contents=contents,
        )
        print(f"✓ Stored {stored_count} embeddings")
    else:
        print(f"⚠️  Mismatch: {len(all_embeddings)} embeddings, {len(all_metadata)} metadata, {len(all_chunks)} chunks")
    
    repo_id = f"{result.repo_info.owner}_{result.repo_info.name}_{branch or 'main'}"
    
    return {
        "success": True,
        "repo_id": repo_id,
        "repo_owner": result.repo_info.owner,
        "repo_name": result.repo_info.name,
        "branch": branch or "main",
        "files_processed": result.total_files,
        "chunks_created": len(all_chunks),
        "chunks_stored": stored_count,
        "local_path": str(result.repo_info.local_path)
    }
