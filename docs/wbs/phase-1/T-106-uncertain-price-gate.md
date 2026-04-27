# T-106 — Hard gate: low `match_confidence` downgrades BUY → REVIEW

| Field | Value |
|---|---|
| Phase | 1 (P0) |
| Effort | 2 hours |
| Depends on | — |
| Blocks | — |
| Status | Not started |

---

## Context

`enrichment/enricher.py` already emits `match_confidence` (0.0–1.0) and
`unreliable_match` (bool). The decision engine surfaces
`low_match_confidence_pct` and `high_price_uncertainty` at the lot level — but
**the per-row decision ignores them**. Today a row with `match_confidence =
0.0` (no real match — pure MRP heuristic) can still be flagged BUY. The
operator has no signal that the projected revenue rests on synthetic data.

This task adds a 6th per-row gate: rows with low confidence are forced to
REVIEW (never BUY) so a human verifies the price before capital is committed.

## Files to create / modify

- `config/settings.py` — `DECISION_THRESHOLDS["min_buy_match_confidence"]`.
- `intelligence/decision.py` — add gate to `_decide_row`.
- `tests/test_pricing_and_scoring.py` (or new test file) — confidence-gate tests.
- `README.md` — config table + data-flow note.

## Specification

### Config

```python
DECISION_THRESHOLDS: Mapping[str, float] = {
    "buy_score_min": 60.0,
    "risk_score_max": 60.0,
    "min_expected_margin_pct": 15.0,
    "min_expected_roi_pct": 25.0,
    # Below this match_confidence, never recommend BUY — force REVIEW.
    # match_confidence = 0.0 means the price came from a pure MRP heuristic
    # with no catalog hit.
    "min_buy_match_confidence": 0.6,
}
```

### `_decide_row` change

```python
match_confidence = _safe_float(row.get("match_confidence", 1.0))
confidence_pass = match_confidence >= thresholds.get("min_buy_match_confidence", 0.0)

if confidence_pass:
    reasons.append(f"match confidence {match_confidence:.2f} ≥ {min_conf:.2f}")
else:
    reasons.append(
        f"match confidence {match_confidence:.2f} below {min_conf:.2f} — price is synthetic"
    )

# Combine with the existing five gates.  If confidence fails, BUY is impossible
# regardless of other gates — the prudent answer is REVIEW.
gates = [score_pass, risk_pass, margin_pass, roi_pass, profit_pass]
all_other_gates_pass = all(gates)

if all_other_gates_pass and confidence_pass:
    recommendation = BUY
elif all_other_gates_pass and not confidence_pass:
    recommendation = REVIEW                                   # forced down by confidence
elif sum(gates) >= 3 and risk_pass and profit_pass:
    recommendation = REVIEW
else:
    recommendation = SKIP
```

> Default value of `match_confidence` when the column is absent is **1.0**, so
> tests that don't construct the column behave as before.

## Acceptance criteria

- [ ] `DECISION_THRESHOLDS["min_buy_match_confidence"]` exposed in settings.
- [ ] `intelligence/decision.py` reads the threshold and adds a confidence gate.
- [ ] A row that passes all five existing gates but has `match_confidence < 0.6` is **REVIEW**, not BUY.
- [ ] A row that has `match_confidence >= 0.6` and passes all five gates is still BUY (no regression).
- [ ] Per-row `reasoning` string includes the confidence verdict.
- [ ] On the real manifest at default settings (every row uses MRPHeuristicPriceProvider, confidence = 1.0), the BUY count is **unchanged** vs pre-T-106 baseline (since confidence is high). Test must demonstrate this.
- [ ] If we artificially set `match_confidence = 0.5` on the BUY rows, all of them downgrade to REVIEW.

## Test requirements

1. `test_low_confidence_forces_review_when_other_gates_pass` — synthesize a row that would BUY (high sellability, low risk, positive margin/ROI/profit) but with `match_confidence = 0.4` → REVIEW.
2. `test_high_confidence_preserves_buy` — same row with `match_confidence = 0.9` → BUY.
3. `test_default_confidence_is_one_when_column_missing` — DataFrame without a `match_confidence` column behaves exactly as before this task (no regression on the existing `test_decision_engine_emits_recommendation_and_reasoning`).
4. `test_reasoning_string_mentions_confidence` — assert the reasoning contains `"match confidence"`.

## Documentation requirements (per `CLAUDE.md`)

- [ ] `README.md` § 5 config table: add `DECISION_THRESHOLDS["min_buy_match_confidence"]`.
- [ ] `README.md` § 3 step 8 (Decision): document the gate and the "missing column → 1.0" default.
- [ ] `intelligence/decision.py` docstring lists the new gate.

## Out of scope

- Per-category confidence thresholds (electronics may need higher confidence than apparel).
- Confidence-aware demotion *within* the lot decision (separate task in Phase 3).

## Risks & considerations

- This change is intentionally conservative: a confidence gate only ever
  *downgrades* a recommendation, never upgrades. Safe by construction.
- Until T-207 (real catalog) ships, every row uses the MRP heuristic with
  confidence 1.0, so this gate is effectively dormant. That's fine — it
  becomes load-bearing the moment a real provider is wired in.
