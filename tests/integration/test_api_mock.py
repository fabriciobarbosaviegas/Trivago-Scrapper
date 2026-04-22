from decimal import Decimal

from fastapi.testclient import TestClient

from src.main import app
from src.models import HotelItem
from src.scraper.trivago_scraper import ScraperResult


class FakeScraper:
    async def search_hotels(self, payload):
        _ = payload
        return ScraperResult(
            hotels=[
                HotelItem(
                    nomeDoHotel="Hotel Mock Recife",
                    local="Recife, PE",
                    precos={"MaxMilhas": Decimal("1138.48"), "Trip.com": Decimal("1799")},
                )
            ],
            warnings=[],
        )


class FakeRateLimiter:
    def check(self, key: str) -> tuple[bool, int]:
        _ = key
        return True, 0


def test_buscar_hoteis_com_mock() -> None:
    with TestClient(app) as client:
        app.state.scraper = FakeScraper()
        app.state.rate_limiter = FakeRateLimiter()

        response = client.post(
            "/api/v1/hoteis/buscar",
            json={
                "destino": "Recife",
                "dataCheckin": "2026-05-10",
                "dataCheckout": "2026-05-12",
                "adultos": 2,
                "criancas": 0,
                "limite_resultados": 10,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quantidade_resultados"] == 1
    assert payload["hoteis"][0]["nomeDoHotel"] == "Hotel Mock Recife"
    assert payload["hoteis"][0]["precos"]["MaxMilhas"] == 1138.48
