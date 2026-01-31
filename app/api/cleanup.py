"""Cleanup utilities for managing temporary repos and embeddings."""

import shutil
from pathlib import Path
from typing import Optional
from qdrant_client import QdrantClient
from config.settings import Settings


class CleanupManager:
    """Manage cleanup of temporary resources."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.temp_repos_dir = Path("temp_repos")
        self.embedding_cache_dir = Path("embedding_cache")
        try:
            self.qdrant_client = QdrantClient(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key
            )
        except Exception as e:
            print(f"⚠️  Qdrant connection failed: {e}")
            self.qdrant_client = None
    
    def cleanup_temp_repo(self, repo_name: str):
        """Delete temporary cloned repository."""
        repo_path = self.temp_repos_dir / repo_name
        if repo_path.exists():
            shutil.rmtree(repo_path)
            print(f"✓ Deleted temp repo: {repo_path}")
    
    def cleanup_all_temp_repos(self):
        """Delete all temporary repositories."""
        if self.temp_repos_dir.exists():
            shutil.rmtree(self.temp_repos_dir)
            self.temp_repos_dir.mkdir(exist_ok=True)
            print(f"✓ Cleaned all temp repos")
    
    def cleanup_embedding_cache(self, repo_id: str):
        """Delete embedding cache for specific repo."""
        if not self.embedding_cache_dir.exists():
            return
        
        deleted_count = 0
        for cache_file in self.embedding_cache_dir.glob("*.json"):
            if repo_id in cache_file.stem:
                cache_file.unlink()
                deleted_count += 1
        
        print(f"✓ Deleted {deleted_count} embedding cache files for {repo_id}")
    
    def cleanup_all_embedding_cache(self):
        """Delete all embedding cache files."""
        if self.embedding_cache_dir.exists():
            deleted_count = len(list(self.embedding_cache_dir.glob("*.json")))
            shutil.rmtree(self.embedding_cache_dir)
            self.embedding_cache_dir.mkdir(exist_ok=True)
            print(f"✓ Deleted {deleted_count} embedding cache files")
    
    def cleanup_qdrant_collection(self, repo_id: str):
        """Delete vectors for specific repo from Qdrant."""
        if not self.qdrant_client:
            print(f"⚠️  Qdrant not available, skipping vector cleanup for {repo_id}")
            return
        
        try:
            collection_name = self.settings.qdrant_collection_name
            
            # Delete by filter
            self.qdrant_client.delete(
                collection_name=collection_name,
                points_selector={
                    "filter": {
                        "must": [
                            {
                                "key": "repo_id",
                                "match": {"value": repo_id}
                            }
                        ]
                    }
                }
            )
            print(f"✓ Deleted Qdrant vectors for {repo_id}")
        except Exception as e:
            print(f"⚠️  Could not delete Qdrant vectors: {e}")
    
    def cleanup_all_qdrant_vectors(self):
        """Recreate Qdrant collection (delete all vectors)."""
        if not self.qdrant_client:
            print(f"⚠️  Qdrant not available, skipping collection cleanup")
            return
        
        try:
            collection_name = self.settings.qdrant_collection_name
            
            # Delete and recreate collection
            self.qdrant_client.delete_collection(collection_name)
            
            from qdrant_client.models import Distance, VectorParams
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.settings.embedding_dimension,
                    distance=Distance.COSINE
                )
            )
            print(f"✓ Recreated Qdrant collection: {collection_name}")
        except Exception as e:
            print(f"⚠️  Could not recreate Qdrant collection: {e}")
    
    def cleanup_for_new_repo(self, old_repo_id: str, new_repo_id: str):
        """Cleanup when switching to a different repository."""
        print(f"\n🧹 Cleaning up for new repo: {new_repo_id}")
        
        # Clean old repo's resources
        self.cleanup_qdrant_collection(old_repo_id)
        self.cleanup_embedding_cache(old_repo_id)
        
        # Clean all temp repos
        self.cleanup_all_temp_repos()
        
        print("✓ Cleanup complete\n")
    
    def cleanup_for_same_repo(self, repo_id: str):
        """Cleanup when using same repo (different PR)."""
        print(f"\n🧹 Using existing embeddings for: {repo_id}")
        
        # Only clean temp repos
        self.cleanup_all_temp_repos()
        
        print("✓ Temp repos cleaned, embeddings preserved\n")
    
    def full_cleanup(self):
        """Complete cleanup of all resources."""
        print("\n🧹 Performing full cleanup...")
        
        self.cleanup_all_temp_repos()
        self.cleanup_all_embedding_cache()
        self.cleanup_all_qdrant_vectors()
        
        print("✓ Full cleanup complete\n")
