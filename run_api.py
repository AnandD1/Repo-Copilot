"""Run the FastAPI application for HITL interface."""

import uvicorn
import os
from pathlib import Path

if __name__ == "__main__":
    # Set working directory to project root
    os.chdir(Path(__file__).parent)
    
    # Run FastAPI server
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"]
    )
