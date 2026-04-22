from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Trivago Scraper API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    trivago_base_url: str = os.getenv("TRIVAGO_BASE_URL", "https://www.trivago.com.br")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12"))
    retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "2"))
    retry_backoff_seconds: float = float(os.getenv("RETRY_BACKOFF_SECONDS", "1.5"))
    use_playwright_fallback: bool = os.getenv("USE_PLAYWRIGHT_FALLBACK", "true").lower() == "true"
    playwright_timeout_ms: int = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "20000"))
    max_results_default: int = int(os.getenv("MAX_RESULTS_DEFAULT", "20"))
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    enrich_indexers_enabled: bool = os.getenv("ENRICH_INDEXERS_ENABLED", "true").lower() == "true"
    max_enrich_hotels: int = int(os.getenv("MAX_ENRICH_HOTELS", "10"))
    playwright_dynamic_enrichment_enabled: bool = (
        os.getenv("PLAYWRIGHT_DYNAMIC_ENRICHMENT_ENABLED", "true").lower() == "true"
    )
    max_playwright_enrich_hotels: int = int(os.getenv("MAX_PLAYWRIGHT_ENRICH_HOTELS", "3"))


def get_settings() -> Settings:
    return Settings()
