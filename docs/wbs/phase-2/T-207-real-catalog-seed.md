# T-207 — Seed `FuzzyCatalogPriceProvider` with real top-1k catalog

| Field | Value |
|---|---|
| Phase | 2 (P1) |
| Effort | 10 hours |
| Depends on | — |
| Blocks | T-301 |
| Status | Not started |

---

## Context

`FuzzyCatalogPriceProvider` exists in the codebase but no real catalog has
ever been wired in. The default provider chain is just
`MRPHeuristicPriceProvider`, which returns a deterministic 0.80 × MRP — i.e.
no real market signal anywhere in the pipeline. T-106's match-confidence gate
is dormant for the same reason.

This task ships a curated catalog of the top ~1,000 SKUs in the operator's
common manifest categories (kitchen, electronics, beauty, apparel, home), each
with a real Amazon price and a reasonable wholesale price. Wires it into the
default provider chain.

## Files to create / modify

- `data/catalog/india_top1k_v1.json` — curated catalog (gitignored if
  considered proprietary; otherwise checked in with a clear "rates as of
  [date]" header).
- `enrichment/catalog_loader.py` — loads + validates the JSON catalog.
- `pipeline/run_pipeline.py` — default provider chain becomes
  `[FuzzyCatalogPriceProvider(catalog), MRPHeuristicPriceProvider()]`.
- `tests/test_catalog_loader.py` — schema + happy-path tests.
- `tests/test_pipeline.py` — assert match_confidence is non-trivially > 0 for
  some real-manifest rows.
- `README.md`.

## Specification

### Catalog schema (`data/catalog/india_top1k_v1.json`)

```json
{
  "schema_version": 1,
  "rates_as_of": "2026-04-15",
  "source_notes": "Amazon.in listed prices captured via [method]; wholesale via [source].",
  "items": [
    {
      "product_name": "Pigeon by Stovekraft Cruise Plus 750-Watt Mixer Grinder with 3 Jars",
      "brand": "pigeon",
      "category": "kitchen",
      "amazon_price": 2599.0,
      "wholesale_price": 1800.0,
      "asin": "B07VR7VY1Y",
      "weight_kg": 4.2
    },
    ...
  ]
}
```

`asin` and `weight_kg` are optional but should be supplied where available
for downstream identity resolution and transport calc.

### `enrichment/catalog_loader.py`

```python
def load_catalog(path: str | Path) -> list[dict]:
    """Load and validate a catalog JSON.

    Validates schema_version, rates_as_of (warn if older than 90 days),
    and that each item has at minimum {product_name, amazon_price}.
    Coerces missing wholesale_price to None.
    """
```

### Pipeline default chain

```python
@dataclass
class Pipeline:
    settings: Settings = field(default_factory=get_settings)
    providers: Sequence[PriceProvider] = field(
        default_factory=lambda: (
            FuzzyCatalogPriceProvider(
                catalog=load_catalog(_DEFAULT_CATALOG_PATH),
                confidence_threshold=0.6,
            ),
            MRPHeuristicPriceProvider(),
        )
    )
```

`_DEFAULT_CATALOG_PATH` defaults to `data/catalog/india_top1k_v1.json` but is
overridable via `BULK_INTEL_CATALOG_PATH` env var so operators can swap in
their own.

## Acceptance criteria

- [ ] `data/catalog/india_top1k_v1.json` exists with **at least 1,000 items**, evenly distributed across the canonical categories.
- [ ] Catalog loader rejects malformed entries with a clear error.
- [ ] Default Pipeline uses the catalog + heuristic chain.
- [ ] On the real manifest, a non-trivial fraction of rows now have `match_confidence > 0.6` and `unreliable_match = False`. Record the count in the PR.
- [ ] BUY recommendations on real-catalog-matched rows differ from the synthetic-MRP path (different `real_price` because amazon × 0.7 binds where amazon is real instead of 0.80 × MRP).

## Test requirements (`tests/test_catalog_loader.py`)

1. `test_load_catalog_happy_path` — load the shipped catalog, assert ≥ 1000 items.
2. `test_catalog_schema_required_fields` — synthesise a malformed catalog, assert raises.
3. `test_catalog_age_warning` — set `rates_as_of` to > 90 days ago, capture a warning log.
4. `test_pipeline_uses_catalog_for_known_skus` — synthesise a tiny manifest with one SKU also present in the catalog; assert that row's `match_confidence == 1.0` and `amazon_price` matches the catalog value, not the heuristic.

## Documentation requirements

- [ ] `README.md` § 4 (How to run): mention the catalog + env-var override.
- [ ] `README.md` § 6 (extension points): "How to swap or extend the catalog".
- [ ] Catalog header (in JSON `source_notes`) cites how prices were captured + last-refresh date.

## Out of scope

- Live API scraping of Amazon prices (T-301).
- Continuous catalog refresh.
- Per-state pricing variations.

## Risks & considerations

- A 1,000-item catalog is small. Coverage on a long-tail manifest will still
  miss most rows — those gracefully fall through to `MRPHeuristicPriceProvider`.
- Catalog data is licensed: ensure scraping methodology respects ToS.
- File size: 1,000 entries is ~200 KB JSON. Acceptable in repo. If it grows
  past ~5 MB, move to git-LFS or external storage.
