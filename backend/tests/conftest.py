"""
Pytest configuration and fixtures for Labgrid Dashboard backend tests.
"""

import os
import sys
from typing import AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure the app module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.routes.health import set_labgrid_client as set_health_labgrid_client
from app.api.routes.targets import set_command_service as set_targets_command_service
from app.api.routes.targets import set_labgrid_client as set_targets_labgrid_client
from app.api.routes.targets import set_preset_service as set_targets_preset_service
from app.api.routes.targets import (
    set_scheduler_service as set_targets_scheduler_service,
)
from app.main import app
from app.models.target import Command, Preset, PresetDetail, Resource, Target
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient
from app.services.preset_service import PresetService
from app.services.scheduler_service import SchedulerService


@pytest.fixture
def mock_targets() -> list[Target]:
    """Fixture providing mock target data."""
    return [
        Target(
            name="test-dut-1",
            status="available",
            acquired_by=None,
            ip_address="192.168.1.100",
            web_url="http://192.168.1.100:8080",
            resources=[
                Resource(
                    type="NetworkSerialPort",
                    params={"host": "192.168.1.100", "port": 4001},
                ),
            ],
            last_command_outputs=[],
        ),
        Target(
            name="test-dut-2",
            status="acquired",
            acquired_by="tester@host",
            ip_address="192.168.1.101",
            web_url=None,
            resources=[],
            last_command_outputs=[],
        ),
    ]


@pytest.fixture
def mock_commands() -> list[Command]:
    """Fixture providing mock command definitions."""
    return [
        Command(name="Test Command", command="echo test", description="A test command"),
        Command(name="System Info", command="uname -a", description="Get system info"),
    ]


@pytest.fixture
def mock_presets() -> list[Preset]:
    """Fixture providing mock preset definitions."""
    return [
        Preset(id="basic", name="Basic", description="Standard commands"),
        Preset(
            id="hardware1", name="Hardware 1", description="Hardware-specific commands"
        ),
    ]


@pytest.fixture
def mock_labgrid_client(mock_targets: list[Target]) -> MagicMock:
    """Fixture providing a mocked LabgridClient."""
    client = MagicMock(spec=LabgridClient)
    client.connected = True
    client.get_places = AsyncMock(return_value=mock_targets)
    client.get_place_info = AsyncMock(
        side_effect=lambda name: next((t for t in mock_targets if t.name == name), None)
    )
    # Mock execute_command to return success output
    client.execute_command = AsyncMock(
        return_value=("Command executed successfully", 0)
    )
    # Mock connect/disconnect
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    # Mock subscribe_updates
    client.subscribe_updates = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_command_service(
    mock_commands: list[Command], mock_presets: list[Preset]
) -> MagicMock:
    """Fixture providing a mocked CommandService."""
    service = MagicMock(spec=CommandService)
    service.get_commands.return_value = mock_commands
    service.get_command_by_name.side_effect = lambda name: next(
        (c for c in mock_commands if c.name == name), None
    )
    service.get_auto_refresh_commands.return_value = ["Test Command"]
    service.get_scheduled_commands.return_value = []

    # Preset-related methods
    service.get_presets.return_value = mock_presets
    service.get_default_preset_id.return_value = "basic"
    service.get_commands_for_preset.return_value = mock_commands
    service.get_command_by_name_for_preset.side_effect = lambda preset_id, name: next(
        (c for c in mock_commands if c.name == name), None
    )
    service.get_preset.side_effect = lambda preset_id: (
        PresetDetail(
            id=preset_id,
            name=preset_id.capitalize(),
            description=f"Description for {preset_id}",
            commands=mock_commands,
            scheduled_commands=[],
            auto_refresh_commands=["Test Command"],
        )
        if preset_id in ["basic", "hardware1"]
        else None
    )

    return service


@pytest.fixture
def mock_preset_service() -> MagicMock:
    """Fixture providing a mocked PresetService."""
    service = MagicMock(spec=PresetService)
    service.get_target_preset.return_value = "basic"
    service.get_default_preset_id.return_value = "basic"
    service.get_all_assignments.return_value = {}
    service.set_target_preset.return_value = None
    return service


@pytest.fixture
def mock_scheduler_service() -> MagicMock:
    """Fixture providing a mocked SchedulerService."""
    service = MagicMock(spec=SchedulerService)
    service.get_commands.return_value = []
    service.get_outputs_for_target.return_value = {}
    service.get_all_outputs.return_value = {}
    return service


@pytest_asyncio.fixture
async def client(
    mock_labgrid_client: MagicMock,
    mock_command_service: MagicMock,
    mock_preset_service: MagicMock,
    mock_scheduler_service: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Fixture providing an async HTTP client for testing the API."""
    # Set up the mocked services
    set_health_labgrid_client(mock_labgrid_client)
    set_targets_labgrid_client(mock_labgrid_client)
    set_targets_command_service(mock_command_service)
    set_targets_preset_service(mock_preset_service)
    set_targets_scheduler_service(mock_scheduler_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up - reset to None
    set_health_labgrid_client(None)  # type: ignore
    set_targets_labgrid_client(None)  # type: ignore
    set_targets_command_service(None)  # type: ignore
    set_targets_preset_service(None)  # type: ignore
    set_targets_scheduler_service(None)  # type: ignore


@pytest.fixture
def commands_yaml_content() -> str:
    """Fixture providing sample commands.yaml content for testing (legacy format)."""
    return """
commands:
  - name: "Test Command 1"
    command: "echo hello"
    description: "Says hello"
  - name: "Test Command 2"
    command: "date"
    description: "Shows date"

auto_refresh_commands:
  - "Test Command 1"
"""


@pytest.fixture
def presets_yaml_content() -> str:
    """Fixture providing sample commands.yaml content with presets for testing."""
    return """
default_preset: basic

presets:
  basic:
    name: "Basic"
    description: "Standard commands"
    commands:
      - name: "Test Command 1"
        command: "echo hello"
        description: "Says hello"
      - name: "Test Command 2"
        command: "date"
        description: "Shows date"
    auto_refresh_commands:
      - "Test Command 1"
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
    auto_refresh_commands:
      - "GPIO Status"
    scheduled_commands: []
"""
