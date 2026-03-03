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
