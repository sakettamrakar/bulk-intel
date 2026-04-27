# T-104 — Add return-rate model (per category)

| Field | Value |
|---|---|
| Phase | 1 (P0) |
| Effort | 5 hours |
| Depends on | T-101 (platform-fee table) |
| Blocks | T-105, T-301, T-303 |
| Status | Not started |

---

## Context

Today the engine assumes 100 % of sold inventory stays sold. Real return
rates are a major operating cost:

| Category | Typical India return rate |
|---|---|
| Apparel | 18–30 % |
| Beauty | 8–12 % |
| Electronics | 10–15 % |
| Home & kitchen | 5–10 % |
| Books | 3–5 % |

Each return costs reverse logistics + restocking + occasionally a write-off.
Without a return model, apparel lots will look profitable on paper and bleed
cash on real returns.

## Files to create / modify

- `config/settings.py` — `CATEGORY_RETURN_RATE`, `RETURN_HANDLING_COST_PCT`.
- `intelligence/profit.py` — apply to revenue and add a separate cost component.
- `output/reporter.py` — surface `return_provision` (T-105 batches the rest).
- `tests/test_cost_engine.py`.
- `README.md`.

## Specification

### Config schema (`config/settings.py`)

```python
# Per-category fraction of sold units that are returned.  Returned units
# generate full reverse-logistics cost and (often) cannot be re-listed
# at full price; we model both effects below.
CATEGORY_RETURN_RATE: Mapping[str, float] = {
    "electronics":  0.13,
    "appliances":   0.10,
    "kitchen":      0.07,
    "kitchenware":  0.07,
    "home":         0.06,
    "apparel":      0.22,    # sizing + colour mismatch dominate
    "beauty":       0.10,
    "toys":         0.08,
    "books":        0.04,
    "stationery":   0.03,
    "unknown":      0.10,
}

# Cost of handling a return as a fraction of the unit sale price
# (reverse shipping + restocking + partial write-off blended).
RETURN_HANDLING_COST_PCT: float = 0.30

DEFAULT_RETURN_RATE: float = 0.10
```

### `Settings` dataclass

```python
category_return_rate: Mapping[str, float] = field(default_factory=lambda: dict(CATEGORY_RETURN_RATE))
return_handling_cost_pct: float = 0.30
default_return_rate: float = 0.10
```

### `intelligence/profit.py` changes

The model in this task:

```python
return_rate = self._resolve_return_rate(out)            # pd.Series, fraction
gross_revenue = sellable_qty * expected_sell_price * price_realization
# Net revenue: returned units don't keep the sale.
expected_revenue = gross_revenue * (1.0 - return_rate)
# Return-handling cost: each returned unit's sale price × handling pct.
return_provision = gross_revenue * return_rate * self.settings.return_handling_cost_pct

expected_cost = (
    acquisition_cost
    + operating_cost            # T-101
    + inspection_cost           # T-102
    + transport_cost            # T-103
    + return_provision          # T-104
)
out["return_rate"] = return_rate.round(4)
out["return_provision"] = return_provision.round(2)
```

Helper:

```python
def _resolve_return_rate(self, df: pd.DataFrame) -> pd.Series:
    table = self.settings.category_return_rate
    if "category" in df.columns:
        cat = df["category"].astype("string").str.lower().fillna("unknown")
    else:
        cat = pd.Series(["unknown"] * len(df), index=df.index)
    return cat.map(lambda c: table.get(c, self.settings.default_return_rate)).astype(float)
```

> **Implementation note**: revenue is now *net* of returns. ROI / margin
> calculations downstream therefore incorporate returns automatically. Do not
> double-deduct return costs.

## Acceptance criteria

- [ ] `CATEGORY_RETURN_RATE`, `RETURN_HANDLING_COST_PCT`, `DEFAULT_RETURN_RATE` in settings.
- [ ] `Settings` dataclass exposes the three new fields.
- [ ] `intelligence/profit.py` reduces `expected_revenue` by `(1 - return_rate)` and adds `return_provision` to `expected_cost`.
- [ ] CSV gains `return_rate` and `return_provision` columns.
- [ ] On the real (kitchen) manifest, expected revenue drops by ~7 % (return rate) and `return_provision` adds ~2 % of gross revenue back to cost.
- [ ] Apparel test rows show notably lower projected profit than equivalent kitchen rows (test below).

## Test requirements (`tests/test_cost_engine.py`)

1. `test_return_rate_lookup_uses_category` — `category="apparel"` → `return_rate == 0.22`.
2. `test_return_rate_falls_back_to_default` — unknown category → `default_return_rate`.
3. `test_returns_reduce_revenue_proportionally` — same row evaluated with `return_rate=0` vs `0.20`: net revenue drops by exactly 20 %.
4. `test_returns_add_handling_cost_proportional_to_returned_units` — given `return_rate=0.20`, `RETURN_HANDLING_COST_PCT=0.30`, `gross_revenue=1000`: `return_provision == 1000 × 0.20 × 0.30 == 60`.
5. `test_apparel_less_profitable_than_kitchen_at_equal_inputs` — identical mrp/floor/qty/price, only category differs: apparel `expected_profit < kitchen expected_profit`.

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` config table: add `CATEGORY_RETURN_RATE`, `RETURN_HANDLING_COST_PCT`.
- [ ] `README.md` § 3 step 6: explain that revenue is net of returns and `return_provision` is in cost.
- [ ] `intelligence/profit.py` docstring lists `return_rate` and `return_provision` columns; note the net-of-returns convention.
- [ ] Inline source comment on the rate table.

## Out of scope

- Per-SKU return rate from a learned model (T-302 / T-304).
- Time-decay on return rate (returns concentrate in first 30 days).
- Asymmetric per-platform return policies (Meesho returns differ from Amazon).

## Risks & considerations

- The 22 % apparel return rate is plausibly conservative for fashion apparel
  but high for innerwear / accessories. Operators may want subcategory tables.
- `RETURN_HANDLING_COST_PCT = 0.30` is a blend of shipping (~₹50–₹100 reverse)
  and write-off probability. Tune with realised data.
