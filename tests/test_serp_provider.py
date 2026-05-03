from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from config.settings import Settings
from enrichment.serp_cache import SerpCache, cache_key
from enrichment.serp_price_provider import (
    BS4SerpProvider,
    ConfigError,
    SerpAmazonPriceProvider,
    SerpAPIClient,
    TokenBucketRateLimiter,
    build_search_query,
    parse_price,
)
from pipeline.run_pipeline import Pipeline


FIXTURES = Path(__file__).parent / "fixtures" / "serp"


class FakeClient:
    backend_name = "fake"

    def __init__(self, results):
        self.results = results
        self.calls = 0

    def search(self, query):
        self.calls += 1
        return self.results


def _results(name):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    out = []
    for row in payload["organic_results"]:
        out.append(
            {
                "title": row["title"],
                "url": row["link"],
                "snippet": row["snippet"],
                "price": parse_price(row["snippet"]),
            }
        )
    return out


def _row(title="Logitech Wireless Mouse M185"):
    return pd.Series(
        {
            "product_name_clean": title,
            "brand": "Logitech",
            "normalized_category": "electronics",
        }
    )


def _settings(tmp_path, **kwargs):
    values = {
        "serp_cache_path": str(tmp_path / "serp.sqlite"),
        "serp_provider_enabled": True,
    }
    values.update(kwargs)
    return Settings(**values)


def test_provider_disabled_by_default():
    pipe = Pipeline()
    assert pipe.settings.serp_provider_enabled is False
    assert all(getattr(provider, "name", "") != "serp_amazon" for provider in pipe._price_providers())


def test_provider_enabled_adds_amazon_price(tmp_path):
    provider = SerpAmazonPriceProvider(
        settings=_settings(tmp_path),
        serp_client=FakeClient(_results("logitech_m185.json")),
    )
    amazon, wholesale, confidence = provider.lookup(_row())
    assert amazon == 1000.0
    assert wholesale is None
    assert confidence > provider.settings.match_accept_threshold


def test_match_score_gate_filters_wrong_brand(tmp_path):
    provider = SerpAmazonPriceProvider(
        settings=_settings(tmp_path),
        serp_client=FakeClient(_results("mixed_brand.json")),
    )
    amazon, _, _ = provider.lookup(_row())
    assert amazon == 1000.0


def test_no_accept_no_weak_returns_none(tmp_path):
    provider = SerpAmazonPriceProvider(
        settings=_settings(tmp_path, serp_allow_weak_fallback=False),
        serp_client=FakeClient(_results("weak_only.json")),
    )
    assert provider.lookup(_row("Logitech Mouse Wireless")) == (None, None, 0.0)


def test_weak_fallback_when_enabled(tmp_path):
    provider = SerpAmazonPriceProvider(
        settings=_settings(tmp_path, serp_allow_weak_fallback=True),
        serp_client=FakeClient(_results("weak_only.json")),
    )
    amazon, _, confidence = provider.lookup(_row("Logitech Mouse Wireless"))
    assert amazon == 800.0
    assert provider.settings.match_weak_threshold <= confidence < provider.settings.match_accept_threshold


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("\u20b91,499", 1499.0),
        ("\u20b91,499.00", 1499.0),
        ("Rs. 1499", 1499.0),
        ("INR 1499", 1499.0),
        ("\u20b91,499 - \u20b92,999", 1499.0),
        ("40% off \u20b91,499", 1499.0),
        ("", None),
        ("free", None),
        (None, None),
    ],
)
def test_parse_price_canonical_inputs(value, expected):
    assert parse_price(value) == expected


def test_build_query_uses_clean_title_with_site_filter():
    query = build_search_query(pd.Series({"product_name_clean": "Clean Name", "product_name": "Raw Name"}))
    assert query == "Clean Name site:amazon.in"


def test_cache_hit_skips_network(tmp_path):
    client = FakeClient(_results("logitech_m185.json"))
    provider = SerpAmazonPriceProvider(settings=_settings(tmp_path), serp_client=client)
    assert provider.lookup(_row())[0] == 1000.0
    client.calls = 0
    assert provider.lookup(_row())[0] == 1000.0
    assert client.calls == 0


def test_cache_ttl_expiry(tmp_path):
    now = [1000.0]
    cache = SerpCache(tmp_path / "cache.sqlite", ttl_hours=1, now_fn=lambda: now[0])
    key = cache_key("title", "fake")
    cache.set(key, {"amazon_price": 1})
    assert cache.get(key) == {"amazon_price": 1}
    now[0] += 7200
    assert cache.get(key) is None


def test_rate_limit_enforced():
    clock = [0.0]

    def sleep(seconds):
        clock[0] += seconds

    limiter = TokenBucketRateLimiter(rate_per_sec=1.0, time_fn=lambda: clock[0], sleep_fn=sleep)
    for _ in range(10):
        limiter.acquire()
    assert clock[0] >= 9.0


def test_retry_on_5xx_fails_fast_on_4xx(monkeypatch):
    settings = Settings(serp_max_retries=3, serp_api_key_env="SERPAPI_API_KEY")
    monkeypatch.setenv("SERPAPI_API_KEY", "secret")

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return {"organic_results": []}

    class Session:
        def __init__(self, codes):
            self.codes = list(codes)
            self.calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            return Response(self.codes.pop(0))

    retry_session = Session([503, 503, 200])
    client = SerpAPIClient(settings=settings, session=retry_session)
    client.search("x")
    assert retry_session.calls == 3

    fail_session = Session([401, 200])
    client = SerpAPIClient(settings=settings, session=fail_session)
    with pytest.raises(ConfigError):
        client.search("x")
    assert fail_session.calls == 1


def test_missing_api_key_raises_config_error(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        SerpAPIClient(settings=Settings())


def test_bs4_provider_blocked_without_env_flag(monkeypatch):
    monkeypatch.delenv("BULK_INTEL_ALLOW_RAW_SERP", raising=False)
    with pytest.raises(ConfigError):
        BS4SerpProvider()
