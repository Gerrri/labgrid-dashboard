"""
Unit tests for acquire/release flow in LabgridClient.

Tests the target acquisition, release, and retry logic used during
command execution.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.labgrid_client import (
    LABGRID_DASHBOARD_USER,
    LabgridClient,
    TargetAcquiredByOtherError,
)


@pytest.fixture
def labgrid_client():
    """Create a LabgridClient instance for testing."""
    client = LabgridClient(url="localhost:20408")
    client._connected = True
    client._session = MagicMock()
    return client


class TestTargetAcquiredByOtherError:
    """Tests for TargetAcquiredByOtherError exception."""

    def test_error_message(self):
        """Test that error message contains target and user info."""
        error = TargetAcquiredByOtherError("test-target", "other-user")
        assert error.target_name == "test-target"
        assert error.acquired_by == "other-user"
        assert "test-target" in str(error)
        assert "other-user" in str(error)


class TestAcquireTarget:
    """Tests for acquire_target method."""

    @pytest.mark.asyncio
    async def test_acquire_target_success(self, labgrid_client):
        """Test successful target acquisition when target is not acquired."""
        with patch.object(labgrid_client, "_get_acquired_by", return_value=None):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"acquired", b"")
                mock_exec.return_value = mock_proc

                result = await labgrid_client.acquire_target("test-target")
                assert result is True
                mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_target_already_acquired_by_us(self, labgrid_client):
        """Test that we skip acquisition when already acquired by us."""
        with patch.object(
            labgrid_client, "_get_acquired_by", return_value=LABGRID_DASHBOARD_USER
        ):
            # Should return True without calling labgrid-client
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                result = await labgrid_client.acquire_target("test-target")
                assert result is True
                mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_acquire_target_already_acquired_by_other(self, labgrid_client):
        """Test that TargetAcquiredByOtherError is raised when acquired by other."""
        with patch.object(
            labgrid_client, "_get_acquired_by", return_value="other-user"
        ):
            with pytest.raises(TargetAcquiredByOtherError) as exc:
                await labgrid_client.acquire_target("test-target")

            assert exc.value.target_name == "test-target"
            assert exc.value.acquired_by == "other-user"

    @pytest.mark.asyncio
    async def test_acquire_target_fails_with_already_acquired_error(
        self, labgrid_client
    ):
        """Test handling of 'already acquired' error from labgrid-client."""
        with patch.object(labgrid_client, "_get_acquired_by", return_value=None):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.returncode = 1
                mock_proc.communicate.return_value = (
                    b"",
                    b"place test-target is already acquired by other-user",
                )
                mock_exec.return_value = mock_proc

                with pytest.raises(TargetAcquiredByOtherError) as exc:
                    await labgrid_client.acquire_target("test-target")

                assert exc.value.target_name == "test-target"

    @pytest.mark.asyncio
    async def test_acquire_target_fails_with_other_error(self, labgrid_client):
        """Test handling of other errors from labgrid-client."""
        with patch.object(labgrid_client, "_get_acquired_by", return_value=None):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.returncode = 1
                mock_proc.communicate.return_value = (b"", b"connection refused")
                mock_exec.return_value = mock_proc

                with pytest.raises(RuntimeError) as exc:
                    await labgrid_client.acquire_target("test-target")

                assert "connection refused" in str(exc.value)


class TestReleaseTarget:
    """Tests for release_target method."""

    @pytest.mark.asyncio
    async def test_release_target_success(self, labgrid_client):
        """Test successful target release."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (b"released", b"")
            mock_exec.return_value = mock_proc

            result = await labgrid_client.release_target("test-target")
            assert result is True
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_target_failure(self, labgrid_client):
        """Test release failure returns False."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate.return_value = (b"", b"release failed")
            mock_exec.return_value = mock_proc

            result = await labgrid_client.release_target("test-target")
            assert result is False


class TestReleaseTargetWithRetry:
    """Tests for release_target_with_retry method."""

    @pytest.mark.asyncio
    async def test_release_with_retry_succeeds_first_attempt(self, labgrid_client):
        """Test that release succeeds on first attempt."""
        with patch.object(
            labgrid_client, "release_target", return_value=True
        ) as mock_release:
            result = await labgrid_client.release_target_with_retry("test-target")
            assert result is True
            assert mock_release.call_count == 1

    @pytest.mark.asyncio
    async def test_release_with_retry_succeeds_on_third_attempt(self, labgrid_client):
        """Test that release retries work correctly."""
        # First two attempts fail, third succeeds
        call_count = 0

        async def mock_release(place_name):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return False
            return True

        with patch.object(labgrid_client, "release_target", side_effect=mock_release):
            with patch("asyncio.sleep", return_value=None):  # Skip actual sleep
                result = await labgrid_client.release_target_with_retry("test-target")
                assert result is True
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_release_with_retry_fails_after_max_retries(self, labgrid_client):
        """Test that release gives up after max retries."""
        with patch.object(labgrid_client, "release_target", return_value=False):
            with patch("asyncio.sleep", return_value=None):  # Skip actual sleep
                result = await labgrid_client.release_target_with_retry(
                    "test-target", max_retries=2
                )
                assert result is False

    @pytest.mark.asyncio
    async def test_release_with_retry_handles_exceptions(self, labgrid_client):
        """Test that release handles exceptions during retry."""
        call_count = 0

        async def mock_release(place_name):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Connection error")
            return True

        with patch.object(labgrid_client, "release_target", side_effect=mock_release):
            with patch("asyncio.sleep", return_value=None):  # Skip actual sleep
                result = await labgrid_client.release_target_with_retry("test-target")
                assert result is True
                assert call_count == 3


class TestExecuteCommandWithAcquireRelease:
    """Tests for execute_command method with acquire/release flow."""

    @pytest.mark.asyncio
    async def test_execute_command_full_flow(self, labgrid_client):
        """Test command execution includes acquire and release."""
        with patch.object(
            labgrid_client, "acquire_target", return_value=True
        ) as mock_acquire:
            with patch.object(
                labgrid_client, "release_target_with_retry", return_value=True
            ) as mock_release:
                with patch.object(
                    labgrid_client,
                    "_execute_via_labgrid_client",
                    return_value="command output",
                ):
                    result, code = await labgrid_client.execute_command(
                        "test", "echo test"
                    )

                    mock_acquire.assert_called_once_with("test")
                    mock_release.assert_called_once_with("test")
                    assert result == "command output"
                    assert code == 0

    @pytest.mark.asyncio
    async def test_execute_command_release_on_error(self, labgrid_client):
        """Test that release is called even when command fails."""
        with patch.object(
            labgrid_client, "acquire_target", return_value=True
        ) as mock_acquire:
            with patch.object(
                labgrid_client, "release_target_with_retry", return_value=True
            ) as mock_release:
                with patch.object(
                    labgrid_client,
                    "_execute_via_labgrid_client",
                    side_effect=RuntimeError("Command failed"),
                ):
                    result, code = await labgrid_client.execute_command(
                        "test", "bad command"
                    )

                    # Acquire and release should both be called
                    mock_acquire.assert_called_once_with("test")
                    mock_release.assert_called_once_with("test")
                    assert "Command failed" in result or "Error" in result
                    assert code == 1

    @pytest.mark.asyncio
    async def test_execute_command_raises_acquired_by_other(self, labgrid_client):
        """Test that TargetAcquiredByOtherError is propagated."""
        with patch.object(
            labgrid_client,
            "acquire_target",
            side_effect=TargetAcquiredByOtherError("test", "other-user"),
        ):
            with pytest.raises(TargetAcquiredByOtherError) as exc:
                await labgrid_client.execute_command("test", "echo test")

            assert exc.value.acquired_by == "other-user"

    @pytest.mark.asyncio
    async def test_execute_command_not_connected(self, labgrid_client):
        """Test that error is returned when not connected."""
        labgrid_client._connected = False

        result, code = await labgrid_client.execute_command("test", "echo test")

        assert "Not connected" in result
        assert code == 1


class TestGetAcquiredBy:
    """Tests for _get_acquired_by helper method."""

    @pytest.mark.asyncio
    async def test_get_acquired_by_returns_owner(self, labgrid_client):
        """Test that acquired_by is returned from cache."""
        labgrid_client._resources_cache = {
            "test-target": {
                "NetworkSerialPort": {
                    "cls": "NetworkSerialPort",
                    "params": {},
                    "acquired": "some-user",
                    "avail": True,
                }
            }
        }

        with patch.object(labgrid_client, "_refresh_cache", return_value=None):
            result = await labgrid_client._get_acquired_by("test-target")
            assert result == "some-user"

    @pytest.mark.asyncio
    async def test_get_acquired_by_returns_none_when_not_acquired(self, labgrid_client):
        """Test that None is returned when target is not acquired."""
        labgrid_client._resources_cache = {
            "test-target": {
                "NetworkSerialPort": {
                    "cls": "NetworkSerialPort",
                    "params": {},
                    "acquired": None,
                    "avail": True,
                }
            }
        }

        with patch.object(labgrid_client, "_refresh_cache", return_value=None):
            result = await labgrid_client._get_acquired_by("test-target")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_acquired_by_returns_none_for_unknown_target(
        self, labgrid_client
    ):
        """Test that None is returned for unknown target."""
        labgrid_client._resources_cache = {}

        with patch.object(labgrid_client, "_refresh_cache", return_value=None):
            result = await labgrid_client._get_acquired_by("unknown-target")
            assert result is None


class TestParseAcquiredByFromError:
    """Tests for _parse_acquired_by_from_error helper method."""

    def test_parse_standard_error_message(self, labgrid_client):
        """Test parsing standard labgrid error message."""
        error = "place test-target is already acquired by other-user"
        result = labgrid_client._parse_acquired_by_from_error(error)
        assert result == "other-user"

    def test_parse_returns_unknown_on_failure(self, labgrid_client):
        """Test that 'unknown' is returned when parsing fails."""
        error = "some other error message"
        result = labgrid_client._parse_acquired_by_from_error(error)
        assert result == "unknown"
