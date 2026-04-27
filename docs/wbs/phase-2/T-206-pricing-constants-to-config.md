# T-206 — Move `pricing.py` constants to `config/settings.py`

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 2 hours |
| Depends on | — |
| Blocks | — |
| Status | Not started |

---

## Context

`intelligence/pricing.py` hard-codes two business-meaningful constants:

- `amazon_discounted = amazon * 0.7` (line 50) — "Amazon listed price is
  ~70 % realisable for liquidation grade".
- `fallback_category_price = mrp * 0.45` (line 42) — "even with no real
  signal, ~45 % of MRP is a defensible anchor".

These are exactly the kind of business-judgement knobs that belong in
`config/settings.py` so a domain expert can tune them without editing code.
They also hide from Phase-2's backtest harness (T-205) since they're not
visible in the `Settings` dataclass.

## Files to modify

- `intelligence/pricing.py` — read constants from `Settings`.
- `config/settings.py` — add the two new keys.
- `pipeline/run_pipeline.py` — pass settings to PricingEngine.
- `tests/test_pricing_and_scoring.py` — add a test that overriding the constants changes behaviour.
- `README.md`.

## Specification

### Config

```python
PRICING_STRATEGY: Mapping[str, float] = {
    # Liquidation buyers can't realise the full Amazon listed price; this is
    # the conservative discount applied to amazon_price before it competes
    # with the wholesale and fallback anchors in pricing.py.
    "amazon_discount_factor": 0.70,
    # When neither amazon nor wholesale price is available, anchor real_price
    # at this fraction of MRP.
    "fallback_pct_of_mrp": 0.45,
}
```

### `Settings` dataclass

```python
pricing_strategy: Mapping[str, float] = field(default_factory=lambda: dict(PRICING_STRATEGY))
```

### `intelligence/pricing.py` change

Make `PricingEngine` accept settings (it currently takes none). Replace the
two literals with `self.settings.pricing_strategy["amazon_discount_factor"]`
and `["fallback_pct_of_mrp"]`. Update the `compute_pricing_metrics` functional
wrapper to take optional settings.

### Pipeline orchestrator

```python
pricing = PricingEngine(self.settings)
```

## Acceptance criteria

- [ ] `PRICING_STRATEGY` exposed in settings with both keys.
- [ ] `Settings.pricing_strategy` field exists.
- [ ] `intelligence/pricing.py` no longer contains literal `0.7` or `0.45`.
- [ ] Test demonstrates that overriding `amazon_discount_factor` to `1.0` makes `real_price = amazon_price` (when amazon < fallback) — the knob actually works.
- [ ] Pipeline runs end-to-end on real manifest with no behaviour change at default settings.

## Test requirements (`tests/test_pricing_and_scoring.py`)

1. `test_real_price_uses_settings_amazon_discount` — set `amazon_discount_factor=1.0`, confirm `real_price == amazon_price` for rows where amazon < mrp×fallback_pct.
2. `test_real_price_uses_settings_fallback_pct` — set `fallback_pct_of_mrp=0.30`, confirm `real_price` clamps lower for rows where amazon×discount > mrp×0.30.
3. `test_default_settings_match_legacy_constants` — at default settings, `real_price` matches the pre-T-206 legacy values for a fixed input row.

## Documentation requirements

- [ ] `README.md` § 5 config table: add `PRICING_STRATEGY["amazon_discount_factor"]` and `PRICING_STRATEGY["fallback_pct_of_mrp"]`.
- [ ] `intelligence/pricing.py` docstring lists the new dependency on `Settings`.
- [ ] Inline comments cite a source / rationale for the default values.

## Out of scope

- Per-category fallback percentages (apparel might want 0.35; electronics
  0.55). Phase 3.
- Per-condition pricing strategy.

## Risks & considerations

- Changing the default values is *not* part of this task. Defaults must
  reproduce existing behaviour exactly.
