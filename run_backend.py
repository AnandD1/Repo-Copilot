"""Run FastAPI backend server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=[
            "temp_repos/*",
            "embedding_cache/*",
            "qdrant_storage/*",
            "evaluation_results/*",
            "workflow_runs/*",
            "test_embedding_cache/*",
            "*.pyc",
            "__pycache__/*",
            ".git/*"
        ],
        log_level="info"
    )
