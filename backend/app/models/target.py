"""
Pydantic models for Labgrid targets, resources, and command outputs.
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Resource(BaseModel):
    """Represents a Labgrid resource attached to a target."""

    type: str = Field(..., description="Resource type, e.g., 'NetworkSerialPort', 'USBSerialPort'")
    params: dict = Field(default_factory=dict, description="Resource-specific parameters")


class CommandOutput(BaseModel):
    """Represents the output of a command executed on a target."""

    command: str = Field(..., description="The command that was executed")
    output: str = Field(..., description="The command output (stdout/stderr)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the command was executed")
    exit_code: int = Field(..., description="Command exit code (0 = success)")


class ScheduledCommandOutput(BaseModel):
    """Represents the latest output of a scheduled command for a specific target."""

    command_name: str = Field(..., description="Display name of the command (used as column header)")
    output: str = Field(..., description="The command output (stdout/stderr)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the command was last executed")
    exit_code: int = Field(default=0, description="Command exit code (0 = success)")


class ScheduledCommand(BaseModel):
    """Represents a command that runs periodically on all targets (from config)."""

    name: str = Field(..., description="Display name for the command (shown as column header)")
    command: str = Field(..., description="The shell command to execute")
    interval_seconds: int = Field(..., ge=5, description="Execution interval in seconds (min 5)")
    description: str = Field(default="", description="Optional description of what this command does")


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
    scheduled_outputs: Dict[str, ScheduledCommandOutput] = Field(
        default_factory=dict, description="Latest outputs from scheduled commands (keyed by command name)"
    )


class Command(BaseModel):
    """Represents a predefined command that can be executed on targets."""

    name: str = Field(..., description="Human-readable command name")
    command: str = Field(..., description="The actual shell command to execute")
    description: str = Field(..., description="What this command does")


class CommandsConfig(BaseModel):
    """Configuration for available commands (legacy, kept for backwards compatibility)."""

    commands: List[Command] = Field(default_factory=list, description="List of available commands")
    auto_refresh_commands: List[str] = Field(
        default_factory=list, description="Command names to auto-refresh"
    )
    scheduled_commands: List[ScheduledCommand] = Field(
        default_factory=list, description="Commands that run periodically on all targets"
    )


class Preset(BaseModel):
    """Represents a hardware preset (summary view)."""

    id: str = Field(..., description="Unique preset identifier (used as key in YAML)")
    name: str = Field(..., description="Human-readable preset name")
    description: str = Field(default="", description="Description of the preset")


class PresetDetail(BaseModel):
    """Represents a hardware preset with full details including commands."""

    id: str = Field(..., description="Unique preset identifier (used as key in YAML)")
    name: str = Field(..., description="Human-readable preset name")
    description: str = Field(default="", description="Description of the preset")
    commands: List[Command] = Field(default_factory=list, description="Commands available in this preset")
    scheduled_commands: List[ScheduledCommand] = Field(
        default_factory=list, description="Scheduled commands for this preset"
    )
    auto_refresh_commands: List[str] = Field(
        default_factory=list, description="Command names to auto-refresh"
    )


class PresetsConfig(BaseModel):
    """Configuration for all presets (loaded from commands.yaml)."""

    default_preset: str = Field(default="basic", description="Default preset ID for new targets")
    presets: Dict[str, PresetDetail] = Field(
        default_factory=dict, description="Dictionary of preset_id -> PresetDetail"
    )


class TargetPresetAssignment(BaseModel):
    """Represents the preset assignment for a target."""

    target_name: str = Field(..., description="Target name")
    preset_id: str = Field(..., description="Assigned preset ID")


class TargetPresetsFile(BaseModel):
    """Structure of the target_presets.json file."""

    assignments: Dict[str, str] = Field(
        default_factory=dict, description="Dictionary of target_name -> preset_id"
    )
