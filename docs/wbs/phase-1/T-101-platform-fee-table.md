# T-101 — Decompose `operating_cost_pct` into platform × category fee table

| Field | Value |
|---|---|
| Phase | 1 (P0 — must ship before any real money is spent) |
| Effort | 6 hours |
| Depends on | — |
| Blocks | T-104, T-105, T-201, T-205 |
| Status | Not started |

---

## Context

Today `intelligence/profit.py` charges every line item a flat
`operating_cost_pct = 0.25` of revenue. This single number is meant to substitute
for **all** post-purchase costs — Amazon/Flipkart/Meesho commissions, closing /
referral fees, FBA storage, fulfilment, payment-gateway, GST. Real Amazon fees
in India vary **5–30 % by category** alone. A single flat number is
miscalibrated by 10+ percentage points either way, which is the difference
between a profitable lot and a loss.

The audit (`docs/audit/2026-04-27-liquidation-framework-audit.md` § Layer 4) flags
this as the **single biggest risk to capital**.

This task replaces the flat number with a structured `PLATFORM_FEES` lookup
keyed on (platform, category). Until T-201 ships, all rows route to a single
default platform; T-101 just makes the table real.

## Files to create / modify

- `config/settings.py` — add `PLATFORM_FEES`, `DEFAULT_PLATFORM`, deprecate `operating_cost_pct` (or keep as a fallback default for unknown platform/category combos).
- `intelligence/profit.py` — read fees from the table; if a row carries no `platform` column, use `DEFAULT_PLATFORM`.
- `output/reporter.py` — surface a `platform_fee_pct` column per row (T-105 will add the rest).
- `tests/test_cost_engine.py` — new file.
- `README.md` — update config table (per `CLAUDE.md`).

## Specification

### `PLATFORM_FEES` schema (`config/settings.py`)

```python
# Per-platform, per-category fee as a fraction of revenue.
# Sources cited inline; verify against current rate cards quarterly.
#
# Each entry is the *all-in* commission an operator pays the platform on
# revenue (commission + closing fee + payment-gateway + platform-specific
# fulfilment if not separately modelled).  GST on commission is included.
#
# When a (platform, category) pair is missing, fall back to
# PLATFORM_FEES[platform]["__default__"], then to FALLBACK_OPERATING_COST_PCT.
PLATFORM_FEES: Mapping[str, Mapping[str, float]] = {
    "amazon": {
        # Source: Amazon India Seller Central Fee Schedule (Q1 2026).
        "electronics":  0.085,
        "appliances":   0.115,
        "kitchen":      0.155,
        "kitchenware":  0.155,
        "home":         0.165,
        "apparel":      0.175,
        "beauty":       0.195,
        "toys":         0.155,
        "books":        0.075,
        "stationery":   0.095,
        "__default__":  0.155,
    },
    "flipkart": {
        # Source: Flipkart Seller Hub India (Q1 2026).
        "electronics":  0.090,
        "appliances":   0.110,
        "kitchen":      0.140,
        "kitchenware":  0.140,
        "home":         0.155,
        "apparel":      0.180,
        "beauty":       0.210,
        "toys":         0.150,
        "books":        0.060,
        "stationery":   0.085,
        "__default__":  0.150,
    },
    "meesho": {
        # Source: Meesho Supplier Panel (Q1 2026); flat 0% commission for many
        # categories, monetisation via shipping + ads.  Approximate effective rate.
        "electronics":  0.040,
        "appliances":   0.040,
        "kitchen":      0.030,
        "kitchenware":  0.030,
        "home":         0.030,
        "apparel":      0.020,
        "beauty":       0.030,
        "toys":         0.030,
        "books":        0.020,
        "stationery":   0.020,
        "__default__":  0.030,
    },
    "b2b": {
        # B2B / kabadi reseller channel — operator just absorbs a flat handling fee.
        "__default__":  0.080,
    },
}

DEFAULT_PLATFORM: str = "amazon"

# Last-resort fallback used only when both platform and category are unknown.
# Kept deliberately conservative.
FALLBACK_OPERATING_COST_PCT: float = 0.18

# Payment-gateway / closing-fee / packaging delta over and above the
# platform commission.  Empirically ~3-6 % of revenue across platforms.
ANCILLARY_REVENUE_FEE_PCT: float = 0.04
```

### `Settings` dataclass

Expose the new tunables via `config.settings.Settings` so the existing pattern
holds. Add fields:

```python
platform_fees: Mapping[str, Mapping[str, float]] = field(default_factory=lambda: ...)
default_platform: str = "amazon"
fallback_operating_cost_pct: float = 0.18
ancillary_revenue_fee_pct: float = 0.04
```

### `intelligence/profit.py` changes

Replace this block:

```python
operating_cost = expected_revenue * a.get("operating_cost_pct", 0.25)
```

with:

```python
platform_fee_pct = self._resolve_platform_fee_pct(out)   # pd.Series, per row
ancillary_pct = self.settings.ancillary_revenue_fee_pct
operating_cost = expected_revenue * (platform_fee_pct + ancillary_pct)
out["platform_fee_pct"] = platform_fee_pct.round(4)
```

Add a private helper:

```python
def _resolve_platform_fee_pct(self, df: pd.DataFrame) -> pd.Series:
    """Return per-row platform commission fraction.

    Looks up ``PLATFORM_FEES[platform][category]`` with these fallbacks:
      1. exact (platform, category)
      2. ``PLATFORM_FEES[platform]["__default__"]``
      3. ``FALLBACK_OPERATING_COST_PCT``
    """
```

The `platform` column is read off the DataFrame if present (T-201 will
populate it); otherwise the helper uses `settings.default_platform`.

The `operating_cost_pct` key in `PROFIT_ASSUMPTIONS` should be removed in this
task. Anyone tuning fees now reaches for `PLATFORM_FEES`, not the old single
knob — do not preserve a deprecated alias.

## Acceptance criteria

- [ ] `config/settings.py` exposes `PLATFORM_FEES` (3+ platforms × 10+ categories), `DEFAULT_PLATFORM`, `FALLBACK_OPERATING_COST_PCT`, `ANCILLARY_REVENUE_FEE_PCT`.
- [ ] `Settings` dataclass exposes the four new fields with defaults.
- [ ] `PROFIT_ASSUMPTIONS["operating_cost_pct"]` is removed (no deprecation alias).
- [ ] `intelligence/profit.py` no longer references `operating_cost_pct`; instead consumes `platform_fees` + `ancillary_revenue_fee_pct`.
- [ ] Output CSV gains a `platform_fee_pct` column (per row).
- [ ] Pipeline runs end-to-end on `data/e8c203803afa10d11e3844dd57636779.xlsx` without error.
- [ ] On that real manifest, BUY-basket projected ROI changes meaningfully (kitchen on Amazon ≈ 15–17 % fees vs the old flat 25 %, so projected revenue × cost ratio improves).

## Test requirements (`tests/test_cost_engine.py`)

Create a new file with at minimum:

1. `test_platform_fee_lookup_uses_table_value` — pass a row with `platform="amazon"`, `category="electronics"` and assert `platform_fee_pct ≈ 0.085`.
2. `test_platform_fee_falls_back_to_platform_default` — `platform="amazon"`, `category="unknown_cat"` → `0.155` (`amazon.__default__`).
3. `test_platform_fee_falls_back_to_global_default` — `platform="meta"` (unknown), `category="anything"` → `FALLBACK_OPERATING_COST_PCT`.
4. `test_default_platform_used_when_column_missing` — DataFrame without a `platform` column uses `settings.default_platform`.
5. `test_apparel_costs_more_than_kitchen` — same revenue & cost inputs, apparel fees > kitchen fees, so apparel `expected_profit < kitchen expected_profit`.

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` config table updated: replace the `operating_cost_pct` row with `PLATFORM_FEES` and `ANCILLARY_REVENUE_FEE_PCT`.
- [ ] `README.md` § 3 (Data flow) step 6 (Profitability): note that operating cost is now `platform_fees[platform][category] + ancillary_revenue_fee_pct`.
- [ ] `intelligence/profit.py` docstring lists the new `platform_fee_pct` column.
- [ ] `config/settings.py` inline comment on every new constant explains units, source, and last-verified date.

## Out of scope (do **not** include in this task)

- Channel routing logic (T-201).
- Transport cost (T-103).
- Return rate (T-104).
- Inspection cost (T-102).
- Cost decomposition CSV columns beyond `platform_fee_pct` (T-105).

## Risks & considerations

- The fee numbers in this task are reasonable Q1 2026 benchmarks but **must be
  verified against current rate cards before commercial use**. Cite sources in
  the inline comment with the date.
- Amazon-India fee tiers depend on item price brackets too (e.g. closing fees
  step up at ₹500 / ₹1000 thresholds). T-101 keeps it at the category level for
  simplicity; price-bracket precision is a Phase-3 enhancement.
- Removing `operating_cost_pct` is a breaking change for any external consumer
  of the config; flag it in the commit message.
