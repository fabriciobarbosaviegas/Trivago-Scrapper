from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.models import HotelSearchRequest, SearchResponse

router = APIRouter(prefix="/api/v1/hoteis", tags=["hoteis"])


@router.post("/buscar", response_model=SearchResponse)
async def buscar_hoteis(payload: HotelSearchRequest, request: Request) -> SearchResponse:
    rate_limiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.check(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "mensagem": "Limite de requisicoes por minuto atingido.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    scraper = request.app.state.scraper
    result = await scraper.search_hotels(payload)

    if not result.hotels:
        raise HTTPException(
            status_code=503,
            detail={
                "mensagem": "Nao foi possivel coletar hoteis no Trivago neste momento.",
                "avisos": result.warnings,
            },
        )

    status = "partial" if result.warnings else "success"
    return SearchResponse(
        status=status,
        timestamp=SearchResponse.now(),
        quantidade_resultados=len(result.hotels),
        hoteis=result.hotels,
        avisos=result.warnings,
    )
