"""Factory for selecting the active structured SERP backend."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from config.settings import Settings
from enrichment.serp_price_provider import SerpAPIClient, SerpClient


@dataclass(frozen=True)
class NullSerpClient:
    """SerpClient that returns no live candidates."""

    backend_name: str = "none"

    def search(self, query: str) -> list[dict[str, Any]]:
        return []


def build_serp_client(settings: Settings) -> SerpClient:
    """Pick SerpAPI, Playwright fallback, or null backend."""
    if settings.serp_provider_enabled and os.getenv(settings.serp_api_key_env):
        return SerpAPIClient(settings)
    if settings.playwright_fallback_enabled and os.getenv("BULK_INTEL_PLAYWRIGHT_FALLBACK"):
        from enrichment.playwright_serp_client import PlaywrightSerpClient

        return PlaywrightSerpClient(settings)
    return NullSerpClient()
