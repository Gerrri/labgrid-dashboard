"""
Tests for the targets API endpoints.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.labgrid_client import TargetAcquiredByOtherError


@pytest.mark.asyncio
async def test_get_targets_returns_list(client: AsyncClient):
    """Test that GET /api/targets returns a list of targets."""
    response = await client.get("/api/targets")

    assert response.status_code == 200
    data = response.json()
    assert "targets" in data
    assert "total" in data
    assert isinstance(data["targets"], list)
    assert data["total"] == 2  # We have 2 mock targets


@pytest.mark.asyncio
async def test_get_targets_contains_expected_fields(client: AsyncClient):
    """Test that targets have all expected fields."""
    response = await client.get("/api/targets")

    assert response.status_code == 200
    data = response.json()
    assert len(data["targets"]) > 0

    target = data["targets"][0]
    assert "name" in target
    assert "status" in target
    assert "acquired_by" in target
    assert "ip_address" in target
    assert "resources" in target


@pytest.mark.asyncio
async def test_get_target_by_name_found(client: AsyncClient):
    """Test that GET /api/targets/{name} returns a specific target."""
    response = await client.get("/api/targets/test-dut-1")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-dut-1"
    assert data["status"] == "available"
    assert data["ip_address"] == "192.168.1.100"


@pytest.mark.asyncio
async def test_get_target_by_name_not_found(client: AsyncClient):
    """Test that GET /api/targets/{name} returns 404 for non-existent target."""
    response = await client.get("/api/targets/non-existent-target")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_target_commands(client: AsyncClient):
    """Test that GET /api/targets/{name}/commands returns available commands."""
    response = await client.get("/api/targets/test-dut-1/commands")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2  # We have 2 mock commands

    command = data[0]
    assert "name" in command
    assert "command" in command
    assert "description" in command


@pytest.mark.asyncio
async def test_get_target_commands_not_found(client: AsyncClient):
    """Test that GET /api/targets/{name}/commands returns 404 for non-existent target."""
    response = await client.get("/api/targets/non-existent-target/commands")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_execute_command_success(client: AsyncClient):
    """Test that POST /api/targets/{name}/command executes a command."""
    response = await client.post(
        "/api/targets/test-dut-1/command",
        json={"command_name": "Test Command"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "command" in data
    assert "output" in data
    assert "timestamp" in data
    assert "exit_code" in data


@pytest.mark.asyncio
async def test_execute_command_target_not_found(client: AsyncClient):
    """Test that POST /api/targets/{name}/command returns 404 for non-existent target."""
    response = await client.post(
        "/api/targets/non-existent-target/command",
        json={"command_name": "Test Command"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_execute_command_invalid_command(client: AsyncClient):
    """Test that POST /api/targets/{name}/command returns 400 for invalid command."""
    response = await client.post(
        "/api/targets/test-dut-1/command",
        json={"command_name": "Invalid Command That Does Not Exist"},
    )

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_execute_command_rolls_back_when_refresh_fails(
    client: AsyncClient,
    mock_labgrid_client,
):
    """Test that command execution falls back to rollback state if refresh fails."""
    original_target = await mock_labgrid_client.get_place_info("test-dut-1")
    mock_labgrid_client.execute_command.side_effect = TargetAcquiredByOtherError(
        "test-dut-1",
        "other-user",
    )
    mock_labgrid_client.get_place_info.side_effect = [
        original_target,
        RuntimeError("coordinator unavailable"),
    ]

    with patch(
        "app.api.routes.targets.broadcast_target_update",
        new=AsyncMock(),
    ) as mock_broadcast:
        response = await client.post(
            "/api/targets/test-dut-1/command",
            json={"command_name": "Test Command"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["exit_code"] == 1
    assert "other-user" in data["output"]
    assert mock_broadcast.await_count == 2
    fallback_update = mock_broadcast.await_args_list[-1].args[0]
    assert fallback_update["status"] == "acquired"
    assert fallback_update["acquired_by"] == "other-user"
