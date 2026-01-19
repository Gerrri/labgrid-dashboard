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
async def test_root_endpoint(client: AsyncClient):
    """Test that root endpoint returns API information."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Labgrid Dashboard API" in data["message"]
    assert "docs" in data
    assert "health" in data
    assert "targets" in data
