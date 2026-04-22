from decimal import Decimal

from src.utils.currency import parse_price_to_decimal


def test_parse_price_ptbr() -> None:
    assert parse_price_to_decimal("R$ 1.234,56") == Decimal("1234.56")


def test_parse_price_integer() -> None:
    assert parse_price_to_decimal("R$ 899") == Decimal("899")


def test_parse_price_nbsp() -> None:
    assert parse_price_to_decimal("R$\xa0134") == Decimal("134")


def test_parse_price_invalid() -> None:
    assert parse_price_to_decimal("Indisponivel") is None
