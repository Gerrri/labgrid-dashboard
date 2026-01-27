"""
WebSocket endpoint for real-time communication.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.api.connection_manager import manager
from app.models.target import CommandOutput, ScheduledCommandOutput
from app.services.command_service import CommandService
from app.services.labgrid_client import LabgridClient
from app.services.scheduler_service import SchedulerService
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances - will be set by main app
_labgrid_client: LabgridClient | None = None
_command_service: CommandService | None = None
_scheduler_service: SchedulerService | None = None


def set_labgrid_client(client: LabgridClient) -> None:
    """Set the global Labgrid client instance."""
    global _labgrid_client
    _labgrid_client = client


def set_command_service(service: CommandService) -> None:
    """Set the global command service instance."""
    global _command_service
    _command_service = service


def set_scheduler_service(service: SchedulerService) -> None:
    """Set the global scheduler service instance."""
    global _scheduler_service
    _scheduler_service = service
    # Set the notify callback to broadcast updates via WebSocket
    service.set_notify_callback(broadcast_scheduled_output)


async def handle_subscribe(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Handle subscribe message from client.

    Args:
        websocket: The WebSocket connection.
        data: Message data containing targets to subscribe to.
    """
    targets = data.get("targets", ["all"])
    manager.subscribe(websocket, targets)

    # Send initial targets list with scheduled outputs
    if _labgrid_client:
        targets_list = await _labgrid_client.get_places()
        # Enrich with scheduled outputs
        if _scheduler_service:
            for target in targets_list:
                target.scheduled_outputs = _scheduler_service.get_outputs_for_target(
                    target.name
                )
        await manager.send_to(
            websocket,
            {
                "type": "targets_list",
                "data": [t.model_dump(mode='json') for t in targets_list],
            },
        )
    logger.info(f"Client subscribed to: {targets}")


async def handle_execute_command(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Handle execute_command message from client.

    Args:
        websocket: The WebSocket connection.
        data: Message data containing target and command_name.
    """
    target_name = data.get("target")
    command_name = data.get("command_name")

    if not target_name or not command_name:
        await manager.send_to(
            websocket,
            {
                "type": "error",
                "data": {"detail": "Missing target or command_name"},
            },
        )
        return

    if not _labgrid_client or not _command_service:
        await manager.send_to(
            websocket,
            {
                "type": "error",
                "data": {"detail": "Services not initialized"},
            },
        )
        return

    # Verify target exists
    target = await _labgrid_client.get_place_info(target_name)
    if target is None:
        await manager.send_to(
            websocket,
            {
                "type": "error",
                "data": {"detail": f"Target '{target_name}' not found"},
            },
        )
        return

    # Get the command from configuration
    command = _command_service.get_command_by_name(command_name)
    if command is None:
        await manager.send_to(
            websocket,
            {
                "type": "error",
                "data": {
                    "detail": f"Command '{command_name}' not found in configuration"
                },
            },
        )
        return

    # Execute the command via Labgrid Coordinator
    logger.info(
        f"Executing command '{command.name}' on target '{target_name}' via WebSocket"
    )

    try:
        # Execute command through the labgrid client
        result_output, exit_code = await _labgrid_client.execute_command(
            target_name, command.command
        )

        output = CommandOutput(
            command=command.command,
            output=result_output,
            timestamp=datetime.now(timezone.utc),
            exit_code=exit_code,
        )
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        output = CommandOutput(
            command=command.command,
            output=f"Error executing command: {str(e)}",
            timestamp=datetime.now(timezone.utc),
            exit_code=1,
        )

    # Send output to the requesting client
    await manager.send_to(
        websocket,
        {
            "type": "command_output",
            "data": {
                "target": target_name,
                "output": output.model_dump(mode='json'),
            },
        },
    )

    # Broadcast command output to all subscribed clients
    await manager.broadcast_to_subscribed(
        {
            "type": "command_output",
            "data": {
                "target": target_name,
                "output": output.model_dump(mode='json'),
            },
        },
        target_name,
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time updates.

    Events Server -> Client:
    - {"type": "target_update", "data": Target}
    - {"type": "command_output", "data": {"target": str, "output": CommandOutput}}
    - {"type": "targets_list", "data": List[Target]}
    - {"type": "error", "data": {"detail": str}}

    Events Client -> Server:
    - {"type": "subscribe", "targets": ["all"] | List[str]}
    - {"type": "execute_command", "target": str, "command_name": str}
    """
    await manager.connect(websocket)

    try:
        # Send initial targets list on connection with scheduled outputs
        if _labgrid_client:
            targets_list = await _labgrid_client.get_places()
            # Enrich with scheduled outputs
            if _scheduler_service:
                for target in targets_list:
                    target.scheduled_outputs = (
                        _scheduler_service.get_outputs_for_target(target.name)
                    )
            await manager.send_to(
                websocket,
                {
                    "type": "targets_list",
                    "data": [t.model_dump(mode='json') for t in targets_list],
                },
            )

        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "subscribe":
                    await handle_subscribe(websocket, message)
                elif msg_type == "execute_command":
                    await handle_execute_command(websocket, message)
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    await manager.send_to(
                        websocket,
                        {
                            "type": "error",
                            "data": {"detail": f"Unknown message type: {msg_type}"},
                        },
                    )

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
                await manager.send_to(
                    websocket,
                    {
                        "type": "error",
                        "data": {"detail": "Invalid JSON message"},
                    },
                )

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")


async def broadcast_target_update(target_data: Dict[str, Any]) -> None:
    """Broadcast a target update to all connected clients.

    This function is called by the Labgrid client when it receives updates.

    Args:
        target_data: The target data to broadcast.
    """
    target_name = target_data.get("name", "")

    # Enrich with scheduled outputs if available
    if _scheduler_service and target_name:
        scheduled_outputs = _scheduler_service.get_outputs_for_target(target_name)
        # Serialize ScheduledCommandOutput objects to JSON-compatible dicts
        target_data["scheduled_outputs"] = {
            cmd_name: output.model_dump(mode='json')
            for cmd_name, output in scheduled_outputs.items()
        }

    await manager.broadcast_to_subscribed(
        {
            "type": "target_update",
            "data": target_data,
        },
        target_name,
    )


async def broadcast_targets_list() -> None:
    """Broadcast current targets list to all connected clients."""
    if _labgrid_client:
        targets_list = await _labgrid_client.get_places()
        # Enrich with scheduled outputs
        if _scheduler_service:
            for target in targets_list:
                target.scheduled_outputs = _scheduler_service.get_outputs_for_target(
                    target.name
                )
        await manager.broadcast(
            {
                "type": "targets_list",
                "data": [t.model_dump(mode='json') for t in targets_list],
            },
        )


async def broadcast_scheduled_output(
    command_name: str, target_name: str, output: ScheduledCommandOutput
) -> None:
    """Broadcast a scheduled command output to all connected clients.

    This function is called by the SchedulerService when a command completes.

    Args:
        command_name: The name of the scheduled command.
        target_name: The target the command was executed on.
        output: The command output.
    """
    await manager.broadcast_to_subscribed(
        {
            "type": "scheduled_output",
            "data": {
                "command_name": command_name,
                "target": target_name,
                "output": output.model_dump(mode='json'),
            },
        },
        target_name,
    )
