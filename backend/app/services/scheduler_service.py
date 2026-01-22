"""
Scheduler service for periodic command execution on targets.

This service executes scheduled commands (defined in commands.yaml) at their
configured intervals on targets, supporting preset-specific scheduled commands.

Each target can have a different preset, and the scheduler executes only
the scheduled commands defined in that target's assigned preset.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set

from app.models.target import ScheduledCommand, ScheduledCommandOutput

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for executing scheduled commands periodically with preset support."""

    def __init__(self):
        """Initialize the scheduler service."""
        # All unique scheduled commands from all presets (for display in UI)
        self._all_commands: List[ScheduledCommand] = []
        # Scheduled commands per preset: preset_id -> List[ScheduledCommand]
        self._preset_commands: Dict[str, List[ScheduledCommand]] = {}
        # Latest outputs: command_name -> target_name -> output
        self._outputs: Dict[str, Dict[str, ScheduledCommandOutput]] = {}
        # Running tasks for each command
        self._tasks: Dict[str, asyncio.Task] = {}
        # Callback for executing commands on targets
        self._execute_callback: Optional[Callable] = None
        # Callback for getting current targets
        self._get_targets_callback: Optional[Callable] = None
        # Callback for notifying about output updates (e.g., WebSocket)
        self._notify_callback: Optional[Callable] = None
        # Callback for getting a target's preset ID
        self._get_target_preset_callback: Optional[Callable] = None
        # Flag to track if scheduler is running
        self._running = False

    def set_commands(self, commands: List[ScheduledCommand]) -> None:
        """Set the scheduled commands from configuration (legacy method).

        This method is kept for backwards compatibility. It sets all commands
        as if they belong to a single default preset.

        Args:
            commands: List of scheduled commands to execute.
        """
        self._all_commands = commands
        # Treat all commands as belonging to a "basic" preset
        self._preset_commands = {"basic": commands}
        # Initialize output storage for each command
        for cmd in commands:
            if cmd.name not in self._outputs:
                self._outputs[cmd.name] = {}
        logger.info(f"Configured {len(commands)} scheduled commands (legacy mode)")

    def set_preset_commands(
        self, preset_commands: Dict[str, List[ScheduledCommand]]
    ) -> None:
        """Set the scheduled commands per preset.

        Args:
            preset_commands: Dictionary of preset_id -> List[ScheduledCommand].
        """
        self._preset_commands = preset_commands

        # Build list of all unique commands for backwards compatibility
        seen_names: Set[str] = set()
        self._all_commands = []
        for commands in preset_commands.values():
            for cmd in commands:
                if cmd.name not in seen_names:
                    seen_names.add(cmd.name)
                    self._all_commands.append(cmd)
                    if cmd.name not in self._outputs:
                        self._outputs[cmd.name] = {}

        total_commands = sum(len(cmds) for cmds in preset_commands.values())
        logger.info(
            f"Configured {len(preset_commands)} presets with "
            f"{total_commands} total scheduled commands "
            f"({len(self._all_commands)} unique)"
        )

    def set_execute_callback(self, callback: Callable) -> None:
        """Set the callback for executing commands on targets.

        Args:
            callback: Async function(target_name, command) -> (output, exit_code)
        """
        self._execute_callback = callback

    def set_get_targets_callback(self, callback: Callable) -> None:
        """Set the callback for getting current targets.

        Args:
            callback: Async function() -> List[Target]
        """
        self._get_targets_callback = callback

    def set_notify_callback(self, callback: Callable) -> None:
        """Set the callback for notifying about output updates.

        Args:
            callback: Async function(command_name, target_name, output) -> None
        """
        self._notify_callback = callback

    def set_get_target_preset_callback(self, callback: Callable) -> None:
        """Set the callback for getting a target's preset ID.

        Args:
            callback: Function(target_name) -> preset_id
        """
        self._get_target_preset_callback = callback

    async def start(self) -> None:
        """Start the scheduler service."""
        self._running = True
        logger.info("Scheduler service starting...")

        # Start a task for each unique scheduled command
        for cmd in self._all_commands:
            await self._start_command_task(cmd)

        logger.info(f"Scheduler service started with {len(self._tasks)} tasks")

    async def stop(self) -> None:
        """Stop the scheduler service and all running tasks."""
        self._running = False

        # Cancel all running tasks
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()
        logger.info("Scheduler service stopped")

    def get_commands(self) -> List[ScheduledCommand]:
        """Get all unique scheduled commands.

        Returns:
            List of all unique scheduled commands across all presets.
        """
        return self._all_commands.copy()

    def get_commands_for_preset(self, preset_id: str) -> List[ScheduledCommand]:
        """Get scheduled commands for a specific preset.

        Args:
            preset_id: The preset ID.

        Returns:
            List of scheduled commands for the preset.
        """
        return self._preset_commands.get(preset_id, [])

    def get_outputs_for_target(
        self, target_name: str
    ) -> Dict[str, ScheduledCommandOutput]:
        """Get all scheduled command outputs for a specific target.

        Args:
            target_name: The target name.

        Returns:
            Dictionary of command_name -> output for the target.
        """
        result = {}
        for cmd_name, targets in self._outputs.items():
            if target_name in targets:
                result[cmd_name] = targets[target_name]
        return result

    def get_all_outputs(self) -> Dict[str, Dict[str, ScheduledCommandOutput]]:
        """Get all outputs for all commands and targets.

        Returns:
            Nested dictionary: command_name -> target_name -> output
        """
        return self._outputs.copy()

    async def _start_command_task(self, cmd: ScheduledCommand) -> None:
        """Start the periodic execution task for a command."""
        if cmd.name in self._tasks:
            return  # Already running

        task = asyncio.create_task(self._run_command_loop(cmd))
        self._tasks[cmd.name] = task
        logger.info(
            f"Started scheduler task for '{cmd.name}' (interval: {cmd.interval_seconds}s)"
        )

    async def _run_command_loop(self, cmd: ScheduledCommand) -> None:
        """Run the periodic execution loop for a command."""
        logger.debug(f"Command loop started for '{cmd.name}'")

        # Execute immediately on start
        await self._execute_on_targets_with_preset(cmd)

        while self._running:
            try:
                await asyncio.sleep(cmd.interval_seconds)

                if not self._running:
                    break

                await self._execute_on_targets_with_preset(cmd)

            except asyncio.CancelledError:
                logger.debug(f"Command loop cancelled for '{cmd.name}'")
                break
            except Exception as e:
                logger.error(f"Error in command loop for '{cmd.name}': {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    async def _execute_on_targets_with_preset(self, cmd: ScheduledCommand) -> None:
        """Execute a command on targets that have this command in their preset.

        Args:
            cmd: The scheduled command to execute.
        """
        if not self._execute_callback or not self._get_targets_callback:
            logger.warning("Callbacks not configured, skipping execution")
            return

        try:
            # Get current targets
            targets = await self._get_targets_callback()

            # Execute on each target that has this command in its preset
            for target in targets:
                if target.status == "offline":
                    continue

                # Check if this command applies to this target's preset
                if not self._should_execute_on_target(cmd, target.name):
                    continue

                try:
                    output, exit_code = await self._execute_callback(
                        target.name, cmd.command
                    )

                    # Store the output
                    scheduled_output = ScheduledCommandOutput(
                        command_name=cmd.name,
                        output=output.strip() if output else "",
                        timestamp=datetime.utcnow(),
                        exit_code=exit_code,
                    )

                    if cmd.name not in self._outputs:
                        self._outputs[cmd.name] = {}
                    self._outputs[cmd.name][target.name] = scheduled_output

                    # Notify listeners (e.g., WebSocket clients)
                    if self._notify_callback:
                        try:
                            await self._notify_callback(
                                cmd.name, target.name, scheduled_output
                            )
                        except Exception as e:
                            logger.debug(f"Notify callback error: {e}")

                    output_preview = output[:50] + "..." if len(output) > 50 else output
                    logger.debug(
                        f"Executed '{cmd.name}' on '{target.name}': {output_preview}"
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to execute '{cmd.name}' on '{target.name}': {e}"
                    )

        except Exception as e:
            logger.error(
                f"Failed to get targets for scheduled command '{cmd.name}': {e}"
            )

    def _should_execute_on_target(
        self, cmd: ScheduledCommand, target_name: str
    ) -> bool:
        """Check if a command should be executed on a target based on its preset.

        Args:
            cmd: The scheduled command.
            target_name: The target name.

        Returns:
            True if the command should be executed on the target.
        """
        # If no preset callback is configured, execute on all targets (legacy mode)
        if not self._get_target_preset_callback:
            return True

        # Get the target's preset
        preset_id = self._get_target_preset_callback(target_name)

        # Check if the command exists in this preset's scheduled commands
        preset_commands = self._preset_commands.get(preset_id, [])
        for preset_cmd in preset_commands:
            if preset_cmd.name == cmd.name:
                return True

        return False

    async def execute_now(self, command_name: str) -> bool:
        """Manually trigger immediate execution of a scheduled command.

        Args:
            command_name: The command name to execute.

        Returns:
            True if execution was triggered, False if command not found.
        """
        for cmd in self._all_commands:
            if cmd.name == command_name:
                await self._execute_on_targets_with_preset(cmd)
                return True
        return False

    # Legacy method - kept for backwards compatibility
    async def _execute_on_all_targets(self, cmd: ScheduledCommand) -> None:
        """Execute a command on all available targets (legacy method).

        This method is kept for backwards compatibility.
        Use _execute_on_targets_with_preset for preset-aware execution.
        """
        await self._execute_on_targets_with_preset(cmd)
