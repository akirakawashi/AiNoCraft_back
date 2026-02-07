from fastapi import APIRouter

from backend.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Check the health of the API.

    Returns:
        HealthResponse: The status of the API.
    """
    return HealthResponse(status="ok")
