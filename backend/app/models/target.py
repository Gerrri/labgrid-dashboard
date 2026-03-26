"""
Pydantic models for Labgrid targets, resources, and command outputs.
"""

from datetime import datetime, timezone
import os
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
    execution_transport: Optional["ExecutionTransport"] = Field(
        default=None,
        description="The transport that was actually used for the execution",
    )


class ScheduledCommandOutput(BaseModel):
    """Represents the latest output of a scheduled command for a specific target."""

    command_name: str = Field(..., description="Display name of the command (used as column header)")
    output: str = Field(..., description="The command output (stdout/stderr)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the command was last executed")
    exit_code: int = Field(default=0, description="Command exit code (0 = success)")
    execution_transport: Optional["ExecutionTransport"] = Field(
        default=None,
        description="The transport that was actually used for the execution",
    )


class ScheduledCommand(BaseModel):
    """Represents a command that runs periodically on all targets (from config)."""

    name: str = Field(..., description="Display name for the command (shown as column header)")
    command: str = Field(..., description="The shell command to execute")
    interval_seconds: int = Field(..., ge=5, description="Execution interval in seconds (min 5)")
    description: str = Field(default="", description="Optional description of what this command does")


ExecutionTransport = Literal["serial", "ssh"]


class SerialCommandExecutionConfig(BaseModel):
    """Serial console execution settings for a preset."""

    resource_name: Optional[str] = Field(
        default=None,
        description="Optional named serial resource to use for command execution",
    )
    prompt: str = Field(
        default=r".*[#\$] ",
        description="Regex for the ready shell prompt",
    )
    login_prompt: str = Field(
        default=r"(?i)login: ?",
        description="Regex for the serial login prompt",
    )
    username: Optional[str] = Field(
        default=None,
        description="Static username for serial login",
    )
    username_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the serial login username",
    )
    password: Optional[str] = Field(
        default=None,
        description="Static password for serial login",
    )
    password_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the serial login password",
    )
    console_ready: str = Field(
        default="",
        description="Optional regex shown before a console becomes interactive",
    )
    login_timeout_seconds: int = Field(
        default=60,
        ge=1,
        description="Maximum wait time for serial login",
    )
    await_login_timeout_seconds: int = Field(
        default=2,
        ge=1,
        description="Silence window before sending a newline during login detection",
    )
    post_login_settle_time_seconds: int = Field(
        default=0,
        ge=0,
        description="Optional settle delay after login before the first prompt check",
    )
    command_timeout_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional command timeout override for serial execution",
    )

    def resolve_username(self) -> str:
        """Resolve the serial username from inline value or environment."""
        if self.username:
            return self.username
        if self.username_env:
            value = os.environ.get(self.username_env)
            if value:
                return value
        return "root"

    def resolve_password(self) -> Optional[str]:
        """Resolve the serial password from inline value or environment."""
        if self.password is not None:
            return self.password
        if self.password_env:
            return os.environ.get(self.password_env)
        return None


class SSHCommandExecutionConfig(BaseModel):
    """SSH execution settings for a preset."""

    resource_name: Optional[str] = Field(
        default=None,
        description="Optional named SSH-capable resource to prefer",
    )
    username: Optional[str] = Field(
        default=None,
        description="Static username override for SSH execution",
    )
    username_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the SSH username",
    )
    password: Optional[str] = Field(
        default=None,
        description="Static password override for SSH execution",
    )
    password_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the SSH password",
    )
    keyfile: Optional[str] = Field(
        default=None,
        description="Path to a private key file used for SSH execution",
    )
    keyfile_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the private key path",
    )
    command_timeout_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional command timeout override for SSH execution",
    )

    def resolve_username(self) -> str:
        """Resolve the SSH username from inline value or environment."""
        if self.username:
            return self.username
        if self.username_env:
            value = os.environ.get(self.username_env)
            if value:
                return value
        return ""

    def resolve_password(self) -> Optional[str]:
        """Resolve the SSH password from inline value or environment."""
        if self.password is not None:
            return self.password
        if self.password_env:
            return os.environ.get(self.password_env)
        return None

    def resolve_keyfile(self) -> str:
        """Resolve the SSH private key path from inline value or environment."""
        if self.keyfile:
            return self.keyfile
        if self.keyfile_env:
            value = os.environ.get(self.keyfile_env)
            if value:
                return value
        return ""


class CommandExecutionConfig(BaseModel):
    """Preset-level command execution transport settings."""

    transport_order: List[ExecutionTransport] = Field(
        default_factory=lambda: ["ssh"],
        description="Preferred transport order for command execution",
    )
    serial: SerialCommandExecutionConfig = Field(
        default_factory=SerialCommandExecutionConfig,
        description="Serial console execution settings",
    )
    ssh: SSHCommandExecutionConfig = Field(
        default_factory=SSHCommandExecutionConfig,
        description="SSH execution settings",
    )


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
    command_capable: Optional[bool] = Field(
        default=None,
        description="Whether the target currently supports command execution",
    )
    command_capability_error: Optional[str] = Field(
        default=None,
        description="Why command execution is currently unavailable for this target",
    )
    command_transport: Optional[ExecutionTransport] = Field(
        default=None,
        description="The selected execution transport for this target",
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
    command_execution: CommandExecutionConfig = Field(
        default_factory=CommandExecutionConfig,
        description="Transport configuration for command execution on this preset",
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
