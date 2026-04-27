# T-201 — Channel router (Amazon / Flipkart / Meesho / B2B)

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 8 hours |
| Depends on | T-101 (platform-fee table) |
| Blocks | T-205 |
| Status | Not started |

---

## Context

Today every row gets one set of fee/return assumptions. A real liquidation
flipper routes by category × brand × condition × price band:

- Branded electronics → Amazon (premium, FBA, ~12 % fees)
- Apparel & home → Meesho (low fees, social commerce)
- Bulky kitchen → Flipkart or category-specific marketplaces (transport-aware)
- Damaged / defective → B2B reseller (cents on the rupee, but moves)

This task introduces a `ChannelRouter` that assigns each row a `platform` based
on a deterministic rule chain. T-101's `PLATFORM_FEES` then computes
platform-specific economics, so the same row can be re-evaluated against
different platforms.

## Files to create / modify

- `intelligence/channel.py` — new module with `ChannelRouter`.
- `config/settings.py` — `CHANNEL_ROUTING_RULES` (ordered list of rules).
- `pipeline/run_pipeline.py` — wire the router between `cleaner` and `enricher` (so the platform column is set early enough that downstream stages see it).
- `intelligence/profit.py` — already T-101-aware; nothing extra here.
- `output/reporter.py` — `platform` becomes a primary column.
- `intelligence/decision.py` — add platform-mix to the lot summary JSON.
- `tests/test_channel_router.py` — new file.
- `README.md`.

## Specification

### Rule schema (`config/settings.py`)

```python
# Ordered list of routing rules.  First match wins.  Each rule is a dict:
#   condition: tuple of column-value predicates as keyword args.  All must match.
#   platform: one of "amazon", "flipkart", "meesho", "b2b".
# The terminal rule (no conditions) catches everything that didn't match above.
CHANNEL_ROUTING_RULES: tuple[Mapping[str, object], ...] = (
    # Confirmed-defective inventory always exits via B2B regardless of category.
    {"condition": {"condition_normalized": ("defective", "salvage")}, "platform": "b2b"},
    # Branded electronics → Amazon if price band is MID/HIGH (Amazon shoppers
    # pay for brand assurance).  LOW-price electronics go to Flipkart.
    {"condition": {"category": "electronics", "brand_known": True, "price_band": ("MID", "HIGH")}, "platform": "amazon"},
    {"condition": {"category": "electronics"}, "platform": "flipkart"},
    # Apparel + home goods → Meesho (low fees, social commerce, price-sensitive
    # buyer base — fits liquidation pricing).
    {"condition": {"category": ("apparel", "home")}, "platform": "meesho"},
    # Beauty → Amazon (cataloged, brand-led, returns are recoverable).
    {"condition": {"category": "beauty"}, "platform": "amazon"},
    # Bulky kitchen → Flipkart by default (Amazon FBA storage on bulky is dear).
    {"condition": {"category": ("kitchen", "kitchenware", "appliances")}, "platform": "flipkart"},
    # Catch-all
    {"condition": {}, "platform": "amazon"},
)
```

`brand_known` is a synthetic predicate that resolves to
`brand.lower() in settings.known_brands`.

### `ChannelRouter` (`intelligence/channel.py`)

```python
@dataclass(frozen=True)
class ChannelRouter:
    settings: Settings

    def route(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of df with a ``platform`` column populated."""
        out = df.copy()
        platforms = []
        for _, row in out.iterrows():
            platforms.append(self._match_row(row))
        out["platform"] = platforms
        return out

    def _match_row(self, row: pd.Series) -> str:
        for rule in self.settings.channel_routing_rules:
            cond = rule["condition"]
            if all(_predicate_matches(row, k, v, self.settings) for k, v in cond.items()):
                return rule["platform"]
        return self.settings.default_platform
```

`_predicate_matches` handles:
- scalar value: row[k] == v
- tuple/list value: row[k] in v
- `brand_known`: row["brand"].lower() in settings.known_brands

### Pipeline wiring

In `pipeline/run_pipeline.py`, insert after cleaner:

```python
df = cleaner.clean(df)
df = ChannelRouter(self.settings).route(df)
df = enricher.enrich(df)
...
```

### Lot summary additions (`intelligence/decision.py`)

Add to JSON:

```json
"platform_mix": {
  "amazon":   {"items": 412, "expected_revenue": 320500.0, "expected_profit": 92100.0},
  "flipkart": {"items": 154, "expected_revenue":  88200.0, "expected_profit": 18400.0},
  "meesho":   {"items":   0, "expected_revenue":      0.0, "expected_profit":     0.0},
  "b2b":      {"items":   0, "expected_revenue":      0.0, "expected_profit":     0.0}
}
```

## Acceptance criteria

- [ ] `intelligence/channel.py` exists with `ChannelRouter` class.
- [ ] `config/settings.py` exposes `CHANNEL_ROUTING_RULES`.
- [ ] `Settings` dataclass exposes `channel_routing_rules`.
- [ ] Pipeline orchestrator routes between cleaning and enrichment.
- [ ] Every row has a `platform ∈ {amazon, flipkart, meesho, b2b}`.
- [ ] Same row evaluated under different platforms produces different `expected_profit` (different `PLATFORM_FEES`).
- [ ] On the real manifest, the platform mix is non-trivial (not all rows on one platform).
- [ ] JSON lot summary contains `platform_mix` block.

## Test requirements (`tests/test_channel_router.py`)

1. `test_defective_routes_to_b2b` — `condition_normalized="defective"` → `platform="b2b"` regardless of category.
2. `test_branded_electronics_mid_band_routes_to_amazon` — `category="electronics"`, brand in `KNOWN_BRANDS`, MID price band → amazon.
3. `test_low_band_electronics_routes_to_flipkart` — same but LOW band → flipkart.
4. `test_apparel_routes_to_meesho` — `category="apparel"` → meesho regardless of brand.
5. `test_unknown_category_uses_default_platform` — synthetic category → `settings.default_platform`.
6. `test_apparel_on_meesho_more_profitable_than_amazon` — same row, force routing to meesho vs amazon, meesho profit > amazon profit (because meesho fees are lower).

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` § 1 (data-flow diagram): insert a "Channel Routing" box between Cleaning and Enrichment.
- [ ] `README.md` § 3: add a stage 2.5 / step describing routing.
- [ ] `README.md` § 5 config table: `CHANNEL_ROUTING_RULES`.
- [ ] `README.md` § 6 (extension points): "How to add a new platform".
- [ ] `intelligence/channel.py` module docstring + class docstring.

## Out of scope

- ML-based routing (rule-based is sufficient for v1).
- Per-state / regional routing (some platforms underperform in tier-3 cities).
- Multi-channel listings of the same SKU (cross-listing). T-201 picks one platform per row.

## Risks & considerations

- Rule-ordering sensitivity. Document the "first match wins" semantics
  prominently and cover with a regression test.
- Operators may want to override the rule table per lot (e.g. they have a
  Meesho promotion this month). Keep the rules as a constructor-injected list,
  not a hardcoded module constant inside the router.
