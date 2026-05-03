# T-309 — Google SERP Amazon price provider

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 16 hours |
| Depends on | T-307 (model-token regex), T-308 (match scorer) |
| Blocks | — |
| Status | Not started |

---

## Context

Today `amazon_price` is filled by the in-process catalog
(`india_top1k_v1.json`) plus an MRP heuristic. Manifests for new
categories or long-tail SKUs miss the catalog entirely and fall back to
`fallback_pct_of_mrp`. We have no plug to fetch live Amazon prices for
unseen SKUs.

This task adds a **`PriceProvider` implementation that fetches Amazon
prices via Google SERP** (e.g. SerpAPI's structured Google Search
endpoint with `q="<title> site:amazon.in"`), validates each candidate
through the T-308 match scorer, and returns the median price across
accepted candidates.

The provider is opt-in (off by default). It plugs into the existing
`PriceProvider` chain; nothing else in the engine changes.

## Compliance & rate-limit posture

This is non-negotiable and must be enforced in code, not just docs:

1. **Direct Amazon scraping is forbidden.** Amazon's robots.txt and ToS
   prohibit it; production runs from rotating IPs in our infra would get
   the IP blocked and may expose us legally. The provider must hit a
   structured SERP API (SerpAPI / SearchAPI / Serper) — not Amazon
   itself, and not raw Google HTML.
2. **`requests + BeautifulSoup` against `google.com` is forbidden** for
   the same reason (Google ToS, fragile HTML, instant CAPTCHA in
   production volume). The implementer may add a `BS4SerpProvider`
   class **only as a developer-mode debugging aid**, gated behind
   `BULK_INTEL_ALLOW_RAW_SERP=1`, never wired into the default chain,
   and excluded from the CI matrix.
3. **Returned price = raw Amazon listing.** Do **not** apply any
   liquidation discount inside this provider. `intelligence/pricing.py`
   already applies `amazon_discount_factor` (default 0.70) and is the
   single place that haircut lives.
4. **Hard rate limit at the client.** No more than
   `SERP_RATE_LIMIT_PER_SEC` requests per second across all rows of a
   manifest. Burst safe — implement via a token bucket, not naïve
   sleep loops. Default: 1 req/sec.
5. **No PII in cache keys or logs.** Cache key derives from the
   manifest row's normalized title only.

## Codebase integration

- Implements `enrichment.enricher.PriceProvider` Protocol
  (`name: str`, `lookup(row) -> tuple[Optional[float], Optional[float],
  float]`). Returns `(amazon_price, None, match_confidence)`.
- Validates each SERP candidate through
  `intelligence.matching.compute_match_score`. Anything not `accept` is
  discarded. `weak` candidates are kept only when no `accept` exists
  and `SERP_ALLOW_WEAK_FALLBACK = True`.
- Cache uses **content-hash keys** so re-running the same manifest
  hits cache (the project rules already endorse this pattern).

## Files to create / modify

- `enrichment/serp_price_provider.py` — new module (the provider class
  + a thin `SerpClient` interface so SerpAPI / SearchAPI / Serper can
  be swapped without touching the provider).
- `enrichment/serp_cache.py` — small SQLite-backed disk cache (keyed
  on SHA-256 of normalized title; TTL configurable).
- `config/settings.py` — `SERP_PROVIDER_ENABLED`, `SERP_API_KEY_ENV`,
  `SERP_BACKEND` (`serpapi` | `searchapi` | `serper`),
  `SERP_RATE_LIMIT_PER_SEC`, `SERP_TIMEOUT_S`, `SERP_MAX_RETRIES`,
  `SERP_CACHE_PATH`, `SERP_CACHE_TTL_HOURS`,
  `SERP_RESULTS_PER_QUERY`, `SERP_ALLOW_WEAK_FALLBACK`. Add to
  `Settings`.
- `pipeline/run_pipeline.py` — when
  `Settings.serp_provider_enabled is True` and the API key env var is
  set, append the provider to the default chain. Off by default.
- `tests/test_serp_provider.py` — fully mocked; no real network calls.
- `tests/fixtures/serp/*.json` — captured SERP responses for tests.
- `requirements.txt` — `requests`, `tenacity` (for retries),
  `cachetools` (in-memory layer above SQLite). All BSD/MIT-licensed.
- `README.md`, `.env.example`.

## Specification

### Config (`config/settings.py`)

```python
SERP_PROVIDER_ENABLED: bool = False         # opt-in
SERP_API_KEY_ENV: str = "SERPAPI_API_KEY"   # name of env var to read

# Which structured SERP backend to call. Each maps to a SerpClient impl.
SERP_BACKEND: str = "serpapi"               # serpapi | searchapi | serper

SERP_RATE_LIMIT_PER_SEC: float = 1.0
SERP_TIMEOUT_S: float = 8.0
SERP_MAX_RETRIES: int = 3                   # exponential backoff, base 1.5s

SERP_CACHE_PATH: str = ".cache/serp_cache.sqlite"
SERP_CACHE_TTL_HOURS: int = 24 * 7          # 1 week

SERP_RESULTS_PER_QUERY: int = 5             # top-N organic results to scan
SERP_ALLOW_WEAK_FALLBACK: bool = False      # accept-only by default
```

### Module surface

```python
# enrichment/serp_price_provider.py

from typing import Protocol, Optional
import pandas as pd

class SerpClient(Protocol):
    """Pluggable SERP backend. Implementations wrap SerpAPI / SearchAPI /
    Serper and return a normalised list of organic results.

    Returned dicts have keys: title, price (float|None), rating
    (float|None), url, snippet. Currency parsing happens here."""

    def search(self, query: str) -> list[dict]: ...


class SerpAPIClient:
    """Concrete SerpClient using SerpAPI's google_shopping or google
    engine. Reads the API key from os.environ[settings.serp_api_key_env]
    at construction time. Raises ConfigError if missing.

    Built-in: tenacity retry with exponential backoff on
    requests.exceptions.* and 5xx. Built-in token-bucket rate limit.
    Honours SERP_TIMEOUT_S."""


class SerpAmazonPriceProvider:
    """PriceProvider that fetches Amazon prices via Google SERP.

    Pipeline:
      1. build_search_query(row) -> "<title> site:amazon.in"
      2. serp_client.search(query) -> raw candidates
      3. parse_price(text) on each candidate
      4. compute_match_score(row, candidate) gate via T-308
      5. keep candidates with decision == 'accept' (or 'weak' if
         SERP_ALLOW_WEAK_FALLBACK is True and no 'accept' exists)
      6. amazon_price = median(prices); match_confidence = max(scores)
      7. cache (input_hash) -> (amazon_price, match_confidence,
         matched_titles, matched_urls). TTL from settings.

    Returns (amazon_price, None, match_confidence) — wholesale_price is
    not in scope.
    """

    name = "serp_amazon"


def build_search_query(row: pd.Series) -> str:
    """`<product_name_clean> site:amazon.in` — falls back to
    product_name when product_name_clean is missing."""


def parse_price(text: str) -> Optional[float]:
    """Parse INR price strings.

    Handles: '₹1,499', '₹1,499.00', 'Rs. 1499', 'INR 1499',
             '₹1,499 - ₹2,999' (returns the lower bound),
             '₹1,499 (40% off)', whitespace / NBSP variants.

    Returns None on unparseable input — never raises."""
```

### Cache (`enrichment/serp_cache.py`)

- SQLite single-file at `SERP_CACHE_PATH`. Schema: `key TEXT PRIMARY
  KEY, payload TEXT, created_at INTEGER`.
- Key = `sha256(normalized_title + "|" + backend_name)`.
- Stale entry (`now - created_at > ttl`) → treated as miss; old row is
  overwritten on next write.
- `get(key) -> dict | None`, `set(key, payload: dict)`, `purge(now)`.
- Concurrency: no cross-process locking; single-writer assumed (a
  pipeline run is single-process). Document this.

## Acceptance criteria

- [ ] `SerpAmazonPriceProvider` implements the `PriceProvider`
  Protocol; `enricher.py` accepts it without modification.
- [ ] Default pipeline behaviour is **unchanged** when
  `SERP_PROVIDER_ENABLED=False` (verified by existing end-to-end test).
- [ ] When enabled and the API key env var is set, the provider
  contributes `amazon_price` for rows the catalog misses.
- [ ] Every accepted candidate cleared T-308's `accept` band, OR
  `SERP_ALLOW_WEAK_FALLBACK=True` and no `accept` candidate existed.
- [ ] Median is computed across accepted candidate prices; the original
  matched titles + URLs are persisted in cache for audit.
- [ ] Token-bucket rate limit is enforced (assertable via test that
  fires N requests and measures elapsed time).
- [ ] Retries trigger only on transient failures (5xx, timeout); 4xx
  fails fast with a clear error.
- [ ] Cache hit on a re-run: zero network calls (test asserts
  `mock_search.call_count == 0` on the second run).
- [ ] `BS4SerpProvider`, if implemented, is gated behind
  `BULK_INTEL_ALLOW_RAW_SERP=1` and is **not** in the default chain.
- [ ] No real network calls in tests — `SerpClient` is mocked end to
  end via `tests/fixtures/serp/*.json`.

## Test requirements (`tests/test_serp_provider.py`)

1. `test_provider_disabled_by_default` — pipeline run with no env var
   set behaves identically to today's baseline.
2. `test_provider_enabled_adds_amazon_price` — fixture SERP returns 3
   matching results; provider returns the median price and a
   confidence > MATCH_ACCEPT_THRESHOLD.
3. `test_match_score_gate_filters_wrong_brand` — fixture contains 2
   matches and 1 wrong-brand result; only the 2 are aggregated.
4. `test_no_accept_no_weak_returns_none` — fixture has only weak
   candidates and `SERP_ALLOW_WEAK_FALLBACK=False` → provider returns
   `(None, None, 0.0)`.
5. `test_weak_fallback_when_enabled` — same fixture, flag flipped →
   provider returns the weak median + a confidence in
   `[MATCH_WEAK_THRESHOLD, MATCH_ACCEPT_THRESHOLD)`.
6. `test_parse_price_canonical_inputs` — table-driven over '₹1,499',
   '₹1,499.00', 'Rs. 1499', 'INR 1499', '₹1,499 - ₹2,999', '40% off
   ₹1,499', '', 'free', `None`. None on unparseable, lower bound on
   ranges.
7. `test_build_query_uses_clean_title_with_site_filter` — output ends
   with ` site:amazon.in`; clean title preferred over raw.
8. `test_cache_hit_skips_network` — second call with same row has zero
   `SerpClient.search` invocations.
9. `test_cache_ttl_expiry` — entries past TTL are treated as misses.
10. `test_rate_limit_enforced` — 10 sequential calls at 1 req/sec take
    >= 9 seconds (use a fake clock; do not actually sleep in CI).
11. `test_retry_on_5xx_fails_fast_on_4xx` — 503 → retried; 401 → no
    retries, raises `ConfigError`.
12. `test_missing_api_key_raises_config_error` — constructing the
    client with the env var unset raises a clear error before any HTTP
    call.
13. `test_bs4_provider_blocked_without_env_flag` — importing /
    constructing `BS4SerpProvider` without `BULK_INTEL_ALLOW_RAW_SERP=1`
    raises.

## Documentation requirements

- [ ] `README.md` § 3 step 3 (Enrichment): note the new optional
  provider and how it sits in the chain.
- [ ] `README.md` § 4 How to run: a "Live SERP prices" subsection
  showing how to set the API key and enable the provider for a single
  run. Include a worked example that runs against the sample manifest.
- [ ] `README.md` § 5 config table: every new setting.
- [ ] `README.md` § 6 Extension points: "How to plug a different SERP
  backend" — point at the `SerpClient` Protocol.
- [ ] `.env.example`: `SERPAPI_API_KEY=` placeholder.
- [ ] `enrichment/serp_price_provider.py` module docstring documents
  the compliance posture (no Amazon scraping, no Google HTML, rate
  limit, cache).
- [ ] `config/priors/README.md` is **not** the right home for these
  knobs — they go in the main config table.

## Out of scope

- Wholesale price discovery via SERP. Different sources, different
  matching rules — Phase 4.
- Flipkart / Meesho SERP providers. Plumbed by the same Protocol but
  ship as their own tasks (T-31x).
- Headless-browser fallback (Playwright). Heavy dependency, separate
  compliance review.
- Auto-tuning of `MATCH_TOKEN_WEIGHTS` from SERP outcomes. Belongs to
  T-305's feedback loop once we have telemetry.
- Any modification to `intelligence/pricing.py` — the existing
  `amazon_discount_factor` continues to apply unchanged.

## Risks & considerations

- **Cost.** SerpAPI bills per query; 1k-row manifest at 1 query/row
  with no cache = ~$5 / run at current pricing. Cache TTL of 1 week
  amortises this for re-runs. Document the rough cost in the README.
- **Match drift.** Amazon listings rotate (new variants, deleted
  ASINs). Cache TTL of 1 week is the trade-off; tune via setting if
  prices look stale.
- **Currency edge cases.** Amazon.in occasionally returns USD prices
  for imports; `parse_price` must reject anything not in INR, not
  silently convert.
- **API key leakage.** Never log the key. Logging filter lives in
  `utils/logging.py`; this task adds a redaction rule for any
  `SERPAPI_*` env var.
- **Regression on the catalog provider.** Both providers can win on
  the same row. The chain order in `pipeline/run_pipeline.py` decides
  who wins; document the rationale (catalog first because it's
  zero-cost; SERP last as a fallback for misses).
- **Test fixtures must be hand-curated** to cover the four match
  decisions (accept / weak / reject-brand / reject-category). Capture
  them once from a live SERP run, then commit; never re-fetch in CI.
