"""
Tests for the health check endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_healthy(client: AsyncClient):
    """Test that health check returns healthy status when connected."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["coordinator_connected"] is True
    assert data["service"] == "labgrid-dashboard-backend"


@pytest.mark.asyncio
async def test_readiness_check_returns_ready(client: AsyncClient):
    """Test that readiness returns ready when command path dependencies exist."""
    response = await client.get("/api/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["api_alive"] is True
    assert data["coordinator_connected"] is True
    assert data["updates_active"] is True
    assert data["command_path_ready"] is True
    assert data["service"] == "labgrid-dashboard-backend"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test that root endpoint returns API information."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Labgrid Dashboard API" in data["message"]
    assert "docs" in data
    assert "health" in data
    assert "readiness" in data
    assert "targets" in data
