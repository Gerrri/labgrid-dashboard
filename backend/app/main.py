"""
Labgrid Dashboard Backend - FastAPI Application

Main entry point for the Labgrid Dashboard API server.
Handles startup/shutdown lifecycle, CORS configuration, and route registration.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.api import api_router
from app.api.routes.health import set_labgrid_client as set_health_labgrid_client
from app.api.routes.targets import set_command_service as set_targets_command_service
from app.api.routes.targets import set_labgrid_client as set_targets_labgrid_client
from app.api.routes.targets import set_preset_service as set_targets_preset_service
from app.api.routes.targets import (
    set_scheduler_service as set_targets_scheduler_service,
)
from app.api.websocket import set_command_service as set_ws_command_service
from app.api.websocket import set_labgrid_client as set_ws_labgrid_client
from app.api.websocket import set_scheduler_service as set_ws_scheduler_service
from app.config import get_settings
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient
from app.services.preset_service import PresetService
from app.services.scheduler_service import SchedulerService
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global service instances
labgrid_client: LabgridClient | None = None
command_service: CommandService | None = None
scheduler_service: SchedulerService | None = None
preset_service: PresetService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle - startup and shutdown events.

    Handles:
    - Loading configuration
    - Connecting to Labgrid Coordinator
    - Loading command definitions
    - Initializing preset service
    - Starting scheduled command execution
    """
    global labgrid_client, command_service, scheduler_service, preset_service

    settings = get_settings()
    logger.info("Starting Labgrid Dashboard Backend...")

    # Initialize command service
    command_service = CommandService(commands_file=settings.commands_file)
    command_service.load()
    logger.info(f"Loaded {len(command_service.get_presets())} presets")
    logger.info(
        f"Loaded {len(command_service.get_commands())} commands (default preset)"
    )
    logger.info(
        f"Loaded {len(command_service.get_scheduled_commands())} scheduled commands (default preset)"
    )

    # Initialize preset service
    preset_service = PresetService(
        presets_file=settings.presets_file,
        default_preset_id=command_service.get_default_preset_id(),
    )
    preset_service.load()
    logger.info(
        f"Loaded {len(preset_service.get_all_assignments())} target preset assignments"
    )

    # Initialize and connect Labgrid client
    labgrid_client = LabgridClient(
        url=settings.coordinator_url,
        realm=settings.coordinator_realm,
        timeout=settings.coordinator_timeout,
    )
    await labgrid_client.connect()

    # Wait for coordinator synchronization to complete before starting scheduler
    # This ensures all targets are known before scheduled commands start executing
    logger.info("Waiting for coordinator synchronization...")
    await asyncio.sleep(2)

    # Initialize scheduler service with preset support
    scheduler_service = SchedulerService()

    # Build preset commands dictionary for scheduler
    preset_commands = {}
    for preset in command_service.get_presets():
        preset_detail = command_service.get_preset(preset.id)
        if preset_detail:
            preset_commands[preset.id] = preset_detail.scheduled_commands

    scheduler_service.set_preset_commands(preset_commands)
    scheduler_service.set_execute_callback(labgrid_client.execute_command)
    scheduler_service.set_get_targets_callback(labgrid_client.get_places)
    scheduler_service.set_get_target_preset_callback(preset_service.get_target_preset)
    await scheduler_service.start()

    # Set the client and service instances for all modules
    set_health_labgrid_client(labgrid_client)
    set_targets_labgrid_client(labgrid_client)
    set_targets_command_service(command_service)
    set_targets_scheduler_service(scheduler_service)
    set_targets_preset_service(preset_service)
    set_ws_labgrid_client(labgrid_client)
    set_ws_command_service(command_service)
    set_ws_scheduler_service(scheduler_service)

    logger.info("Labgrid Dashboard Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Labgrid Dashboard Backend...")

    if scheduler_service:
        await scheduler_service.stop()

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
            "presets": "/api/presets",
            "websocket": "/api/ws",
        }

    return app


# Create the app instance
app = create_app()


# Create the app instance
app = create_app()
