"""
Labgrid Dashboard Backend - FastAPI Application

This is a placeholder entry point. The full implementation will be added in subsequent tasks.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Labgrid Dashboard API",
    description="REST API for Labgrid Dashboard - Monitor and interact with DUTs",
    version="0.1.0",
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "labgrid-dashboard-backend"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Labgrid Dashboard API",
        "docs": "/docs",
        "health": "/api/health",
    }
