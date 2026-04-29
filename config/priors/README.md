# Priors snapshots

Versioned JSON snapshots of the per-category and per-condition priors that
the engine treats as tunable. Maintained by the **outcome feedback loop**
(`tools/feedback_update.py`, see T-305).

## Schema

Every snapshot is a JSON object with the following keys:

| Key | Type | Notes |
|---|---|---|
| `version` | string | e.g. `"v0"`, `"v3"` — monotonically increasing |
| `created_at` | string (ISO date) | when the snapshot was written |
| `source_observations` | integer | total realised rows used to derive it |
| `category_return_rate` | `{category: float}` | per-category fraction of sold units returned |
| `category_holding_days` | `{category: int}` | per-category expected days to clear inventory |
| `condition_to_sell_through` | `{condition: {sellable_factor, risk_score}}` | per-condition factors |

Categories not present in a snapshot fall back to the module-level constants
in `config/settings.py`.

## Lifecycle

1. **Read**: `get_settings()` reads `BULK_INTEL_PRIORS_PATH` (default
   `config/priors/latest.json`) and overlays the JSON values on top of the
   in-code defaults.  Missing file → defaults are used silently.
2. **Propose**: `python -m tools.feedback_update --outcomes lot.csv` reads
   realised outcomes, applies a Bayesian shrinkage update against the
   current priors, and writes a new versioned file (no in-place edits).
3. **Apply**: re-run with `--apply` to overwrite `latest.json` with the new
   version.  Without `--apply` the existing `latest.json` is untouched.

## Version-bumping policy

- Use `vN+1` (no semver) — this is operator-internal state, not a public API.
- Never delete an old version: rolling back to `v0` must always be possible
  by setting `BULK_INTEL_PRIORS_PATH=config/priors/v0.json`.
- Keep `created_at` and `source_observations` honest: they are how a future
  reviewer judges whether a prior set is well-supported.
