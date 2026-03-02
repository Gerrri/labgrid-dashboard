"""
Health check endpoint for the Labgrid Dashboard API.
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.services.labgrid_client import LabgridClient

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    coordinator_connected: bool
    service: str = "labgrid-dashboard-backend"


class ReadinessResponse(BaseModel):
    """Readiness check response model."""

    status: str
    api_alive: bool = True
    coordinator_connected: bool
    updates_active: bool
    command_path_ready: bool
    service: str = "labgrid-dashboard-backend"


# Global labgrid client instance (set during app startup)
_labgrid_client: LabgridClient | None = None


def set_labgrid_client(client: LabgridClient) -> None:
    """Set the global Labgrid client instance.

    Args:
        client: The LabgridClient instance to use.
    """
    global _labgrid_client
    _labgrid_client = client


def get_labgrid_client() -> LabgridClient | None:
    """Get the global Labgrid client instance.

    Returns:
        The LabgridClient instance, or None if not initialized.
    """
    return _labgrid_client


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns the current health status of the API including
    the connection status to the Labgrid Coordinator.

    Returns:
        HealthResponse with status information.
    """
    client = get_labgrid_client()

    if client is None:
        return HealthResponse(
            status="degraded",
            coordinator_connected=False,
        )

    return HealthResponse(
        status="healthy" if client.connected else "degraded",
        coordinator_connected=client.connected,
    )


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness_check(response: Response) -> ReadinessResponse:
    """Readiness endpoint for deployment orchestration."""
    client = get_labgrid_client()

    if client is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready",
            coordinator_connected=False,
            updates_active=False,
            command_path_ready=False,
        )

    if not client.command_path_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if client.command_path_ready else "not_ready",
        coordinator_connected=client.connected,
        updates_active=client.updates_active,
        command_path_ready=client.command_path_ready,
    )
