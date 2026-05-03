# T-308 — Product match scoring engine

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 12 hours |
| Depends on | T-307 (reuses model-token extractor + rapidfuzz dep) |
| Blocks | T-309 (SERP price provider gates results through this) |
| Status | Not started |

---

## Context

The pipeline already accepts third-party prices via the `PriceProvider`
Protocol (`enrichment/enricher.py`) and already carries
`match_confidence` / `unreliable_match` columns through to the decision
gate. What it lacks is a **shared, testable scoring function** that
turns "manifest row" + "candidate external listing" into a single
confidence number using consistent rules.

Today each provider invents its own match logic
(`FuzzyCatalogPriceProvider` uses `difflib`, others use exact lookups).
That makes match quality opaque, the threshold (`min_buy_match_confidence
= 0.6`) inconsistent across providers, and any new external source — a
SERP scraper, a marketplace API — has to reinvent the wheel.

This task extracts product-matching into a single typed module so:

- Existing providers can migrate to it with a one-line call.
- T-309 (Google SERP Amazon prices) plugs in cleanly.
- Match quality becomes auditable: every accept/reject ships with a
  per-feature breakdown.

This task is **pure logic** — no I/O, no external services. It depends
on T-307 only because T-307 introduces the model-token regex and the
`rapidfuzz` dependency this task reuses.

## Codebase integration

- The scoring function is consumed by `PriceProvider` implementations.
  It does **not** modify the Protocol shape.
- Reuse `processing/cleaner.normalize_brand` and `_normalize_category`
  (or whatever the cleaner exposes) for canonicalisation. Do not
  reimplement.
- Reuse `intelligence/homogeneity.normalize_for_clustering` and the
  model-token regex from T-307 for the title-similarity arm. Centralising
  these means the homogeneity engine and the matcher always agree on
  what a "model token" is.
- The Protocol stays `lookup(row) -> (amazon, wholesale, confidence)`.
  This task only changes how `confidence` is computed.

## Files to create / modify

- `intelligence/matching.py` — new module.
- `enrichment/enricher.py` — `FuzzyCatalogPriceProvider` migrates to the
  new scorer (single call site). Existing tests must still pass.
- `config/settings.py` — `MATCH_TOKEN_WEIGHTS`,
  `MATCH_ACCEPT_THRESHOLD`, `MATCH_WEAK_THRESHOLD`,
  `MATCH_BRAND_MISMATCH_OVERRIDE`. Add to `Settings`.
- `tests/test_matching.py`.
- `README.md`.

## Specification

### Config (`config/settings.py`)

```python
# Weighted contribution of each feature to the [0, 1] match score.
# Must sum to 1.0. The model-token feature is weighted highest because
# a wrong model is the most expensive false positive in liquidation
# (price for the wrong SKU is worse than no price).
MATCH_TOKEN_WEIGHTS: Mapping[str, float] = {
    "model":        0.50,
    "brand":        0.30,
    "product_type": 0.15,
    "extra_tokens": 0.05,
}

# Accept / weak / reject bands for the final score.
MATCH_ACCEPT_THRESHOLD: float = 0.80
MATCH_WEAK_THRESHOLD: float = 0.65
# Below MATCH_WEAK_THRESHOLD → reject.

# Brand mismatch is normally a hard reject. Override only when the rest
# of the score clears this floor (very rare, but covers brand aliases
# we missed in BRAND_ALIASES).
MATCH_BRAND_MISMATCH_OVERRIDE: float = 0.92
```

### Module surface (`intelligence/matching.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class MatchFeatures:
    """Per-feature similarity in [0, 1]. Auditable record of the score."""
    model: float
    brand: float
    product_type: float
    extra_tokens: float
    # Booleans raised when a hard rule fires.
    brand_mismatch: bool
    category_mismatch: bool

@dataclass(frozen=True)
class MatchResult:
    score: float                                    # 0..1
    decision: Literal["accept", "weak", "reject"]
    features: MatchFeatures
    reasons: tuple[str, ...]                        # human-readable


def extract_model_tokens(title: str, settings: Settings) -> tuple[str, ...]:
    """Return uppercased model-identifier tokens from a free-text title.

    Reuses HOMOGENEITY_MODEL_TOKEN_PATTERN. Order-preserving, deduped."""


def compute_match_score(
    manifest_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    settings: Settings,
) -> MatchResult:
    """Score a single (manifest_row, candidate) pair.

    Inputs:
      manifest_row keys read: product_name_clean, brand,
        normalized_category. Falls back to product_name / category if
        the cleaned versions are absent.
      candidate keys read: title, brand (optional), category (optional).

    Algorithm (deterministic, no I/O):

      1. Extract model tokens from both titles.
         model_score = jaccard(tokens_a, tokens_b); 0 if either side empty.

      2. brand_score = 1.0 if normalized brands equal, else
         rapidfuzz.fuzz.token_set_ratio / 100 (handles aliases that
         survived BRAND_ALIASES).

      3. product_type_score = rapidfuzz.fuzz.partial_ratio over the
         non-model, non-brand head-noun ('mouse', 'laptop'). Detection
         is heuristic: take the first non-stopword non-model non-brand
         token from each side.

      4. extra_tokens_score = rapidfuzz.fuzz.token_sort_ratio / 100 over
         the residual tokens.

      5. raw = sum(weights[k] * features[k] for k in weights).

      6. Hard rules:
         - if categories differ AND both present → category_mismatch=True;
           force decision='reject', score = min(raw, 0.49).
         - if brand_mismatch AND raw < MATCH_BRAND_MISMATCH_OVERRIDE →
           force decision='reject', score = min(raw, 0.59).

      7. Decision band from the (post-rule) score:
            score >= MATCH_ACCEPT_THRESHOLD  → 'accept'
            score >= MATCH_WEAK_THRESHOLD    → 'weak'
            otherwise                        → 'reject'.

    The reasons tuple records every rule that fired and the top-2
    contributing features so a reviewer can see why the score landed."""


def validate_product_match(
    manifest_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    settings: Settings,
) -> bool:
    """Convenience predicate: returns True iff decision == 'accept'."""
```

### `FuzzyCatalogPriceProvider` migration

Replace the inline `difflib.SequenceMatcher` ratio with a call to
`compute_match_score`. The provider already holds a list of catalog
candidates; for each one, score against the manifest row, take the best
`MatchResult` whose decision is not `'reject'`, and return its price +
score as `match_confidence`. Below threshold → return
`(None, None, 0.0)` exactly as today.

This migration is the **single behavioural change** to the existing
pipeline; everything else is additive.

## Acceptance criteria

- [ ] `intelligence/matching.py` module exists with the four public
  symbols above, all type-hinted, with a module docstring covering the
  algorithm.
- [ ] `MatchResult.score` lies in `[0, 1]` for every test case.
- [ ] `MatchResult.decision` is one of `accept | weak | reject` and is
  consistent with thresholds.
- [ ] Score is **deterministic** for the same inputs (no RNG, no I/O).
- [ ] `FuzzyCatalogPriceProvider` uses `compute_match_score`. The full
  existing test suite (minus the four pre-existing failures) still
  passes.
- [ ] Brand-mismatch hard rule fires: a manifest row branded "Sony" and
  a candidate branded "Boat" with otherwise-similar titles → decision
  is `reject` regardless of title similarity.
- [ ] Category-mismatch hard rule fires: same model token across
  different normalized categories (e.g. "M185" appearing in both an
  Electronics and a Stationery row) → reject.
- [ ] No new third-party dependencies beyond `rapidfuzz` (already added
  by T-307).

## Test requirements (`tests/test_matching.py`)

1. `test_identical_titles_score_one` — same title, brand, category →
   score >= 0.99 and decision='accept'.
2. `test_logitech_m185_variants_accept` — manifest "Logitech Wireless
   Mouse M185" vs candidate "Logitech M185 Mouse Black" → accept.
3. `test_different_models_same_brand_reject` — "Logitech M185" vs
   "Logitech M720" → decision in `{weak, reject}`, model_score < 0.5.
4. `test_brand_mismatch_hard_rejects` — "Sony WH-1000XM5" vs "Boat
   Rockerz 550" → reject; reasons contain "brand_mismatch".
5. `test_category_mismatch_hard_rejects` — manifest category=electronics
   vs candidate category=apparel, otherwise similar → reject; reasons
   contain "category_mismatch".
6. `test_weak_band_when_only_one_feature_strong` — strong brand match,
   no model on either side → score in `[0.65, 0.80)`, decision='weak'.
7. `test_score_is_deterministic` — same inputs through 10 calls → same
   score every time.
8. `test_score_features_sum_to_weighted_total` — pre-rule
   `sum(weight[k] * features[k])` equals the raw score (within float
   tolerance) for a row where no hard rule fires.
9. `test_extract_model_tokens_canonical_examples` — covers M185,
   WH1000XM5, RTX3060, B07VR7VY1Y; rejects "USB", "4K", "the".
10. `test_brand_alias_override` — when raw score >= 0.92 and brands
    differ as strings, the override allows acceptance (covers aliases
    not in `BRAND_ALIASES`).
11. `test_fuzzy_catalog_provider_uses_new_scorer` — integration test:
    construct a provider with a synthetic catalog, call `lookup()` on a
    matching row → returns price + match_confidence > 0.8.

## Documentation requirements

- [ ] `README.md` § 3 step 3 (Enrichment): note that all `PriceProvider`
  implementations now share `intelligence.matching.compute_match_score`.
- [ ] `README.md` § 5 config table: add `MATCH_TOKEN_WEIGHTS`,
  `MATCH_ACCEPT_THRESHOLD`, `MATCH_WEAK_THRESHOLD`,
  `MATCH_BRAND_MISMATCH_OVERRIDE`.
- [ ] `intelligence/matching.py` docstring lists the four features, the
  hard rules, and the threshold semantics with a worked example.
- [ ] `README.md` § 6 Extension points: "How to write a new
  PriceProvider" — point at this module as the canonical scorer.

## Out of scope

- Embedding-based semantic similarity. Phase 4.
- Multi-language matching (Hindi / regional brand spellings). Phase 4.
- Image-based matching. Phase 4 / out of project.
- Learning weights from data — `MATCH_TOKEN_WEIGHTS` are operator-set
  priors. The T-305 feedback loop may eventually tune them, but only
  after T-309 ships and we have telemetry.

## Risks & considerations

- **Weight tuning is the highest-leverage knob.** Defaults are operator
  judgment. Document that the test suite encodes the chosen defaults so
  changing weights surfaces as broken assertions in #6 and #8 — that's
  intentional, not a bug.
- **Model-token false negatives** on brands with weird SKU schemes
  (Apple "iPhone 15", Sony "WH-1000XM5"). The shared regex from T-307
  must handle these; if it doesn't, fix the regex there, not here.
- **Hard rules are coarse.** A category-mismatch reject prevents
  legitimate cross-category accessories (laptop + bag) from ever
  matching. That's the right default for a price scorer; if a future
  module needs softer semantics, add a separate function rather than
  weakening this one.
- **Provider migration risk.** The `FuzzyCatalogPriceProvider` test
  suite is the canary. Run it on every commit during this task — drift
  in match scores there will distort end-to-end pricing.
