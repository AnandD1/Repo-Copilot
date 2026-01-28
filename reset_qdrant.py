"""Reset Qdrant collections to match new embedding dimension."""

from qdrant_client import QdrantClient
from config.settings import settings

def reset_collections():
    """Delete and recreate Qdrant collections with new dimensions."""
    
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=60,
        prefer_grpc=False
    )
    
    collections_to_reset = [
        settings.qdrant_collection_name,  # code_embeddings
        "conventions_index"  # conventions collection
    ]
    
    for collection_name in collections_to_reset:
        try:
            # Check if collection exists
            collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            
            if exists:
                print(f"Deleting collection: {collection_name}")
                client.delete_collection(collection_name)
                print(f"✓ Deleted {collection_name}")
            else:
                print(f"Collection {collection_name} does not exist, skipping...")
        
        except Exception as e:
            print(f"Error processing {collection_name}: {e}")
    
    client.close()
    print("\n✓ Qdrant collections reset complete!")
    print(f"New embedding dimension: {settings.embedding_dimension}")
    print("Next time you run ingestion or conventions, new collections will be created automatically.")

if __name__ == "__main__":
    print("="*70)
    print("QDRANT COLLECTION RESET")
    print("="*70)
    print(f"This will delete existing collections to match new embedding dimension")
    print(f"Old dimension: 3072 (Gemini)")
    print(f"New dimension: {settings.embedding_dimension} (BGE)")
    print("="*70)
    
    response = input("\nContinue? (y/n): ")
    if response.lower() == 'y':
        reset_collections()
    else:
        print("Cancelled.")
