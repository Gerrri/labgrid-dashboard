"""
Tests for the CommandService preset functionality.
"""

import os
import tempfile

import pytest
from app.services.command_service import CommandService


class TestCommandServicePresets:
    """Tests for the CommandService preset functionality."""

    @pytest.fixture
    def presets_yaml_content(self) -> str:
        """Sample commands.yaml with presets."""
        return """
default_preset: basic

presets:
  basic:
    name: "Basic"
    description: "Standard Linux commands"
    commands:
      - name: "Linux Version"
        command: "cat /etc/os-release"
        description: "Shows the Linux distribution"
      - name: "System Time"
        command: "date"
        description: "Current system time"
    auto_refresh_commands:
      - "Linux Version"
    scheduled_commands:
      - name: "Uptime"
        command: "uptime -p"
        interval_seconds: 60
        description: "System uptime"

  hardware1:
    name: "Hardware 1"
    description: "Hardware-specific commands"
    commands:
      - name: "GPIO Status"
        command: "cat /sys/class/gpio/export"
        description: "GPIO Pin Status"
      - name: "Temperature"
        command: "cat /sys/class/thermal/thermal_zone0/temp"
        description: "CPU Temperature"
    auto_refresh_commands:
      - "GPIO Status"
    scheduled_commands:
      - name: "Temperature"
        command: "cat /sys/class/thermal/thermal_zone0/temp"
        interval_seconds: 30
        description: "CPU Temperature monitoring"
"""

    @pytest.fixture
    def legacy_yaml_content(self) -> str:
        """Sample commands.yaml in legacy format (without presets)."""
        return """
commands:
  - name: "Test Command"
    command: "echo hello"
    description: "Says hello"

auto_refresh_commands:
  - "Test Command"

scheduled_commands:
  - name: "Uptime"
    command: "uptime -p"
    interval_seconds: 60
    description: "System uptime"
"""

    def test_load_presets_format(self, presets_yaml_content: str):
        """Test loading commands.yaml with presets format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                # Should have 2 presets
                presets = service.get_presets()
                assert len(presets) == 2

                # Check preset names
                preset_ids = {p.id for p in presets}
                assert "basic" in preset_ids
                assert "hardware1" in preset_ids
            finally:
                os.unlink(f.name)

    def test_get_default_preset_id(self, presets_yaml_content: str):
        """Test getting the default preset ID."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                assert service.get_default_preset_id() == "basic"
            finally:
                os.unlink(f.name)

    def test_get_preset(self, presets_yaml_content: str):
        """Test getting a specific preset by ID."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                preset = service.get_preset("basic")
                assert preset is not None
                assert preset.id == "basic"
                assert preset.name == "Basic"
                assert preset.description == "Standard Linux commands"
                assert len(preset.commands) == 2
                assert len(preset.scheduled_commands) == 1
            finally:
                os.unlink(f.name)

    def test_get_preset_not_found(self, presets_yaml_content: str):
        """Test getting a non-existent preset returns None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                preset = service.get_preset("non-existent")
                assert preset is None
            finally:
                os.unlink(f.name)

    def test_get_commands_for_preset(self, presets_yaml_content: str):
        """Test getting commands for a specific preset."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                commands = service.get_commands_for_preset("hardware1")
                assert len(commands) == 2
                command_names = {c.name for c in commands}
                assert "GPIO Status" in command_names
                assert "Temperature" in command_names
            finally:
                os.unlink(f.name)

    def test_get_scheduled_commands_for_preset(self, presets_yaml_content: str):
        """Test getting scheduled commands for a specific preset."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                scheduled = service.get_scheduled_commands_for_preset("hardware1")
                assert len(scheduled) == 1
                assert scheduled[0].name == "Temperature"
                assert scheduled[0].interval_seconds == 30
            finally:
                os.unlink(f.name)

    def test_get_auto_refresh_commands_for_preset(self, presets_yaml_content: str):
        """Test getting auto-refresh commands for a specific preset."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                auto_refresh = service.get_auto_refresh_commands_for_preset("basic")
                assert "Linux Version" in auto_refresh
            finally:
                os.unlink(f.name)

    def test_get_command_by_name_for_preset(self, presets_yaml_content: str):
        """Test getting a command by name from a specific preset."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                cmd = service.get_command_by_name_for_preset("hardware1", "GPIO Status")
                assert cmd is not None
                assert cmd.name == "GPIO Status"
                assert "gpio" in cmd.command

                # Command from another preset should not be found
                cmd = service.get_command_by_name_for_preset(
                    "hardware1", "Linux Version"
                )
                assert cmd is None
            finally:
                os.unlink(f.name)

    def test_legacy_format_creates_basic_preset(self, legacy_yaml_content: str):
        """Test that legacy format creates a single 'basic' preset."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(legacy_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                presets = service.get_presets()
                assert len(presets) == 1
                assert presets[0].id == "basic"

                # Commands should be accessible
                commands = service.get_commands()
                assert len(commands) == 1
                assert commands[0].name == "Test Command"
            finally:
                os.unlink(f.name)

    def test_backwards_compatibility_get_commands(self, presets_yaml_content: str):
        """Test that get_commands() returns commands from default preset."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                # get_commands() should return commands from default preset
                commands = service.get_commands()
                assert len(commands) == 2
                command_names = {c.name for c in commands}
                assert "Linux Version" in command_names
            finally:
                os.unlink(f.name)

    def test_get_all_unique_scheduled_commands(self, presets_yaml_content: str):
        """Test getting all unique scheduled commands from all presets."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                all_scheduled = service.get_all_unique_scheduled_commands()
                # Should have 2 unique scheduled commands: Uptime and Temperature
                assert len(all_scheduled) == 2
                names = {c.name for c in all_scheduled}
                assert "Uptime" in names
                assert "Temperature" in names
            finally:
                os.unlink(f.name)

    def test_get_command_by_name_searches_all_presets(self, presets_yaml_content: str):
        """Test that get_command_by_name searches all presets."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(presets_yaml_content)
            f.flush()

            try:
                service = CommandService(commands_file=f.name)
                service.load()

                # Command from basic preset
                cmd = service.get_command_by_name("Linux Version")
                assert cmd is not None

                # Command from hardware1 preset
                cmd = service.get_command_by_name("GPIO Status")
                assert cmd is not None
            finally:
                os.unlink(f.name)
