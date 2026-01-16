"""
Labgrid Dashboard Backend - FastAPI Application

Main entry point for the Labgrid Dashboard API server.
Handles startup/shutdown lifecycle, CORS configuration, and route registration.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.routes.health import set_labgrid_client as set_health_labgrid_client
from app.api.routes.targets import set_command_service as set_targets_command_service
from app.api.routes.targets import set_labgrid_client as set_targets_labgrid_client
from app.api.websocket import set_command_service as set_ws_command_service
from app.api.websocket import set_labgrid_client as set_ws_labgrid_client
from app.config import get_settings
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global service instances
labgrid_client: LabgridClient | None = None
command_service: CommandService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle - startup and shutdown events.

    Handles:
    - Loading configuration
    - Connecting to Labgrid Coordinator
    - Loading command definitions
    """
    global labgrid_client, command_service

    settings = get_settings()
    logger.info("Starting Labgrid Dashboard Backend...")

    # Initialize command service
    command_service = CommandService(commands_file=settings.commands_file)
    command_service.load()
    logger.info(f"Loaded {len(command_service.get_commands())} commands")

    # Initialize and connect Labgrid client
    labgrid_client = LabgridClient(
        url=settings.coordinator_url,
        realm=settings.coordinator_realm,
        timeout=settings.coordinator_timeout,
    )
    await labgrid_client.connect()

    # Set the client and service instances for all modules
    set_health_labgrid_client(labgrid_client)
    set_targets_labgrid_client(labgrid_client)
    set_targets_command_service(command_service)
    set_ws_labgrid_client(labgrid_client)
    set_ws_command_service(command_service)

    logger.info("Labgrid Dashboard Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Labgrid Dashboard Backend...")

    if labgrid_client:
        await labgrid_client.disconnect()

    logger.info("Labgrid Dashboard Backend stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Labgrid Dashboard API",
        description="REST API for Labgrid Dashboard - Monitor and interact with DUTs",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register main API router (includes all sub-routers)
    app.include_router(api_router)

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "Labgrid Dashboard API",
            "docs": "/docs",
            "health": "/api/health",
            "targets": "/api/targets",
            "websocket": "/api/ws",
        }

    return app


# Create the app instance
app = create_app()
