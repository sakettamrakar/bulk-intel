# T-204 — Lot rollup view (group by SKU / product)

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 4 hours |
| Depends on | — |
| Blocks | — |
| Status | Not started |

---

## Context

The real manifest has 412 identical Pigeon rows + 234 Lifelong rows + … Each
appears as a separate row in the output CSV with identical scores and
recommendations. Operators don't read 1,367 rows — they want a **rolled-up
view**: "Buy 412 of Pigeon Mixer Grinder X at floor ₹318/unit, projected total
profit ₹130 K." Today this requires manual `pandas.groupby` work.

This task adds a second output file: `*_rollup.csv` aggregated by
`(brand, product_name_clean)` (or `sku` when stable across rows).

## Files to create / modify

- `output/reporter.py` — add a `_build_rollup` method.
- `pipeline/run_pipeline.py` — return the new `rollup` path in `outputs`.
- `tests/test_pipeline.py` — assert the rollup file exists and aggregates correctly.
- `README.md` — document the new file.

## Specification

### Rollup grouping key

Use this priority:

1. If the manifest has stable `sku` values (each product appears with the same SKU on every row), group by `sku`.
2. Else group by `(brand_normalised, product_name_clean)`.
3. Fall back to `product_name_clean` only.

Detect via `sku.nunique() / len(df) < 0.5` (lots of duplication implies stable
grouping).

### Aggregation

For each group:

| Column | Aggregation |
|---|---|
| `group_key` | The grouping value |
| `units` | `sum(quantity)` |
| `mrp` | `mean` (rounded) |
| `floor_price` | `mean` (rounded) |
| `real_price` | `mean` |
| `expected_revenue` | `sum` |
| `expected_cost` | `sum` |
| `expected_profit` | `sum` |
| `expected_roi_pct` | re-compute from the summed numbers, NOT mean of per-row ROI |
| `sellability_score` | `mean` |
| `risk_score` | `mean` |
| `condition_normalized` | mode |
| `recommendation` | `_lot_rec(group)` — see below |
| `unit_recommendation_mix` | `"BUY:412 REVIEW:0 SKIP:0"` literal string |

### `_lot_rec(group)` rule

```
if all rows BUY: "BUY"
elif all rows SKIP: "SKIP"
elif majority BUY: "BUY (majority)"
elif majority SKIP: "SKIP (majority)"
else: "REVIEW"
```

### Output file

`<input_stem>_rollup.csv`, sorted by `expected_profit` descending so the
operator's first read is "biggest profit groups".

## Acceptance criteria

- [ ] `output/reporter.py` produces a third file: `<stem>_rollup.csv`.
- [ ] Pipeline `outputs` dict gains a `"rollup"` key.
- [ ] Aggregated `expected_profit` summed across rollup rows ≈ original CSV's `expected_profit` sum (test assertion within rounding).
- [ ] On the real manifest, the rollup is dramatically smaller (~50–100 groups vs 1,367 rows).
- [ ] `expected_roi_pct` in the rollup is computed from summed revenue/cost, not mean of per-row ROI (avoid Simpson's-paradox surprises).

## Test requirements (`tests/test_pipeline.py` or new `tests/test_rollup.py`)

1. `test_rollup_file_present` — pipeline `outputs` includes `"rollup"` key and the file exists.
2. `test_rollup_aggregates_units` — synthesise a manifest with 5 identical rows; rollup should have 1 group with `units=5`.
3. `test_rollup_profit_sums_match_per_row` — `rollup["expected_profit"].sum() ≈ csv["expected_profit"].sum()` within 1 % rounding.
4. `test_rollup_roi_uses_summed_amounts_not_mean` — synthesise a group where per-row ROI mean ≠ summed-ROI; assert rollup uses the latter.
5. `test_rollup_recommendation_majority_logic` — group with 3 BUY + 1 SKIP → "BUY (majority)".

## Documentation requirements

- [ ] `README.md` § 4 (How to run): the third output file is documented.
- [ ] Sample rollup snippet shown in README.
- [ ] `output/reporter.py` module + class docstrings updated.

## Out of scope

- Cross-lot rollup (combining results from multiple manifests).
- A separate JSON rollup summary (defer until an explicit consumer exists).

## Risks & considerations

- Grouping key choice can subtly differ between manifests. Surface the chosen
  key in a `rollup_key` metadata column in the CSV header (or as the first
  CSV row's comment) so the operator can see how rows were merged.
- Some manifests carry per-unit serial-number SKUs (each row a unique tag);
  in that case rollup falls back to `product_name_clean` and groups will be
  bigger than ideal.
