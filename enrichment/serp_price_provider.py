"""Structured SERP Amazon price provider.

This module never scrapes Amazon directly and never parses raw Google HTML.
Production lookups must use a structured SERP backend such as SerpAPI,
SearchAPI, or Serper. The concrete client enforces a token-bucket rate limit,
uses retries only for transient failures, and caches accepted Amazon listing
prices by a hash of normalized title plus backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import statistics
import time
from typing import Any, Callable, Optional, Protocol

import pandas as pd
import requests

from config.settings import Settings, get_settings
from enrichment.serp_cache import SerpCache, cache_key
from intelligence.homogeneity import normalize_for_clustering
from intelligence.matching import compute_match_score


class ConfigError(RuntimeError):
    """Raised when a SERP provider is misconfigured."""


class SerpClient(Protocol):
    """Pluggable structured SERP backend."""

    backend_name: str

    def search(self, query: str) -> list[dict[str, Any]]:
        """Return normalized organic result dictionaries."""
        ...


class TokenBucketRateLimiter:
    """Single-token bucket limiter suitable for sequential provider calls."""

    def __init__(
        self,
        rate_per_sec: float,
        time_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.rate_per_sec = max(float(rate_per_sec), 0.0001)
        self._time_fn = time_fn or time.monotonic
        self._sleep_fn = sleep_fn or time.sleep
        self._next_allowed = self._time_fn()

    def acquire(self) -> None:
        now = self._time_fn()
        if now < self._next_allowed:
            wait = self._next_allowed - now
            self._sleep_fn(wait)
            now = self._time_fn()
        self._next_allowed = max(now, self._next_allowed) + (1.0 / self.rate_per_sec)


@dataclass
class SerpAPIClient:
    """Concrete structured SERP client using SerpAPI-style JSON responses."""

    settings: Settings
    session: requests.Session = field(default_factory=requests.Session)
    rate_limiter: TokenBucketRateLimiter | None = None
    backend_name: str = "serpapi"

    def __post_init__(self) -> None:
        api_key = os.getenv(self.settings.serp_api_key_env)
        if not api_key:
            raise ConfigError(f"Missing SERP API key env var: {self.settings.serp_api_key_env}")
        self._api_key = api_key
        if self.rate_limiter is None:
            self.rate_limiter = TokenBucketRateLimiter(self.settings.serp_rate_limit_per_sec)

    def search(self, query: str) -> list[dict[str, Any]]:
        assert self.rate_limiter is not None
        self.rate_limiter.acquire()

        last_error: Exception | None = None
        for attempt in range(self.settings.serp_max_retries):
            try:
                response = self.session.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google",
                        "q": query,
                        "api_key": self._api_key,
                        "num": self.settings.serp_results_per_query,
                        "gl": "in",
                    },
                    timeout=self.settings.serp_timeout_s,
                )
                if 400 <= response.status_code < 500:
                    raise ConfigError(f"SERP backend returned HTTP {response.status_code}")
                if response.status_code >= 500:
                    raise requests.HTTPError(f"SERP backend returned HTTP {response.status_code}")
                response.raise_for_status()
                return _normalize_serp_results(response.json(), self.settings.serp_results_per_query)
            except ConfigError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == self.settings.serp_max_retries - 1:
                    break
                time.sleep(1.5 ** attempt)
        raise RuntimeError(f"SERP request failed after retries: {last_error}")


@dataclass
class SerpAmazonPriceProvider:
    """PriceProvider that fetches Amazon prices through structured SERP."""

    settings: Settings = field(default_factory=get_settings)
    serp_client: SerpClient | None = None
    cache: SerpCache | None = None
    name: str = "serp_amazon"

    def __post_init__(self) -> None:
        if self.serp_client is None:
            from enrichment.serp_backend_factory import build_serp_client

            self.serp_client = build_serp_client(self.settings)
        if self.cache is None:
            self.cache = SerpCache(
                self.settings.serp_cache_path,
                ttl_hours=self.settings.serp_cache_ttl_hours,
            )

    def with_client(self, serp_client: SerpClient) -> "SerpAmazonPriceProvider":
        """Return a provider clone using the same settings/cache and a new client."""
        return SerpAmazonPriceProvider(
            settings=self.settings,
            serp_client=serp_client,
            cache=self.cache,
            name=self.name,
        )

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None, float]:
        title = str(row.get("product_name_clean") or row.get("product_name") or "").strip()
        if not title:
            return (None, None, 0.0)

        assert self.serp_client is not None
        assert self.cache is not None

        normalized_title = normalize_for_clustering(title, self.settings)
        key = cache_key(normalized_title, self.serp_client.backend_name)
        cached = self.cache.get(key)
        if cached is not None:
            price = cached.get("amazon_price")
            confidence = float(cached.get("match_confidence") or 0.0)
            return (float(price), None, confidence) if price is not None else (None, None, 0.0)

        query = build_search_query(row)
        candidates = self.serp_client.search(query)
        selected = self._select_candidates(row, candidates)
        if not selected:
            self.cache.set(
                key,
                {
                    "amazon_price": None,
                    "match_confidence": 0.0,
                    "search_signature": normalized_title,
                    "brand": str(row.get("brand") or ""),
                    "matched_titles": [],
                    "matched_urls": [],
                },
            )
            return (None, None, 0.0)

        prices = [item["price"] for item in selected]
        confidence = max(item["score"] for item in selected)
        price = float(statistics.median(prices))
        self.cache.set(
            key,
            {
                "amazon_price": price,
                "match_confidence": confidence,
                "search_signature": normalized_title,
                "brand": str(row.get("brand") or ""),
                "matched_titles": [item["title"] for item in selected],
                "matched_urls": [item.get("url", "") for item in selected],
            },
        )
        return (price, None, confidence)

    def _select_candidates(self, row: pd.Series, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        weak: list[dict[str, Any]] = []

        for candidate in candidates[: self.settings.serp_results_per_query]:
            title = str(candidate.get("title") or "")
            if "amazon.in" not in str(candidate.get("url") or "").lower():
                continue
            price = candidate.get("price")
            if price is None:
                price = parse_price(" ".join(str(candidate.get(k) or "") for k in ("title", "snippet")))
            if price is None:
                continue
            scoring_candidate = dict(candidate)
            if not scoring_candidate.get("brand"):
                scoring_candidate["brand"] = _infer_brand_from_title(title)
            result = compute_match_score(row, scoring_candidate, self.settings)
            enriched = {
                "title": title,
                "url": str(candidate.get("url") or ""),
                "price": float(price),
                "score": result.score,
                "decision": result.decision,
            }
            if result.decision == "accept":
                accepted.append(enriched)
            elif result.decision == "weak":
                weak.append(enriched)

        if accepted:
            return accepted
        if self.settings.serp_allow_weak_fallback:
            return weak
        return []


class BS4SerpProvider:
    """Developer-mode raw SERP helper, blocked unless explicitly enabled."""

    name = "bs4_serp"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if os.getenv("BULK_INTEL_ALLOW_RAW_SERP") != "1":
            raise ConfigError("Raw SERP scraping is blocked unless BULK_INTEL_ALLOW_RAW_SERP=1")
        raise ConfigError("Raw SERP scraping is not wired into the production provider chain")


def build_search_query(row: pd.Series) -> str:
    """Return ``<clean title> site:amazon.in``."""
    title = row.get("product_name_clean") or row.get("product_name") or ""
    return f"{str(title).strip()} site:amazon.in"


def parse_price(text: object) -> Optional[float]:
    """Parse INR price strings, returning the lower bound for ranges."""
    if text is None:
        return None
    value = str(text).replace("\u00a0", " ").strip()
    if not value:
        return None
    if re.search(r"\$|usd", value, re.I):
        return None
    marker = r"(?:\u20b9|rs\.?|inr)"
    if not re.search(marker, value, re.I):
        return None
    pattern = re.compile(rf"{marker}\s*([0-9][0-9,\s]*(?:\.[0-9]+)?)", re.I)
    matches = pattern.findall(value)
    if not matches:
        pattern = re.compile(rf"([0-9][0-9,\s]*(?:\.[0-9]+)?)\s*{marker}", re.I)
        matches = pattern.findall(value)
    if not matches:
        return None
    try:
        return float(matches[0].replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def _infer_brand_from_title(title: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", " ", title).strip().split()
    return token[0] if token else ""


def _normalize_serp_results(payload: Mapping[str, Any], limit: int) -> list[dict[str, Any]]:
    rows = list(payload.get("organic_results") or []) + list(payload.get("shopping_results") or [])
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        title = str(row.get("title") or "")
        snippet = str(row.get("snippet") or row.get("description") or "")
        price = row.get("extracted_price")
        if price is None:
            price = parse_price(str(row.get("price") or "") or snippet or title)
        url = row.get("link") or row.get("url") or ""
        out.append(
            {
                "title": title,
                "price": float(price) if price is not None else None,
                "rating": row.get("rating"),
                "url": str(url),
                "snippet": snippet,
            }
        )
    return out
