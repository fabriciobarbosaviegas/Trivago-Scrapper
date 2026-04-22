from decimal import Decimal
from pathlib import Path

from src.scraper.parser import (
    parse_hotel_seeds_from_html,
    parse_hotels_from_html,
    parse_indexer_prices_from_detail_html,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "html_samples" / "trivago_sample.html"
)
REAL_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "html_samples"
    / "trivago_real_recife_http.html"
)


def test_parse_hotels_from_snapshot() -> None:
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    hotels, warnings = parse_hotels_from_html(html, limit=10)

    assert len(hotels) == 2
    assert hotels[0].nomeDoHotel == "Hotel Atlante Plaza"
    assert hotels[0].local == "Boa Viagem, Recife"
    assert hotels[0].precos["MaxMilhas"] == Decimal("1138.48")
    assert hotels[0].precos["Trip.com"] == Decimal("1799.00")
    assert warnings == []


def test_parse_hotels_from_real_snapshot_uses_currency_prices() -> None:
    html = REAL_FIXTURE_PATH.read_text(encoding="utf-8")
    hotels, warnings = parse_hotels_from_html(html, limit=5)

    assert len(hotels) == 5
    assert hotels[0].nomeDoHotel == "Rede Andrade Vela Branca"
    assert hotels[0].local.startswith("8.2 km")
    assert hotels[0].precos["Trivago"] == Decimal("134")
    assert warnings == []


def test_parse_hotel_seeds_from_real_snapshot_extracts_url() -> None:
        html = REAL_FIXTURE_PATH.read_text(encoding="utf-8")
        seeds, warnings = parse_hotel_seeds_from_html(html, limit=2)

        assert len(seeds) == 2
        assert seeds[0].nome == "Rede Andrade Vela Branca"
        assert seeds[0].url is not None
        assert seeds[0].url.startswith("https://www.trivago.com.br/")
        assert seeds[0].preco_trivago == Decimal("134")
        assert warnings == []


def test_parse_indexer_prices_from_detail_html() -> None:
        html = """
        <html><body>
            <div>Booking.com R$ 1.250,40</div>
            <div>Trip.com R$ 1.199,00</div>
            <div>8.2 km ate Centro</div>
            <script>var offers = [{\"site\":\"Expedia\",\"price\":\"R$ 1.310,00\"}]</script>
        </body></html>
        """

        prices = parse_indexer_prices_from_detail_html(html)
        assert prices["Booking.com"] == Decimal("1250.40")
        assert prices["Trip.com"] == Decimal("1199.00")
        assert prices["Expedia"] == Decimal("1310.00")
