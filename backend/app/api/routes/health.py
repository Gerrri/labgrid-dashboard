"""
Health check endpoint for the Labgrid Dashboard API.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.labgrid_client import LabgridClient

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    coordinator_connected: bool
    mock_mode: bool = False
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
            mock_mode=False,
        )

    return HealthResponse(
        status="healthy" if client.connected else "degraded",
        coordinator_connected=client.connected,
        mock_mode=client.mock_mode,
    )
