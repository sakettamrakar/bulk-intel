# T-310 — Canonical product groups (search-ready groupings)

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 8 hours |
| Depends on | T-307 (provides `sku_cluster_id` + model-token regex) |
| Blocks | T-311 |
| Status | Implemented |

---

## Context

T-307 attaches three cluster-id columns to each row. That's enough for
homogeneity scoring and rollups, but it's **not enough to drive SERP**:

- A SERP backend bills per query. We must search *one query per group*, not
  one query per row, on a 12k-row manifest. T-307 has clusters but no
  per-group representative title and no group-level aggregates.
- A query like "Logitech Wireless Mouse M185 Black 100 pack" returns garbage.
  We need a deliberately lossy **search signature** ("logitech mouse m185")
  that collapses irrelevant variation (color, size, packaging) without
  losing the brand + product type + model identity.
- The downstream prioritiser (T-311) ranks groups by *inventory value*, not
  row count. We need `group_total_quantity`, `group_total_value`,
  `group_variant_count` materialised on each group.

This task produces a **groups DataFrame** keyed on `group_id` that becomes
the unit of work for everything past clustering. Existing per-row outputs
are unchanged; the rollup in `output/reporter.py` adopts it.

This task is **pure logic** — no I/O, no SERP, no network.

## Codebase integration

- Reuses `intelligence/homogeneity.py` from T-307 (`sku_cluster_id`,
  `normalize_for_clustering`, model-token regex). Do not reinvent.
- Reuses `processing/cleaner.py` for brand / category. Do not reinvent.
- A new module `intelligence/grouping.py` produces the groups DataFrame
  *after* T-307's `HomogeneityEngine.annotate(df)` has run.
- `output/reporter.py::_build_rollup` already prefers `sku_cluster_id`
  (T-307); after T-310 it switches to consuming the groups DataFrame
  directly when present, which is more efficient than re-aggregating.
- The pipeline orchestrator carries the groups DataFrame as a sibling
  artifact (`pipeline_result.groups`), not a column on `df`.

## Files to create / modify

- `intelligence/grouping.py` — new module.
- `intelligence/homogeneity.py` — expose `model_tokens(title) -> tuple[str, ...]`
  publicly so this module can reuse the regex without copying it. (Pure
  refactor; no behaviour change.)
- `pipeline/run_pipeline.py` — invoke `build_canonical_groups(df)` after
  the homogeneity stage, persist to `pipeline_result.groups`.
- `output/reporter.py` — consume the groups DataFrame for the rollup CSV
  when present; keep the existing fallback path for when it isn't.
- `config/settings.py` — `SEARCH_SIGNATURE_DROP_TOKENS`,
  `CANONICAL_TITLE_MAX_LEN`, `MIN_GROUP_QUANTITY_FOR_SEARCH`. Add to
  `Settings`.
- `tests/test_grouping.py`.
- `README.md`.

## Specification

### Config (`config/settings.py`)

```python
# Tokens stripped *only* when building search_signature — these are the
# attributes that distinguish variants within a single product (color,
# size, pack-size). Keep them in the row's product_name_clean; drop them
# from the SERP query so "M185 Black" and "M185 Grey" share a signature.
# This is a SUPERSET of HOMOGENEITY_FILLER_TOKENS (T-307); it strips more.
SEARCH_SIGNATURE_DROP_TOKENS: frozenset[str] = frozenset({
    # T-307 fillers (stop-words, units) are dropped first.
    # Variant-only attributes (drop these for the search signature):
    "black", "white", "blue", "red", "grey", "gray", "silver", "gold",
    "rose", "rosegold", "green", "yellow", "pink", "orange", "purple",
    "brown", "beige", "cream", "ivory", "navy",
    "small", "medium", "large", "xs", "s", "m", "l", "xl", "xxl",
    "pack", "packs", "set", "sets", "piece", "pieces", "pcs",
    "combo", "kit",
    "left", "right",
})

# Hard ceiling on canonical title length to keep SERP queries clean.
CANONICAL_TITLE_MAX_LEN: int = 80

# Groups whose total_quantity is below this threshold are still emitted in
# the groups DataFrame, but T-311 deprioritises them. Operators don't pay
# SerpAPI to look up a one-off oddity.
MIN_GROUP_QUANTITY_FOR_SEARCH: int = 2
```

### Module surface (`intelligence/grouping.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from config.settings import Settings


def build_search_signature(title: str, settings: Settings) -> str:
    """Stable, lossy SERP key.

    Pipeline:
      1. normalize_for_clustering(title) from T-307 (lowercase, strip
         punctuation, collapse whitespace, preserve model tokens).
      2. Drop SEARCH_SIGNATURE_DROP_TOKENS (a superset of T-307 fillers).
      3. If a model token is present, the signature is
         "<brand> <head_noun> <model>" in that order.
      4. If no model token, the signature is the deduped, ordered token
         list, truncated to CANONICAL_TITLE_MAX_LEN.

    Two titles in the same T-307 cluster MAY produce different
    signatures (e.g. one row missing the brand); the grouping algorithm
    below collapses those.
    """


def select_canonical_title(titles: list[str], settings: Settings) -> str:
    """Pick the most informative representative for a group.

    Score each title on:
      * +3 if it contains a model token
      * +2 if it contains a recognised brand (settings.known_brands)
      * +1 for each non-filler token (length proxy)
      * −1 if length exceeds CANONICAL_TITLE_MAX_LEN
    Break ties deterministically by lexicographic order so a re-run on
    the same manifest yields the same canonical title."""


@dataclass(frozen=True)
class CanonicalGroupingEngine:
    settings: Settings

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a groups DataFrame keyed on group_id.

        Columns:
          group_id              : str (stable, e.g. "g0", "g1", ...)
          search_signature      : str (output of build_search_signature)
          canonical_title       : str (output of select_canonical_title)
          brand                 : str | None (modal value among rows)
          normalized_category   : str | None (modal value among rows)
          model_tokens          : tuple[str, ...]
          variant_count         : int (number of distinct
                                       product_name_clean values)
          group_total_quantity  : int (sum of row quantity)
          group_total_value     : float (sum of qty * floor_price)
          group_member_skus     : tuple[str, ...] (each row's sku, deduped)
          eligible_for_search   : bool (True iff group_total_quantity >=
                                        MIN_GROUP_QUANTITY_FOR_SEARCH)

        Algorithm:
          1. Group rows by sku_cluster_id (from T-307).
          2. Within each cluster, build the search_signature for each row;
             collapse rows whose signatures match exactly into one group.
             Rows that share a cluster but produce different signatures
             stay split (rare; happens when one row is missing the brand).
          3. group_id is assigned in descending order of
             group_total_value so g0 is always the most valuable group.
        """


def build_canonical_groups(
    df: pd.DataFrame, settings: Optional[Settings] = None
) -> pd.DataFrame:
    """Functional wrapper for the orchestrator."""
```

### Reporter integration

`_build_rollup` adds a new fast path:

```python
if "_groups" in df.attrs:        # set by pipeline orchestrator
    return _rollup_from_groups(df.attrs["_groups"], df)
# ... existing fallbacks unchanged ...
```

The fast path passes through `canonical_title`, `group_total_quantity`,
`group_total_value`, `variant_count` so operators see them in the rollup
CSV.

## Acceptance criteria

- [ ] `intelligence/grouping.py` exposes `build_canonical_groups`,
  `build_search_signature`, `select_canonical_title`,
  `CanonicalGroupingEngine` — all type-hinted.
- [ ] On the bundled real manifest, `build_canonical_groups(df).shape[0] <
  df.shape[0]`. (Strict inequality — at least one collapse.)
- [ ] `group_id` is stable: a permuted-row run produces the same
  `(canonical_title, group_total_value)` set with the same group ids.
- [ ] `g0` is always the highest-value group.
- [ ] No new third-party deps (uses `rapidfuzz` already added by T-307).
- [ ] End-to-end pipeline test still passes; rollup CSV gains
  `canonical_title`, `group_total_quantity`, `group_total_value`,
  `variant_count` columns.
- [ ] All public functions are pure / deterministic — no I/O, no clock,
  no RNG.

## Test requirements (`tests/test_grouping.py`)

1. `test_signature_collapses_color_variants` —
   `"Logitech Wireless Mouse M185 Black"` and
   `"Logitech Mouse M185 Grey"` produce identical signatures.
2. `test_signature_keeps_model_distinct` —
   `"Logitech M185"` and `"Logitech M720"` produce **different**
   signatures.
3. `test_signature_truncated_to_max_len` — a 200-character title
   produces a signature ≤ `CANONICAL_TITLE_MAX_LEN`.
4. `test_canonical_title_prefers_model_and_brand` — given three
   variant titles where only one has both brand + model, that one is
   selected.
5. `test_canonical_title_is_deterministic` — equal-score ties resolve
   lexicographically; running twice gives the same result.
6. `test_groups_keyed_by_value_descending` — synthetic 3-group manifest;
   assert `g0` corresponds to the largest `group_total_value`.
7. `test_group_total_quantity_and_value_sum_correctly` — synthetic data
   with known sums.
8. `test_eligible_for_search_threshold` — group with quantity = 1 →
   `eligible_for_search = False`; group with quantity = 5 → `True`.
9. `test_real_manifest_collapses_at_least_10_pct` — schema-level
   expectation on the bundled real manifest.
10. `test_pipeline_publishes_groups_attr` — after running the orchestrator
    end-to-end, `result.df.attrs["_groups"]` is the groups DataFrame and
    the rollup CSV uses it.

## Documentation requirements

- [ ] `README.md` § 3: insert step 5.6 "Canonical groups" between
  homogeneity (T-307) and profitability, describing the lossy signature
  vs the lossless cluster id.
- [ ] `README.md` § 5 config table: `SEARCH_SIGNATURE_DROP_TOKENS`,
  `CANONICAL_TITLE_MAX_LEN`, `MIN_GROUP_QUANTITY_FOR_SEARCH`.
- [ ] `intelligence/grouping.py` module docstring: when to use cluster_id
  (rollups, homogeneity) vs group_id (SERP, value-weighted decisions).
- [ ] Sample-manifest run output committed showing one row per group in
  the rollup CSV.

## Out of scope

- Embedding-based or LLM-based grouping. Phase 4.
- Per-variant price tracking inside a group. T-311 stores aggregated
  market prices at the group level only.
- Cross-manifest deduplication (caching across manifests). That belongs
  to the cache layer in T-311.
- Any modification to the row-level homogeneity scores from T-307.

## Risks & considerations

- **Signature too aggressive.** Dropping "pack" / "set" can wrongly
  collapse a 6-pack vs a 24-pack of the same SKU into one group. The
  per-row quantity is preserved, so group_total_quantity stays correct,
  but downstream ROI projections that vary with pack-size may drift. If
  this surfaces in backtest, move pack-size tokens out of
  `SEARCH_SIGNATURE_DROP_TOKENS` and into a separate facet on the group
  shape.
- **Modal brand / category.** When rows in a group disagree, we pick the
  mode. With 50/50 splits the choice is arbitrary; document that a tie
  resolves lexicographically and surface a warning in logs.
- **`group_id` ordering by value.** Means group ids change if floor
  prices change between runs. That's intentional (priority order matters
  for T-311) but must be documented so consumers don't treat `g0` as a
  primary key across runs — the stable id is `search_signature`.
