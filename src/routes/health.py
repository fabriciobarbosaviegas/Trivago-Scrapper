from __future__ import annotations

from fastapi import APIRouter

from src.models import HealthResponse, SearchResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    return HealthResponse(
        status="ok",
        scraper_available=True,
        timestamp=SearchResponse.now(),
    )
