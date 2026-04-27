# T-102 — Add inspection cost for `not_tested` / `unknown`

| Field | Value |
|---|---|
| Phase | 1 (P0) |
| Effort | 3 hours |
| Depends on | — |
| Blocks | T-105 |
| Status | Not started |

---

## Context

The lot-level decision (`intelligence/decision.py`) already prints "Lot is
largely untested — inspection cost dominates" as a reason when `untested_pct >
50`, but the inspection cost itself is **never charged to `expected_cost`**.
On the test manifest (1,367 "Not Tested" items), the engine currently shows a
₹157 K BUY-basket profit that does not subtract a single rupee of inspection.
At a realistic ₹40–₹80/unit for power-on testing of small kitchen appliances,
that's ₹55–110 K of unrecognised cost — enough to flip a 37 % projected ROI to
~10 %.

This task adds an explicit, configurable per-condition inspection-cost-per-unit
and applies it in the profit engine.

## Files to create / modify

- `config/settings.py` — add `INSPECTION_COST_PER_UNIT`.
- `intelligence/profit.py` — apply cost per row.
- `output/reporter.py` — surface `inspection_cost` column (T-105 will batch all the cost-decomposition columns; this task just adds the one).
- `tests/test_cost_engine.py` — add inspection-specific cases.
- `README.md` — config table + data-flow note.

## Specification

### `INSPECTION_COST_PER_UNIT` schema (`config/settings.py`)

```python
# ₹/unit cost of inspecting and testing a unit before listing.
# Only applied to conditions where the platform listing requires a tested
# product (not_tested, unknown, used_*).  ``new`` and ``like_new`` are zero
# because they're either sealed or visibly inspected at intake.
#
# Values are rough operator estimates; tune per category and labour cost.
INSPECTION_COST_PER_UNIT: Mapping[str, float] = {
    "new":         0.0,
    "like_new":    0.0,
    "used_good":  20.0,
    "used_fair":  30.0,
    "not_tested": 50.0,
    "defective":  10.0,   # cursory triage before scrapping
    "unknown":    50.0,
}
```

### `Settings` dataclass

```python
inspection_cost_per_unit: Mapping[str, float] = field(default_factory=lambda: dict(INSPECTION_COST_PER_UNIT))
```

### `intelligence/profit.py` changes

Inside `compute()`, after computing `acquisition_cost`:

```python
inspection_cost = self._resolve_inspection_cost(out, qty)
expected_cost = acquisition_cost + operating_cost + inspection_cost
out["inspection_cost"] = inspection_cost.round(2)
```

Helper:

```python
def _resolve_inspection_cost(self, df: pd.DataFrame, qty: pd.Series) -> pd.Series:
    """Per-row inspection cost = qty × per-condition ₹/unit."""
    table = self.settings.inspection_cost_per_unit
    if "condition_normalized" in df.columns:
        col = df["condition_normalized"].fillna("unknown")
    else:
        col = pd.Series(["unknown"] * len(df), index=df.index)
    per_unit = col.map(lambda c: table.get(c, table["unknown"])).astype(float)
    return qty * per_unit
```

## Acceptance criteria

- [ ] `INSPECTION_COST_PER_UNIT` added to `config/settings.py` with non-zero
      values for `not_tested`, `used_good`, `used_fair`, `unknown` and 0 for
      `new` / `like_new`.
- [ ] `Settings.inspection_cost_per_unit` field exists.
- [ ] `intelligence/profit.py` adds `inspection_cost` column and folds it into
      `expected_cost`.
- [ ] On the real manifest, after T-101 has shipped: BUY-basket profit drops
      meaningfully (~₹55–₹110 K). Lot-level `expected_cost` increases by
      `total_units × ₹50` for the test manifest (it's all `not_tested`).
- [ ] No existing test breaks; `pytest` stays green.

## Test requirements (`tests/test_cost_engine.py`)

1. `test_inspection_cost_zero_for_new_items` — a `new` row should add ₹0 of inspection cost.
2. `test_inspection_cost_for_not_tested_uses_per_unit_rate` — a `not_tested` row, qty=10, ₹50/unit → `inspection_cost == 500.0`.
3. `test_inspection_cost_lowers_profit` — same row evaluated with and without inspection cost; profit drops by exactly the inspection_cost value.
4. `test_inspection_cost_falls_back_to_unknown_for_unrecognised_label` — synthetic condition `"weird_label"` lands at the `unknown` rate.

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` § 5 config table: add row `INSPECTION_COST_PER_UNIT`.
- [ ] `README.md` § 3 step 6 (Profitability) lists `inspection_cost` as a new column and explains *why* `not_tested` carries a real cost (the lot-summary reason that already names it).
- [ ] `intelligence/profit.py` module docstring lists `inspection_cost` in the columns block.
- [ ] `config/settings.py` inline comment cites the ₹/unit basis.

## Out of scope

- Per-category overrides on inspection cost (a stove takes longer to test than a measuring spoon, but T-102 keeps it per-condition).
- Variable inspection cost driven by lot size economies (T-303 capital-cost work might subsume this).

## Risks & considerations

- `defective.inspection = ₹10` represents the time to confirm a unit is truly
  scrap; tune to taste.
- Some operators don't inspect at all and instead rely on customer returns to
  surface defects. They can set all values to 0 in their settings override.
