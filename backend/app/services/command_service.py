"""
Service for loading and managing command configurations.
"""

import logging
from pathlib import Path
from typing import List, Optional

import yaml

from app.models.target import Command, CommandsConfig

logger = logging.getLogger(__name__)


class CommandService:
    """Service for managing predefined commands from configuration."""

    def __init__(self, commands_file: str = "commands.yaml"):
        """Initialize the command service.

        Args:
            commands_file: Path to the commands YAML configuration file.
        """
        self._commands_file = commands_file
        self._config: Optional[CommandsConfig] = None

    def load(self) -> None:
        """Load commands from the YAML configuration file."""
        config_path = Path(self._commands_file)

        if not config_path.exists():
            logger.warning(f"Commands file not found: {config_path}")
            self._config = CommandsConfig()
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                logger.warning(f"Commands file is empty: {config_path}")
                self._config = CommandsConfig()
                return

            commands = [
                Command(
                    name=cmd.get("name", ""),
                    command=cmd.get("command", ""),
                    description=cmd.get("description", ""),
                )
                for cmd in data.get("commands", [])
            ]

            auto_refresh = data.get("auto_refresh_commands", [])

            self._config = CommandsConfig(
                commands=commands,
                auto_refresh_commands=auto_refresh,
            )

            logger.info(f"Loaded {len(commands)} commands from {config_path}")

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse commands file: {e}")
            self._config = CommandsConfig()
        except Exception as e:
            logger.error(f"Failed to load commands: {e}")
            self._config = CommandsConfig()

    def get_commands(self) -> List[Command]:
        """Get all available commands.

        Returns:
            List of available commands.
        """
        if self._config is None:
            self.load()
        return self._config.commands if self._config else []

    def get_auto_refresh_commands(self) -> List[str]:
        """Get command names that should be auto-refreshed.

        Returns:
            List of command names for auto-refresh.
        """
        if self._config is None:
            self.load()
        return self._config.auto_refresh_commands if self._config else []

    def get_command_by_name(self, name: str) -> Optional[Command]:
        """Get a specific command by name.

        Args:
            name: The command name to find.

        Returns:
            The command if found, None otherwise.
        """
        commands = self.get_commands()
        for cmd in commands:
            if cmd.name == name:
                return cmd
        return None

    def reload(self) -> None:
        """Reload commands from the configuration file."""
        self._config = None
        self.load()
