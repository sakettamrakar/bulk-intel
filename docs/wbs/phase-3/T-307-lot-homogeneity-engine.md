# T-307 — Lot homogeneity engine

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 10 hours |
| Depends on | — (independent) |
| Blocks | — |
| Status | Not started |

---

## Context

Liquidation lots vary wildly in concentration. A pallet of 200 identical
Logitech M185 mice is operationally completely different from a pallet of 200
mixed-brand peripherals — even when ROI projections are similar — because:

- A homogeneous lot lists faster (one listing, bulk shipping rates apply).
- A homogeneous lot is easier to forecast (one velocity prior dominates).
- A fragmented lot demands per-SKU triage which scales labour cost
  super-linearly.

Today the engine emits no quantitative measure of this. Operators eyeball
the manifest. We will surface three lot-level scores in the JSON lot
summary so a downstream UI / decision policy can weight homogeneity
explicitly:

1. **SKU homogeneity** — how concentrated is the lot at the
   item-identity level (e.g. exact model number).
2. **Brand homogeneity** — how concentrated by brand.
3. **Category homogeneity** — how concentrated by canonical category.

This task is **independent** of T-308 / T-309 and can ship first.

## Codebase integration

The pipeline already has the inputs we need — do not invent parallel ones:

- `processing/cleaner.py` produces `brand`, `normalized_category`,
  `product_name_clean`. Reuse these. Do **not** reimplement brand /
  category extraction inside this module.
- The lot-level summary lives in `df.attrs["lot_summary"]` (see
  `intelligence/decision.py::_calculate_lot_summary`). Homogeneity
  outputs land there alongside `roi_band_90pct`.
- Per-row group identifiers (`sku_cluster_id`) feed
  `output/reporter.py::_build_rollup`, which already groups rows; this
  task replaces its current `sku`-or-`product_name_clean` grouping
  fallback with a stable cluster id when SKUs are missing or noisy.

## Files to create / modify

- `intelligence/homogeneity.py` — new module (pure functions + a
  `HomogeneityEngine` dataclass mirroring the other engines).
- `pipeline/run_pipeline.py` — wire after `cleaner` + `enricher`, before
  `decision`, so `cluster_id` columns exist by the time the rollup
  builds.
- `intelligence/decision.py` — pull the three scores into
  `lot_summary`.
- `output/reporter.py` — surface `sku_cluster_id` in `PRIMARY_COLUMNS`;
  rollup uses `sku_cluster_id` when present.
- `config/settings.py` — `HOMOGENEITY_THRESHOLDS`, fuzz cutoff,
  filler-word list. Add to `Settings` dataclass.
- `tests/test_homogeneity.py` — see Test requirements.
- `README.md`.

## Specification

### Config (`config/settings.py`)

```python
# Token cleanup applied before SKU clustering. Operators can extend.
HOMOGENEITY_FILLER_TOKENS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "for", "with", "and", "or",
    "new", "open", "box", "lot", "pack", "set",
    "black", "white", "blue", "red", "grey", "gray", "silver",
    "small", "medium", "large", "xl", "xxl",
    # Units: kept here, not in cleaner.py, because cleaner is shared.
    "ml", "g", "kg", "cm", "mm", "inch", "in",
})

# Model-token regex. Anything matching is preserved verbatim through
# normalization and weighted heavily during clustering.
# Examples it must match: M185, WH1000XM5, RTX3060, 15Pro, B07VR7VY1Y.
HOMOGENEITY_MODEL_TOKEN_PATTERN: str = r"\b(?:[A-Z]{1,5}\d{2,6}[A-Z0-9]*|[BX]0[A-Z0-9]{8})\b"

# Fuzz threshold for collapsing two normalized titles into the same
# SKU cluster. rapidfuzz.fuzz.token_sort_ratio scale is 0-100.
HOMOGENEITY_SKU_FUZZ_CUTOFF: int = 88

# Qualitative interpretation bands. Score is in [0, 1].
HOMOGENEITY_THRESHOLDS: Mapping[str, float] = {
    "highly_homogeneous":     0.85,
    "moderately_homogeneous": 0.60,
    "mixed":                  0.30,
    # below 0.30 → "highly fragmented"
}
```

### Module surface (`intelligence/homogeneity.py`)

```python
from dataclasses import dataclass
import pandas as pd
from config.settings import Settings

@dataclass(frozen=True)
class HomogeneityEngine:
    settings: Settings

    def annotate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return df + per-row cluster ids.

        Adds three columns:
          - ``sku_cluster_id`` (str) — model-aware fuzzy cluster
          - ``brand_cluster_id`` (str) — exact match on cleaner's `brand`
          - ``category_cluster_id`` (str) — exact match on `normalized_category`

        Rows that share a cluster_id are members of the same group.
        """

    def lot_scores(self, df: pd.DataFrame) -> dict[str, float | str]:
        """Return the three lot-level scores + interpretation labels.

        {
          "sku_homogeneity": 0.0..1.0,
          "brand_homogeneity": 0.0..1.0,
          "category_homogeneity": 0.0..1.0,
          "sku_homogeneity_label": "Highly homogeneous" | ...,
          ...
        }
        """


def normalize_for_clustering(title: str, settings: Settings) -> str:
    """Lowercase, strip punctuation, drop fillers, collapse whitespace,
    PRESERVE model tokens (uppercased) verbatim. Pure / deterministic."""


def cluster_skus(titles: list[str], settings: Settings) -> list[str]:
    """Greedy fuzzy clustering keyed on rapidfuzz.token_sort_ratio.

    Two titles cluster together if (a) they share a model token, OR
    (b) they share no model token AND token_sort_ratio >= cutoff.
    Returns parallel list of cluster ids (e.g. "c0", "c1", ...).
    """


def compute_homogeneity_score(counts: pd.Series) -> float:
    """Entropy-based concentration score in [0, 1].

    Uses Shannon entropy with natural log. Normalised by log(N) where N
    is the number of distinct clusters. Single cluster → score 1.0.
    Uniform across N clusters → score 0.0. Empty input → 0.0.

        H = -sum(p_i * ln(p_i))
        score = 1 - H / ln(N)   if N > 1, else 1.0
    """


def interpret_homogeneity(score: float, settings: Settings) -> str:
    """Map a [0,1] score to one of:
       'Highly homogeneous' | 'Moderately homogeneous' |
       'Mixed lot' | 'Highly fragmented'
    Threshold edges are inclusive on the upper bound."""
```

### Decision integration

In `decision.py::_calculate_lot_summary`, append the engine output:

```python
homogeneity = HomogeneityEngine(self.settings).lot_scores(df)
summary["homogeneity"] = homogeneity
```

The keys go in under a single `"homogeneity"` namespace (not flattened)
to avoid polluting the top-level summary shape.

### Reporter integration

`output/reporter.py::_build_rollup` currently picks a group key by:

```
sku → group_key (brand|product_name_clean) → product_name_clean
```

Change the priority to: `sku_cluster_id` (if present) → existing chain.
Do not remove the existing fallbacks; they cover the no-cleaning path.

## Acceptance criteria

- [ ] `intelligence/homogeneity.py` exposes `HomogeneityEngine`,
  `normalize_for_clustering`, `cluster_skus`, `compute_homogeneity_score`,
  `interpret_homogeneity`, all type-hinted.
- [ ] Pipeline emits `sku_cluster_id`, `brand_cluster_id`,
  `category_cluster_id` columns on the per-row DataFrame.
- [ ] `df.attrs["lot_summary"]["homogeneity"]` contains six keys: three
  scores + three labels.
- [ ] Score is **1.0** for a synthetic single-SKU lot of 100 rows.
- [ ] Score is **< 0.20** for a synthetic 100-row lot of 100 distinct
  SKUs in equal proportion.
- [ ] On the real Bulk4Traders manifest, category_homogeneity is **at
  least 0.10 above** sku_homogeneity (catalog has many models per
  category).
- [ ] `_build_rollup` now groups on `sku_cluster_id` when present;
  rollup row count for the real manifest drops vs the prior `sku`-keyed
  baseline (regression test asserts strict inequality).
- [ ] `rapidfuzz` added to `requirements.txt`.

## Test requirements (`tests/test_homogeneity.py`)

1. `test_score_is_one_for_single_cluster` — counts = `[100]` → score == 1.0.
2. `test_score_is_zero_for_uniform_distribution` — counts =
   `[10]*10` → score == 0.0 (within float tolerance).
3. `test_score_handles_empty_input` — `compute_homogeneity_score(pd.Series([], dtype=int))` → 0.0, no exception.
4. `test_normalize_preserves_model_tokens` —
   `"Logitech Wireless Mouse M185 Black"` and `"Logitech M185 Mouse"`
   normalize to strings that **both contain** `"M185"`.
5. `test_cluster_collapses_logitech_m185_variants` — three variant
   titles cluster into a single id; an unrelated `"Logitech Keyboard
   K380"` does not join them.
6. `test_cluster_does_not_merge_different_models` —
   `"Logitech M185"` and `"Logitech M720"` get distinct cluster ids
   (model tokens differ).
7. `test_engine_attaches_three_cluster_columns` — pipeline integration
   smoke test on `data/sample_manifest.csv`.
8. `test_lot_scores_namespace_in_summary` — after `decide(df)`,
   `df.attrs["lot_summary"]["homogeneity"]` has all six keys, scores in
   `[0, 1]`, labels in the four allowed strings.
9. `test_interpret_thresholds_at_boundaries` — score 0.85 → "Highly
   homogeneous", 0.84999 → "Moderately homogeneous", 0.60 →
   "Moderately homogeneous", 0.59999 → "Mixed lot", 0.30 → "Mixed lot",
   0.29999 → "Highly fragmented".
10. `test_real_manifest_category_above_sku_homogeneity` — schema-level
    expectation on the bundled real manifest.

## Documentation requirements

- [ ] `README.md` § 3: insert step 5.5 "Homogeneity" between scoring and
  profitability, with the formula.
- [ ] `README.md` § 5 config table: add the four new settings.
- [ ] `intelligence/homogeneity.py` module docstring documents the
  entropy formula, the model-token regex, and the fuzz cutoff rationale.
- [ ] Sample manifest run output (`output/reports/*.json`) committed
  showing the new keys for human review.

## Out of scope

- Multi-feature clustering (price band, size, weight). Phase 4.
- Embedding-based semantic clustering (sentence-transformers). Phase 4.
- Time-windowed homogeneity (this lot vs last 10 lots). Phase 4.
- Auto-decision-rule changes based on homogeneity (e.g. "skip lot if
  fragmented"). That belongs to a follow-up task once we have telemetry
  on what scores correlate with operator regret.

## Risks & considerations

- **Greedy clustering is order-sensitive.** Sort titles deterministically
  before clustering (lexicographic) so two runs over the same manifest
  produce identical cluster ids.
- **Model-token regex over-matches** generic alphanumerics (`USB30`,
  `4K`). The regex is deliberately conservative; tune via test cases as
  false positives surface on real data.
- **Fuzz cutoff trade-off.** 88 is empirical. Below 80 begins to merge
  distinct products; above 92 fails on common abbreviations
  ("Wireless" vs "Wrls"). Expose as a setting so domain experts tune it
  without editing code.
- **Empty / single-row lots** must not crash. Score is 1.0 for N=1 and
  0.0 for N=0. Tests cover both.
