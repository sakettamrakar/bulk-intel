from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from config.settings import Settings
from enrichment.playwright_serp_client import (
    BudgetExhausted,
    CaptchaEncountered,
    PlaywrightSerpClient,
    detect_captcha,
    parse_results,
)
from enrichment.serp_backend_factory import NullSerpClient, build_serp_client
from enrichment.serp_cache import SerpCache
from enrichment.serp_orchestrator import ExecutionMode, PartialSerpOrchestrator
from enrichment.serp_price_provider import SerpAmazonPriceProvider, SerpAPIClient


FIXTURES = Path(__file__).parent / "fixtures" / "playwright_serp"


class FakePage:
    def __init__(self, html: str, url: str = "https://www.google.com/search?q=x", solved_html: str | None = None):
        self.html = html
        self.url = url
        self.solved_html = solved_html
        self.screenshots = []

    def content(self):
        return self.html

    def inner_text(self, selector="body"):
        import re

        return re.sub(r"<[^>]+>", " ", self.html)

    def goto(self, url, timeout=None):
        self.url = url

    def wait_for_selector(self, selector, timeout=None):
        if self.solved_html is None:
            raise TimeoutError("not solved")
        self.html = self.solved_html

    def screenshot(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake")
        self.screenshots.append(path)


def test_search_returns_serp_client_shape(tmp_path):
    client = _client(tmp_path, page=FakePage(_html("normal.html")))
    results = client.search("logitech m185")
    assert results
    assert {"title", "price", "rating", "url", "snippet"}.issubset(results[0])


def test_search_filters_sponsored_results(tmp_path):
    results = _client(tmp_path, page=FakePage(_html("normal.html"))).search("logitech m185")
    assert len(results) == 3
    assert all("Sponsored" not in row["title"] for row in results)


def test_budget_cap_raises_after_n_queries(tmp_path):
    client = _client(tmp_path, Settings(playwright_max_queries_per_run=3), FakePage(_html("normal.html")))
    for _ in range(3):
        client.search("x")
    with pytest.raises(BudgetExhausted):
        client.search("x")


def test_captcha_fixture_detected():
    assert detect_captcha(FakePage(_html("captcha_sorry.html"), url="https://www.google.com/sorry/index"))
    assert detect_captcha(FakePage(_html("captcha_recaptcha.html")))
    assert detect_captcha(FakePage(_html("captcha_unusual.html")))
    assert not detect_captcha(FakePage(_html("normal.html")))


def test_captcha_in_headless_raises_immediately(tmp_path):
    page = FakePage(_html("captcha_recaptcha.html"))
    client = _client(tmp_path, Settings(playwright_headless=True), page)
    with pytest.raises(CaptchaEncountered) as exc:
        client.search("x")
    assert Path(exc.value.screenshot_path).exists()


def test_captcha_in_headed_waits_for_human_solve(tmp_path):
    page = FakePage(_html("captcha_recaptcha.html"), solved_html=_html("normal.html"))
    results = _client(tmp_path, Settings(playwright_headless=False), page).search("x")
    assert results


def test_rate_limit_enforced_with_jitter(tmp_path):
    clock = [0.0]

    def sleep(seconds):
        clock[0] += seconds

    client = PlaywrightSerpClient(
        Settings(playwright_rate_limit_seconds=8.0, playwright_rate_limit_jitter_seconds=2.0),
        page_factory=lambda: FakePage(_html("normal.html")),
        time_fn=lambda: clock[0],
        sleep_fn=sleep,
        random_fn=lambda a, b: -2.0,
    )
    for _ in range(5):
        client.search("x")
    assert clock[0] >= 24.0


def test_persistent_profile_directory_created(tmp_path):
    settings = Settings(playwright_profile_path=str(tmp_path / "profile"))
    _client(tmp_path, settings, FakePage(_html("normal.html"))).search("x")
    assert Path(settings.playwright_profile_path).exists()
    _client(tmp_path, settings, FakePage(_html("normal.html"))).search("x")
    assert Path(settings.playwright_profile_path).exists()


def test_parse_results_falls_through_layers():
    results = parse_results(FakePage(_html("jsonld.html")))
    assert results[0]["title"] == "Logitech M185 Mouse"


def test_parse_results_returns_empty_on_unknown_layout(caplog):
    assert parse_results(FakePage(_html("empty.html"))) == []
    assert "no recognizable results" in caplog.text.lower()


def test_factory_picks_serpapi_when_key_present(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "secret")
    client = build_serp_client(Settings(serp_provider_enabled=True))
    assert isinstance(client, SerpAPIClient)


def test_factory_picks_playwright_when_only_fallback_enabled(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.setenv("BULK_INTEL_PLAYWRIGHT_FALLBACK", "1")
    client = build_serp_client(Settings(playwright_fallback_enabled=True, playwright_profile_path=str(tmp_path / "profile")))
    assert isinstance(client, PlaywrightSerpClient)


def test_factory_returns_null_client_when_nothing_configured(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("BULK_INTEL_PLAYWRIGHT_FALLBACK", raising=False)
    assert isinstance(build_serp_client(Settings()), NullSerpClient)


def test_orchestrator_records_mid_run_switch(tmp_path):
    class QuotaClient:
        backend_name = "serpapi"

        def search(self, query):
            raise RuntimeError("quota 429")

    settings = Settings(
        playwright_fallback_enabled=True,
        serp_cache_path=str(tmp_path / "cache.sqlite"),
        serp_state_path=str(tmp_path / "state.json"),
        playwright_profile_path=str(tmp_path / "profile"),
    )
    cache = SerpCache(settings.serp_cache_path, ttl_hours=1)
    provider = SerpAmazonPriceProvider(settings=settings, serp_client=QuotaClient(), cache=cache)
    groups = pd.DataFrame([
        {
            "group_id": "g0",
            "search_signature": "logitech m185",
            "canonical_title": "Logitech M185 Mouse",
            "brand": "Logitech",
            "normalized_category": "electronics",
            "model_tokens": ("M185",),
            "variant_count": 1,
            "group_total_quantity": 2,
            "group_total_value": 100.0,
            "group_member_skus": ("SKU1",),
            "eligible_for_search": True,
        }
    ])
    orch = PartialSerpOrchestrator(
        settings=settings,
        provider=provider,
        cache=cache,
        state_path=tmp_path / "state.json",
        playwright_client_factory=lambda _: PlaywrightSerpClient(
            settings,
            page_factory=lambda: FakePage(_html("normal.html")),
        ),
    )
    out = orch.enrich(groups, ExecutionMode.FULL)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["mid_run_backend_switch"] is True
    assert out.attrs["search_execution_summary"]["mid_run_backend_switch"] is True
    assert out.attrs["search_execution_summary"]["serp_backend_used"] == "playwright"


def _client(tmp_path, settings=None, page=None):
    settings = settings or Settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "playwright_profile_path": str(tmp_path / "profile"),
            "playwright_rate_limit_seconds": 0.0,
            "playwright_rate_limit_jitter_seconds": 0.0,
        }
    )
    return PlaywrightSerpClient(settings, page_factory=lambda: page or FakePage(_html("normal.html")))


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
