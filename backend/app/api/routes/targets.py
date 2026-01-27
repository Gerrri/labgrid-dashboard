"""
REST API routes for target and preset operations.
"""

import logging
from datetime import datetime, timezone
from typing import List

from app.models.responses import (
    CommandExecutionRequest,
    ErrorResponse,
    PresetsListResponse,
    ScheduledCommandsResponse,
    SetTargetPresetRequest,
    TargetListResponse,
    TargetPresetResponse,
)
from app.models.target import (
    Command,
    CommandOutput,
    Preset,
    PresetDetail,
    ScheduledCommand,
    Target,
)
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient
from app.services.preset_service import PresetService
from app.services.scheduler_service import SchedulerService
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/targets", tags=["targets"])

# Global instances - will be set by main app
_labgrid_client: LabgridClient | None = None
_command_service: CommandService | None = None
_scheduler_service: SchedulerService | None = None
_preset_service: PresetService | None = None


def set_labgrid_client(client: LabgridClient) -> None:
    """Set the global Labgrid client instance."""
    global _labgrid_client
    _labgrid_client = client


def set_command_service(service: CommandService) -> None:
    """Set the global command service instance."""
    global _command_service
    _command_service = service


def set_scheduler_service(service: SchedulerService) -> None:
    """Set the global scheduler service instance."""
    global _scheduler_service
    _scheduler_service = service


def set_preset_service(service: PresetService) -> None:
    """Set the global preset service instance."""
    global _preset_service
    _preset_service = service


def get_labgrid_client() -> LabgridClient:
    """Dependency to get the Labgrid client."""
    if _labgrid_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Labgrid client not initialized",
        )
    return _labgrid_client


def get_command_service() -> CommandService:
    """Dependency to get the command service."""
    if _command_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Command service not initialized",
        )
    return _command_service


def get_scheduler_service() -> SchedulerService:
    """Dependency to get the scheduler service."""
    if _scheduler_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not initialized",
        )
    return _scheduler_service


def get_preset_service() -> PresetService:
    """Dependency to get the preset service."""
    if _preset_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preset service not initialized",
        )
    return _preset_service


@router.get(
    "",
    response_model=TargetListResponse,
    summary="Get all targets",
    description="Returns a list of all targets with their status, acquired_by, ip_address, and scheduled command outputs.",
)
async def get_targets(
    client: LabgridClient = Depends(get_labgrid_client),
    scheduler: SchedulerService = Depends(get_scheduler_service),
) -> TargetListResponse:
    """Get all targets from the Labgrid coordinator with scheduled command outputs."""
    targets = await client.get_places()

    # Enrich targets with scheduled command outputs
    for target in targets:
        target.scheduled_outputs = scheduler.get_outputs_for_target(target.name)

    return TargetListResponse(targets=targets, total=len(targets))


@router.get(
    "/scheduled-commands",
    response_model=ScheduledCommandsResponse,
    summary="Get scheduled commands",
    description="Returns the list of configured scheduled commands.",
)
async def get_scheduled_commands(
    scheduler: SchedulerService = Depends(get_scheduler_service),
) -> ScheduledCommandsResponse:
    """Get all configured scheduled commands."""
    commands = scheduler.get_commands()
    return ScheduledCommandsResponse(commands=commands)


@router.get(
    "/{name}",
    response_model=Target,
    summary="Get single target",
    description="Returns detailed information about a specific target.",
    responses={
        404: {"model": ErrorResponse, "description": "Target not found"},
    },
)
async def get_target(
    name: str,
    client: LabgridClient = Depends(get_labgrid_client),
) -> Target:
    """Get a specific target by name."""
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )
    return target


@router.get(
    "/{name}/commands",
    response_model=List[Command],
    summary="Get available commands for target",
    description="Returns the list of available commands for a target based on its assigned preset.",
    responses={
        404: {"model": ErrorResponse, "description": "Target not found"},
    },
)
async def get_target_commands(
    name: str,
    client: LabgridClient = Depends(get_labgrid_client),
    cmd_service: CommandService = Depends(get_command_service),
    preset_service: PresetService = Depends(get_preset_service),
) -> List[Command]:
    """Get available commands for a specific target based on its preset."""
    # Verify target exists
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )

    # Get the target's preset and return its commands
    preset_id = preset_service.get_target_preset(name)
    return cmd_service.get_commands_for_preset(preset_id)


@router.post(
    "/{name}/command",
    response_model=CommandOutput,
    summary="Execute command",
    description="Execute a predefined command on a target.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid command"},
        404: {"model": ErrorResponse, "description": "Target not found"},
    },
)
async def execute_command(
    name: str,
    request: CommandExecutionRequest,
    client: LabgridClient = Depends(get_labgrid_client),
    cmd_service: CommandService = Depends(get_command_service),
    preset_service: PresetService = Depends(get_preset_service),
) -> CommandOutput:
    """Execute a predefined command on a target."""
    # Verify target exists
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )

    # Get the target's preset
    preset_id = preset_service.get_target_preset(name)

    # Get the command from the target's preset
    command = cmd_service.get_command_by_name_for_preset(
        preset_id, request.command_name
    )

    # If not found in preset, try to find it globally (backwards compatibility)
    if command is None:
        command = cmd_service.get_command_by_name(request.command_name)

    if command is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Command '{request.command_name}' not found in configuration",
        )

    # Execute the command via Labgrid Coordinator
    logger.info(f"Executing command '{command.name}' on target '{name}'")

    try:
        # Execute command through the labgrid client
        result_output, exit_code = await client.execute_command(name, command.command)

        output = CommandOutput(
            command=command.command,
            output=result_output,
            timestamp=datetime.now(timezone.utc),
            exit_code=exit_code,
        )
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        output = CommandOutput(
            command=command.command,
            output=f"Error executing command: {str(e)}",
            timestamp=datetime.now(timezone.utc),
            exit_code=1,
        )

    return output


@router.get(
    "/{name}/preset",
    response_model=TargetPresetResponse,
    summary="Get target preset",
    description="Returns the currently assigned preset for a target.",
    responses={
        404: {"model": ErrorResponse, "description": "Target not found"},
    },
)
async def get_target_preset(
    name: str,
    client: LabgridClient = Depends(get_labgrid_client),
    cmd_service: CommandService = Depends(get_command_service),
    preset_service: PresetService = Depends(get_preset_service),
) -> TargetPresetResponse:
    """Get the preset assigned to a target."""
    # Verify target exists
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )

    # Get the target's preset
    preset_id = preset_service.get_target_preset(name)
    preset_detail = cmd_service.get_preset(preset_id)

    if preset_detail is None:
        # Fallback to default preset if the assigned one doesn't exist
        default_id = cmd_service.get_default_preset_id()
        preset_detail = cmd_service.get_preset(default_id)
        preset_id = default_id

    # Convert to summary Preset
    preset = Preset(
        id=preset_detail.id if preset_detail else preset_id,
        name=preset_detail.name if preset_detail else preset_id,
        description=preset_detail.description if preset_detail else "",
    )

    return TargetPresetResponse(
        target_name=name,
        preset_id=preset_id,
        preset=preset,
    )


@router.put(
    "/{name}/preset",
    response_model=TargetPresetResponse,
    summary="Set target preset",
    description="Assign a preset to a target.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid preset ID"},
        404: {"model": ErrorResponse, "description": "Target not found"},
    },
)
async def set_target_preset(
    name: str,
    request: SetTargetPresetRequest,
    client: LabgridClient = Depends(get_labgrid_client),
    cmd_service: CommandService = Depends(get_command_service),
    preset_service: PresetService = Depends(get_preset_service),
) -> TargetPresetResponse:
    """Set the preset for a target."""
    # Verify target exists
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )

    # Verify preset exists
    preset_detail = cmd_service.get_preset(request.preset_id)
    if preset_detail is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Preset '{request.preset_id}' not found",
        )

    # Set the preset assignment
    preset_service.set_target_preset(name, request.preset_id)
    logger.info(f"Set preset for target '{name}' to '{request.preset_id}'")

    # Convert to summary Preset
    preset = Preset(
        id=preset_detail.id,
        name=preset_detail.name,
        description=preset_detail.description,
    )

    return TargetPresetResponse(
        target_name=name,
        preset_id=request.preset_id,
        preset=preset,
    )


# Create a separate router for preset endpoints (not under /targets prefix)
presets_router = APIRouter(prefix="/presets", tags=["presets"])


@presets_router.get(
    "",
    response_model=PresetsListResponse,
    summary="Get all presets",
    description="Returns a list of all available hardware presets.",
)
async def get_presets(
    cmd_service: CommandService = Depends(get_command_service),
) -> PresetsListResponse:
    """Get all available presets."""
    presets = cmd_service.get_presets()
    default_preset = cmd_service.get_default_preset_id()

    return PresetsListResponse(
        presets=presets,
        default_preset=default_preset,
    )


@presets_router.get(
    "/{preset_id}",
    response_model=PresetDetail,
    summary="Get preset details",
    description="Returns detailed information about a specific preset including its commands.",
    responses={
        404: {"model": ErrorResponse, "description": "Preset not found"},
    },
)
async def get_preset_detail(
    preset_id: str,
    cmd_service: CommandService = Depends(get_command_service),
) -> PresetDetail:
    """Get detailed information about a preset."""
    preset = cmd_service.get_preset(preset_id)
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_id}' not found",
        )
    return preset
