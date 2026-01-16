"""
Pydantic models for Labgrid targets, resources, and command outputs.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Resource(BaseModel):
    """Represents a Labgrid resource attached to a target."""

    type: str = Field(..., description="Resource type, e.g., 'NetworkSerialPort', 'USBSerialPort'")
    params: dict = Field(default_factory=dict, description="Resource-specific parameters")


class CommandOutput(BaseModel):
    """Represents the output of a command executed on a target."""

    command: str = Field(..., description="The command that was executed")
    output: str = Field(..., description="The command output (stdout/stderr)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the command was executed")
    exit_code: int = Field(..., description="Command exit code (0 = success)")


class Target(BaseModel):
    """Represents a Labgrid target/place with its current state."""

    name: str = Field(..., description="Unique target/place name")
    status: Literal["available", "acquired", "offline"] = Field(
        ..., description="Current target status"
    )
    acquired_by: Optional[str] = Field(None, description="User who acquired the target")
    ip_address: Optional[str] = Field(None, description="Target IP address if available")
    web_url: Optional[str] = Field(None, description="Web interface URL if available")
    resources: List[Resource] = Field(default_factory=list, description="Attached resources")
    last_command_outputs: List[CommandOutput] = Field(
        default_factory=list, description="Recent command outputs"
    )


class Command(BaseModel):
    """Represents a predefined command that can be executed on targets."""

    name: str = Field(..., description="Human-readable command name")
    command: str = Field(..., description="The actual shell command to execute")
    description: str = Field(..., description="What this command does")


class CommandsConfig(BaseModel):
    """Configuration for available commands."""

    commands: List[Command] = Field(default_factory=list, description="List of available commands")
    auto_refresh_commands: List[str] = Field(
        default_factory=list, description="Command names to auto-refresh"
    )
