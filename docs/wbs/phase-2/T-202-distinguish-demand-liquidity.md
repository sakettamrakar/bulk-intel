# T-202 — Differentiate `DEMAND_SCORE` from `CATEGORY_LIQUIDITY_SCORE`

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 2 hours |
| Depends on | — |
| Blocks | — |
| Status | Not started |

---

## Context

`config/settings.py` currently defines `DEMAND_SCORE` and
`CATEGORY_LIQUIDITY_SCORE` with **identical values** for every category. Both
are weighted separately in `SCORING_WEIGHTS`, giving the false impression of a
multi-factor sellability score when in reality a single signal contributes
twice.

This task makes the two maps semantically distinct.

## Conceptual model

| Signal | Question it answers | Influenced by |
|---|---|---|
| `DEMAND_SCORE` | "How many people want this category?" | search volume, BSR, total transactions |
| `CATEGORY_LIQUIDITY_SCORE` | "How fast can a single seller's inventory clear?" | seller density, marketplace velocity, price-elasticity, stock duration |

Examples to internalise the distinction:
- **Electronics** — high demand (90), but low liquidity (40) per seller because thousands of competing sellers; your unit waits in queue.
- **Apparel** — high demand (75), high liquidity (75) per seller because SKUs differentiate naturally.
- **Books** — moderate demand (40) but high liquidity (60) for in-demand titles (Amazon BSR-led).
- **Beauty** — high demand (80) but moderate liquidity (55) because brand sensitivity creates winner-takes-most dynamics.

## Files to modify

- `config/settings.py` — recalibrate `CATEGORY_LIQUIDITY_SCORE` so it differs from `DEMAND_SCORE`.
- `tests/test_pricing_and_scoring.py` — add a test ensuring the two maps are not identical.
- `README.md` — clarify the distinction in the config table.

## Specification

```python
DEMAND_SCORE: Mapping[str, float] = {
    "electronics": 90.0,
    "appliances":  75.0,
    "apparel":     75.0,
    "home":        70.0,
    "kitchen":     70.0,
    "kitchenware": 70.0,
    "cooking":     70.0,
    "pots_pans":   70.0,
    "beauty":      80.0,
    "toys":        65.0,
    "books":       40.0,
    "stationery":  35.0,
    "unknown":     50.0,
}

# Category liquidity = how fast a single seller's inventory clears given the
# competitive density of the marketplace.  High demand does NOT imply high
# liquidity; electronics has very high demand but very high seller density.
CATEGORY_LIQUIDITY_SCORE: Mapping[str, float] = {
    "electronics": 40.0,   # high demand, but ~thousands of competing sellers
    "appliances":  55.0,   # moderate demand, moderate seller density
    "apparel":     75.0,   # SKU differentiation aids individual sellers
    "home":        65.0,
    "kitchen":     55.0,
    "kitchenware": 55.0,
    "cooking":     55.0,
    "pots_pans":   60.0,
    "beauty":      55.0,   # brand-led winner-takes-most dynamics
    "toys":        70.0,   # gift-driven, branded-toys clear fast in season
    "books":       60.0,   # Amazon BSR drives long-tail discovery
    "stationery":  50.0,
    "unknown":     50.0,
}
```

## Acceptance criteria

- [ ] `CATEGORY_LIQUIDITY_SCORE` differs from `DEMAND_SCORE` on **at least 6 categories**.
- [ ] No category has the same value for both unless explicitly intended (`unknown` may match).
- [ ] On the real manifest, sellability scores shift slightly (since the two signals now contribute differently). Record the new distribution in the PR description.

## Test requirements

1. `test_demand_and_liquidity_are_not_identical` — assert the two mappings differ on at least 6 keys.
2. `test_electronics_high_demand_low_liquidity` — `DEMAND_SCORE["electronics"] > CATEGORY_LIQUIDITY_SCORE["electronics"]`.
3. `test_apparel_demand_close_to_liquidity` — within 10 points (illustrates SKU differentiation).
4. Existing `test_high_discount_known_brand_scores_higher` continues to pass.

## Documentation requirements

- [ ] `README.md` config table: separate descriptions for `DEMAND_SCORE` ("how many people want this category") vs `CATEGORY_LIQUIDITY_SCORE` ("how fast a single seller's inventory clears").
- [ ] Inline comment block at the top of each map explaining the distinction with one example.

## Out of scope

- Live BSR / seller-count integration (T-301).
- Per-platform liquidity (electronics-on-Amazon vs electronics-on-Flipkart).

## Risks & considerations

- Numbers above are operator-judgement defaults. They'll shift once T-205
  (backtest harness) has realised data to regress against.
- Some downstream tests may have implicitly relied on identical values; run
  `pytest -v` before committing and adjust any failing assertions to test the
  new behaviour, not regress to the old.
