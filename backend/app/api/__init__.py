"""
API module for the Labgrid Dashboard backend.
"""

from fastapi import APIRouter

from .routes import health_router, presets_router, targets_router
from .websocket import router as websocket_router

# Create main API router with /api prefix
api_router = APIRouter(prefix="/api")

# Include sub-routers
api_router.include_router(health_router)
api_router.include_router(targets_router)
api_router.include_router(presets_router)
api_router.include_router(websocket_router)

__all__ = [
    "api_router",
    "health_router",
    "targets_router",
    "presets_router",
    "websocket_router",
]
