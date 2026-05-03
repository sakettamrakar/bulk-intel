# T-312 — Playwright Google SERP fallback client

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 12 hours |
| Depends on | T-309 (`SerpClient` Protocol + `SerpCache`), T-311 (top-N limit semantics) |
| Blocks | — |
| Status | Not started |

---

## Context

T-309 ships a SerpAPI-backed price provider. That works as long as the
operator has a paid SerpAPI subscription and remaining quota. Two
realistic failure modes today:

1. **No API key** in the environment (cold-start, demo, dev workstations).
2. **Quota exhausted** mid-manifest (rare but operationally fatal — a
   12k-row run halves at the 4k-row mark with no good recovery).

We need a **fallback `SerpClient` implementation that drives a real
browser** via Playwright so the engine still runs end-to-end without
the paid API. The fallback is **deliberately bounded** — it is not a
production scraper, and the WBS treats it that way.

This task is a deliberate reversal of T-309's "no Playwright, no raw
Google HTML" rule. The reversal is bounded by:

- **Operator-assisted** by default: headed browser, the operator can see
  the window, CAPTCHAs pause the run and prompt for human resolution.
- **Hard query cap** per run (default 10, matches T-311's
  `SERP_PREVIEW_LIMIT`). The fallback is for triage, not full enrichment.
- **Explicit opt-in** via env var. The flag isn't on by default; an
  unconfigured machine can't accidentally start scraping Google.
- **Same Protocol surface** as T-309's `SerpClient`, so T-311's
  orchestrator picks it up without code changes — pure swap.

## Compliance & operational posture

Read this before writing any selector code:

1. **Google's ToS prohibits automated scraping of Search.** Running this
   in production against a busy IP is a fast path to a CAPTCHA wall and
   eventually to an IP block. The shape we're shipping (operator-assisted,
   capped at single-digit queries per run) is what makes this defensible
   for triage, not for bulk enrichment.
2. **Headless: false by default.** Set `PLAYWRIGHT_HEADLESS=false` in
   the default config. Operators who run it inside CI override that
   knowingly; the default surface keeps the human in the loop.
3. **Persistent browser context.** Store cookies / login state on disk
   under `.cache/playwright/` so a logged-in Google session reduces
   CAPTCHA frequency. The operator signs in **once**; the engine
   reuses that profile.
4. **CAPTCHA detection → pause + prompt.** When the page contains
   `recaptcha`, `sorry/index`, `Our systems have detected unusual
   traffic`, or a missing results container, the client pauses, logs a
   loud warning, and (in headed mode) waits for the operator to solve
   the challenge or quit. In headless mode it raises immediately.
5. **Hard rate limit far below SerpAPI's.** 1 query per 6–10 seconds with
   jitter, regardless of the orchestrator's token bucket from T-309.
   Implemented as the inner loop of `search()`, not at the orchestrator
   layer, because Google sees the *browser*, not the orchestrator.
6. **Hard query cap per run.** `PLAYWRIGHT_MAX_QUERIES_PER_RUN`
   (default 10). The client raises a clear `BudgetExhausted` error
   when reached; the orchestrator surfaces it as a normal "incomplete
   run" with `serp_pending_count > 0`.
7. **No login automation.** Never type Google credentials. The operator
   logs in manually inside the persistent profile; the engine never
   handles secrets.
8. **No proxy rotation, no fingerprint spoofing.** Adding either turns
   this from "operator triage tool" into "production scraper", which is
   the line we're not crossing in this task. Out of scope.

These are not nice-to-haves. They are how this task stays shippable.

## Codebase integration

- Implements the **same `SerpClient` Protocol** that T-309 defined
  (`search(query: str) -> list[dict]`). T-311's orchestrator and
  T-309's `SerpAmazonPriceProvider` both consume it; no Protocol
  changes.
- Reuses **T-309's `SerpCache`** as-is. Cache keys still include the
  backend name, so a Playwright result and a SerpAPI result for the
  same query do not collide. T-311's `cache_stats` automatically counts
  hits across both backends.
- Reuses **T-308's matcher** for accept / weak / reject gating. The
  fallback returns raw candidates; matching is unchanged.
- Reuses **T-311's run-state and coverage telemetry**. A Playwright
  run looks identical to a SerpAPI run from the orchestrator's point of
  view; only `cache_stats.backend` and a new `serp_backend_used`
  field on the manifest summary distinguish them.

## Files to create / modify

- `enrichment/playwright_serp_client.py` — new module:
  `PlaywrightSerpClient`, `BudgetExhausted`, `CaptchaEncountered`.
- `enrichment/serp_backend_factory.py` — new tiny module that picks the
  active client based on env / settings (one place to read the env vars,
  not five).
- `enrichment/serp_price_provider.py` (T-309) — accepts an injected
  `SerpClient`, no longer hard-wires `SerpAPIClient` in its constructor
  default. (One-line refactor; T-309's tests stay green by passing
  `SerpAPIClient()` explicitly.)
- `pipeline/run_pipeline.py` — when both SerpAPI and Playwright are
  configured, prefer SerpAPI; on construction failure or runtime
  `BudgetExhausted` (after the SerpAPI quota), fall back to Playwright
  for the remainder of the run. Log the switch loudly.
- `config/settings.py` — `PLAYWRIGHT_FALLBACK_ENABLED`,
  `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_MAX_QUERIES_PER_RUN`,
  `PLAYWRIGHT_RATE_LIMIT_SECONDS`, `PLAYWRIGHT_RATE_LIMIT_JITTER_SECONDS`,
  `PLAYWRIGHT_PROFILE_PATH`, `PLAYWRIGHT_PAGE_TIMEOUT_S`,
  `PLAYWRIGHT_CAPTCHA_TIMEOUT_S`. Add to `Settings`.
- `requirements.txt` — `playwright`. Document
  `python -m playwright install chromium` as a one-time post-install
  step in the README.
- `tests/test_playwright_serp_client.py` — fully mocked (no real
  browser launches in CI). Use the recorded HTML fixtures pattern.
- `tests/fixtures/playwright_serp/*.html` — captured Google SERP
  pages (one normal, one CAPTCHA, one empty-results) for parser tests.
- `README.md`, `.env.example`, `docs/operator/playwright-fallback.md`.

## Specification

### Config (`config/settings.py`)

```python
PLAYWRIGHT_FALLBACK_ENABLED: bool = False        # opt-in
PLAYWRIGHT_HEADLESS: bool = False                # human-in-the-loop default
PLAYWRIGHT_MAX_QUERIES_PER_RUN: int = 10         # matches SERP_PREVIEW_LIMIT
PLAYWRIGHT_RATE_LIMIT_SECONDS: float = 8.0
PLAYWRIGHT_RATE_LIMIT_JITTER_SECONDS: float = 2.0  # uniform [-jitter, +jitter]
PLAYWRIGHT_PROFILE_PATH: str = ".cache/playwright/profile"
PLAYWRIGHT_PAGE_TIMEOUT_S: float = 15.0          # page.goto + waitForSelector
PLAYWRIGHT_CAPTCHA_TIMEOUT_S: float = 180.0      # human solve window (headed)
```

Env-var equivalents read by `serp_backend_factory.py`:
`BULK_INTEL_PLAYWRIGHT_FALLBACK=1`,
`BULK_INTEL_PLAYWRIGHT_HEADLESS=0|1`.

### Module surface (`enrichment/playwright_serp_client.py`)

```python
from __future__ import annotations
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Iterator

class BudgetExhausted(RuntimeError):
    """Raised when PLAYWRIGHT_MAX_QUERIES_PER_RUN is reached.
    The orchestrator catches this and reports it as a clean
    'preview_completed' state — the run is bounded, not crashed."""

class CaptchaEncountered(RuntimeError):
    """Raised in headless mode (or after the headed timeout window
    expires). Includes the page URL and a screenshot path written to
    .cache/playwright/captcha_<ts>.png so an operator can inspect."""


@dataclass(frozen=True)
class PlaywrightSerpClient:
    """Implements the SerpClient Protocol (T-309) by driving a real
    Chromium via Playwright.

    Lifecycle:
      __init__ does NOT launch a browser. The first call to search()
      lazily spins one up via _ensure_session(). __exit__ / close()
      shuts it down cleanly. This makes the client cheap to construct
      (e.g. when the factory has to instantiate it just to fail over).
    """
    settings: Settings
    queries_used: int = 0    # mutated via object.__setattr__ since frozen

    def search(self, query: str) -> list[dict]:
        """Return organic results in T-309's SerpClient format:
            [{title, price, rating, url, snippet}, ...]

        Pipeline per query:
          1. enforce queries_used < PLAYWRIGHT_MAX_QUERIES_PER_RUN, else
             raise BudgetExhausted.
          2. enforce per-query rate limit (sleep for
             RATE_LIMIT_SECONDS ± JITTER) since the last successful
             search().
          3. page.goto("https://www.google.com/search?q=" + urlencoded(query))
          4. detect_captcha(page) — if positive, handle per
             PLAYWRIGHT_HEADLESS:
               headed:    log warning, await page.wait_for_selector(
                          results_container, timeout=CAPTCHA_TIMEOUT_S);
                          if it appears, continue; else raise.
               headless:  raise CaptchaEncountered immediately.
          5. parse_results(page) — return organic candidates only.
             Sponsored / shopping ads are filtered out by default.
          6. queries_used += 1.

        Currency: parse_price() reuses T-309's parser; no INR
        conversion. If a candidate carries a USD price (rare for
        amazon.in), it is returned as None so downstream matching
        rejects it cleanly rather than corrupting the price."""

    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, *exc): self.close()


def detect_captcha(page) -> bool:
    """True if any of the following hold:
      - URL path includes /sorry/ or /signin
      - body text contains 'unusual traffic' or 'recaptcha'
      - the organic-results container selector is missing after
        PAGE_TIMEOUT_S.
    """


def parse_results(page) -> list[dict]:
    """Selector strategy, ordered:

      1. JSON-LD blocks via document.querySelectorAll('script[type=
         "application/ld+json"]'). Most stable, cover Shopping cards.
      2. Structured product cards: 'div.g' / 'div[data-snc]' / current
         organic-result selector. Capture the one that returned the
         most rows on the recorded fixtures, then fall through if
         empty.
      3. Last-resort: link href + cite-text scraping. Returns title +
         url only; price=None.

    Each layer is best-effort. parse_results returns whatever the
    earliest non-empty layer produced — never raises on selector
    drift; logs a warning and returns []."""
```

### Backend factory (`enrichment/serp_backend_factory.py`)

```python
def build_serp_client(settings: Settings) -> SerpClient:
    """Pick the active SerpClient.

    Decision tree (top to bottom):
      1. SerpAPI key present AND SERP_PROVIDER_ENABLED → SerpAPIClient.
      2. PLAYWRIGHT_FALLBACK_ENABLED AND
         BULK_INTEL_PLAYWRIGHT_FALLBACK env set → PlaywrightSerpClient.
      3. else → NullSerpClient (returns []), so the engine still runs
         end-to-end but with no live prices.

    The factory does not chain backends. Cross-backend failover (SerpAPI
    quota exhausted mid-run → Playwright takes over) is handled by the
    orchestrator wrapping its provider call in try/except for
    rate_limited / 4xx-quota errors and rebuilding the client once.
    """
```

### Orchestrator failover (T-311 patch)

In `PartialSerpOrchestrator.enrich()`, the fetch step is:

```python
try:
    candidates = self.provider.lookup_for_group(group)
except SerpAPIQuotaExceeded:
    if self.settings.playwright_fallback_enabled:
        logger.warning(
            "SerpAPI quota exhausted; switching to Playwright fallback "
            "for the remainder of this run (capped at %d queries)",
            self.settings.playwright_max_queries_per_run,
        )
        self.provider = self.provider.with_client(
            PlaywrightSerpClient(self.settings)
        )
        candidates = self.provider.lookup_for_group(group)
    else:
        raise
```

The switch is logged loudly and recorded on the run-state file as
`mid_run_backend_switch=True` so the manifest summary surfaces it.

### Manifest summary additions

The `search_execution_summary` from T-311 gains:

```json
{
  "serp_backend_used": "serpapi" | "playwright" | "mixed" | "none",
  "playwright_queries_used": 7,
  "playwright_budget_remaining": 3,
  "captchas_encountered": 1,
  "mid_run_backend_switch": false
}
```

## Acceptance criteria

- [ ] `PlaywrightSerpClient` implements the `SerpClient` Protocol from
  T-309 byte-for-byte (same return shape from `search`).
- [ ] Default behaviour with `PLAYWRIGHT_FALLBACK_ENABLED=False` is
  unchanged — every existing T-309 / T-311 test passes.
- [ ] No real browser launches in CI: tests use recorded HTML fixtures
  and a fake `Page` / `BrowserContext` injected via factory hooks.
- [ ] Hard query cap is enforced: setting limit=3 and calling `search()`
  four times → fourth call raises `BudgetExhausted`. The orchestrator
  catches and reports it cleanly (does not crash the run).
- [ ] `detect_captcha` returns True for each of the three captured
  CAPTCHA fixtures (`/sorry/index`, reCAPTCHA challenge, "unusual
  traffic" interstitial).
- [ ] In **headless** mode, `CaptchaEncountered` is raised within
  `PLAYWRIGHT_PAGE_TIMEOUT_S` of hitting the CAPTCHA fixture.
- [ ] In **headed** mode (simulated via fake page), the client waits up
  to `PLAYWRIGHT_CAPTCHA_TIMEOUT_S` for the results selector to appear
  and proceeds when it does.
- [ ] Rate limit is enforced: 5 sequential `search()` calls with
  rate=8s take ≥ 32s on a fake clock. (Real test uses
  `time.monotonic` patched.)
- [ ] Persistent profile path is created on first launch and reused on
  the second — login cookies survive process restart (asserted by file
  existence, not by hitting Google).
- [ ] `serp_backend_factory.build_serp_client` selects backends per the
  decision tree; no backend ever silently activates without its env
  flag.
- [ ] Mid-run failover from SerpAPI to Playwright is recorded on the
  state file as `mid_run_backend_switch=True` and surfaced in the
  manifest summary.
- [ ] CAPTCHA screenshot is written to disk under
  `.cache/playwright/captcha_<unix_ts>.png` and the path is included
  in the raised exception.
- [ ] Cache key format from T-309 is unchanged (so Playwright-served
  results remain reusable by SerpAPI runs and vice versa).
- [ ] `requirements.txt` adds `playwright`; README documents the
  `python -m playwright install chromium` post-install step.

## Test requirements

`tests/test_playwright_serp_client.py`:

1. `test_search_returns_serp_client_shape` — fixture page →
   list of dicts with the five required keys.
2. `test_search_filters_sponsored_results` — fixture with one
   sponsored card and three organic results → only the three organic
   are returned.
3. `test_budget_cap_raises_after_n_queries` — limit=3, call 4×.
4. `test_captcha_fixture_detected` — three CAPTCHA fixtures, one
   normal fixture; `detect_captcha` returns the right boolean for each.
5. `test_captcha_in_headless_raises_immediately` —
   `PLAYWRIGHT_HEADLESS=True`, CAPTCHA fixture → `CaptchaEncountered`.
6. `test_captcha_in_headed_waits_for_human_solve` — fake page that
   "becomes solved" after 2s → client returns parsed results, no
   exception.
7. `test_rate_limit_enforced_with_jitter` — patched clock, 5
   sequential calls, asserts ≥ `(N-1) * (rate - jitter)` elapsed.
8. `test_persistent_profile_directory_created` — first launch
   creates the profile path; second uses it without reinitialising.
9. `test_parse_results_falls_through_layers` — fixture missing the
   primary selector but containing JSON-LD → parser returns LD-derived
   results.
10. `test_parse_results_returns_empty_on_unknown_layout` — fixture
    with no recognisable structure → returns `[]`, logs a warning,
    does **not** raise.
11. `test_factory_picks_serpapi_when_key_present` — env var set →
    factory returns `SerpAPIClient`.
12. `test_factory_picks_playwright_when_only_fallback_enabled` — no
    SerpAPI key, `PLAYWRIGHT_FALLBACK_ENABLED=True` → factory returns
    `PlaywrightSerpClient`.
13. `test_factory_returns_null_client_when_nothing_configured` —
    pipeline runs end-to-end with no live prices, no exception.
14. `test_orchestrator_records_mid_run_switch` — simulate SerpAPI
    quota error mid-run → run-state file shows
    `mid_run_backend_switch=True`, summary reflects it.

## Documentation requirements

- [ ] `README.md` § 3 step 3 (Enrichment): mention the optional
  Playwright fallback and link to the operator guide.
- [ ] `README.md` § 4: a "Run without a SerpAPI key" subsection with the
  copy-pasteable env-var setup and a one-time
  `python -m playwright install chromium` reminder.
- [ ] `README.md` § 5: every new setting in the config table.
- [ ] `enrichment/playwright_serp_client.py` module docstring repeats
  the compliance posture verbatim.
- [ ] `docs/operator/playwright-fallback.md` — operator-facing guide:
  how to log into Google in the persistent profile, what CAPTCHA
  resolution looks like, when to abort, the recommended query cap.
- [ ] `.env.example`: `BULK_INTEL_PLAYWRIGHT_FALLBACK=` placeholder
  with a comment pointing at the operator guide.

## Out of scope

- **Stealth plugins / fingerprint spoofing.** This is the line that
  separates "operator triage tool" from "production scraper". Adding
  them changes the risk profile; do it in a separate task with explicit
  legal review.
- **Proxy rotation.** Same reasoning.
- **Login automation.** The operator logs in once, manually, inside the
  persistent profile. The engine never touches Google credentials.
- **Bulk Playwright runs.** The query cap is the safety belt; an
  operator who needs more should buy SerpAPI quota.
- **Other search engines.** Bing / Brave SERP are different shapes and
  CAPTCHAs; their own task if we ever need it.
- **CAPTCHA-solving services** (2captcha, anticaptcha). Out — both for
  cost and for the "are we still a triage tool" question.

## Risks & considerations

- **Selector drift is the chronic failure mode.** Google rotates DOM
  every few months. The layered selector strategy and the "return [] +
  warn" semantics are the mitigations; they are deliberate. The fixture
  set must be refreshed quarterly (add a calendar reminder in the
  operator guide).
- **CAPTCHA frequency** depends heavily on the operator's IP / Google
  account. Document expectations: a fresh IP may CAPTCHA on the first
  query; a logged-in account that's done normal browsing rarely
  CAPTCHAs in single-digit volumes. The persistent profile is the main
  defence.
- **Headless detection.** Modern Google increasingly fingerprints
  headless Chrome. Default is `headless=False` for that reason; CI runs
  must use mocked pages, not real browsers.
- **Mid-run switch leaves partial telemetry.** Coverage metrics from
  T-311 still work but the operator must understand that a run with
  `mid_run_backend_switch=True` mixed two latency profiles. Document
  prominently.
- **Disk usage.** The persistent profile + CAPTCHA screenshots can
  grow. Add `.cache/playwright/` to `.gitignore` (it's a runtime
  artifact) and document a manual purge command in the operator guide.
- **The cap is a feature, not a bug.** Resist requests to bump
  `PLAYWRIGHT_MAX_QUERIES_PER_RUN` above ~25 without re-evaluating the
  compliance posture. If operators routinely need more, the answer is
  SerpAPI quota, not a higher cap.
