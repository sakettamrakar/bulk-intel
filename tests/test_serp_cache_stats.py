from __future__ import annotations

from enrichment.serp_cache import SerpCache, cache_key


def test_stats_count_hits_and_misses(tmp_path):
    cache = SerpCache(tmp_path / "cache.sqlite", ttl_hours=1)
    cache.set("a", {"value": 1})
    assert cache.get("a") == {"value": 1}
    assert cache.get("b") is None
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.expired == 0
    assert stats.size == 1


def test_stats_count_expired_separately_from_misses(tmp_path):
    now = [100.0]
    cache = SerpCache(tmp_path / "cache.sqlite", ttl_hours=1, now_fn=lambda: now[0])
    cache.set("a", {"value": 1})
    now[0] += 7200
    assert cache.get("a") is None
    stats = cache.stats()
    assert stats.expired == 1
    assert stats.misses == 0


def test_cache_invalidate_by_signature(tmp_path):
    cache = SerpCache(tmp_path / "cache.sqlite", ttl_hours=1)
    cache.set(cache_key("logitech mouse m185", "fake"), {"search_signature": "logitech mouse m185", "brand": "logitech"})
    cache.set(cache_key("sony headphones", "fake"), {"search_signature": "sony headphones", "brand": "sony"})
    assert cache.invalidate_by_payload_field("search_signature", "logitech") == 1
    assert cache.stats().size == 1


def test_cache_invalidate_by_age(tmp_path):
    now = [1000.0]
    cache = SerpCache(tmp_path / "cache.sqlite", ttl_hours=100, now_fn=lambda: now[0])
    cache.set("old", {"value": 1})
    now[0] += 100
    cache.set("new", {"value": 2})
    assert cache.purge(older_than=1050) == 1
    assert cache.get("old") is None
    assert cache.get("new") == {"value": 2}
