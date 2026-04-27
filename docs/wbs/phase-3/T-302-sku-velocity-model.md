# T-302 — SKU velocity / sell-through history model

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 16 hours |
| Depends on | T-301 (BSR ingestion); T-205 (backtest harness) |
| Blocks | T-304 |
| Status | Not started |

---

## Context

`condition.sellable_factor` and `expected_sellable_pct` are static priors that
give every kitchen-not-tested row the same 0.65 sell-through. Real velocity
is per-SKU and depends on brand, category, season, listing quality, and
historical performance.

This task replaces (or augments) the static prior with a **per-SKU velocity
estimate** sourced from realised sales history accumulated via T-205's
backtest data and (where available) BSR-trend signal from T-301.

## Files to create / modify

- `intelligence/velocity.py` — new module with a velocity estimator.
- `data/velocity/` — directory for accumulated sales-history snapshots.
- `intelligence/profit.py` — consume the per-SKU velocity if present, else fall back to the static `min(base, condition_factor)`.
- `tools/velocity_update.py` — CLI to ingest a new outcomes CSV and update the velocity store.
- `tests/test_velocity.py`.
- `README.md`.

## Specification

### Velocity store

Per-SKU JSON (or Parquet) file aggregating realised observations:

```json
{
  "schema_version": 1,
  "as_of": "2026-09-01",
  "skus": {
    "B07VR7VY1Y": {
      "observations": 4,
      "mean_sell_through_30d": 0.78,
      "mean_sell_through_90d": 0.91,
      "stddev_sell_through": 0.06,
      "last_observed": "2026-08-12"
    },
    ...
  }
}
```

### Velocity estimator (`intelligence/velocity.py`)

```python
def estimate_velocity(row: pd.Series, store: dict, settings: Settings) -> tuple[float, float]:
    """Return (velocity_estimate, confidence) for a row.

    Resolution priority:
      1. Per-SKU history with >= 3 observations: weighted by recency.
      2. Per-(category, condition_normalized) history.
      3. Per-(category) history.
      4. Static fallback: min(expected_sellable_pct, condition.sellable_factor).
    """
```

Confidence is `min(1.0, observations / 5)` for SKU-level, scaled down for
category-level and 0 for static fallback.

### `intelligence/profit.py` change

```python
velocity, velocity_confidence = self._resolve_velocity(out)
# Blend dynamic velocity with static prior, weighted by confidence.
static_prior = np.minimum(
    self.settings.profit_assumptions["expected_sellable_pct"],
    sellable_factor,
)
effective_sellable_pct = (
    velocity_confidence * velocity
    + (1 - velocity_confidence) * static_prior
)
out["velocity_estimate"] = velocity.round(4)
out["velocity_confidence"] = velocity_confidence.round(4)
```

### `tools/velocity_update.py`

```
usage: python -m tools.velocity_update --outcomes data/historical/lot_X.csv [--store data/velocity/store.json]

Reads realised outcomes, updates the per-SKU and per-category aggregates in
the velocity store, writes a new versioned JSON.
```

## Acceptance criteria

- [ ] `intelligence/velocity.py` exists with `estimate_velocity` and a smooth fallback chain.
- [ ] Pipeline blends dynamic velocity with the static prior based on confidence.
- [ ] CSV gains `velocity_estimate` and `velocity_confidence` columns.
- [ ] Items with sufficient history use SKU-level velocity; new items fall back gracefully.
- [ ] `tools.velocity_update` updates the store idempotently (running twice with the same outcomes file produces identical store output).
- [ ] Backtest report (T-205) shows improved roi_correlation after velocity is in play (compare before/after).

## Test requirements (`tests/test_velocity.py`)

1. `test_sku_with_history_uses_per_sku_velocity` — SKU with 5 prior observations + new row → velocity from history.
2. `test_unseen_sku_falls_back_to_category` — SKU not in store → category-level velocity used.
3. `test_no_history_falls_back_to_static_prior` — empty store → effective_sellable_pct == static prior, confidence = 0.
4. `test_velocity_update_is_idempotent` — running update twice produces identical JSON.
5. `test_velocity_confidence_scales_with_observations` — 1 observation → low confidence, 10+ → high confidence.

## Documentation requirements

- [ ] `README.md` § 3 step 6: explain the dynamic-velocity blend.
- [ ] `README.md` § 4: describe `python -m tools.velocity_update`.
- [ ] `intelligence/velocity.py` docstring documents the resolution priority + confidence formula.

## Out of scope

- Time-series modelling (ARIMA / Prophet) — Phase 4 if needed.
- Cross-platform velocity (Amazon-only velocity for now).

## Risks & considerations

- Velocity store can grow large; cap at top-N skus by recent observation count
  and aggregate the long tail at category level.
- Stale velocity (last_observed > 180 days) should decay confidence; document
  the decay function in the module docstring.
