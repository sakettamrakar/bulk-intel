# T-305 — Outcome feedback loop (closes the prior-update cycle)

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 12 hours |
| Depends on | T-205 (backtest harness) |
| Blocks | — |
| Status | Not started |

---

## Context

After every realised lot the operator has new data: which BUY rows actually
made money, which were wrong calls, which SKIPs would have profited. Today
that data dies in a spreadsheet. We want a mechanism that:

1. Ingests realised outcomes (same CSV format as T-205).
2. Updates per-category priors (`CATEGORY_RETURN_RATE`,
   `CATEGORY_HOLDING_DAYS`, `CONDITION_TO_SELL_THROUGH`).
3. Versions the priors so behaviour changes are auditable and reversible.

This is what makes the engine **self-improving** rather than a static
heuristic.

## Files to create / modify

- `tools/feedback_update.py` — CLI: ingest outcomes, propose new priors.
- `config/priors/v0.json` — initial snapshot of static priors (copied from `config/settings.py`).
- `config/priors/` directory with versioned snapshots.
- `config/settings.py` — add a loader that prefers `latest.json` when present, else falls back to module-level constants.
- `tests/test_feedback_loop.py`.
- `README.md`.

## Specification

### Priors snapshot schema (`config/priors/v0.json`)

```json
{
  "version": "v0",
  "created_at": "2026-04-27",
  "source_observations": 0,
  "category_return_rate":     {...},
  "category_holding_days":    {...},
  "condition_to_sell_through":{...}
}
```

### `tools/feedback_update.py`

```
usage: python -m tools.feedback_update \
    --outcomes data/historical/lot_X.csv \
    --current-priors config/priors/latest.json \
    --new-priors    config/priors/v3.json \
    [--apply]

Steps:
1. Compute per-category realised return rate, holding days, sell-through.
2. Apply Bayesian-style update: new = (alpha * prior + N * observed) / (alpha + N)
   where alpha is configurable shrinkage (default 20).  Stronger alpha = more
   conservative updates.
3. Write new priors JSON.
4. With --apply, also update config/priors/latest.json (symlink or copy).
5. Print a diff of priors, including which categories moved most.
```

### Settings loader change

```python
def get_settings() -> Settings:
    priors_path = os.getenv("BULK_INTEL_PRIORS_PATH", "config/priors/latest.json")
    overrides = _load_priors_if_exists(priors_path)
    return Settings(
        category_return_rate     = overrides.get("category_return_rate", CATEGORY_RETURN_RATE),
        category_holding_days    = overrides.get("category_holding_days", CATEGORY_HOLDING_DAYS),
        condition_to_sell_through= overrides.get("condition_to_sell_through", CONDITION_TO_SELL_THROUGH),
        # ...
    )
```

If the priors file is missing, log INFO and use module defaults — never crash.

## Acceptance criteria

- [ ] `config/priors/v0.json` exists (snapshot of current defaults).
- [ ] `config/priors/latest.json` exists as a symlink/copy of v0.
- [ ] `tools/feedback_update` runs end-to-end on the T-205 example outcomes.
- [ ] Settings loader prefers `latest.json` when present, falls back silently when not.
- [ ] Each new priors file is monotonically versioned.
- [ ] Diff is human-readable; explains the magnitude of every priors shift.
- [ ] `--apply` is an explicit flag — running without it never changes
      `latest.json`.

## Test requirements (`tests/test_feedback_loop.py`)

1. `test_priors_file_loaded_when_present` — write a custom priors JSON, set env var, assert `Settings` reflects it.
2. `test_priors_fallback_to_defaults_when_missing` — env var pointing to nonexistent file → defaults used, no crash.
3. `test_bayesian_update_shrinks_to_prior_when_n_small` — 1 observation with extreme value moves prior only slightly.
4. `test_bayesian_update_dominated_by_data_when_n_large` — 100 observations with consistent value moves prior most of the way.
5. `test_apply_flag_required_to_overwrite_latest` — without `--apply`, `latest.json` unchanged.

## Documentation requirements

- [ ] `README.md` § 4 (How to run): "Updating priors after a real lot".
- [ ] `README.md` § 6 (extension points): how `BULK_INTEL_PRIORS_PATH` overrides defaults.
- [ ] `config/priors/README.md` — schema definition + version-bumping policy.
- [ ] `tools/feedback_update.py` CLI `--help`.

## Out of scope

- Live event-stream feedback.
- Per-platform or per-region priors.
- Auto-deployment of new priors (human review gates the `--apply`).

## Risks & considerations

- Bayesian shrinkage parameter (`alpha`) is critical: too low and a single
  unlucky lot rewires the engine; too high and priors barely move. Default 20
  is a reasonable starting point; expose as `--shrinkage`.
- Versioned priors give us the ability to roll back to v0 if a new prior set
  performs worse — surface this in the README.
