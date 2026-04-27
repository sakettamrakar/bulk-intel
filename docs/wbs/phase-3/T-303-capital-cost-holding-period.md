# T-303 — Capital cost / holding-period model

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 6 hours |
| Depends on | T-104 (return rate model) |
| Blocks | — |
| Status | Not started |

---

## Context

Inventory that takes 90 days to clear ties up working capital and pays
warehouse rent, neither of which appear in `expected_cost` today. A 30 %
projected ROI over 6 months is annualised ~60 %, but that's before subtracting
the ~14 % cost of capital + storage. For slow-clearing categories this
inverts the BUY decision.

This task introduces:

1. Per-category expected `holding_period_days`.
2. A `capital_cost_per_year_pct` knob (cost of capital + storage blended).
3. Folds `holding_period_days × capital_cost_per_year_pct / 365 × lot_cost`
   into `expected_cost`.

## Files to create / modify

- `config/settings.py` — `CATEGORY_HOLDING_DAYS`, `CAPITAL_COST_PER_YEAR_PCT`.
- `intelligence/profit.py` — apply.
- `output/reporter.py` — `holding_cost` column.
- `tests/test_cost_engine.py`.
- `README.md`.

## Specification

### Config

```python
# Expected days of inventory holding from purchase to last unit cleared.
# Pulled from operator's category-specific historical clearance curves.
CATEGORY_HOLDING_DAYS: Mapping[str, int] = {
    "electronics":  60,
    "appliances":   75,
    "kitchen":      90,
    "kitchenware":  90,
    "home":         90,
    "apparel":      120,    # seasonal, slow
    "beauty":       60,
    "toys":         100,
    "books":        180,    # long tail
    "stationery":   120,
    "unknown":      90,
}

# Annualised cost of capital + storage (warehouse rent + WIP financing).
CAPITAL_COST_PER_YEAR_PCT: float = 0.18

DEFAULT_HOLDING_DAYS: int = 90
```

### `intelligence/profit.py` change

```python
holding_days = self._resolve_holding_days(out)
holding_cost = (
    qty * floor                                               # capital tied up
    * self.settings.capital_cost_per_year_pct
    * holding_days / 365.0
)
expected_cost = (
    acquisition_cost
    + operating_cost
    + inspection_cost
    + transport_cost
    + return_provision
    + holding_cost
)
out["holding_days"] = holding_days
out["holding_cost"] = holding_cost.round(2)
```

## Acceptance criteria

- [ ] `CATEGORY_HOLDING_DAYS`, `CAPITAL_COST_PER_YEAR_PCT`, `DEFAULT_HOLDING_DAYS` in settings.
- [ ] `Settings` dataclass exposes them.
- [ ] CSV gains `holding_days` and `holding_cost` columns.
- [ ] Books / stationery rows show notably more holding cost than electronics for equal lot cost.
- [ ] On the real manifest (kitchen, 90 days), holding cost ≈ `lot_cost × 0.18 × 90/365 ≈ 4.4 % of lot_cost`. Test asserts this within rounding.

## Test requirements

1. `test_holding_cost_zero_when_holding_days_zero` — set days to 0 → holding_cost == 0.
2. `test_holding_cost_scales_linearly_with_days` — 30 days vs 90 days → 3× holding_cost for same lot.
3. `test_holding_cost_uses_category_default` — apparel row with no override → 120 days.
4. `test_books_more_expensive_to_hold_than_electronics` — same lot_cost, books vs electronics: holding_cost is higher for books.

## Documentation requirements

- [ ] `README.md` § 5 config table: add `CATEGORY_HOLDING_DAYS`, `CAPITAL_COST_PER_YEAR_PCT`.
- [ ] `README.md` § 3 step 6: holding cost is now a cost component.
- [ ] Inline comment cites the cost-of-capital basis (RBI repo + warehouse rent estimate).

## Out of scope

- Per-SKU historical clearance distributions (T-302 territory).
- Variable holding cost (high-velocity SKUs hold less). Phase 4.

## Risks & considerations

- The 18 % cost of capital is operator-specific; some self-funded operators
  use 10 %, leveraged operators use 20+. Easy to tune.
- Holding-day priors must be revisited annually as marketplace velocity
  changes (e.g. Amazon's storage fee changes shift effective holding cost).
