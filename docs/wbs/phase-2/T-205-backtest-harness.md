# T-205 — Backtest harness for threshold calibration

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 8 hours |
| Depends on | T-101..T-104 (real cost engine) |
| Blocks | T-304, T-305, T-306 |
| Status | Not started |

---

## Context

`DECISION_THRESHOLDS` (`buy_score_min=60`, `risk_score_max=60`,
`min_expected_margin_pct=15`, `min_expected_roi_pct=25`,
`min_buy_match_confidence=0.6`) are guesses. There's no calibration loop
against actual realised outcomes. The right tool is a **backtest harness**:
take historical lots where realised ROI is known, run the engine, regress
predicted vs actual, recommend new threshold values.

This is the precondition for any ML / feedback-loop work in Phase 3.

## Files to create / modify

- `tools/backtest.py` — new CLI entry point.
- `tools/__init__.py` — empty.
- `data/historical/` — directory for known-outcome lots (gitignored except
  for an example).
- `data/historical/EXAMPLE_lot_outcomes.csv` — 5 synthetic but realistic
  example outcomes shipped in-repo so the harness has something to run on.
- `tests/test_backtest.py` — covers harness logic.
- `README.md` — backtest section under § 4.
- `.gitignore` — ignore real `data/historical/*.csv` except `EXAMPLE_*`.

## Specification

### `data/historical/` schema

Each row in a "lot outcomes" CSV is one resold SKU with realised numbers.
Required columns:

```
manifest_id,         # which manifest this row came from
sku,
realised_units_sold, # actual units that cleared in the holding period
realised_avg_sale_price,
realised_returns,    # number of units returned
realised_total_cost, # actual cost incurred (acquisition + fees + transport + ...)
realised_holding_days,
notes
```

`EXAMPLE_lot_outcomes.csv` has 5 rows (3 BUY-and-profitable, 1 BUY-but-loss,
1 SKIP-but-would-have-profited) so backtest exercises every quadrant.

### `tools/backtest.py`

```
usage: python -m tools.backtest --manifest MANIFEST_CSV --outcomes OUTCOMES_CSV [--report report.json]

Joins the engine's per-row predictions (run on the manifest) to realised
outcomes (per the outcomes CSV) by sku, and emits a JSON report:

{
  "manifest": "...",
  "rows_predicted": 1367,
  "rows_with_outcome": 142,
  "confusion_matrix": {
    "BUY-profitable":   55,
    "BUY-loss":          7,
    "SKIP-would-profit": 12,
    "SKIP-correct":      68
  },
  "predicted_vs_actual": {
    "roi_correlation": 0.62,
    "profit_mae":      28.4,
    "calibration_slope": 0.74,
    "calibration_intercept": -3.1
  },
  "threshold_sweep": {
    "buy_score_min":          {"30": {...}, "40": {...}, ..., "90": {...}},
    "min_expected_roi_pct":   {"10": {...}, "15": {...}, ..., "60": {...}},
    "min_expected_margin_pct":{"5": {...},  "10": {...}, ..., "30": {...}}
  },
  "recommended_thresholds": {
    "buy_score_min": 65.0,
    "min_expected_roi_pct": 30.0,
    "min_expected_margin_pct": 12.0
  }
}
```

`threshold_sweep` runs the engine N times with each threshold varied
independently (others held at default) and reports the resulting precision /
recall / realised-profit-on-BUY-basket. `recommended_thresholds` picks the
arg-max of "realised profit on BUY basket weighted by precision".

### Confusion matrix definitions

A row is:
- **BUY-profitable** if `recommendation == "BUY"` and realised `unit_profit > 0`.
- **BUY-loss** if `recommendation == "BUY"` and realised `unit_profit ≤ 0`.
- **SKIP-correct** if `recommendation == "SKIP"` and realised `unit_profit ≤ 0`.
- **SKIP-would-profit** if `recommendation == "SKIP"` and realised `unit_profit > 0`.
- **REVIEW**: excluded from the matrix (separate REVIEW-precision metric).

### Realised unit profit

`realised_unit_profit = (realised_avg_sale_price × (units_sold - returns) - realised_total_cost) / units_sold`.

## Acceptance criteria

- [ ] `python -m tools.backtest --manifest data/sample_manifest.csv --outcomes data/historical/EXAMPLE_lot_outcomes.csv --report /tmp/r.json` runs without error.
- [ ] Report JSON contains all four blocks (`confusion_matrix`, `predicted_vs_actual`, `threshold_sweep`, `recommended_thresholds`).
- [ ] `recommended_thresholds` are real numbers in plausible ranges.
- [ ] At least one outcome row joins to a manifest row (ship matching IDs in the example).
- [ ] Pipeline tests still green.

## Test requirements (`tests/test_backtest.py`)

1. `test_backtest_runs_on_example_data` — invoke the CLI, assert exit code 0 and JSON report parses.
2. `test_confusion_matrix_counts_match_synthetic` — synthesise 5 rows with known outcomes, assert each row lands in the right bucket.
3. `test_predicted_vs_actual_correlation_in_range` — `roi_correlation ∈ [-1, 1]`.
4. `test_threshold_sweep_monotonicity` — when `buy_score_min` rises, BUY count never increases (monotone).

## Documentation requirements

- [ ] `README.md` § 4 (How to run): a "Backtest" subsection with the CLI invocation.
- [ ] `tools/backtest.py` module docstring describes the inputs, outputs, and confusion-matrix definitions verbatim.
- [ ] `data/historical/EXAMPLE_lot_outcomes.csv` ships with a header comment row (or sibling `README.md`) explaining the schema.
- [ ] `.gitignore` excludes real lot data; comment in the gitignore says why.

## Out of scope

- Multi-objective optimisation across multiple thresholds simultaneously.
- Bayesian / probabilistic threshold tuning. Phase 3.
- Real outcomes ingestion via API (CSV in, JSON out for now).

## Risks & considerations

- Outcome data is highly sensitive (real margins). Hence gitignore real files
  by default and ship only a synthetic example in-repo.
- Threshold sweep at every percentile is expensive on a 100k-row manifest;
  cap the sweep to 7-10 candidate values per knob.
- The confusion-matrix bucketing has a free parameter (what counts as
  "profitable" — break-even? > 5 %?). Default to `> 0`; expose as `--profit-cutoff`.
