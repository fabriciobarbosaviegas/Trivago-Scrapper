from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

from bs4 import BeautifulSoup, Tag

from src.models import HotelItem
from src.utils.currency import parse_price_to_decimal

PRICE_TEXT_RE = re.compile(r"R\$\s*[\d\.,]+")
KNOWN_INDEXERS = [
    "MaxMilhas",
    "Trip.com",
    "Booking.com",
    "Hoteis.com",
    "Decolar",
    "Expedia",
    "Agoda",
    "Kayak",
    "eDreams",
    "Traveloka",
    "123Milhas",
]


@dataclass(frozen=True)
class HotelSeed:
    nome: str
    local: str
    preco_trivago: Decimal
    url: str | None = None


def _clean_text(value: str | None) -> str:
    raw = (value or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", raw).strip()


def _first_text(container: Tag, selectors: list[str]) -> str:
    for selector in selectors:
        node = container.select_one(selector)
        if node:
            text = _clean_text(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _extract_indexer_prices(
    flat_text: str,
    allow_trivago_fallback: bool = True,
) -> dict[str, Decimal]:
    prices: dict[str, Decimal] = OrderedDict()
    text = _clean_text(flat_text)

    for indexer in KNOWN_INDEXERS:
        pattern = re.compile(
            rf"{re.escape(indexer)}[^\n\r]{{0,80}}?({PRICE_TEXT_RE.pattern})",
            flags=re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            price = parse_price_to_decimal(match.group(1))
            if price is not None:
                prices[indexer] = price

    if allow_trivago_fallback and not prices:
        all_prices = PRICE_TEXT_RE.findall(text)
        if all_prices:
            first_price = parse_price_to_decimal(all_prices[0])
            if first_price is not None:
                prices["Trivago"] = first_price

    return prices


def _extract_hotel_seeds_from_json_ld(soup: BeautifulSoup, limit: int) -> list[HotelSeed]:
    seeds: list[HotelSeed] = []
    seen: set[tuple[str, str]] = set()

    scripts = soup.select('script[type="application/ld+json"]')
    for script in scripts:
        raw_json = script.string or script.get_text(strip=True)
        if not raw_json:
            continue

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") != "ItemList":
                continue

            item_list = node.get("itemListElement")
            if not isinstance(item_list, list):
                continue

            for list_item in item_list:
                if not isinstance(list_item, dict):
                    continue
                item = list_item.get("item")
                if not isinstance(item, dict):
                    continue

                name = _clean_text(item.get("name"))
                location = _clean_text(item.get("address")) or "Local nao informado"
                raw_price = _clean_text(item.get("priceRange"))
                hotel_url = _clean_text(item.get("url")) or None
                price = parse_price_to_decimal(raw_price)

                if not name or price is None:
                    continue

                key = (name.lower(), location.lower())
                if key in seen:
                    continue

                seen.add(key)
                seeds.append(
                    HotelSeed(
                        nome=name,
                        local=location,
                        preco_trivago=price,
                        url=hotel_url,
                    )
                )

                if len(seeds) >= limit:
                    return seeds

    return seeds


def parse_hotel_seeds_from_html(html: str, limit: int = 20) -> tuple[list[HotelSeed], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []
    seeds = _extract_hotel_seeds_from_json_ld(soup, limit=limit)

    if not seeds:
        warnings.append("Nao foi possivel extrair seeds de hotel via JSON-LD.")

    return seeds, warnings


def parse_indexer_prices_from_detail_html(html: str) -> dict[str, Decimal]:
    soup = BeautifulSoup(html, "html.parser")
    visible_text = _clean_text(soup.get_text(" ", strip=True))
    prices = _extract_indexer_prices(visible_text, allow_trivago_fallback=False)

    # Fallback: alguns parceiros aparecem apenas em blocos JSON embutidos.
    script_text = _clean_text(" ".join(script.get_text(" ", strip=True) for script in soup.find_all("script")))
    script_prices = _extract_indexer_prices(script_text, allow_trivago_fallback=False)
    prices.update(script_prices)
    return prices


def parse_hotels_from_html(html: str, limit: int = 20) -> tuple[list[HotelItem], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []

    seeds = _extract_hotel_seeds_from_json_ld(soup, limit=limit)
    if seeds:
        return [
            HotelItem(
                nomeDoHotel=seed.nome,
                local=seed.local,
                precos={"Trivago": seed.preco_trivago},
            )
            for seed in seeds
        ], warnings

    containers = soup.select(
        '[data-testid*="accommodation" i], [data-testid*="item" i], article, li'
    )
    if not containers:
        warnings.append("Nao foi possivel detectar containers de hotel no HTML.")

    hotels: list[HotelItem] = []
    seen: set[tuple[str, str]] = set()

    for container in containers:
        name = _first_text(
            container,
            [
                '[data-testid*="name" i]',
                "h2",
                "h3",
                '[itemprop="name"]',
                "a[title]",
            ],
        )
        location = _first_text(
            container,
            [
                '[data-testid*="location" i]',
                '[class*="location" i]',
                '[class*="address" i]',
                '[itemprop="address"]',
            ],
        )

        full_text = _clean_text(container.get_text(" ", strip=True))
        prices = _extract_indexer_prices(full_text)

        if not name or not prices:
            continue

        key = (name.lower(), location.lower())
        if key in seen:
            continue

        seen.add(key)
        hotels.append(
            HotelItem(
                nomeDoHotel=name,
                local=location or "Local nao informado",
                precos=prices,
            )
        )

        if len(hotels) >= limit:
            break

    if not hotels:
        warnings.append("Nenhum hotel com preco foi extraido da pagina atual.")

    return hotels, warnings
