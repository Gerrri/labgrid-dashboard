"""
Response models for API endpoints.
"""

from typing import List

from app.models.target import Preset, PresetDetail, ScheduledCommand, Target
from pydantic import BaseModel, Field


class TargetListResponse(BaseModel):
    """Response model for list of targets."""

    targets: List[Target] = Field(..., description="List of targets")
    total: int = Field(..., description="Total number of targets")


class ScheduledCommandsResponse(BaseModel):
    """Response model for list of scheduled commands."""

    commands: List[ScheduledCommand] = Field(
        ..., description="List of scheduled commands"
    )


class CommandExecutionRequest(BaseModel):
    """Request model for command execution."""

    command_name: str = Field(..., description="Name of the command to execute")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")


class WebSocketMessage(BaseModel):
    """WebSocket message model."""

    type: str = Field(..., description="Message type")
    data: dict = Field(default_factory=dict, description="Message data")


class WebSocketSubscribeMessage(BaseModel):
    """WebSocket subscribe message from client."""

    type: str = Field(default="subscribe", description="Message type")
    targets: List[str] = Field(
        default=["all"], description="List of target names to subscribe to, or ['all']"
    )


class WebSocketExecuteCommandMessage(BaseModel):
    """WebSocket execute command message from client."""

    type: str = Field(default="execute_command", description="Message type")
    target: str = Field(..., description="Target name to execute command on")
    command_name: str = Field(..., description="Name of the command to execute")


class PresetsListResponse(BaseModel):
    """Response model for list of available presets."""

    presets: List[Preset] = Field(..., description="List of available presets")
    default_preset: str = Field(..., description="Default preset ID")


class TargetPresetResponse(BaseModel):
    """Response model for a target's preset assignment."""

    target_name: str = Field(..., description="Target name")
    preset_id: str = Field(..., description="Assigned preset ID")
    preset: Preset = Field(..., description="Preset details")


class SetTargetPresetRequest(BaseModel):
    """Request model for setting a target's preset."""

    preset_id: str = Field(..., description="Preset ID to assign to the target")
