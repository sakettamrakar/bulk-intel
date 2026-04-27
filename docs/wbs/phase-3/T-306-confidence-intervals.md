# T-306 — Confidence intervals on every projection

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 8 hours |
| Depends on | T-205 (backtest harness) |
| Blocks | — |
| Status | Not started |

---

## Context

`expected_profit = ₹302` is a point estimate. An operator commits real
capital based on it. They need a band: `₹150 – ₹450 (90 % CI)` is much more
useful for risk-managed decisioning than the point.

The data to compute this exists implicitly in:
- `condition_to_sell_through` stddev (T-302 surfaces it).
- Historical `roi_correlation` from T-205 (model error).
- Per-category return-rate variance (could be tracked).

This task adds explicit per-row confidence intervals on profit, ROI, and
margin — at the row level and aggregated for baskets / lots.

## Files to create / modify

- `intelligence/profit.py` — Monte Carlo or analytical CI computation.
- `intelligence/decision.py` — fold lot-level CI into JSON summary.
- `output/reporter.py` — surface CI columns and lines in the summary.
- `tests/test_profit.py` (or expand `test_condition_aware_economics.py`).
- `README.md`.

## Specification

### CI source variance

For each row, model `expected_profit` as a function of two random variables:

- `sell_through ~ Beta(α, β)` parameterised so `mean = velocity_estimate` and `stddev = settings.profit_assumptions["sell_through_stddev"]` (default 0.10).
- `return_rate ~ Beta(α', β')` with `mean = category_return_rate` and `stddev = 0.05` (default).

### Computation

Use Monte Carlo with N=1000 samples per row (vectorised so the cost is
acceptable on a 5,000-row manifest):

```python
samples_st  = beta_samples(velocity_estimate, sell_through_stddev, N)
samples_rr  = beta_samples(return_rate, return_rate_stddev, N)
samples_revenue = sellable_qty * samples_st * expected_sell_price * (1 - samples_rr)
samples_cost    = ...  # same structure, with returns + holding sampled too
samples_profit  = samples_revenue - samples_cost
```

Per-row outputs:

| Column | Definition |
|---|---|
| `expected_profit_p5`  | 5th percentile of the profit distribution |
| `expected_profit_p50` | median (sanity-checks against `expected_profit`) |
| `expected_profit_p95` | 95th percentile |
| `expected_roi_p5`     | 5th percentile of ROI |
| `expected_roi_p95`    | 95th percentile of ROI |
| `prob_profit_positive`| fraction of samples with profit > 0 |

### Lot summary additions

```json
"profit_band_90pct": {"low": -12_000.0, "median": 157_000.0, "high": 305_000.0},
"roi_band_90pct":    {"low": -3.5,      "median": 37.3,     "high": 65.2},
"prob_lot_profitable": 0.84
```

## Acceptance criteria

- [ ] CSV gains six new CI columns.
- [ ] JSON lot summary includes `profit_band_90pct`, `roi_band_90pct`, `prob_lot_profitable`.
- [ ] Per-row median ≈ existing `expected_profit` (within 1 % for monotonic transforms).
- [ ] Pipeline run on real manifest takes < 2× the current runtime (Monte Carlo cost is bounded).
- [ ] `prob_profit_positive` for high-margin BUY rows is > 0.95; for SKIP rows is < 0.5.

## Test requirements

1. `test_ci_columns_present` — synthesise a row, assert all six CI columns are written.
2. `test_median_matches_point_estimate` — `expected_profit_p50 ≈ expected_profit`.
3. `test_p95_greater_than_p5` — for any row.
4. `test_prob_positive_high_for_profitable_row` — synthesise a row known to be safely profitable; assert `prob_profit_positive > 0.9`.
5. `test_prob_positive_low_for_marginal_row` — synthesise a row near break-even; assert `0.3 < prob_profit_positive < 0.7`.

## Documentation requirements

- [ ] `README.md` § 3 step 6: explain that revenue/profit are now random variables and what CI means.
- [ ] `README.md` § 5 config table: `sell_through_stddev`, `return_rate_stddev`.
- [ ] `intelligence/profit.py` docstring documents the Monte Carlo seed (set explicitly for reproducibility).
- [ ] `intelligence/decision.py` documents the new JSON keys.

## Out of scope

- Bayesian inference on the priors themselves (T-305 covers the priors).
- Multi-variate correlations between sell_through and return_rate.
- Closed-form solutions; Monte Carlo is fine at 1k samples × N rows.

## Risks & considerations

- Monte Carlo determinism: set the random seed deterministically (e.g.
  hash(sku) % 2^32) so two runs on the same manifest produce identical CIs.
- 1k samples × 100k rows = 100M evaluations; vectorise in numpy. If still too
  slow, reduce samples to 500 and document the trade-off.
- The CI is only as good as the variance estimates fed in; document that
  current variances are operator-judgement defaults until T-205/T-302 measure
  them.
