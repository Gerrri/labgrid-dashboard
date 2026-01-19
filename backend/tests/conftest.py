"""
Pytest configuration and fixtures for Labgrid Dashboard backend tests.
"""

import os
import sys
from typing import AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure the app module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.models.target import Target, Resource, Command
from app.services.labgrid_client import LabgridClient
from app.services.command_service import CommandService
from app.api.routes.health import set_labgrid_client as set_health_labgrid_client
from app.api.routes.targets import set_labgrid_client as set_targets_labgrid_client
from app.api.routes.targets import set_command_service as set_targets_command_service


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
                Resource(type="NetworkSerialPort", params={"host": "192.168.1.100", "port": 4001}),
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
def mock_labgrid_client(mock_targets: list[Target]) -> MagicMock:
    """Fixture providing a mocked LabgridClient."""
    client = MagicMock(spec=LabgridClient)
    client.connected = True
    client.get_places = AsyncMock(return_value=mock_targets)
    client.get_place_info = AsyncMock(
        side_effect=lambda name: next(
            (t for t in mock_targets if t.name == name), None
        )
    )
    return client


@pytest.fixture
def mock_command_service(mock_commands: list[Command]) -> MagicMock:
    """Fixture providing a mocked CommandService."""
    service = MagicMock(spec=CommandService)
    service.get_commands.return_value = mock_commands
    service.get_command_by_name.side_effect = lambda name: next(
        (c for c in mock_commands if c.name == name), None
    )
    service.get_auto_refresh_commands.return_value = ["Test Command"]
    return service


@pytest_asyncio.fixture
async def client(
    mock_labgrid_client: MagicMock,
    mock_command_service: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Fixture providing an async HTTP client for testing the API."""
    # Set up the mocked services
    set_health_labgrid_client(mock_labgrid_client)
    set_targets_labgrid_client(mock_labgrid_client)
    set_targets_command_service(mock_command_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up
    set_health_labgrid_client(None)
    set_targets_labgrid_client(None)
    set_targets_command_service(None)


@pytest.fixture
def commands_yaml_content() -> str:
    """Fixture providing sample commands.yaml content for testing."""
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
