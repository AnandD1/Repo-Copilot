"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="Repo-Copilot API",
    description="AI-powered code review assistant with full PR analysis workflow",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1", tags=["PR Review"])

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Repo-Copilot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "api": "/api/v1"
    }
