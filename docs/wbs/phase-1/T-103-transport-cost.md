# T-103 — Add category-aware transport cost (weight tiers)

| Field | Value |
|---|---|
| Phase | 1 (P0) |
| Effort | 5 hours |
| Depends on | — |
| Blocks | T-105, T-201 |
| Status | Not started |

---

## Context

A 5 kg gas stove and a 50 g earphone are charged identical operating cost
today. Transport (inbound from manifest origin + outbound to customer or FBA)
is a real ₹/unit cost that varies with item weight class and category. On the
test manifest (Bulk4Traders kitchen lot, mostly bulky items), transport is a
non-trivial ~5–8 % of revenue and is currently invisible.

This task adds a two-step transport model:

1. Map each `category` → a weight tier (`small` / `medium` / `bulky`).
2. Map each tier → a fixed ₹/unit transport cost (intake + outbound combined).

## Files to create / modify

- `config/settings.py` — `CATEGORY_WEIGHT_TIER`, `TRANSPORT_COST_PER_UNIT`.
- `intelligence/profit.py` — apply.
- `output/reporter.py` — surface `transport_cost` column (T-105 batches the rest).
- `tests/test_cost_engine.py`.
- `README.md`.

## Specification

### Config schema (`config/settings.py`)

```python
# Maps each canonical category to a coarse weight tier.  Drives
# TRANSPORT_COST_PER_UNIT below.  Categories not listed default to "medium".
CATEGORY_WEIGHT_TIER: Mapping[str, str] = {
    "stationery":   "small",
    "books":        "small",
    "beauty":       "small",
    "apparel":      "small",
    "toys":         "medium",
    "electronics":  "medium",
    "home":         "medium",
    "kitchen":      "bulky",
    "kitchenware":  "bulky",
    "appliances":   "bulky",
    "unknown":      "medium",
}

# ₹/unit transport (inbound from manifest origin + outbound to customer/FBA).
# Tier values are ballpark India-tier-1-to-tier-2 rates; tune per region.
TRANSPORT_COST_PER_UNIT: Mapping[str, float] = {
    "small":   25.0,
    "medium":  60.0,
    "bulky":  150.0,
}

DEFAULT_WEIGHT_TIER: str = "medium"
```

### `Settings` dataclass

```python
category_weight_tier: Mapping[str, str] = field(default_factory=lambda: dict(CATEGORY_WEIGHT_TIER))
transport_cost_per_unit: Mapping[str, float] = field(default_factory=lambda: dict(TRANSPORT_COST_PER_UNIT))
default_weight_tier: str = "medium"
```

### `intelligence/profit.py` changes

After computing `inspection_cost` (T-102), add:

```python
transport_cost = self._resolve_transport_cost(out, qty)
expected_cost = acquisition_cost + operating_cost + inspection_cost + transport_cost
out["transport_cost"] = transport_cost.round(2)
```

Helper:

```python
def _resolve_transport_cost(self, df: pd.DataFrame, qty: pd.Series) -> pd.Series:
    tier_map = self.settings.category_weight_tier
    cost_map = self.settings.transport_cost_per_unit
    default_tier = self.settings.default_weight_tier
    if "category" in df.columns:
        cat = df["category"].astype("string").str.lower().fillna("unknown")
    else:
        cat = pd.Series(["unknown"] * len(df), index=df.index)
    tier = cat.map(lambda c: tier_map.get(c, default_tier))
    per_unit = tier.map(lambda t: cost_map.get(t, cost_map[default_tier])).astype(float)
    return qty * per_unit
```

## Acceptance criteria

- [ ] `CATEGORY_WEIGHT_TIER`, `TRANSPORT_COST_PER_UNIT`, `DEFAULT_WEIGHT_TIER` exposed in settings.
- [ ] `Settings` dataclass exposes the three new fields.
- [ ] `intelligence/profit.py` adds `transport_cost` column and includes it in `expected_cost`.
- [ ] Pipeline runs end-to-end on the real manifest.
- [ ] On the real manifest (kitchen → bulky tier → ₹150/unit × 1,367 items), `expected_cost` increases by ~₹205 K vs pre-T-103 baseline.

## Test requirements (`tests/test_cost_engine.py`)

1. `test_transport_cost_uses_category_tier` — kitchen → bulky tier → ₹150/unit; assert `transport_cost == qty × 150`.
2. `test_transport_cost_falls_back_to_default_tier` — synthetic category `"foo"` → medium → ₹60.
3. `test_bulky_costs_more_than_small` — same MRP/floor, kitchen vs stationery: `expected_cost` higher for kitchen.
4. `test_transport_cost_scales_with_quantity` — qty=10 vs qty=1 → 10× transport_cost.

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` § 5 config table: add `CATEGORY_WEIGHT_TIER` and `TRANSPORT_COST_PER_UNIT`.
- [ ] `README.md` § 3 step 6: `transport_cost` is a new cost-decomposition column.
- [ ] Inline comments cite tier definitions (kg ranges) and the regional basis (e.g. "India tier-1 → tier-2 rates").
- [ ] `intelligence/profit.py` module docstring updated.

## Out of scope

- Real per-SKU weight from the manifest (manifests rarely carry weights).
- Distance-aware transport (warehouse → customer pin code). T-103 averages it.
- Cubic-volume pricing (volumetric weight). Phase 3 if needed.

## Risks & considerations

- The flat ₹/unit/tier model is wrong at the tails (a 30 kg cooktop is more than
  ₹150 to ship; a 200 g tablet case is less than ₹60). The model accepts that
  imprecision in exchange for not requiring real weights.
- Operators with FBA ship-to-warehouse pricing should override with their
  actual rate cards.
