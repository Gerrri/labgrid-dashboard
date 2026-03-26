"""
Tests for startup and reconnect behavior in the main application module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.main import (
    COORDINATOR_RECONNECT_INITIAL_DELAY_SECONDS,
    reconnect_coordinator_in_background,
    sync_coordinator_runtime,
)
from app.models.target import (
    CommandExecutionConfig,
    CommandOutput,
    SerialCommandExecutionConfig,
    Target,
)
from app.services.command_execution_service import (
    CommandExecutionResult,
    CommandExecutionService,
    TransportExecutionError,
)
from app.services.labgrid_client import LabgridConnectionError


@pytest.mark.asyncio
async def test_sync_coordinator_runtime_restores_updates_and_broadcasts():
    """Test that synchronization restores subscriptions and broadcasts targets."""
    client = MagicMock()
    client.subscribe_updates = AsyncMock(return_value=True)
    callback = AsyncMock()

    with patch("app.main.wait_for_targets_ready", new=AsyncMock(return_value=True)):
        with patch("app.main.broadcast_targets_list", new=AsyncMock()) as broadcast:
            await sync_coordinator_runtime(
                client,
                timeout_seconds=30,
                poll_interval_seconds=5,
                target_update_callback=callback,
            )

    client.subscribe_updates.assert_awaited_once_with(callback)
    broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnect_coordinator_in_background_retries_until_success():
    """Test that the reconnect loop retries failed startup connections."""
    client = MagicMock()
    client.connect = AsyncMock(
        side_effect=[
            LabgridConnectionError("startup failed"),
            True,
        ]
    )
    client.disconnect = AsyncMock()
    callback = AsyncMock()
    sleep_calls: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleep_calls.append(seconds)

    with patch("app.main.asyncio.sleep", new=fake_sleep):
        with patch("app.main.sync_coordinator_runtime", new=AsyncMock()) as sync_runtime:
            await reconnect_coordinator_in_background(
                client,
                timeout_seconds=30,
                poll_interval_seconds=5,
                target_update_callback=callback,
            )

    assert sleep_calls == [
        COORDINATOR_RECONNECT_INITIAL_DELAY_SECONDS,
        COORDINATOR_RECONNECT_INITIAL_DELAY_SECONDS * 2,
    ]
    assert client.connect.await_count == 2
    client.disconnect.assert_awaited_once()
    sync_runtime.assert_awaited_once_with(client, 30, 5, callback)


@pytest.mark.asyncio
async def test_command_execution_service_prefers_serial_then_ssh():
    """Test that serial is preferred over SSH when configured."""
    labgrid_client = MagicMock()
    labgrid_client.connected = True
    labgrid_client._session = MagicMock()
    labgrid_client._session.get_place.return_value = "place"
    labgrid_client._command_locks = {}
    labgrid_client.acquire_target = AsyncMock(return_value=True)
    labgrid_client.release_target_with_retry = AsyncMock(return_value=True)

    command_service = MagicMock()
    command_service.get_default_preset_id.return_value = "basic"
    command_service.get_execution_config_for_preset.return_value = CommandExecutionConfig(
        transport_order=["serial", "ssh"],
        serial=SerialCommandExecutionConfig(resource_name="console"),
    )

    preset_service = MagicMock()
    preset_service.get_target_preset.return_value = "basic"

    execution_service = CommandExecutionService(
        labgrid_client=labgrid_client,
        command_service=command_service,
        preset_service=preset_service,
    )
    execution_service._try_execute_via_serial = AsyncMock(
        return_value=CommandExecutionResult("serial ok", 0, "serial")
    )
    execution_service._try_execute_via_ssh = AsyncMock(
        return_value=CommandExecutionResult("ssh ok", 0, "ssh")
    )

    result = await execution_service.execute_command("dut-1", "echo test")
    output, exit_code = result

    assert output == "serial ok"
    assert exit_code == 0
    assert result.execution_transport == "serial"
    execution_service._try_execute_via_serial.assert_awaited_once()
    execution_service._try_execute_via_ssh.assert_not_awaited()
    labgrid_client.acquire_target.assert_awaited_once_with("dut-1")
    labgrid_client.release_target_with_retry.assert_awaited_once_with("dut-1")


@pytest.mark.asyncio
async def test_command_execution_service_falls_back_to_ssh_when_serial_unavailable(
):
    """Test that SSH is used when serial transport is unavailable."""
    labgrid_client = MagicMock()
    labgrid_client.connected = True
    labgrid_client._session = MagicMock()
    labgrid_client._session.get_place.return_value = "place"
    labgrid_client._command_locks = {}
    labgrid_client.acquire_target = AsyncMock(return_value=True)
    labgrid_client.release_target_with_retry = AsyncMock(return_value=True)

    command_service = MagicMock()
    command_service.get_default_preset_id.return_value = "basic"
    command_service.get_execution_config_for_preset.return_value = CommandExecutionConfig(
        transport_order=["serial", "ssh"],
        serial=SerialCommandExecutionConfig(resource_name="console"),
    )

    preset_service = MagicMock()
    preset_service.get_target_preset.return_value = "basic"

    execution_service = CommandExecutionService(
        labgrid_client=labgrid_client,
        command_service=command_service,
        preset_service=preset_service,
    )
    execution_service._try_execute_via_serial = AsyncMock(return_value=None)
    execution_service._try_execute_via_ssh = AsyncMock(
        return_value=CommandExecutionResult("ssh ok", 0, "ssh")
    )

    result = await execution_service.execute_command("dut-1", "echo test")
    output, exit_code = result

    assert output == "ssh ok"
    assert exit_code == 0
    assert result.execution_transport == "ssh"
    execution_service._try_execute_via_serial.assert_awaited_once()
    execution_service._try_execute_via_ssh.assert_awaited_once()


@pytest.mark.asyncio
async def test_command_execution_service_falls_back_to_ssh_when_serial_transport_fails():
    """Test that SSH is used when serial transport errors before command execution."""
    labgrid_client = MagicMock()
    labgrid_client.connected = True
    labgrid_client._session = MagicMock()
    labgrid_client._session.get_place.return_value = "place"
    labgrid_client._command_locks = {}
    labgrid_client.acquire_target = AsyncMock(return_value=True)
    labgrid_client.release_target_with_retry = AsyncMock(return_value=True)

    command_service = MagicMock()
    command_service.get_default_preset_id.return_value = "basic"
    command_service.get_execution_config_for_preset.return_value = CommandExecutionConfig(
        transport_order=["serial", "ssh"],
        serial=SerialCommandExecutionConfig(resource_name="console"),
    )

    preset_service = MagicMock()
    preset_service.get_target_preset.return_value = "basic"

    execution_service = CommandExecutionService(
        labgrid_client=labgrid_client,
        command_service=command_service,
        preset_service=preset_service,
    )
    execution_service._reset_target_proxy_connections = MagicMock()
    execution_service._try_execute_via_serial = AsyncMock(
        side_effect=TransportExecutionError("serial login failed")
    )
    execution_service._try_execute_via_ssh = AsyncMock(
        return_value=CommandExecutionResult("ssh ok", 0, "ssh")
    )

    result = await execution_service.execute_command("dut-1", "echo test")
    output, exit_code = result

    assert output == "ssh ok"
    assert exit_code == 0
    assert result.execution_transport == "ssh"
    execution_service._try_execute_via_serial.assert_awaited_once()
    execution_service._try_execute_via_ssh.assert_awaited_once()
    assert execution_service._reset_target_proxy_connections.call_count == 2
    execution_service._reset_target_proxy_connections.assert_called_with("dut-1")


@pytest.mark.asyncio
async def test_command_execution_service_returns_serial_error_when_no_fallback_exists():
    """Test that the serial transport error is surfaced when no fallback transport exists."""
    labgrid_client = MagicMock()
    labgrid_client.connected = True
    labgrid_client._session = MagicMock()
    labgrid_client._session.get_place.return_value = "place"
    labgrid_client._command_locks = {}
    labgrid_client.acquire_target = AsyncMock(return_value=True)
    labgrid_client.release_target_with_retry = AsyncMock(return_value=True)

    command_service = MagicMock()
    command_service.get_default_preset_id.return_value = "basic"
    command_service.get_execution_config_for_preset.return_value = CommandExecutionConfig(
        transport_order=["serial"],
        serial=SerialCommandExecutionConfig(resource_name="console"),
    )

    preset_service = MagicMock()
    preset_service.get_target_preset.return_value = "basic"

    execution_service = CommandExecutionService(
        labgrid_client=labgrid_client,
        command_service=command_service,
        preset_service=preset_service,
    )
    execution_service._reset_target_proxy_connections = MagicMock()
    execution_service._try_execute_via_serial = AsyncMock(
        side_effect=TransportExecutionError("serial login failed")
    )

    result = await execution_service.execute_command("dut-1", "echo test")
    output, exit_code = result

    assert output == "Error: serial login failed"
    assert exit_code == 1
    assert result.execution_transport is None


def test_command_execution_service_enrich_target_includes_cached_outputs():
    """Manual command outputs should be reattached when targets are enriched."""
    execution_service = CommandExecutionService(
        labgrid_client=MagicMock(),
        command_service=MagicMock(),
        preset_service=MagicMock(),
    )
    execution_service.get_target_command_state = MagicMock(
        return_value=(True, "ssh", None)
    )
    execution_service.record_output(
        "dut-1",
        CommandOutput(
            command="cat /etc/os-release",
            output="ok",
            exit_code=0,
            execution_transport="ssh",
        ),
    )

    target = Target(
        name="dut-1",
        status="available",
        acquired_by=None,
        resources=[],
    )

    enriched = execution_service.enrich_target(target)

    assert enriched.command_capable is True
    assert enriched.command_transport == "ssh"
    assert len(enriched.last_command_outputs) == 1
    assert enriched.last_command_outputs[0].execution_transport == "ssh"
