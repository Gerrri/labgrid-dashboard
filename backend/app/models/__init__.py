"""
Pydantic models for the Labgrid Dashboard.
"""

from .target import Resource, CommandOutput, Target, Command, CommandsConfig
from .responses import (
    TargetListResponse,
    CommandExecutionRequest,
    ErrorResponse,
    WebSocketMessage,
    WebSocketSubscribeMessage,
    WebSocketExecuteCommandMessage,
)

__all__ = [
    "Resource",
    "CommandOutput",
    "Target",
    "Command",
    "CommandsConfig",
    "TargetListResponse",
    "CommandExecutionRequest",
    "ErrorResponse",
    "WebSocketMessage",
    "WebSocketSubscribeMessage",
    "WebSocketExecuteCommandMessage",
]
