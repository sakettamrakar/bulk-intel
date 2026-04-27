# T-301 — Amazon BSR ingestion provider

| Field | Value |
|---|---|
| Phase | 3 (P2 — advanced intelligence) |
| Effort | 12 hours |
| Depends on | T-207 (real catalog seed) |
| Blocks | T-302 |
| Status | Not started |

---

## Context

The current `sellability_score` mixes static category demand with discount %.
None of it reflects **actual Amazon Best-Seller Rank** for the SKU. BSR is the
single most predictive demand signal an operator can read for free.

This task adds an `AmazonBSRProvider` (or extends the catalog) that resolves
`amazon_bsr` (lower = better) per row and folds it into scoring.

## Files to create / modify

- `enrichment/bsr_provider.py` — new provider returning `bsr` for high-confidence catalog matches.
- `enrichment/enricher.py` — extend `PriceProvider.lookup` return shape **only if necessary**; else add a parallel `BSRProvider` Protocol.
- `intelligence/scoring.py` — add a BSR component to `sellability_score`.
- `config/settings.py` — `BSR_BUCKETS`, `SCORING_WEIGHTS["bsr"]`.
- `data/catalog/india_top1k_v1.json` — extend to optionally carry a `bsr` field (T-207 catalog format).
- `tests/test_bsr_provider.py`, `tests/test_pricing_and_scoring.py`.
- `README.md`.

## Specification

### BSR ingestion

Two implementation strategies — pick one for v1:

1. **Static catalog field**: extend the catalog JSON with `bsr` per item. Cheap, no live API. Good for a top-1k catalog.
2. **Live scraping** (`amazon_bsr_scraper.py`): per-row request to Amazon's product page. Expensive, rate-limit-prone, ToS-sensitive. Defer.

Ship strategy 1. Strategy 2 is a follow-up.

### `BSR_BUCKETS` (`config/settings.py`)

```python
# BSR bands → 0-100 sellability bonus.  Lower BSR (top of category) = higher
# bonus.  Buckets are per top-level category since a BSR of 50,000 means very
# different things in "Kitchen" vs "Books".
BSR_BUCKETS: Mapping[str, list[tuple[int, float]]] = {
    "electronics": [(1000, 95), (10000, 80), (50000, 60), (200000, 40), (1_000_000, 25)],
    "kitchen":     [(500,  95), (5000,  80), (25000, 60), (100_000, 40), (500_000, 25)],
    "apparel":     [(2000, 95), (20000, 80), (100_000, 60), (500_000, 40), (2_000_000, 25)],
    "_default":    [(1000, 95), (10000, 80), (50000, 60), (200000, 40), (1_000_000, 25)],
}

# Default sellability bonus when no BSR is available.
DEFAULT_BSR_SCORE: float = 50.0
```

### `SCORING_WEIGHTS` change

Re-weight to include `bsr`:

```python
SCORING_WEIGHTS: Mapping[str, float] = {
    "discount_percentage": 0.20,
    "market_gap":          0.15,
    "demand_score":        0.10,
    "category_liquidity":  0.10,
    "brand_score":         0.10,
    "price_band":          0.10,
    "bsr":                 0.25,   # new — strongest single demand signal
}
```

(weights still sum to 1.0)

### `intelligence/scoring.py` change

Read `amazon_bsr` column, look up the bucket, contribute to sellability.

## Acceptance criteria

- [ ] Catalog format supports `bsr` field (optional per item).
- [ ] `BSRProvider` (or extended catalog provider) populates `amazon_bsr` column.
- [ ] `scoring.py` computes a BSR-band score per row, weighted into `sellability_score`.
- [ ] On the real manifest, sellability ranking shifts: BSR-favourable items move up regardless of MRP / floor.
- [ ] Items without BSR (long-tail) get `DEFAULT_BSR_SCORE` and are not silently penalised.

## Test requirements

1. `test_bsr_lookup_by_category_band` — BSR=500 in kitchen → 95-band score.
2. `test_bsr_default_when_missing` — row without BSR → `DEFAULT_BSR_SCORE` (50).
3. `test_lower_bsr_higher_sellability` — two identical rows differing only in BSR; the one with the lower BSR scores higher in sellability.
4. `test_per_category_bsr_thresholds` — BSR=50,000 in books vs kitchen; assert different band scores.

## Documentation requirements

- [ ] `README.md` § 5 config table: `BSR_BUCKETS`, `DEFAULT_BSR_SCORE`, updated `SCORING_WEIGHTS`.
- [ ] `README.md` § 3 step 5 (Scoring): document BSR component.
- [ ] `enrichment/bsr_provider.py` docstring covers the two ingestion strategies and which one ships.

## Out of scope

- Live Amazon scraping (consider as separate T-30X).
- BSR over time (trend) — T-302 covers velocity.
- Flipkart / Meesho rank equivalents.

## Risks & considerations

- BSR data licensing / ToS. Static catalog snapshotting reduces but doesn't
  eliminate risk; document the source clearly.
- Cold-start: only catalog-matched items get BSR. The long tail still relies
  on the heuristic. Acceptable trade-off.
