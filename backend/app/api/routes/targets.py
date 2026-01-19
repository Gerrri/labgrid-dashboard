"""
REST API routes for target operations.
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.responses import CommandExecutionRequest, ErrorResponse, TargetListResponse, ScheduledCommandsResponse
from app.models.target import Command, CommandOutput, ScheduledCommand, Target
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient
from app.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/targets", tags=["targets"])

# Global instances - will be set by main app
_labgrid_client: LabgridClient | None = None
_command_service: CommandService | None = None
_scheduler_service: SchedulerService | None = None


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
    summary="Get available commands",
    description="Returns the list of available commands for a target.",
    responses={
        404: {"model": ErrorResponse, "description": "Target not found"},
    },
)
async def get_target_commands(
    name: str,
    client: LabgridClient = Depends(get_labgrid_client),
    cmd_service: CommandService = Depends(get_command_service),
) -> List[Command]:
    """Get available commands for a specific target."""
    # Verify target exists
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )

    # Return all available commands (same for all targets)
    return cmd_service.get_commands()


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
) -> CommandOutput:
    """Execute a predefined command on a target."""
    # Verify target exists
    target = await client.get_place_info(name)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{name}' not found",
        )

    # Get the command from configuration
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
            timestamp=datetime.utcnow(),
            exit_code=exit_code,
        )
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        output = CommandOutput(
            command=command.command,
            output=f"Error executing command: {str(e)}",
            timestamp=datetime.utcnow(),
            exit_code=1,
        )

    return output
