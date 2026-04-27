# T-105 — Surface cost decomposition in CSV + JSON

| Field | Value |
|---|---|
| Phase | 1 (P0) |
| Effort | 2 hours |
| Depends on | T-101, T-102, T-103, T-104 |
| Blocks | — |
| Status | Not started |

---

## Context

After T-101..T-104 the engine computes five cost components per row:
`acquisition_cost`, `platform_fee_pct` × revenue, `inspection_cost`,
`transport_cost`, `return_provision`. The operator must be able to **audit
every cost line for every BUY recommendation** to trust the projection. This
task makes the decomposition visible in both the CSV (per-row) and the JSON lot
summary (aggregated).

## Files to create / modify

- `output/reporter.py` — extend `PRIMARY_COLUMNS` and the per-basket summary.
- `intelligence/decision.py` — add aggregated cost breakdown to the lot JSON.
- `tests/test_pipeline.py` — assert new columns / keys exist.
- `README.md` — sample report block updated.

## Specification

### CSV columns (per row, in `output/reporter.py:PRIMARY_COLUMNS`)

Insert immediately after `expected_cost`:

```
expected_cost,
  acquisition_cost,        # qty × floor × (1 + acquisition_overhead_pct)
  platform_fee_pct,        # T-101
  ancillary_revenue_fee_pct,# T-101 (constant for now)
  platform_fee_amount,     # gross_revenue × (platform_fee_pct + ancillary)
  inspection_cost,         # T-102
  transport_cost,          # T-103
  return_rate,             # T-104
  return_provision,        # T-104
```

`profit.py` already produces most of these; this task adds the two derived
*amount* columns (`acquisition_cost`, `platform_fee_amount`) and ensures all
flow through to the CSV.

### Plain-text summary (`output/reporter.py:_build_summary`)

Add a per-basket **cost decomposition table**:

```
--- BUY basket cost decomposition (566 items) ---
  acquisition           :     312,456.00   (74.2 %)
  platform fees         :      66,890.00   (15.9 %)
  inspection            :      28,300.00   (6.7 %)
  transport             :       8,490.00   (2.0 %)
  return provision      :       4,844.00   (1.2 %)
  --------
  total cost            :     420,980.00
```

Show it for both BUY and REVIEW baskets.

### JSON lot summary (`intelligence/decision.py`)

Add an `expected_cost_breakdown` block:

```json
"expected_cost_breakdown": {
  "acquisition":       312456.0,
  "platform_fees":      66890.0,
  "inspection":         28300.0,
  "transport":           8490.0,
  "return_provision":    4844.0,
  "total":             420980.0
}
```

## Acceptance criteria

- [ ] CSV gains all eight new columns (`acquisition_cost`, `platform_fee_pct`, `ancillary_revenue_fee_pct`, `platform_fee_amount`, `inspection_cost`, `transport_cost`, `return_rate`, `return_provision`).
- [ ] Plain-text summary includes a cost-decomposition table per non-empty basket (BUY, REVIEW).
- [ ] JSON lot summary includes `expected_cost_breakdown`.
- [ ] All existing test assertions still hold; expand `tests/test_pipeline.py` `expected_keys` to include the new JSON key (and any sub-keys you want guaranteed).
- [ ] On the real manifest, the breakdown sums to the existing `expected_cost` total (assertion in test).

## Test requirements (`tests/test_pipeline.py`, plus add file as needed)

1. `test_cost_breakdown_keys_present_in_json` — assert `expected_cost_breakdown` key with the six sub-keys is in the lot JSON.
2. `test_cost_breakdown_sums_to_total_cost` — within rounding, `sum(breakdown values except total) == breakdown["total"]` and `breakdown["total"] ≈ df["expected_cost"].sum()`.
3. `test_csv_includes_all_cost_components` — read the CSV, assert every column from the spec exists.

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` § 3 step 9 (Output): list the new columns and JSON key.
- [ ] `README.md` § 4 (How to run) — update the sample summary block to show the breakdown.
- [ ] `output/reporter.py` module docstring lists every output column the file is responsible for.
- [ ] `intelligence/decision.py` docstring documents the new `expected_cost_breakdown` JSON key.

## Out of scope

- Reordering existing columns.
- Per-platform breakdown (T-201 will add that once channel routing exists).

## Risks & considerations

- The summary table can get visually noisy on small lots. Acceptable trade-off
  — the operator's primary read is via the CSV anyway.
- Column ordering matters for downstream consumers; document in the README so
  dashboards can pin to the contract.
