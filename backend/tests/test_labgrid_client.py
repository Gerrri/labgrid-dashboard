"""
Tests for the LabgridClient.

These tests verify the client behavior using pytest-mock for mocking
the labgrid library dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from app.services.labgrid_client import LabgridClient, LabgridConnectionError


class TestLabgridClient:
    """Test cases for LabgridClient."""

    @pytest.fixture
    def client(self) -> LabgridClient:
        """Create a LabgridClient instance."""
        return LabgridClient(
            url="ws://localhost:20408/ws",
            realm="realm1",
            timeout=5,
        )

    def test_initial_state(self, client: LabgridClient):
        """Test initial client state before connection."""
        assert client.connected is False

    def test_url_cleanup(self):
        """Test that URL is properly cleaned from ws:// prefix."""
        client = LabgridClient(url="ws://coordinator:20408/ws")
        # URL should have ws:// and /ws removed
        assert client._url == "coordinator:20408"

    @pytest.mark.asyncio
    async def test_connect_raises_error_when_labgrid_not_available(
        self, client: LabgridClient
    ):
        """Test that connect raises LabgridConnectionError when labgrid is not available."""
        with patch.dict("sys.modules", {"labgrid.remote.client": None}):
            with pytest.raises(LabgridConnectionError):
                await client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self, client: LabgridClient):
        """Test that disconnect properly cleans up the client state."""
        # Manually set connected state for testing
        client._connected = True
        client._resources_cache = {"test": {}}
        client._places_cache = {"test": {}}

        await client.disconnect()

        assert client.connected is False
        assert client._resources_cache == {}
        assert client._places_cache == {}

    @pytest.mark.asyncio
    async def test_get_places_returns_empty_when_not_connected(
        self, client: LabgridClient
    ):
        """Test that get_places returns empty list when not connected."""
        places = await client.get_places()
        assert places == []

    @pytest.mark.asyncio
    async def test_get_place_info_returns_none_when_not_connected(
        self, client: LabgridClient
    ):
        """Test that get_place_info returns None when not connected."""
        target = await client.get_place_info("dut-1")
        assert target is None

    @pytest.mark.asyncio
    async def test_subscribe_updates_returns_false_when_not_connected(
        self, client: LabgridClient
    ):
        """Test that subscribe_updates returns False when not connected."""

        def callback(name, data):
            pass

        result = await client.subscribe_updates(callback)
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_command_returns_error_when_not_connected(
        self, client: LabgridClient
    ):
        """Test that execute_command returns error when not connected."""
        output, exit_code = await client.execute_command("dut-1", "echo test")

        assert exit_code == 1
        assert "Not connected" in output

    def test_parse_serial_output_removes_prompts(self, client: LabgridClient):
        """Test that serial output parsing removes prompts correctly."""
        raw = "uptime -p\r\ndut-1:/# uptime -p\r\nup 1 hour, 45 minutes\r\ndut-1:/# "
        result = client._parse_serial_output(raw, "uptime -p")

        assert result == "up 1 hour, 45 minutes"

    def test_parse_serial_output_handles_empty_input(self, client: LabgridClient):
        """Test that serial output parsing handles empty input."""
        result = client._parse_serial_output("", "echo test")
        assert result == ""

    def test_parse_serial_output_removes_command_echo(self, client: LabgridClient):
        """Test that serial output parsing removes command echo."""
        raw = "echo hello\nhello\nroot@host:~# "
        result = client._parse_serial_output(raw, "echo hello")

        assert result == "hello"

    def test_resolve_hostname_to_ip(self, client: LabgridClient):
        """Test hostname resolution."""
        # localhost should resolve to 127.0.0.1
        ip = client._resolve_hostname_to_ip("localhost")
        assert ip == "127.0.0.1"

    def test_resolve_hostname_to_ip_returns_none_for_invalid(
        self, client: LabgridClient
    ):
        """Test that invalid hostname returns None."""
        ip = client._resolve_hostname_to_ip("this-host-does-not-exist-12345.invalid")
        assert ip is None


class TestLabgridClientWithMockedSession:
    """Test cases with mocked labgrid ClientSession."""

    def _create_mock_resource_entry(self, cls_name, params, acquired, avail):
        """Create a mock ResourceEntry object that mimics labgrid's structure."""
        mock_entry = MagicMock()
        mock_entry.cls = cls_name
        mock_entry.params = params
        mock_entry.acquired = acquired
        mock_entry.avail = avail
        mock_entry.data = {
            "cls": cls_name,
            "params": params,
            "acquired": acquired,
            "avail": avail,
        }
        return mock_entry

    @pytest_asyncio.fixture
    async def connected_client(self):
        """Create a connected client with mocked session."""
        client = LabgridClient(url="localhost:20408")

        # Mock the session
        mock_session = MagicMock()
        mock_session.resources = {}
        mock_session.places = {}
        mock_session.start = AsyncMock()
        mock_session.close = AsyncMock()

        client._session = mock_session
        client._connected = True

        yield client

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_places_with_resources(self, connected_client: LabgridClient):
        """Test getting places when resources are available."""
        # Set up mock resources in the session's resources dict
        # Structure: session.resources[exporter][group][res_type] = ResourceEntry
        mock_entry = self._create_mock_resource_entry(
            cls_name="NetworkSerialPort",
            params={"host": "192.168.1.100", "port": 5000},
            acquired=None,
            avail=True,
        )
        connected_client._session.resources = {
            "exporter-1": {"default": {"NetworkSerialPort": mock_entry}}
        }

        places = await connected_client.get_places()

        assert len(places) == 1
        assert places[0].name == "exporter-1"
        assert places[0].status == "available"

    @pytest.mark.asyncio
    async def test_get_places_with_acquired_resource(
        self, connected_client: LabgridClient
    ):
        """Test getting places with acquired resources."""
        mock_entry = self._create_mock_resource_entry(
            cls_name="NetworkSerialPort",
            params={"host": "192.168.1.100", "port": 5000},
            acquired="user@host",
            avail=True,
        )
        connected_client._session.resources = {
            "exporter-1": {"default": {"NetworkSerialPort": mock_entry}}
        }

        places = await connected_client.get_places()

        assert len(places) == 1
        assert places[0].status == "acquired"
        assert places[0].acquired_by == "user@host"

    @pytest.mark.asyncio
    async def test_get_places_with_offline_resource(
        self, connected_client: LabgridClient
    ):
        """Test getting places with offline resources."""
        # For offline resources, params might be empty and avail=False
        mock_entry = self._create_mock_resource_entry(
            cls_name="NetworkSerialPort",
            params={},
            acquired=None,
            avail=False,
        )
        connected_client._session.resources = {
            "exporter-1": {"default": {"NetworkSerialPort": mock_entry}}
        }

        places = await connected_client.get_places()

        assert len(places) == 1
        assert places[0].status == "offline"

    @pytest.mark.asyncio
    async def test_subscribe_updates_returns_true_when_connected(
        self, connected_client: LabgridClient
    ):
        """Test that subscribe_updates returns True when connected."""

        def callback(name, data):
            pass

        result = await connected_client.subscribe_updates(callback)
        assert result is True
