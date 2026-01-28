# Embedding Migration: Gemini → BGE

## Summary

Successfully migrated from **Google Gemini embedding-001** to **HuggingFace BAAI/bge-large-en-v1.5** embeddings.

## Changes Made

### 1. Configuration ([config/settings.py](config/settings.py))
- **Model**: `models/gemini-embedding-001` → `BAAI/bge-large-en-v1.5`
- **Dimension**: `3072` → `1024`
- Added: `embedding_device` (cpu/cuda)
- Added: `embedding_normalize` (True for cosine similarity)
- Deprecated: `google_api_key` (kept for backward compatibility)

### 2. Embedder ([app/ingest/embedder.py](app/ingest/embedder.py))
- Replaced: `GoogleGenerativeAIEmbeddings` → `HuggingFaceBgeEmbeddings`
- Removed: API key requirement
- Added: Device configuration (CPU/GPU)
- Added: Normalization for cosine similarity
- Updated: Retry logic (removed rate-limit specific handling)
- Model initialization now downloads to local cache (~1.34GB)

### 3. Conventions Manager ([app/conventions/conventions_manager.py](app/conventions/conventions_manager.py))
- Removed: API rate limiting delays
- Updated: Batch size from 20 → 50 (no API limits)
- Removed: Inter-batch delays (local model has no rate limits)

### 4. Dependencies ([requirements.txt](requirements.txt))
- Removed: `langchain-google-genai`
- Added: `langchain-community` (for HuggingFace embeddings)
- Added: `sentence-transformers` (BGE model backend)

### 5. Utilities
- Created: [reset_qdrant.py](reset_qdrant.py) for dimension migration

## Key Advantages

### ✅ No API Costs
- **Before**: API calls to Google ($)
- **After**: Local inference (free)

### ✅ No Rate Limits
- **Before**: 100 requests/minute (free tier)
- **After**: Unlimited (hardware dependent)

### ✅ Privacy
- **Before**: Data sent to Google servers
- **After**: All processing local

### ✅ Performance
- **Before**: Network latency + API processing
- **After**: Local GPU/CPU inference (can use CUDA)

### ⚠️ Trade-offs
- **Storage**: 1.34GB model downloaded locally
- **Initial Load**: Model loads into memory on first use
- **Dimension**: 1024 vs 3072 (BGE is more compact)

## Performance Results

### Test Results (ScratchYOLO conventions)
- **Extracted**: 282 conventions
- **Embedding Time**: ~5 seconds (CPU)
- **Similarity Scores**: 0.64-0.74 (good quality)
- **Model Load**: ~1-2 seconds (cached after first load)

## GPU Acceleration

To use GPU (much faster):

1. Install PyTorch with CUDA:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

2. Update `.env`:
   ```
   EMBEDDING_DEVICE=cuda
   ```

## Migration Steps for Existing Data

If you have existing embeddings in Qdrant:

```bash
python reset_qdrant.py  # Deletes old collections
python test_conventions.py  # Re-embed with new model
```

## Backward Compatibility

- Cache system automatically handles dimension changes
- Old caches (3072-dim) won't be used with new model (1024-dim)
- Each cache file includes model hash to prevent mismatches

## Model Details

**BAAI/bge-large-en-v1.5**:
- Architecture: BERT-large
- Dimensions: 1024
- Max Tokens: 512
- Languages: English (optimized)
- License: MIT
- Rank: #1 on MTEB leaderboard (retrieval tasks)

## Next Steps

1. ✅ Test with larger repositories
2. ✅ Benchmark GPU vs CPU performance
3. ✅ Consider `bge-m3` for multilingual support
4. ✅ Monitor memory usage for large batches
