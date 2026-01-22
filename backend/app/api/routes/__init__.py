"""
API routes for the Labgrid Dashboard backend.
"""

from .health import router as health_router
from .targets import presets_router
from .targets import router as targets_router

__all__ = ["health_router", "targets_router", "presets_router"]
__all__ = ["health_router", "targets_router", "presets_router"]
