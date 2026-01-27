"""
Tests for the SchedulerService.

This module tests the scheduler service which executes scheduled commands
periodically on targets, with support for preset-specific scheduled commands.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.target import ScheduledCommand, ScheduledCommandOutput, Target
from app.services.scheduler_service import SchedulerService


@pytest.fixture
def scheduler():
    """Create a scheduler service instance."""
    return SchedulerService()


@pytest.fixture
def sample_command():
    """Create a sample scheduled command."""
    return ScheduledCommand(
        name="uptime",
        command="uptime",
        interval_seconds=5,
        description="Check system uptime",
    )


@pytest.fixture
def sample_commands():
    """Create sample scheduled commands."""
    return [
        ScheduledCommand(
            name="uptime",
            command="uptime",
            interval_seconds=5,
            description="Check system uptime",
        ),
        ScheduledCommand(
            name="free",
            command="free -h",
            interval_seconds=10,
            description="Check memory usage",
        ),
    ]


@pytest.fixture
def sample_target():
    """Create a sample target."""
    return Target(
        name="dut-1",
        status="available",
        acquired_by=None,
        tags=["test"],
        resources=[],
        preset="basic",
    )


@pytest.fixture
def sample_targets():
    """Create sample targets."""
    return [
        Target(
            name="dut-1",
            status="available",
            acquired_by=None,
            tags=["test"],
            resources=[],
            preset="basic",
        ),
        Target(
            name="dut-2",
            status="acquired",
            acquired_by="user1",
            tags=["test"],
            resources=[],
            preset="basic",
        ),
        Target(
            name="dut-3",
            status="offline",
            acquired_by=None,
            tags=["test"],
            resources=[],
            preset="advanced",
        ),
    ]


class TestSchedulerServiceInitialization:
    """Test scheduler service initialization and configuration."""

    def test_init(self, scheduler):
        """Test scheduler initialization."""
        # Arrange & Act - created by fixture
        # Assert
        assert scheduler._all_commands == []
        assert scheduler._preset_commands == {}
        assert scheduler._outputs == {}
        assert scheduler._tasks == {}
        assert scheduler._execute_callback is None
        assert scheduler._get_targets_callback is None
        assert scheduler._notify_callback is None
        assert scheduler._get_target_preset_callback is None
        assert scheduler._running is False
        assert scheduler._target_locks == {}

    def test_set_commands_legacy(self, scheduler, sample_commands):
        """Test setting commands using legacy method."""
        # Arrange & Act
        scheduler.set_commands(sample_commands)

        # Assert
        assert scheduler._all_commands == sample_commands
        assert scheduler._preset_commands == {"basic": sample_commands}
        assert "uptime" in scheduler._outputs
        assert "free" in scheduler._outputs

    def test_set_preset_commands(self, scheduler):
        """Test setting preset-specific commands."""
        # Arrange
        basic_commands = [
            ScheduledCommand(
                name="uptime",
                command="uptime",
                interval_seconds=5,
                description="Check uptime",
            )
        ]
        advanced_commands = [
            ScheduledCommand(
                name="uptime",
                command="uptime",
                interval_seconds=5,
                description="Check uptime",
            ),
            ScheduledCommand(
                name="sensors",
                command="sensors",
                interval_seconds=10,
                description="Check sensors",
            ),
        ]
        preset_commands = {"basic": basic_commands, "advanced": advanced_commands}

        # Act
        scheduler.set_preset_commands(preset_commands)

        # Assert
        assert scheduler._preset_commands == preset_commands
        assert len(scheduler._all_commands) == 2  # uptime and sensors (unique)
        assert "uptime" in scheduler._outputs
        assert "sensors" in scheduler._outputs

    def test_set_callbacks(self, scheduler):
        """Test setting callbacks."""
        # Arrange
        execute_callback = AsyncMock()
        get_targets_callback = AsyncMock()
        notify_callback = AsyncMock()
        get_preset_callback = MagicMock()

        # Act
        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)
        scheduler.set_notify_callback(notify_callback)
        scheduler.set_get_target_preset_callback(get_preset_callback)

        # Assert
        assert scheduler._execute_callback == execute_callback
        assert scheduler._get_targets_callback == get_targets_callback
        assert scheduler._notify_callback == notify_callback
        assert scheduler._get_target_preset_callback == get_preset_callback


class TestSchedulerServiceGettingData:
    """Test scheduler service data retrieval methods."""

    def test_get_commands(self, scheduler, sample_commands):
        """Test getting all commands."""
        # Arrange
        scheduler.set_commands(sample_commands)

        # Act
        commands = scheduler.get_commands()

        # Assert
        assert commands == sample_commands
        assert commands is not scheduler._all_commands  # Should be a copy

    def test_get_commands_for_preset(self, scheduler):
        """Test getting commands for a specific preset."""
        # Arrange
        basic_commands = [
            ScheduledCommand(
                name="uptime", command="uptime", interval_seconds=5, description=""
            )
        ]
        advanced_commands = [
            ScheduledCommand(
                name="sensors", command="sensors", interval_seconds=10, description=""
            )
        ]
        scheduler.set_preset_commands(
            {"basic": basic_commands, "advanced": advanced_commands}
        )

        # Act
        basic = scheduler.get_commands_for_preset("basic")
        advanced = scheduler.get_commands_for_preset("advanced")
        unknown = scheduler.get_commands_for_preset("unknown")

        # Assert
        assert basic == basic_commands
        assert advanced == advanced_commands
        assert unknown == []

    def test_get_outputs_for_target(self, scheduler):
        """Test getting outputs for a specific target."""
        # Arrange
        scheduler._outputs = {
            "uptime": {
                "dut-1": ScheduledCommandOutput(
                    command_name="uptime",
                    output="up 5 days",
                    timestamp=datetime.now(timezone.utc),
                    exit_code=0,
                ),
                "dut-2": ScheduledCommandOutput(
                    command_name="uptime",
                    output="up 10 days",
                    timestamp=datetime.now(timezone.utc),
                    exit_code=0,
                ),
            },
            "free": {
                "dut-1": ScheduledCommandOutput(
                    command_name="free",
                    output="Memory: 8GB",
                    timestamp=datetime.now(timezone.utc),
                    exit_code=0,
                )
            },
        }

        # Act
        dut1_outputs = scheduler.get_outputs_for_target("dut-1")
        dut2_outputs = scheduler.get_outputs_for_target("dut-2")
        dut3_outputs = scheduler.get_outputs_for_target("dut-3")

        # Assert
        assert len(dut1_outputs) == 2
        assert "uptime" in dut1_outputs
        assert "free" in dut1_outputs
        assert len(dut2_outputs) == 1
        assert "uptime" in dut2_outputs
        assert len(dut3_outputs) == 0

    def test_get_all_outputs(self, scheduler):
        """Test getting all outputs."""
        # Arrange
        outputs = {
            "uptime": {
                "dut-1": ScheduledCommandOutput(
                    command_name="uptime",
                    output="up 5 days",
                    timestamp=datetime.now(timezone.utc),
                    exit_code=0,
                )
            }
        }
        scheduler._outputs = outputs

        # Act
        all_outputs = scheduler.get_all_outputs()

        # Assert
        assert all_outputs == outputs
        assert all_outputs is not scheduler._outputs  # Should be a copy


class TestSchedulerServiceStartStop:
    """Test scheduler service start/stop functionality."""

    @pytest.mark.asyncio
    async def test_start(self, scheduler, sample_commands):
        """Test starting the scheduler."""
        # Arrange
        scheduler.set_commands(sample_commands)

        # Act
        await scheduler.start()

        # Assert
        assert scheduler._running is True
        assert len(scheduler._tasks) == 2
        assert "uptime" in scheduler._tasks
        assert "free" in scheduler._tasks

        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop(self, scheduler, sample_commands):
        """Test stopping the scheduler."""
        # Arrange
        scheduler.set_commands(sample_commands)
        await scheduler.start()
        assert scheduler._running is True

        # Act
        await scheduler.stop()

        # Assert
        assert scheduler._running is False
        assert len(scheduler._tasks) == 0

    @pytest.mark.asyncio
    async def test_start_command_task_already_running(self, scheduler, sample_command):
        """Test starting a task that is already running."""
        # Arrange
        scheduler._all_commands = [sample_command]
        await scheduler._start_command_task(sample_command)
        initial_task = scheduler._tasks.get(sample_command.name)

        # Act
        await scheduler._start_command_task(sample_command)

        # Assert
        assert scheduler._tasks.get(sample_command.name) is initial_task

        # Cleanup
        await scheduler.stop()


class TestSchedulerServiceExecution:
    """Test scheduler service command execution."""

    @pytest.mark.asyncio
    async def test_execute_on_targets_with_preset_no_callbacks(
        self, scheduler, sample_command
    ):
        """Test execution when callbacks are not configured."""
        # Arrange - no callbacks set
        # Act
        await scheduler._execute_on_targets_with_preset(sample_command)

        # Assert - should return early without error

    @pytest.mark.asyncio
    async def test_execute_on_targets_with_preset_success(
        self, scheduler, sample_command, sample_targets
    ):
        """Test successful execution on targets."""
        # Arrange
        scheduler.set_commands([sample_command])
        execute_callback = AsyncMock(return_value=("up 5 days", 0))
        get_targets_callback = AsyncMock(return_value=sample_targets)
        notify_callback = AsyncMock()

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)
        scheduler.set_notify_callback(notify_callback)

        # Act
        await scheduler._execute_on_targets_with_preset(sample_command)

        # Assert
        # Should execute on dut-1 (available) and dut-2 (acquired)
        # Should NOT execute on dut-3 (offline)
        assert execute_callback.call_count == 2
        assert "uptime" in scheduler._outputs
        assert "dut-1" in scheduler._outputs["uptime"]
        assert "dut-2" in scheduler._outputs["uptime"]
        assert "dut-3" not in scheduler._outputs["uptime"]
        assert notify_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_on_targets_skip_offline(
        self, scheduler, sample_command, sample_target
    ):
        """Test that offline targets are skipped."""
        # Arrange
        sample_target.status = "offline"
        scheduler.set_commands([sample_command])
        execute_callback = AsyncMock(return_value=("output", 0))
        get_targets_callback = AsyncMock(return_value=[sample_target])

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)

        # Act
        await scheduler._execute_on_targets_with_preset(sample_command)

        # Assert
        execute_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_on_targets_with_preset_filtering(
        self, scheduler, sample_targets
    ):
        """Test that commands are filtered by preset."""
        # Arrange
        basic_cmd = ScheduledCommand(
            name="uptime", command="uptime", interval_seconds=5, description=""
        )
        advanced_cmd = ScheduledCommand(
            name="sensors", command="sensors", interval_seconds=10, description=""
        )
        scheduler.set_preset_commands(
            {"basic": [basic_cmd], "advanced": [advanced_cmd]}
        )

        execute_callback = AsyncMock(return_value=("output", 0))
        get_targets_callback = AsyncMock(return_value=sample_targets)
        get_preset_callback = lambda name: "basic" if "dut-1" in name or "dut-2" in name else "advanced"

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)
        scheduler.set_get_target_preset_callback(get_preset_callback)

        # Act - execute basic command
        await scheduler._execute_on_targets_with_preset(basic_cmd)

        # Assert - should only execute on dut-1 and dut-2 (have basic preset)
        # dut-3 is offline anyway
        assert execute_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_on_targets_handles_execution_error(
        self, scheduler, sample_command, sample_target
    ):
        """Test handling of execution errors."""
        # Arrange
        scheduler.set_commands([sample_command])
        execute_callback = AsyncMock(side_effect=Exception("Command failed"))
        get_targets_callback = AsyncMock(return_value=[sample_target])

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)

        # Act - should not raise
        await scheduler._execute_on_targets_with_preset(sample_command)

        # Assert
        execute_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_on_targets_handles_get_targets_error(
        self, scheduler, sample_command
    ):
        """Test handling of get_targets errors."""
        # Arrange
        scheduler.set_commands([sample_command])
        execute_callback = AsyncMock(return_value=("output", 0))
        get_targets_callback = AsyncMock(side_effect=Exception("Failed to get targets"))

        scheduler.set_execute_callback(execute_callback)  # Need this set too
        scheduler.set_get_targets_callback(get_targets_callback)

        # Act - should not raise
        await scheduler._execute_on_targets_with_preset(sample_command)

        # Assert
        get_targets_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_on_targets_with_target_lock(
        self, scheduler, sample_command, sample_target
    ):
        """Test that target locks prevent concurrent execution."""
        # Arrange
        scheduler.set_commands([sample_command])

        # Simulate slow execution
        async def slow_execution(target, cmd):
            await asyncio.sleep(0.1)
            return ("output", 0)

        execute_callback = AsyncMock(side_effect=slow_execution)
        get_targets_callback = AsyncMock(return_value=[sample_target])

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)

        # Act - execute twice concurrently
        task1 = asyncio.create_task(
            scheduler._execute_on_targets_with_preset(sample_command)
        )
        # Give first task time to acquire lock
        await asyncio.sleep(0.01)
        task2 = asyncio.create_task(
            scheduler._execute_on_targets_with_preset(sample_command)
        )

        await task1
        await task2

        # Assert - should only execute once due to lock
        assert execute_callback.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_on_targets_notify_callback_error(
        self, scheduler, sample_command, sample_target
    ):
        """Test handling of notify callback errors."""
        # Arrange
        scheduler.set_commands([sample_command])
        execute_callback = AsyncMock(return_value=("output", 0))
        get_targets_callback = AsyncMock(return_value=[sample_target])
        notify_callback = AsyncMock(side_effect=Exception("Notify failed"))

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)
        scheduler.set_notify_callback(notify_callback)

        # Act - should not raise
        await scheduler._execute_on_targets_with_preset(sample_command)

        # Assert
        execute_callback.assert_called_once()
        notify_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_now_command_found(self, scheduler, sample_commands):
        """Test manually triggering command execution."""
        # Arrange
        scheduler.set_commands(sample_commands)
        execute_callback = AsyncMock(return_value=("output", 0))
        get_targets_callback = AsyncMock(return_value=[])

        scheduler.set_execute_callback(execute_callback)
        scheduler.set_get_targets_callback(get_targets_callback)

        # Act
        result = await scheduler.execute_now("uptime")

        # Assert
        assert result is True
        get_targets_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_now_command_not_found(self, scheduler, sample_commands):
        """Test manually triggering non-existent command."""
        # Arrange
        scheduler.set_commands(sample_commands)

        # Act
        result = await scheduler.execute_now("nonexistent")

        # Assert
        assert result is False


class TestSchedulerServiceShouldExecute:
    """Test scheduler preset filtering logic."""

    def test_should_execute_no_preset_callback(self, scheduler, sample_command):
        """Test execution decision when no preset callback is set."""
        # Arrange - no preset callback
        # Act
        should_execute = scheduler._should_execute_on_target(sample_command, "dut-1")

        # Assert
        assert should_execute is True  # Legacy mode, execute on all

    def test_should_execute_command_in_preset(self, scheduler):
        """Test execution when command is in target's preset."""
        # Arrange
        cmd = ScheduledCommand(
            name="uptime", command="uptime", interval_seconds=5, description=""
        )
        scheduler.set_preset_commands({"basic": [cmd]})
        get_preset_callback = lambda name: "basic"
        scheduler.set_get_target_preset_callback(get_preset_callback)

        # Act
        should_execute = scheduler._should_execute_on_target(cmd, "dut-1")

        # Assert
        assert should_execute is True

    def test_should_execute_command_not_in_preset(self, scheduler):
        """Test execution when command is not in target's preset."""
        # Arrange
        cmd = ScheduledCommand(
            name="uptime", command="uptime", interval_seconds=5, description=""
        )
        scheduler.set_preset_commands({"advanced": [cmd]})
        get_preset_callback = lambda name: "basic"  # Target has different preset
        scheduler.set_get_target_preset_callback(get_preset_callback)

        # Act
        should_execute = scheduler._should_execute_on_target(cmd, "dut-1")

        # Assert
        assert should_execute is False


class TestSchedulerServiceCommandLoop:
    """Test scheduler command loop functionality."""

    @pytest.mark.asyncio
    async def test_run_command_loop_executes_periodically(self, scheduler, sample_command):
        """Test that command loop executes periodically."""
        # Arrange
        scheduler._running = True
        execute_count = 0

        async def count_executions(cmd):
            nonlocal execute_count
            execute_count += 1

        # Mock the execute method
        scheduler._execute_on_targets_with_preset = AsyncMock(side_effect=count_executions)

        # Use very short interval for testing
        sample_command.interval_seconds = 0.05

        # Act - run loop for short time
        loop_task = asyncio.create_task(scheduler._run_command_loop(sample_command))
        await asyncio.sleep(0.15)  # Allow ~2 executions
        scheduler._running = False
        await loop_task

        # Assert - should execute immediately + at least once more
        assert execute_count >= 2

    @pytest.mark.asyncio
    async def test_run_command_loop_handles_exception(self, scheduler, sample_command):
        """Test that command loop handles exceptions during periodic execution."""
        # Arrange
        scheduler._running = True
        call_count = 0

        async def fail_on_second_call(cmd):
            nonlocal call_count
            call_count += 1
            # First call succeeds (immediate execution before loop)
            # Second call fails (first iteration in loop)
            if call_count == 2:
                raise Exception("Second call fails")
            # Third call: stop the loop
            elif call_count == 3:
                scheduler._running = False

        # Mock asyncio.sleep to make the test faster
        original_sleep = asyncio.sleep
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            # Use very short actual sleep
            await original_sleep(0.01)

        with __import__('unittest.mock').mock.patch('asyncio.sleep', side_effect=mock_sleep):
            scheduler._execute_on_targets_with_preset = AsyncMock(side_effect=fail_on_second_call)
            sample_command.interval_seconds = 0.05

            # Act - run loop
            loop_task = asyncio.create_task(scheduler._run_command_loop(sample_command))

            # Wait for loop to finish
            try:
                await asyncio.wait_for(loop_task, timeout=1.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                pass

        # Assert - should have called 3 times:
        # 1. immediate (succeeds)
        # 2. first loop iteration (fails, triggers 5s retry)
        # 3. after retry (succeeds and stops loop)
        assert call_count == 3
        assert 5 in sleep_calls  # 5s error retry delay was called

    @pytest.mark.asyncio
    async def test_run_command_loop_cancellation(self, scheduler, sample_command):
        """Test that command loop handles cancellation."""
        # Arrange
        scheduler._running = True
        scheduler._execute_on_targets_with_preset = AsyncMock(return_value=None)
        sample_command.interval_seconds = 10  # Long interval

        # Act
        loop_task = asyncio.create_task(scheduler._run_command_loop(sample_command))
        await asyncio.sleep(0.05)  # Wait for loop to start and get into sleep
        loop_task.cancel()

        # Assert - cancellation should be caught and handled by the loop
        try:
            await loop_task
        except asyncio.CancelledError:
            pass  # Expected - the loop catches it and breaks, but still propagates

        # Verify the task was cancelled
        assert loop_task.cancelled() or loop_task.done()


class TestSchedulerServiceLegacyMethods:
    """Test legacy compatibility methods."""

    @pytest.mark.asyncio
    async def test_execute_on_all_targets_calls_preset_method(
        self, scheduler, sample_command
    ):
        """Test that legacy method calls the preset-aware method."""
        # Arrange
        scheduler._execute_on_targets_with_preset = AsyncMock()

        # Act
        await scheduler._execute_on_all_targets(sample_command)

        # Assert
        scheduler._execute_on_targets_with_preset.assert_called_once_with(sample_command)
