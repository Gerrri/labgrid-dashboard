"""
Tests for the CommandService.
"""

import os
import tempfile
from pathlib import Path

import pytest

from app.services.command_service import CommandService


class TestCommandService:
    """Test cases for CommandService."""

    def test_load_commands_from_file(self, commands_yaml_content: str):
        """Test that CommandService loads commands from YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(commands_yaml_content)
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()

            commands = service.get_commands()
            assert len(commands) == 2
            assert commands[0].name == "Test Command 1"
            assert commands[0].command == "echo hello"
            assert commands[1].name == "Test Command 2"
        finally:
            os.unlink(temp_path)

    def test_load_commands_file_not_found(self):
        """Test that CommandService handles missing file gracefully."""
        service = CommandService(commands_file="non_existent_file.yaml")
        service.load()

        commands = service.get_commands()
        assert commands == []

    def test_get_command_by_name(self, commands_yaml_content: str):
        """Test that get_command_by_name returns correct command."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(commands_yaml_content)
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()

            command = service.get_command_by_name("Test Command 1")
            assert command is not None
            assert command.name == "Test Command 1"
            assert command.command == "echo hello"
        finally:
            os.unlink(temp_path)

    def test_get_command_by_name_not_found(self, commands_yaml_content: str):
        """Test that get_command_by_name returns None for non-existent command."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(commands_yaml_content)
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()

            command = service.get_command_by_name("Non Existent Command")
            assert command is None
        finally:
            os.unlink(temp_path)

    def test_get_auto_refresh_commands(self, commands_yaml_content: str):
        """Test that get_auto_refresh_commands returns correct list."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(commands_yaml_content)
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()

            auto_refresh = service.get_auto_refresh_commands()
            assert len(auto_refresh) == 1
            assert auto_refresh[0] == "Test Command 1"
        finally:
            os.unlink(temp_path)

    def test_reload_commands(self, commands_yaml_content: str):
        """Test that reload refreshes commands from file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(commands_yaml_content)
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()
            assert len(service.get_commands()) == 2

            # Update the file with new content
            with open(temp_path, "w") as f:
                f.write("""
commands:
  - name: "New Command"
    command: "echo new"
    description: "A new command"
""")

            service.reload()
            commands = service.get_commands()
            assert len(commands) == 1
            assert commands[0].name == "New Command"
        finally:
            os.unlink(temp_path)

    def test_empty_yaml_file(self):
        """Test that CommandService handles empty YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()

            commands = service.get_commands()
            assert commands == []
        finally:
            os.unlink(temp_path)

    def test_invalid_yaml_file(self):
        """Test that CommandService handles invalid YAML gracefully."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("{ invalid yaml content [")
            temp_path = f.name

        try:
            service = CommandService(commands_file=temp_path)
            service.load()

            commands = service.get_commands()
            assert commands == []
        finally:
            os.unlink(temp_path)
