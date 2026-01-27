"""
Tests for the ConnectionManager.

This module tests the WebSocket connection manager which handles
connection lifecycle and message broadcasting.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from app.api.connection_manager import ConnectionManager


@pytest.fixture
def manager():
    """Create a fresh connection manager instance."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def mock_websockets():
    """Create multiple mock WebSockets."""
    websockets = []
    for i in range(3):
        ws = MagicMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        websockets.append(ws)
    return websockets


class TestConnectionManagerInitialization:
    """Test connection manager initialization."""

    def test_init(self, manager):
        """Test manager initialization."""
        # Assert
        assert manager.active_connections == []
        assert manager._subscriptions == {}
        assert manager.connection_count == 0


class TestConnectionManagerConnectionLifecycle:
    """Test connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket):
        """Test connecting a new WebSocket."""
        # Act
        await manager.connect(mock_websocket)

        # Assert
        assert mock_websocket in manager.active_connections
        assert mock_websocket in manager._subscriptions
        assert manager._subscriptions[mock_websocket] == {"all"}
        assert manager.connection_count == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple(self, manager, mock_websockets):
        """Test connecting multiple WebSockets."""
        # Act
        for ws in mock_websockets:
            await manager.connect(ws)

        # Assert
        assert len(manager.active_connections) == 3
        assert manager.connection_count == 3
        for ws in mock_websockets:
            assert ws in manager.active_connections
            assert manager._subscriptions[ws] == {"all"}

    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """Test disconnecting a WebSocket."""
        # Arrange
        await manager.connect(mock_websocket)
        assert manager.connection_count == 1

        # Act
        await manager.disconnect(mock_websocket)

        # Assert
        assert mock_websocket not in manager.active_connections
        assert mock_websocket not in manager._subscriptions
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, manager, mock_websocket):
        """Test disconnecting a WebSocket that was never connected."""
        # Act - should not raise
        await manager.disconnect(mock_websocket)

        # Assert
        assert mock_websocket not in manager.active_connections
        assert manager.connection_count == 0


class TestConnectionManagerSubscriptions:
    """Test subscription management."""

    @pytest.mark.asyncio
    async def test_subscribe_all(self, manager, mock_websocket):
        """Test subscribing to all targets."""
        # Arrange
        await manager.connect(mock_websocket)

        # Act
        manager.subscribe(mock_websocket, ["all"])

        # Assert
        assert manager._subscriptions[mock_websocket] == {"all"}

    @pytest.mark.asyncio
    async def test_subscribe_specific_targets(self, manager, mock_websocket):
        """Test subscribing to specific targets."""
        # Arrange
        await manager.connect(mock_websocket)

        # Act
        manager.subscribe(mock_websocket, ["dut-1", "dut-2"])

        # Assert
        assert manager._subscriptions[mock_websocket] == {"dut-1", "dut-2"}

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, manager, mock_websocket):
        """Test subscribing when not connected."""
        # Act - should not raise, but also not add subscription
        manager.subscribe(mock_websocket, ["dut-1"])

        # Assert
        assert mock_websocket not in manager._subscriptions

    @pytest.mark.asyncio
    async def test_is_subscribed_to_all(self, manager, mock_websocket):
        """Test checking subscription when subscribed to all."""
        # Arrange
        await manager.connect(mock_websocket)
        manager.subscribe(mock_websocket, ["all"])

        # Act & Assert
        assert manager.is_subscribed(mock_websocket, "dut-1") is True
        assert manager.is_subscribed(mock_websocket, "dut-2") is True
        assert manager.is_subscribed(mock_websocket, "any-target") is True

    @pytest.mark.asyncio
    async def test_is_subscribed_to_specific(self, manager, mock_websocket):
        """Test checking subscription when subscribed to specific targets."""
        # Arrange
        await manager.connect(mock_websocket)
        manager.subscribe(mock_websocket, ["dut-1", "dut-2"])

        # Act & Assert
        assert manager.is_subscribed(mock_websocket, "dut-1") is True
        assert manager.is_subscribed(mock_websocket, "dut-2") is True
        assert manager.is_subscribed(mock_websocket, "dut-3") is False

    @pytest.mark.asyncio
    async def test_is_subscribed_not_connected(self, manager, mock_websocket):
        """Test checking subscription when not connected."""
        # Act & Assert
        assert manager.is_subscribed(mock_websocket, "dut-1") is False


class TestConnectionManagerBroadcasting:
    """Test message broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, manager, mock_websockets):
        """Test broadcasting to all connected clients."""
        # Arrange
        for ws in mock_websockets:
            await manager.connect(ws)

        message = {"type": "test", "data": "hello"}

        # Act
        await manager.broadcast(message)

        # Assert
        for ws in mock_websockets:
            ws.send_text.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self, manager):
        """Test broadcasting with no connections."""
        # Arrange
        message = {"type": "test", "data": "hello"}

        # Act - should not raise
        await manager.broadcast(message)

        # Assert - no errors

    @pytest.mark.asyncio
    async def test_broadcast_handles_send_error(self, manager, mock_websockets):
        """Test broadcasting handles send errors gracefully."""
        # Arrange
        for ws in mock_websockets:
            await manager.connect(ws)

        # Make one websocket fail to send
        mock_websockets[1].send_text.side_effect = Exception("Connection lost")

        message = {"type": "test", "data": "hello"}

        # Act
        await manager.broadcast(message)

        # Assert - failed connection should be removed
        assert mock_websockets[0] in manager.active_connections
        assert mock_websockets[1] not in manager.active_connections
        assert mock_websockets[2] in manager.active_connections
        assert manager.connection_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribed_all(self, manager, mock_websockets):
        """Test broadcasting to clients subscribed to a target (all subscribed)."""
        # Arrange
        for ws in mock_websockets:
            await manager.connect(ws)
            manager.subscribe(ws, ["all"])

        message = {"type": "target_update", "data": {"name": "dut-1"}}

        # Act
        await manager.broadcast_to_subscribed(message, "dut-1")

        # Assert
        for ws in mock_websockets:
            ws.send_text.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribed_specific(self, manager, mock_websockets):
        """Test broadcasting to clients subscribed to specific target."""
        # Arrange
        await manager.connect(mock_websockets[0])
        manager.subscribe(mock_websockets[0], ["dut-1"])

        await manager.connect(mock_websockets[1])
        manager.subscribe(mock_websockets[1], ["dut-2"])

        await manager.connect(mock_websockets[2])
        manager.subscribe(mock_websockets[2], ["all"])

        message = {"type": "target_update", "data": {"name": "dut-1"}}

        # Act
        await manager.broadcast_to_subscribed(message, "dut-1")

        # Assert
        mock_websockets[0].send_text.assert_called_once()  # subscribed to dut-1
        mock_websockets[1].send_text.assert_not_called()  # subscribed to dut-2
        mock_websockets[2].send_text.assert_called_once()  # subscribed to all

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribed_handles_error(self, manager, mock_websockets):
        """Test broadcast_to_subscribed handles send errors."""
        # Arrange
        for ws in mock_websockets:
            await manager.connect(ws)

        # Make one websocket fail
        mock_websockets[1].send_text.side_effect = Exception("Connection lost")

        message = {"type": "test", "data": "hello"}

        # Act
        await manager.broadcast_to_subscribed(message, "dut-1")

        # Assert
        assert mock_websockets[1] not in manager.active_connections
        assert manager.connection_count == 2

    @pytest.mark.asyncio
    async def test_send_to(self, manager, mock_websocket):
        """Test sending to a specific WebSocket."""
        # Arrange
        await manager.connect(mock_websocket)
        message = {"type": "test", "data": "hello"}

        # Act
        await manager.send_to(mock_websocket, message)

        # Assert
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_send_to_handles_error(self, manager, mock_websocket):
        """Test send_to handles send errors."""
        # Arrange
        await manager.connect(mock_websocket)
        mock_websocket.send_text.side_effect = Exception("Connection lost")

        message = {"type": "test", "data": "hello"}

        # Act
        await manager.send_to(mock_websocket, message)

        # Assert - connection should be removed
        assert mock_websocket not in manager.active_connections
        assert manager.connection_count == 0


class TestConnectionManagerProperties:
    """Test connection manager properties."""

    @pytest.mark.asyncio
    async def test_connection_count_property(self, manager, mock_websockets):
        """Test connection_count property."""
        # Arrange & Act
        assert manager.connection_count == 0

        await manager.connect(mock_websockets[0])
        assert manager.connection_count == 1

        await manager.connect(mock_websockets[1])
        assert manager.connection_count == 2

        await manager.disconnect(mock_websockets[0])
        assert manager.connection_count == 1

        await manager.disconnect(mock_websockets[1])
        assert manager.connection_count == 0
