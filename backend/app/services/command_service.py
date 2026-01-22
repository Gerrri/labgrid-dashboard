"""
Service for loading and managing command configurations with preset support.

This service loads presets from commands.yaml and provides methods to access
commands and scheduled commands for specific presets.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from app.models.target import (
    Command,
    CommandsConfig,
    Preset,
    PresetDetail,
    PresetsConfig,
    ScheduledCommand,
)

logger = logging.getLogger(__name__)


class CommandService:
    """Service for managing predefined commands and presets from configuration."""

    def __init__(self, commands_file: str = "commands.yaml"):
        """Initialize the command service.

        Args:
            commands_file: Path to the commands YAML configuration file.
        """
        self._commands_file = commands_file
        self._presets_config: Optional[PresetsConfig] = None
        # Legacy config for backwards compatibility
        self._legacy_config: Optional[CommandsConfig] = None

    def load(self) -> None:
        """Load commands from the YAML configuration file.

        Supports both the new preset-based format and the legacy flat format.
        """
        config_path = Path(self._commands_file)

        if not config_path.exists():
            logger.warning(f"Commands file not found: {config_path}")
            self._init_empty_config()
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                logger.warning(f"Commands file is empty: {config_path}")
                self._init_empty_config()
                return

            # Check if this is the new preset-based format or legacy format
            if "presets" in data:
                self._load_presets_format(data)
            else:
                self._load_legacy_format(data)

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse commands file: {e}")
            self._init_empty_config()
        except Exception as e:
            logger.error(f"Failed to load commands: {e}")
            self._init_empty_config()

    def _init_empty_config(self) -> None:
        """Initialize with empty configuration."""
        self._presets_config = PresetsConfig(default_preset="basic", presets={})
        self._legacy_config = CommandsConfig()

    def _load_presets_format(self, data: dict) -> None:
        """Load the new preset-based format.

        Args:
            data: Parsed YAML data.
        """
        default_preset = data.get("default_preset", "basic")
        presets_data = data.get("presets", {})

        presets: Dict[str, PresetDetail] = {}

        for preset_id, preset_data in presets_data.items():
            commands = [
                Command(
                    name=cmd.get("name", ""),
                    command=cmd.get("command", ""),
                    description=cmd.get("description", ""),
                )
                for cmd in preset_data.get("commands", [])
            ]

            scheduled_commands = [
                ScheduledCommand(
                    name=cmd.get("name", ""),
                    command=cmd.get("command", ""),
                    interval_seconds=cmd.get("interval_seconds", 60),
                    description=cmd.get("description", ""),
                )
                for cmd in preset_data.get("scheduled_commands", [])
            ]

            auto_refresh = preset_data.get("auto_refresh_commands", [])

            presets[preset_id] = PresetDetail(
                id=preset_id,
                name=preset_data.get("name", preset_id),
                description=preset_data.get("description", ""),
                commands=commands,
                scheduled_commands=scheduled_commands,
                auto_refresh_commands=auto_refresh,
            )

        self._presets_config = PresetsConfig(
            default_preset=default_preset,
            presets=presets,
        )

        # Also populate legacy config for backwards compatibility (using default preset)
        default_preset_detail = presets.get(default_preset)
        if default_preset_detail:
            self._legacy_config = CommandsConfig(
                commands=default_preset_detail.commands,
                auto_refresh_commands=default_preset_detail.auto_refresh_commands,
                scheduled_commands=default_preset_detail.scheduled_commands,
            )
        else:
            self._legacy_config = CommandsConfig()

        total_commands = sum(len(p.commands) for p in presets.values())
        total_scheduled = sum(len(p.scheduled_commands) for p in presets.values())
        logger.info(
            f"Loaded {len(presets)} presets with {total_commands} total commands, "
            f"{total_scheduled} total scheduled commands"
        )

    def _load_legacy_format(self, data: dict) -> None:
        """Load the legacy flat format (for backwards compatibility).

        Args:
            data: Parsed YAML data.
        """
        commands = [
            Command(
                name=cmd.get("name", ""),
                command=cmd.get("command", ""),
                description=cmd.get("description", ""),
            )
            for cmd in data.get("commands", [])
        ]

        auto_refresh = data.get("auto_refresh_commands", [])

        scheduled_commands = [
            ScheduledCommand(
                name=cmd.get("name", ""),
                command=cmd.get("command", ""),
                interval_seconds=cmd.get("interval_seconds", 60),
                description=cmd.get("description", ""),
            )
            for cmd in data.get("scheduled_commands", [])
        ]

        self._legacy_config = CommandsConfig(
            commands=commands,
            auto_refresh_commands=auto_refresh,
            scheduled_commands=scheduled_commands,
        )

        # Create a single "basic" preset from the legacy data
        basic_preset = PresetDetail(
            id="basic",
            name="Basic",
            description="Default commands",
            commands=commands,
            scheduled_commands=scheduled_commands,
            auto_refresh_commands=auto_refresh,
        )

        self._presets_config = PresetsConfig(
            default_preset="basic",
            presets={"basic": basic_preset},
        )

        logger.info(
            f"Loaded legacy format with {len(commands)} commands, "
            f"{len(scheduled_commands)} scheduled commands"
        )

    def _ensure_loaded(self) -> None:
        """Ensure configuration is loaded."""
        if self._presets_config is None:
            self.load()

    # --- Preset-related methods ---

    def get_presets(self) -> List[Preset]:
        """Get all available presets (summary view).

        Returns:
            List of Preset objects with id, name, and description.
        """
        self._ensure_loaded()
        if not self._presets_config:
            return []

        return [
            Preset(id=preset.id, name=preset.name, description=preset.description)
            for preset in self._presets_config.presets.values()
        ]

    def get_preset(self, preset_id: str) -> Optional[PresetDetail]:
        """Get a specific preset by ID.

        Args:
            preset_id: The preset ID to find.

        Returns:
            The PresetDetail if found, None otherwise.
        """
        self._ensure_loaded()
        if not self._presets_config:
            return None

        return self._presets_config.presets.get(preset_id)

    def get_commands_for_preset(self, preset_id: str) -> List[Command]:
        """Get commands for a specific preset.

        Args:
            preset_id: The preset ID.

        Returns:
            List of commands for the preset, or empty list if not found.
        """
        preset = self.get_preset(preset_id)
        if preset:
            return preset.commands
        return []

    def get_scheduled_commands_for_preset(
        self, preset_id: str
    ) -> List[ScheduledCommand]:
        """Get scheduled commands for a specific preset.

        Args:
            preset_id: The preset ID.

        Returns:
            List of scheduled commands for the preset, or empty list if not found.
        """
        preset = self.get_preset(preset_id)
        if preset:
            return preset.scheduled_commands
        return []

    def get_auto_refresh_commands_for_preset(self, preset_id: str) -> List[str]:
        """Get auto-refresh command names for a specific preset.

        Args:
            preset_id: The preset ID.

        Returns:
            List of command names to auto-refresh.
        """
        preset = self.get_preset(preset_id)
        if preset:
            return preset.auto_refresh_commands
        return []

    def get_default_preset_id(self) -> str:
        """Get the default preset ID.

        Returns:
            The default preset ID (usually 'basic').
        """
        self._ensure_loaded()
        if self._presets_config:
            return self._presets_config.default_preset
        return "basic"

    def get_command_by_name_for_preset(
        self, preset_id: str, command_name: str
    ) -> Optional[Command]:
        """Get a specific command by name from a preset.

        Args:
            preset_id: The preset ID.
            command_name: The command name to find.

        Returns:
            The command if found, None otherwise.
        """
        commands = self.get_commands_for_preset(preset_id)
        for cmd in commands:
            if cmd.name == command_name:
                return cmd
        return None

    # --- Legacy methods for backwards compatibility ---

    def get_commands(self) -> List[Command]:
        """Get all available commands (from default preset).

        Returns:
            List of available commands.
        """
        self._ensure_loaded()
        return self._legacy_config.commands if self._legacy_config else []

    def get_auto_refresh_commands(self) -> List[str]:
        """Get command names that should be auto-refreshed (from default preset).

        Returns:
            List of command names for auto-refresh.
        """
        self._ensure_loaded()
        return self._legacy_config.auto_refresh_commands if self._legacy_config else []

    def get_scheduled_commands(self) -> List[ScheduledCommand]:
        """Get all scheduled commands (from default preset).

        Returns:
            List of scheduled commands.
        """
        self._ensure_loaded()
        return self._legacy_config.scheduled_commands if self._legacy_config else []

    def get_command_by_name(self, name: str) -> Optional[Command]:
        """Get a specific command by name (searches all presets).

        Args:
            name: The command name to find.

        Returns:
            The command if found, None otherwise.
        """
        self._ensure_loaded()
        # First check legacy/default preset
        if self._legacy_config:
            for cmd in self._legacy_config.commands:
                if cmd.name == name:
                    return cmd

        # Then search all presets
        if self._presets_config:
            for preset in self._presets_config.presets.values():
                for cmd in preset.commands:
                    if cmd.name == name:
                        return cmd

        return None

    def get_all_unique_scheduled_commands(self) -> List[ScheduledCommand]:
        """Get all unique scheduled commands from all presets.

        Commands are considered unique by their name.
        This is useful for the scheduler to know all possible scheduled commands.

        Returns:
            List of unique scheduled commands from all presets.
        """
        self._ensure_loaded()
        if not self._presets_config:
            return []

        seen_names: set = set()
        unique_commands: List[ScheduledCommand] = []

        for preset in self._presets_config.presets.values():
            for cmd in preset.scheduled_commands:
                if cmd.name not in seen_names:
                    seen_names.add(cmd.name)
                    unique_commands.append(cmd)

        return unique_commands

    def reload(self) -> None:
        """Reload commands from the configuration file."""
        self._presets_config = None
        self._legacy_config = None
        self.load()
