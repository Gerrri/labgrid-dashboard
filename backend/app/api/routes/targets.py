"""
REST API routes for target operations.
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.responses import CommandExecutionRequest, ErrorResponse, TargetListResponse
from app.models.target import Command, CommandOutput, Target
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/targets", tags=["targets"])

# Global instances - will be set by main app
_labgrid_client: LabgridClient | None = None
_command_service: CommandService | None = None


def set_labgrid_client(client: LabgridClient) -> None:
    """Set the global Labgrid client instance."""
    global _labgrid_client
    _labgrid_client = client


def set_command_service(service: CommandService) -> None:
    """Set the global command service instance."""
    global _command_service
    _command_service = service


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


@router.get(
    "",
    response_model=TargetListResponse,
    summary="Get all targets",
    description="Returns a list of all targets with their status, acquired_by, ip_address, etc.",
)
async def get_targets(
    client: LabgridClient = Depends(get_labgrid_client),
) -> TargetListResponse:
    """Get all targets from the Labgrid coordinator."""
    targets = await client.get_places()
    return TargetListResponse(targets=targets, total=len(targets))


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

    # Execute the command (mock for now - actual implementation would use SSH/serial)
    logger.info(f"Executing command '{command.name}' on target '{name}'")

    # Mock command execution result
    output = CommandOutput(
        command=command.command,
        output=f"[Mock] Executed '{command.command}' on {name}\nOutput would appear here.",
        timestamp=datetime.utcnow(),
        exit_code=0,
    )

    return output
