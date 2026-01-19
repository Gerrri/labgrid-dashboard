"""
Scheduler service for periodic command execution on targets.

This service executes scheduled commands (defined in commands.yaml) at their
configured intervals on all available targets, caching the latest output.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from app.models.target import ScheduledCommand, ScheduledCommandOutput

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for executing scheduled commands periodically."""

    def __init__(self):
        """Initialize the scheduler service."""
        # Scheduled commands from configuration
        self._commands: List[ScheduledCommand] = []
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
        # Flag to track if scheduler is running
        self._running = False

    def set_commands(self, commands: List[ScheduledCommand]) -> None:
        """Set the scheduled commands from configuration.
        
        Args:
            commands: List of scheduled commands to execute.
        """
        self._commands = commands
        # Initialize output storage for each command
        for cmd in commands:
            if cmd.name not in self._outputs:
                self._outputs[cmd.name] = {}
        logger.info(f"Configured {len(commands)} scheduled commands")

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

    async def start(self) -> None:
        """Start the scheduler service."""
        self._running = True
        logger.info("Scheduler service starting...")
        
        # Start a task for each scheduled command
        for cmd in self._commands:
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
        """Get all scheduled commands.
        
        Returns:
            List of scheduled commands.
        """
        return self._commands.copy()

    def get_outputs_for_target(self, target_name: str) -> Dict[str, ScheduledCommandOutput]:
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
        logger.info(f"Started scheduler task for '{cmd.name}' (interval: {cmd.interval_seconds}s)")

    async def _run_command_loop(self, cmd: ScheduledCommand) -> None:
        """Run the periodic execution loop for a command."""
        logger.debug(f"Command loop started for '{cmd.name}'")
        
        # Execute immediately on start
        await self._execute_on_all_targets(cmd)
        
        while self._running:
            try:
                await asyncio.sleep(cmd.interval_seconds)
                
                if not self._running:
                    break
                
                await self._execute_on_all_targets(cmd)
                
            except asyncio.CancelledError:
                logger.debug(f"Command loop cancelled for '{cmd.name}'")
                break
            except Exception as e:
                logger.error(f"Error in command loop for '{cmd.name}': {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    async def _execute_on_all_targets(self, cmd: ScheduledCommand) -> None:
        """Execute a command on all available targets."""
        if not self._execute_callback or not self._get_targets_callback:
            logger.warning("Callbacks not configured, skipping execution")
            return
        
        try:
            # Get current targets
            targets = await self._get_targets_callback()
            
            # Execute on each target (excluding offline ones)
            for target in targets:
                if target.status == "offline":
                    continue
                
                try:
                    output, exit_code = await self._execute_callback(target.name, cmd.command)
                    
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
                            await self._notify_callback(cmd.name, target.name, scheduled_output)
                        except Exception as e:
                            logger.debug(f"Notify callback error: {e}")
                    
                    logger.debug(f"Executed '{cmd.name}' on '{target.name}': {output[:50]}..." if len(output) > 50 else f"Executed '{cmd.name}' on '{target.name}': {output}")
                    
                except Exception as e:
                    logger.warning(f"Failed to execute '{cmd.name}' on '{target.name}': {e}")
                    
        except Exception as e:
            logger.error(f"Failed to get targets for scheduled command '{cmd.name}': {e}")

    async def execute_now(self, command_name: str) -> bool:
        """Manually trigger immediate execution of a scheduled command.
        
        Args:
            command_name: The command name to execute.
            
        Returns:
            True if execution was triggered, False if command not found.
        """
        for cmd in self._commands:
            if cmd.name == command_name:
                await self._execute_on_all_targets(cmd)
                return True
        return False
