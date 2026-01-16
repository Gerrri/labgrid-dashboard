"""
Response models for API endpoints.
"""

from typing import List

from pydantic import BaseModel, Field

from app.models.target import Target


class TargetListResponse(BaseModel):
    """Response model for list of targets."""

    targets: List[Target] = Field(..., description="List of targets")
    total: int = Field(..., description="Total number of targets")


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
