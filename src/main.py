from __future__ import annotations

from fastapi import FastAPI

from src.config import get_settings
from src.routes.health import router as health_router
from src.routes.hotels import router as hotels_router
from src.scraper.trivago_scraper import TrivagoScraper
from src.utils.rate_limit import InMemoryRateLimiter

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API FastAPI para consultar hoteis e precos indexados no Trivago. "
        "Retorna nomeDoHotel, local e precos por indexador."
    ),
)


@app.on_event("startup")
async def startup_event() -> None:
    app.state.scraper = TrivagoScraper(settings)
    app.state.rate_limiter = InMemoryRateLimiter(
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )


app.include_router(health_router)
app.include_router(hotels_router)
