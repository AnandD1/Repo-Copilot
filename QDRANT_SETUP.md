# Qdrant Setup Guide

Complete guide to setting up Qdrant vector database for Repo_Copilot.

## Overview

Qdrant is a high-performance vector database optimized for similarity search. It provides:
- Fast HNSW-based approximate nearest neighbor search
- Rich filtering capabilities for metadata
- Cloud-native architecture with horizontal scaling
- Built-in payload indexing for fast filtered searches
- Simple HTTP/gRPC API

## Installation Options

### Option 1: Docker (Recommended)

**Prerequisites:** Docker installed on your system

```bash
# Pull Qdrant image
docker pull qdrant/qdrant

# Run Qdrant container
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant
```

**For Windows PowerShell:**
```powershell
docker run -p 6333:6333 -p 6334:6334 `
    -v ${PWD}/qdrant_storage:/qdrant/storage:z `
    qdrant/qdrant
```

The service will be available at:
- REST API: `http://localhost:6333`
- gRPC API: `http://localhost:6334`
- Dashboard: `http://localhost:6333/dashboard`

### Option 2: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage:z
    restart: unless-stopped
```

Start with:
```bash
docker-compose up -d
```

### Option 3: Local Installation

**Linux/macOS:**
```bash
# Download and install
curl -sSf https://raw.githubusercontent.com/qdrant/qdrant/master/install.sh | sh

# Run Qdrant
./qdrant
```

**Windows:**
Download the latest release from [Qdrant Releases](https://github.com/qdrant/qdrant/releases) and run the executable.

### Option 4: Qdrant Cloud

Use the managed cloud service:
1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io/)
2. Create a cluster
3. Get your API URL and API key
4. Update `.env` with cloud credentials

## Configuration

### 1. Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional, for Qdrant Cloud
QDRANT_COLLECTION_NAME=code_embeddings
```

**For Qdrant Cloud:**
```bash
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-api-key-here
QDRANT_COLLECTION_NAME=code_embeddings
```

### 2. Install Python Client

```bash
pip install qdrant-client>=1.7.0
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

## Collection Schema

The application automatically creates a collection with:

- **Vector Configuration:**
  - Dimension: 3072 (Google Gemini embeddings)
  - Distance: COSINE similarity
  - Index: HNSW (Hierarchical Navigable Small World)

- **Payload Indexes** (for fast filtering):
  - `chunk_id` (keyword)
  - `repo` (keyword)
  - `branch` (keyword)
  - `file_path` (text)
  - `language` (keyword)

- **Metadata Fields:**
  - `chunk_index`, `start_line`, `end_line`
  - `chunk_type`, `symbol`, `imports`
  - `embedding_model`, `embedding_dimension`, `token_count`
  - `content_hash`, `content`, `created_at`

## Testing

### 1. Verify Qdrant is Running

```bash
curl http://localhost:6333/healthz
```

Expected response: `{"title":"healthz","version":"1.x.x"}`

### 2. Check Dashboard

Open browser: `http://localhost:6333/dashboard`

### 3. Run Test Script

```bash
# From project root
python -m app.storage.vector_store
```

Or run the end-to-end pipeline test:
```bash
python test_vector_storage.py
```

## Usage Examples

### Basic Usage

```python
from app.storage.vector_store import QdrantVectorStore

# Initialize (auto-creates collection)
vector_store = QdrantVectorStore()

# Insert embeddings
vector_store.insert_embeddings(
    embeddings=embedding_results,
    metadata_list=metadata_list,
    contents=contents,
    upsert=True  # Update if exists
)

# Search similar vectors
results = vector_store.similarity_search(
    query_embedding=query_vector,
    limit=10,
    repo="pallets/flask",
    language="python",
    min_similarity=0.7
)

# Get statistics
stats = vector_store.get_statistics()
print(f"Total chunks: {stats['total_chunks']}")
```

### Advanced Filtering

```python
# Search within specific file
results = vector_store.similarity_search(
    query_embedding=query_vector,
    file_path="src/app.py",
    limit=5
)

# Search specific branch
results = vector_store.similarity_search(
    query_embedding=query_vector,
    repo="myorg/myrepo",
    branch="develop",
    limit=10
)

# Delete repository data
deleted = vector_store.delete_by_repo(
    repo="pallets/flask",
    branch="main"  # Optional
)
```

## Performance Tuning

### HNSW Parameters

For better performance, tune HNSW parameters when creating collection:

```python
from qdrant_client.models import HnswConfigDiff

self.client.update_collection(
    collection_name=self.collection_name,
    hnsw_config=HnswConfigDiff(
        m=16,  # Number of connections (default: 16)
        ef_construct=100,  # Construction time (higher = better quality)
    )
)
```

### Search Parameters

```python
from qdrant_client.models import SearchParams

results = self.client.search(
    collection_name=self.collection_name,
    query_vector=query_vector,
    search_params=SearchParams(
        hnsw_ef=128,  # Search effort (higher = better recall)
        exact=False   # Use approximate search
    )
)
```

### Optimization Settings

In `.env`:
```bash
# Increase memory limit for better performance
QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=4
QDRANT__STORAGE__PERFORMANCE__MAX_OPTIMIZATION_THREADS=2
```

## Monitoring

### Collection Info

```python
info = vector_store.client.get_collection(vector_store.collection_name)
print(f"Points: {info.points_count}")
print(f"Indexed: {info.indexed_vectors_count}")
print(f"Status: {info.status}")
```

### Dashboard Metrics

Access `http://localhost:6333/dashboard` for:
- Collection statistics
- Query performance
- Memory usage
- Index health

## Backup & Restore

### Backup Collection

```bash
# Create snapshot
curl -X POST 'http://localhost:6333/collections/code_embeddings/snapshots'

# Download snapshot (replace {snapshot-name} with actual name)
curl 'http://localhost:6333/collections/code_embeddings/snapshots/{snapshot-name}' \
    --output snapshot.snapshot
```

### Restore Collection

```bash
# Upload snapshot
curl -X POST 'http://localhost:6333/collections/code_embeddings/snapshots/upload' \
    -H 'Content-Type: multipart/form-data' \
    -F 'snapshot=@snapshot.snapshot'

# Restore from snapshot
curl -X PUT 'http://localhost:6333/collections/code_embeddings/snapshots/recover' \
    -H 'Content-Type: application/json' \
    -d '{"location": "http://localhost:6333/collections/code_embeddings/snapshots/{snapshot-name}"}'
```

## Troubleshooting

### Connection Refused

**Problem:** `ConnectionRefusedError: [Errno 111] Connection refused`

**Solutions:**
1. Verify Qdrant is running: `docker ps` or check process
2. Check port availability: `netstat -an | grep 6333`
3. Verify URL in `.env`: `QDRANT_URL=http://localhost:6333`

### Dimension Mismatch

**Problem:** `Wrong vector dimension: expected 3072, got XXXX`

**Solutions:**
1. Check embedding model: Must use Google Gemini (3072D)
2. Verify `EMBEDDING_DIMENSION=3072` in settings
3. Delete and recreate collection if changed

### Slow Searches

**Problem:** Queries taking too long

**Solutions:**
1. Increase `hnsw_ef` parameter (default: 128)
2. Create payload indexes for frequently filtered fields
3. Use approximate search (`exact=False`)
4. Consider quantization for large collections

### Out of Memory

**Problem:** Qdrant crashes or becomes unresponsive

**Solutions:**
1. Increase Docker memory limit
2. Enable quantization to reduce memory footprint
3. Use disk-based storage for vectors
4. Scale horizontally with Qdrant cluster

## Migration from PostgreSQL + pgvector

If migrating from PostgreSQL:

1. **Export existing embeddings:**
   ```python
   # Connect to PostgreSQL
   import psycopg2
   conn = psycopg2.connect(postgres_connection_string)
   
   # Export data
   cursor = conn.cursor()
   cursor.execute("SELECT * FROM embeddings")
   rows = cursor.fetchall()
   ```

2. **Import to Qdrant:**
   ```python
   from app.storage.vector_store import QdrantVectorStore
   
   vector_store = QdrantVectorStore()
   
   # Convert and insert
   for row in rows:
       # Transform to EmbeddingResult format
       vector_store.insert_embeddings(...)
   ```

3. **Verify migration:**
   ```python
   stats = vector_store.get_statistics()
   print(f"Migrated {stats['total_chunks']} chunks")
   ```

## Additional Resources

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Python Client API](https://github.com/qdrant/qdrant-client)
- [Performance Tuning](https://qdrant.tech/documentation/guides/optimization/)
- [Cloud Getting Started](https://qdrant.tech/documentation/cloud/)

## Support

For issues:
1. Check Qdrant logs: `docker logs <container-id>`
2. Verify dashboard: `http://localhost:6333/dashboard`
3. Review [Qdrant GitHub Issues](https://github.com/qdrant/qdrant/issues)
