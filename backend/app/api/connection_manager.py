"""
WebSocket connection manager for managing active connections and broadcasting messages.
"""

import json
import logging
from typing import Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: List[WebSocket] = []
        self._subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self._subscriptions[websocket] = {"all"}  # Subscribe to all by default
        logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self._subscriptions:
            del self._subscriptions[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, targets: List[str]) -> None:
        """Update subscription for a WebSocket connection.

        Args:
            websocket: The WebSocket connection to update.
            targets: List of target names to subscribe to, or ["all"] for all targets.
        """
        if websocket in self._subscriptions:
            self._subscriptions[websocket] = set(targets)
            logger.info(f"Updated subscription: {targets}")

    def is_subscribed(self, websocket: WebSocket, target_name: str) -> bool:
        """Check if a WebSocket is subscribed to a specific target.

        Args:
            websocket: The WebSocket connection to check.
            target_name: The target name to check subscription for.

        Returns:
            True if subscribed, False otherwise.
        """
        if websocket not in self._subscriptions:
            return False
        subscriptions = self._subscriptions[websocket]
        return "all" in subscriptions or target_name in subscriptions

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: The message to broadcast.
        """
        message_json = json.dumps(message)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def broadcast_to_subscribed(self, message: dict, target_name: str) -> None:
        """Broadcast a message only to clients subscribed to a specific target.

        Args:
            message: The message to broadcast.
            target_name: The target name to filter subscribers.
        """
        message_json = json.dumps(message)
        disconnected = []

        for connection in self.active_connections:
            if self.is_subscribed(connection, target_name):
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"Failed to send message to connection: {e}")
                    disconnected.append(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def send_to(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a specific WebSocket connection.

        Args:
            websocket: The WebSocket connection to send to.
            message: The message to send.
        """
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")
            await self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()
