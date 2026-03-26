"""
Scheduler service for periodic command execution on targets.

This service executes scheduled commands (defined in commands.yaml) at their
configured intervals on targets, supporting preset-specific scheduled commands.

Each target can have a different preset, and the scheduler executes only
the scheduled commands defined in that target's assigned preset.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from copy import deepcopy
from typing import Callable, Dict, List, Optional, Set, Union

from app.models.target import ScheduledCommand, ScheduledCommandOutput

logger = logging.getLogger(__name__)

SCHEDULER_ERROR_BACKOFF_INITIAL = 5
SCHEDULER_ERROR_BACKOFF_MAX = 60


@dataclass(frozen=True)
class _ScheduledCommandRegistration:
    """Internal scheduler registration for a preset-scoped command."""

    key: str
    preset_id: str
    command: ScheduledCommand


class SchedulerService:
    """Service for executing scheduled commands periodically with preset support."""

    def __init__(self):
        """Initialize the scheduler service."""
        # All unique scheduled commands from all presets (for display in UI)
        self._all_commands: List[ScheduledCommand] = []
        self._command_registrations: List[_ScheduledCommandRegistration] = []
        # Scheduled commands per preset: preset_id -> List[ScheduledCommand]
        self._preset_commands: Dict[str, List[ScheduledCommand]] = {}
        # Latest outputs keyed by internal registration key -> target_name -> output
        self._outputs: Dict[str, Dict[str, ScheduledCommandOutput]] = {}
        # Running tasks keyed by internal registration key
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
        # Locks per target to prevent concurrent command execution on same target
        self._target_locks: Dict[str, asyncio.Lock] = {}

    def set_commands(self, commands: List[ScheduledCommand]) -> None:
        """Set the scheduled commands from configuration (legacy method).

        This method is kept for backwards compatibility. It sets all commands
        as if they belong to a single default preset.

        Args:
            commands: List of scheduled commands to execute.
        """
        self._all_commands = commands
        self._command_registrations = [
            _ScheduledCommandRegistration(
                key=cmd.name,
                preset_id="basic",
                command=cmd,
            )
            for cmd in commands
        ]
        # Treat all commands as belonging to a "basic" preset
        self._preset_commands = {"basic": commands}
        # Initialize output storage for each command
        self._outputs = {
            registration.key: {} for registration in self._command_registrations
        }
        logger.info(f"Configured {len(commands)} scheduled commands (legacy mode)")

    def set_preset_commands(
        self, preset_commands: Dict[str, List[ScheduledCommand]]
    ) -> None:
        """Set the scheduled commands per preset.

        Args:
            preset_commands: Dictionary of preset_id -> List[ScheduledCommand].
        """
        self._preset_commands = preset_commands

        # Build registrations for every preset-scoped command while preserving
        # a unique display-name list for the existing UI/API surface.
        seen_names: Set[str] = set()
        self._all_commands = []
        self._command_registrations = []
        for preset_id, commands in preset_commands.items():
            for index, cmd in enumerate(commands):
                self._command_registrations.append(
                    _ScheduledCommandRegistration(
                        key=self._build_registration_key(preset_id, cmd, index),
                        preset_id=preset_id,
                        command=cmd,
                    )
                )
                if cmd.name not in seen_names:
                    seen_names.add(cmd.name)
                    self._all_commands.append(cmd)
        self._outputs = {
            registration.key: self._outputs.get(registration.key, {})
            for registration in self._command_registrations
        }

        total_commands = sum(len(cmds) for cmds in preset_commands.values())
        logger.info(
            f"Configured {len(preset_commands)} presets with "
            f"{total_commands} total scheduled commands "
            f"({len(self._all_commands)} unique)"
        )

    def set_execute_callback(self, callback: Callable) -> None:
        """Set the callback for executing commands on targets.

        Args:
            callback: Async function(target_name, command) -> result object or tuple
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
        for registration in self._command_registrations:
            await self._start_command_task(registration)

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
        active_preset_id = None
        if self._get_target_preset_callback:
            active_preset_id = self._get_target_preset_callback(target_name)

        for registration in self._command_registrations:
            if (
                active_preset_id is not None
                and registration.preset_id != active_preset_id
            ):
                continue

            targets = self._outputs.get(registration.key, {})
            if target_name in targets:
                result[registration.command.name] = targets[target_name]
        return result

    def get_all_outputs(self) -> Dict[str, Dict[str, ScheduledCommandOutput]]:
        """Get all outputs for all commands and targets.

        Returns:
            Nested dictionary keyed by internal scheduler command key.
        """
        return deepcopy(self._outputs)

    def _build_registration_key(
        self,
        preset_id: str,
        cmd: ScheduledCommand,
        index: int,
    ) -> str:
        """Build a stable internal key for a preset-scoped scheduled command."""
        return f"{preset_id}:{index}:{cmd.name}"

    def _resolve_registration(
        self,
        command: Union[ScheduledCommand, _ScheduledCommandRegistration],
    ) -> _ScheduledCommandRegistration:
        """Resolve an internal registration for a scheduled command input."""
        if isinstance(command, _ScheduledCommandRegistration):
            return command

        for registration in self._command_registrations:
            if registration.command is command:
                return registration

        return _ScheduledCommandRegistration(
            key=command.name,
            preset_id="basic",
            command=command,
        )

    async def _start_command_task(
        self,
        command: Union[ScheduledCommand, _ScheduledCommandRegistration],
    ) -> None:
        """Start the periodic execution task for a command."""
        registration = self._resolve_registration(command)
        if registration.key in self._tasks:
            return  # Already running

        task = asyncio.create_task(self._run_command_loop(registration))
        self._tasks[registration.key] = task
        logger.info(
            "Started scheduler task for '%s' in preset '%s' (interval: %ss)",
            registration.command.name,
            registration.preset_id,
            registration.command.interval_seconds,
        )

    async def _run_command_loop(
        self,
        command: Union[ScheduledCommand, _ScheduledCommandRegistration],
    ) -> None:
        """Run the periodic execution loop for a command."""
        registration = self._resolve_registration(command)
        logger.debug("Command loop started for '%s'", registration.command.name)
        retry_delay = SCHEDULER_ERROR_BACKOFF_INITIAL
        run_immediately = True

        while self._running:
            try:
                if run_immediately:
                    run_immediately = False
                else:
                    await asyncio.sleep(registration.command.interval_seconds)

                if not self._running:
                    break

                await self._execute_on_targets_with_preset(registration)
                retry_delay = SCHEDULER_ERROR_BACKOFF_INITIAL

            except asyncio.CancelledError:
                logger.debug(
                    "Command loop cancelled for '%s'", registration.command.name
                )
                break
            except Exception as e:
                logger.error(
                    "Error in command loop for '%s': %s",
                    registration.command.name,
                    e,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = self._get_next_retry_delay(retry_delay)

    def _get_next_retry_delay(self, current_delay: int) -> int:
        """Compute the next retry delay with an exponential backoff cap."""
        return min(current_delay * 2, SCHEDULER_ERROR_BACKOFF_MAX)

    async def _execute_on_targets_with_preset(
        self,
        command: Union[ScheduledCommand, _ScheduledCommandRegistration],
    ) -> None:
        """Execute a command on targets that have this command in their preset.

        Scheduled commands run on ALL targets except offline ones.
        This allows monitoring metrics (uptime, load, memory) even on acquired targets.

        Uses per-target locking to prevent race conditions when multiple scheduled
        commands try to execute on the same target simultaneously.

        Args:
            command: The scheduled command or internal registration to execute.
        """
        registration = self._resolve_registration(command)
        cmd = registration.command
        if not self._execute_callback or not self._get_targets_callback:
            logger.warning("Callbacks not configured, skipping execution")
            return

        try:
            # Get current targets
            targets = await self._get_targets_callback()

            logger.info(
                f"Scheduler for '{cmd.name}': found {len(targets)} targets: {[t.name for t in targets]}"
            )

            # Execute on each target that has this command in its preset
            for target in targets:
                # Skip only offline targets (scheduled commands run on acquired targets too)
                if target.status == "offline":
                    logger.info(
                        f"Skipping '{cmd.name}' on '{target.name}': target is offline"
                    )
                    continue

                # Check if this command applies to this target's preset
                if not self._should_execute_on_target(registration, target.name):
                    logger.info(
                        f"Skipping '{cmd.name}' on '{target.name}': command not in target's preset"
                    )
                    continue

                # Get or create lock for this target
                if target.name not in self._target_locks:
                    self._target_locks[target.name] = asyncio.Lock()

                target_lock = self._target_locks[target.name]

                # Queue behind the current command instead of dropping this run.
                if target_lock.locked():
                    logger.warning(
                        f"Delaying '{cmd.name}' on '{target.name}': target is busy, waiting for current command to finish"
                    )

                # Execute with lock to prevent concurrent access
                async with target_lock:
                    try:
                        result = await self._execute_callback(
                            target.name, cmd.command
                        )
                        execution_transport = None
                        if isinstance(result, tuple):
                            output, exit_code = result
                        else:
                            output = result.output
                            exit_code = result.exit_code
                            execution_transport = getattr(
                                result,
                                "execution_transport",
                                None,
                            )

                        # Store the output
                        scheduled_output = ScheduledCommandOutput(
                            command_name=cmd.name,
                            output=output.strip() if output else "",
                            timestamp=datetime.now(timezone.utc),
                            exit_code=exit_code,
                            execution_transport=execution_transport,
                        )

                        if registration.key not in self._outputs:
                            self._outputs[registration.key] = {}
                        self._outputs[registration.key][target.name] = scheduled_output

                        # Notify listeners (e.g., WebSocket clients)
                        if self._notify_callback:
                            try:
                                await self._notify_callback(
                                    cmd.name, target.name, scheduled_output
                                )
                            except Exception as e:
                                logger.debug(f"Notify callback error: {e}")

                        output_preview = (
                            output[:50] + "..." if len(output) > 50 else output
                        )
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
        self,
        command: Union[ScheduledCommand, _ScheduledCommandRegistration],
        target_name: str,
    ) -> bool:
        """Check if a command should be executed on a target based on its preset.

        Args:
            command: The scheduled command or internal registration.
            target_name: The target name.

        Returns:
            True if the command should be executed on the target.
        """
        registration = self._resolve_registration(command)
        # If no preset callback is configured, execute on all targets (legacy mode)
        if not self._get_target_preset_callback:
            return True

        # Get the target's preset
        preset_id = self._get_target_preset_callback(target_name)
        return preset_id == registration.preset_id

    async def execute_now(self, command_name: str) -> bool:
        """Manually trigger immediate execution of a scheduled command.

        Args:
            command_name: The command name to execute.

        Returns:
            True if execution was triggered, False if command not found.
        """
        matched = [
            registration
            for registration in self._command_registrations
            if registration.command.name == command_name
        ]
        if not matched:
            return False

        for registration in matched:
            await self._execute_on_targets_with_preset(registration)
        return True

    # Legacy method - kept for backwards compatibility
    async def _execute_on_all_targets(self, cmd: ScheduledCommand) -> None:
        """Execute a command on all available targets (legacy method).

        This method is kept for backwards compatibility.
        Use _execute_on_targets_with_preset for preset-aware execution.
        """
        await self._execute_on_targets_with_preset(cmd)
