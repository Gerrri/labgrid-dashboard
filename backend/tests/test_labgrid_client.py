"""
Tests for the LabgridClient.

These tests focus on the mock mode behavior since the actual WAMP connection
requires a running Labgrid Coordinator.
"""

import pytest
import pytest_asyncio

from app.services.labgrid_client import LabgridClient


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

    @pytest.mark.asyncio
    async def test_connect_enables_mock_mode_when_coordinator_unavailable(
        self, client: LabgridClient
    ):
        """Test that connect falls back to mock mode when coordinator is unavailable."""
        result = await client.connect()

        assert result is True
        assert client.connected is True
        assert client.mock_mode is True

    @pytest.mark.asyncio
    async def test_disconnect(self, client: LabgridClient):
        """Test that disconnect properly cleans up the client state."""
        await client.connect()
        await client.disconnect()

        assert client.connected is False
        assert client.mock_mode is False

    @pytest.mark.asyncio
    async def test_get_places_in_mock_mode(self, client: LabgridClient):
        """Test that get_places returns mock data in mock mode."""
        await client.connect()
        assert client.mock_mode is True

        places = await client.get_places()

        assert len(places) == 3
        assert places[0].name == "dut-1"
        assert places[1].name == "dut-2"
        assert places[2].name == "dut-3"

    @pytest.mark.asyncio
    async def test_get_place_info_in_mock_mode(self, client: LabgridClient):
        """Test that get_place_info returns correct mock target."""
        await client.connect()

        target = await client.get_place_info("dut-1")

        assert target is not None
        assert target.name == "dut-1"
        assert target.status == "available"
        assert target.ip_address == "192.168.1.101"

    @pytest.mark.asyncio
    async def test_get_place_info_not_found_in_mock_mode(self, client: LabgridClient):
        """Test that get_place_info returns None for non-existent target."""
        await client.connect()

        target = await client.get_place_info("non-existent")

        assert target is None

    @pytest.mark.asyncio
    async def test_mock_places_have_different_statuses(self, client: LabgridClient):
        """Test that mock places have different statuses for testing."""
        await client.connect()

        places = await client.get_places()
        statuses = [p.status for p in places]

        assert "available" in statuses
        assert "acquired" in statuses
        assert "offline" in statuses

    @pytest.mark.asyncio
    async def test_mock_acquired_target_has_acquired_by(self, client: LabgridClient):
        """Test that acquired mock target has acquired_by field."""
        await client.connect()

        target = await client.get_place_info("dut-2")

        assert target is not None
        assert target.status == "acquired"
        assert target.acquired_by is not None
        assert "developer@host" in target.acquired_by

    @pytest.mark.asyncio
    async def test_subscribe_updates_in_mock_mode(self, client: LabgridClient):
        """Test that subscribe_updates works in mock mode."""
        await client.connect()

        callback_called = False

        def callback(name, data):
            nonlocal callback_called
            callback_called = True

        result = await client.subscribe_updates(callback)

        # In mock mode, subscription should succeed but not actually call the callback
        assert result is True

    @pytest.mark.asyncio
    async def test_mock_target_resources(self, client: LabgridClient):
        """Test that mock targets have resources."""
        await client.connect()

        target = await client.get_place_info("dut-1")

        assert target is not None
        assert len(target.resources) > 0
        resource_types = [r.type for r in target.resources]
        assert "NetworkSerialPort" in resource_types

    def test_initial_state(self, client: LabgridClient):
        """Test initial client state before connection."""
        assert client.connected is False
        assert client.mock_mode is False
