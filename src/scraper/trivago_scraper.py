from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote_plus

import httpx

from src.config import Settings
from src.models import HotelItem, HotelSearchRequest
from src.scraper.parser import (
    HotelSeed,
    parse_hotel_seeds_from_html,
    parse_hotels_from_html,
    parse_indexer_prices_from_detail_html,
)


@dataclass
class ScraperResult:
    hotels: list[HotelItem]
    warnings: list[str]


class TrivagoScraper:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _build_search_url(self, payload: HotelSearchRequest) -> str:
        destination = quote_plus(payload.destino)
        print(
            f"{self.settings.trivago_base_url}/"
            f"?aDateRange[arr]={payload.dataCheckin.isoformat()}"
            f"&aDateRange[dep]={payload.dataCheckout.isoformat()}"
            f"&aPriceRange[from]=0&aPriceRange[to]=0"
            f"&iRoomType=7&iPathId=0&iGeoDistanceLimit=20000"
            f"&iOffset=0&iIncludeAll=0"
            f"&sQuery={destination}"
            f"&aRooms[0][adults]={payload.adultos}"
            f"&aRooms[0][children]={payload.criancas}"
        )
        return (
            f"{self.settings.trivago_base_url}/"
            f"?aDateRange[arr]={payload.dataCheckin.isoformat()}"
            f"&aDateRange[dep]={payload.dataCheckout.isoformat()}"
            f"&aPriceRange[from]=0&aPriceRange[to]=0"
            f"&iRoomType=7&iPathId=0&iGeoDistanceLimit=20000"
            f"&iOffset=0&iIncludeAll=0"
            f"&sQuery={destination}"
            f"&aRooms[0][adults]={payload.adultos}"
            f"&aRooms[0][children]={payload.criancas}"
        )

    def _default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def _build_hotels_from_seeds(
        self,
        client: httpx.AsyncClient,
        seeds: list[HotelSeed],
        headers: dict[str, str],
    ) -> tuple[list[HotelItem], list[str]]:
        warnings: list[str] = []
        hotels: list[HotelItem] = []

        if not self.settings.enrich_indexers_enabled:
            for seed in seeds:
                hotels.append(
                    HotelItem(
                        nomeDoHotel=seed.nome,
                        local=seed.local,
                        precos={"Trivago": seed.preco_trivago},
                    )
                )
            return hotels, warnings

        seeds_to_enrich = seeds[: max(1, self.settings.max_enrich_hotels)]
        skipped_count = len(seeds) - len(seeds_to_enrich)
        if skipped_count > 0:
            warnings.append(
                f"Enriquecimento limitado aos primeiros {len(seeds_to_enrich)} hoteis."
            )

        semaphore = asyncio.Semaphore(4)
        playwright_semaphore = asyncio.Semaphore(1)

        max_playwright = max(0, self.settings.max_playwright_enrich_hotels)

        async def enrich(
            seed: HotelSeed,
            allow_playwright_dynamic: bool,
        ) -> tuple[HotelSeed, dict[str, dict[str, Decimal] | str | None]]:

            partner_prices: dict[str, Decimal] = {}
            issue: str | None = None

            if not seed.url:
                issue = f"Hotel {seed.nome} sem URL de detalhe para enriquecer indexadores."
                return seed, {"prices": partner_prices, "warning": issue}

            try:
                async with semaphore:
                    response = await client.get(seed.url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                partner_prices = parse_indexer_prices_from_detail_html(response.text)
                if not partner_prices and allow_playwright_dynamic:
                    async with playwright_semaphore:
                        dynamic_prices, dynamic_warning = await self._enrich_seed_with_playwright(seed)
                    partner_prices.update(dynamic_prices)
                    if not partner_prices:
                        issue = dynamic_warning
                elif not partner_prices:
                    issue = f"Sem indexadores adicionais na pagina de detalhe de {seed.nome}."
            except (httpx.RequestError, httpx.HTTPStatusError):
                issue = f"Falha ao enriquecer indexadores para {seed.nome}."

            return seed, {"prices": partner_prices, "warning": issue}

        enriched = await asyncio.gather(
            *(
                enrich(
                    seed,
                    allow_playwright_dynamic=(
                        self.settings.playwright_dynamic_enrichment_enabled and index < max_playwright
                    ),
                )
                for index, seed in enumerate(seeds_to_enrich)
            )
        )
        for seed, result in enriched:
            merged_prices: dict[str, Decimal] = {"Trivago": seed.preco_trivago}
            partner_prices = result["prices"]
            if isinstance(partner_prices, dict):
                merged_prices.update(partner_prices)
            hotels.append(
                HotelItem(
                    nomeDoHotel=seed.nome,
                    local=seed.local,
                    precos=merged_prices,
                )
            )
            warning = result["warning"]
            if warning:
                warnings.append(str(warning))

        # Hoteis nao enriquecidos sao retornados com preco campeao para manter cobertura.
        for seed in seeds[len(seeds_to_enrich) :]:
            hotels.append(
                HotelItem(
                    nomeDoHotel=seed.nome,
                    local=seed.local,
                    precos={"Trivago": seed.preco_trivago},
                )
            )

        return hotels, warnings

    async def _enrich_seed_with_playwright(self, seed: HotelSeed) -> tuple[dict[str, Decimal], str | None]:
        if not seed.url:
            return {}, f"Hotel {seed.nome} sem URL para enriquecimento dinamico."

        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            return {}, "Playwright nao instalado no ambiente."

        click_selectors = [
            'button[data-testid="static-main-champion"]',
            'button:has-text("Ver preços")',
            'button:has-text("Ver os preços")',
            'a:has-text("Ver preços")',
            'a:has-text("Ver os preços")',
        ]

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                    ),
                    locale="pt-BR",
                )
                page = await context.new_page()
                await page.goto(
                    seed.url,
                    wait_until="domcontentloaded",
                    timeout=self.settings.playwright_timeout_ms,
                )
                await page.wait_for_timeout(1200)

                clicked = False
                for selector in click_selectors:
                    locator = page.locator(selector)
                    if await locator.count() == 0:
                        continue
                    try:
                        await locator.first.click(timeout=3000)
                        clicked = True
                        break
                    except Exception:
                        continue

                if clicked:
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass

                await page.wait_for_timeout(1800)
                html = await page.content()
                await context.close()
                await browser.close()

                prices = parse_indexer_prices_from_detail_html(html)
                if prices:
                    return prices, None
                return {}, f"Sem indexadores adicionais na pagina dinamica de {seed.nome}."

        except PlaywrightTimeoutError:
            return {}, f"Timeout no enriquecimento dinamico de {seed.nome}."
        except Exception as exc:
            return {}, f"Erro no enriquecimento dinamico de {seed.nome}: {exc.__class__.__name__}."

    async def search_hotels(self, payload: HotelSearchRequest) -> ScraperResult:
        url = self._build_search_url(payload)
        warnings: list[str] = []

        hotels, parse_warnings = await self._fetch_via_http(url, payload.limite_resultados)
        warnings.extend(parse_warnings)

        if hotels:
            return ScraperResult(hotels=hotels, warnings=warnings)

        if self.settings.use_playwright_fallback:
            fallback_hotels, fallback_warnings = await self._fetch_via_playwright(
                url,
                payload.limite_resultados,
            )
            warnings.extend(fallback_warnings)
            return ScraperResult(hotels=fallback_hotels, warnings=warnings)

        warnings.append("Fallback via Playwright desativado.")
        return ScraperResult(hotels=[], warnings=warnings)

    async def _fetch_via_http(self, url: str, limit: int) -> tuple[list[HotelItem], list[str]]:
        headers = self._default_headers()

        last_warning = ""
        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                    response = await client.get(url, headers=headers, follow_redirects=True)

                    if response.status_code in {403, 429}:
                        return [], [
                            f"Trivago retornou status {response.status_code} na tentativa HTTP."
                        ]

                    response.raise_for_status()
                    seeds, seed_warnings = parse_hotel_seeds_from_html(response.text, limit=limit)
                    if seeds:
                        hotels, enrich_warnings = await self._build_hotels_from_seeds(
                            client,
                            seeds,
                            headers,
                        )
                        return hotels, seed_warnings + enrich_warnings

                    hotels, warnings = parse_hotels_from_html(response.text, limit=limit)
                    return hotels, warnings

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_warning = f"Tentativa HTTP {attempt} falhou: {exc.__class__.__name__}."
                await asyncio.sleep(self.settings.retry_backoff_seconds * attempt)

        warnings = [last_warning] if last_warning else ["Falha desconhecida na coleta HTTP."]
        return [], warnings

    async def _fetch_via_playwright(self, url: str, limit: int) -> tuple[list[HotelItem], list[str]]:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            return [], ["Playwright nao instalado no ambiente."]

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                    ),
                    locale="pt-BR",
                )
                page = await context.new_page()
                await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=self.settings.playwright_timeout_ms,
                )
                await page.wait_for_timeout(1800)
                html = await page.content()
                await context.close()
                await browser.close()

                hotels, warnings = parse_hotels_from_html(html, limit=limit)
                if not hotels:
                    warnings.append("Fallback Playwright executou, mas nao encontrou hoteis.")
                return hotels, warnings

        except PlaywrightTimeoutError:
            return [], ["Timeout no fallback Playwright."]
        except Exception as exc:
            return [], [f"Erro inesperado no fallback Playwright: {exc.__class__.__name__}."]
