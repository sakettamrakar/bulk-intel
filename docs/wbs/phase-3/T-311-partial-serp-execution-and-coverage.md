# T-311 — Partial SERP execution & coverage telemetry

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 14 hours |
| Depends on | T-309 (SerpAmazonPriceProvider), T-310 (canonical groups) |
| Blocks | — |
| Status | Not started |

---

## Context

A 12k-row manifest grouped via T-310 yields ~700–900 unique product groups.
Searching all of them eagerly costs $5–$10 per run at SerpAPI's per-query
price and burns hours of wall time. Operators want to *triage first*: hit
the top-N most valuable groups, see whether the manifest is even worth
pursuing, and only then commit to full enrichment.

This task adds three things on top of T-309:

1. **ExecutionMode** — `preview` (top-N), `incremental` (resume from a
   prior run's state), `full` (everything).
2. **Per-group execution flags + run-state persistence** — every group
   carries its own enrichment status, and a JSON state file makes
   `incremental` mode safe to interrupt and resume.
3. **Inventory-value-weighted coverage telemetry** — manifest-level
   metrics that say "we've SERP'd 12 groups out of 800, but those 12
   represent 64 % of inventory value." Row-count percentages are
   misleading for liquidation work; value-weighted is the metric an
   operator actually cares about.

Plus the small Module 7 polish from the prompt:
- Cache statistics in the run summary (`hits / misses / expired`).
- A `cache_invalidate` CLI command for explicit invalidation.

## Codebase integration

- Wraps `enrichment.serp_price_provider.SerpAmazonPriceProvider` from
  T-309 — does **not** reimplement SERP fetching, parsing, or matching.
- Operates on the groups DataFrame from T-310, not raw rows.
- The manifest-row-level `amazon_price` is filled by joining the group's
  enriched price back across all member rows of that group.
- Adheres to T-309's compliance posture: SerpAPI only, no Amazon
  scraping, no raw Google HTML, rate-limited token bucket, hard-gated
  `BS4SerpProvider` if it exists.

## Files to create / modify

- `enrichment/serp_orchestrator.py` — new module: `ExecutionMode`,
  `SerpRunState`, `PartialSerpOrchestrator`.
- `enrichment/serp_state.py` — JSON-backed run-state store
  (separate file because it's the only stateful piece; T-309's cache
  stays untouched at the data layer).
- `enrichment/serp_cache.py` (from T-309) — extend with `stats() ->
  CacheStats` and a `purge(older_than)` method.
- `pipeline/run_pipeline.py` — accept `execution_mode` and
  `serp_preview_limit` CLI flags; when `Settings.serp_provider_enabled`
  is True, drive enrichment through the orchestrator instead of calling
  the provider directly per row.
- `output/reporter.py` — manifest summary JSON gains
  `search_execution_summary` and `cache_stats` keys; rollup CSV gains
  the per-group execution flags.
- `tools/cache_invalidate.py` — small CLI to purge entries by
  signature, brand, or age.
- `config/settings.py` — `SERP_PREVIEW_LIMIT`, `SERP_STATE_PATH`,
  `SERP_VALUE_COVERAGE_TARGET`. Add to `Settings`.
- `tests/test_serp_orchestrator.py`.
- `tests/test_serp_cache_stats.py`.
- `README.md`.

## Specification

### Config (`config/settings.py`)

```python
SERP_PREVIEW_LIMIT: int = 10                  # top-N groups in preview mode
SERP_STATE_PATH: str = ".cache/serp_state.json"
SERP_VALUE_COVERAGE_TARGET: float = 0.80      # informational; used in
                                              # the summary as "groups
                                              # needed to hit X% value
                                              # coverage"
```

### ExecutionMode

```python
# enrichment/serp_orchestrator.py
from enum import Enum

class ExecutionMode(str, Enum):
    PREVIEW     = "preview"      # search top-N groups by inventory value
    INCREMENTAL = "incremental"  # resume: skip groups already completed
    FULL        = "full"         # search every eligible group
```

`str` mixin keeps JSON serialisation trivial.

### Per-group execution flags

The orchestrator augments the groups DataFrame from T-310 with:

| Column | Type | Meaning |
|---|---|---|
| `serp_attempted` | bool | the orchestrator picked this group up |
| `serp_completed` | bool | a non-error response came back |
| `serp_source_found` | bool | at least one organic result was returned |
| `price_extracted` | bool | `parse_price` produced a non-None value |
| `match_validated` | bool | T-308's matcher returned `accept` for ≥1 candidate |
| `cache_hit` | bool | response served from cache |
| `execution_stage` | str | terminal stage reached (`queued` \| `fetched` \| `parsed` \| `matched` \| `priced` \| `failed`) |
| `last_execution_time` | str (ISO 8601) | UTC timestamp of last attempt |
| `error_kind` | str \| None | `timeout` / `rate_limited` / `4xx` / `5xx` / `parse_error` / `match_reject` |

### Prioritisation

```python
def rank_groups_for_search(groups: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Sort groups by descending priority. Stable, deterministic.

    Priority key (lexicographic, descending):
      1. group_total_value           — main signal
      2. group_total_quantity        — tie-break
      3. variant_count (descending)  — more variants → richer signal
      4. canonical_title             — final lex tiebreak

    Groups with eligible_for_search == False are sorted last regardless.
    """
```

### Run-state store

```python
# enrichment/serp_state.py
@dataclass(frozen=True)
class SerpRunState:
    manifest_hash: str           # sha256 of sorted search_signatures
    started_at: str              # ISO 8601 UTC
    last_updated_at: str
    completed_signatures: tuple[str, ...]
    failed_signatures: tuple[str, ...]
    mode: ExecutionMode

def load_state(path: Path) -> SerpRunState | None: ...
def save_state(state: SerpRunState, path: Path) -> None: ...
```

Stored as JSON. Atomic write (temp file + rename) so an interrupted run
can't corrupt the state file.

`manifest_hash` lets the orchestrator refuse to resume against a
different manifest while sharing the same state file path — surfaces a
clear error rather than silently mixing histories.

### Orchestrator surface

```python
@dataclass(frozen=True)
class PartialSerpOrchestrator:
    settings: Settings
    provider: SerpAmazonPriceProvider
    cache: SerpCache
    state_path: Path

    def enrich(
        self,
        groups: pd.DataFrame,
        mode: ExecutionMode = ExecutionMode.PREVIEW,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Return the groups DataFrame augmented with the per-group
        execution-flag columns AND amazon_price / match_confidence /
        matched_titles / matched_urls.

        Behaviour by mode:

          PREVIEW
            Pick the top `limit or settings.serp_preview_limit` groups
            by rank_groups_for_search and SERP only those. Persist the
            new state. Other groups have serp_attempted=False and no
            price.

          INCREMENTAL
            Load state from settings.serp_state_path. Refuse if
            manifest_hash differs from the current run's hash. SERP
            every eligible group whose signature is NOT in
            completed_signatures. Persist state after every group
            (single-writer atomic write) so a SIGINT loses at most
            one in-flight result.

          FULL
            Ignore prior state. SERP every group with
            eligible_for_search=True. Update state on completion.

        Honours T-309's rate limiter and cache. Cache hits do not
        consume the rate budget.
        """

    def coverage(self, groups: pd.DataFrame) -> dict:
        """Manifest-level execution + coverage metrics.

        Returns:
            {
              "total_manifest_rows":         int,
              "grouped_products":            int,
              "eligible_groups":             int,
              "execution_mode":              "preview" | ...,
              "serp_preview_limit":          int,
              "serp_completed_count":        int,
              "serp_pending_count":          int,
              "serp_failed_count":           int,

              "row_coverage_pct":            float,  # rows in completed groups / total rows
              "value_coverage_pct":          float,  # group_total_value of completed groups
                                                    #   / sum of all group_total_value
              "groups_needed_for_value_target": int, # how many ranked groups would have
                                                    #   to be SERP'd to hit
                                                    #   SERP_VALUE_COVERAGE_TARGET

              "cache_stats": {
                "hits":    int,
                "misses":  int,
                "expired": int,
                "size":    int,
              },
            }
        """
```

### Coverage formulae (precise)

Let `G` be the set of all groups, `E` the eligible subset
(`eligible_for_search==True`), `C ⊆ E` the completed subset, and
`q(g)`, `v(g)` the group's quantity and value.

```
row_coverage_pct       = sum(q(g) for g in C) / sum(q(g) for g in G) * 100
value_coverage_pct     = sum(v(g) for g in C) / sum(v(g) for g in G) * 100
groups_needed_for_target =
    smallest k s.t. sum of top-k groups in rank order
    has cumulative_value_share >= SERP_VALUE_COVERAGE_TARGET.
```

### Cache statistics

`SerpCache.stats() -> CacheStats(hits, misses, expired, size)`. Counters
are in-memory per-process; reset at orchestrator construction. `size`
is the live row count in SQLite.

### `tools/cache_invalidate.py`

```
usage:
  python -m tools.cache_invalidate --by-signature "logitech mouse m185"
  python -m tools.cache_invalidate --by-brand logitech
  python -m tools.cache_invalidate --older-than-hours 168
  python -m tools.cache_invalidate --all   # confirms via stdin
```

Reads `SERP_CACHE_PATH` from settings. Reports rows deleted.

## Acceptance criteria

- [ ] All three modes run end-to-end against a mocked SerpClient and
  produce the expected per-group flag values.
- [ ] PREVIEW with `limit=10` against a 100-group fixture results in
  exactly 10 groups with `serp_completed=True` and 90 with
  `serp_attempted=False`. The 10 completed groups are the 10 highest
  by `group_total_value`.
- [ ] INCREMENTAL refuses (clear error, exit code 2 from CLI) when
  state's `manifest_hash` doesn't match the current run.
- [ ] INCREMENTAL run after a PREVIEW skips the previously-completed
  groups; total network calls = (eligible groups − preview limit).
- [ ] State file is atomically written: a kill -9 between groups leaves
  the file valid JSON.
- [ ] `value_coverage_pct` is computed by **inventory value**, not row
  count (test asserts the two diverge on a synthetic skewed manifest).
- [ ] `groups_needed_for_value_target` matches the formula above for
  three hand-checked cases.
- [ ] `cache_stats` round-trips correctly: a second run on the same
  manifest reports `hits == eligible_count`, `misses == 0`.
- [ ] `tools.cache_invalidate` deletes only matching rows; reports
  count.
- [ ] Default behaviour with `SERP_PROVIDER_ENABLED=False` is unchanged
  (existing pipeline test still passes).
- [ ] No real network calls in any test; SerpClient and SerpCache both
  mockable / injectable.

## Test requirements

`tests/test_serp_orchestrator.py`:

1. `test_preview_mode_serps_only_top_n` — 100-group fixture, limit=10,
   asserts exactly the top 10 by value were SERP'd.
2. `test_preview_mode_marks_others_attempted_false` —
   non-top groups carry `serp_attempted=False`.
3. `test_full_mode_serps_every_eligible_group` —
   ineligible-quantity groups skipped, all others completed.
4. `test_incremental_resumes_from_state` — run preview, then
   incremental; second run's network call count equals `eligible − preview_limit`.
5. `test_incremental_refuses_on_manifest_hash_mismatch` —
   state from manifest A vs current manifest B → raises clearly.
6. `test_state_file_atomic_write_survives_kill` — simulate
   half-written file via monkeypatch; orchestrator recovers.
7. `test_rank_is_deterministic_under_permutation` —
   shuffling group rows yields identical `(group_id_for_signature)`
   ranking output.
8. `test_failed_groups_recorded_in_state_not_completed` —
   provider raising on a group leaves it in `failed_signatures`.
9. `test_value_coverage_uses_inventory_value` — synthetic skewed
   manifest where 1 of 10 groups holds 90% of value; SERPing that 1
   group yields `value_coverage_pct == 90.0`, `row_coverage_pct == 10.0`.
10. `test_groups_needed_for_value_target_correct` — target 0.8 on a
    {0.6, 0.3, 0.05, 0.05} value-share manifest → answer is 2.
11. `test_orchestrator_publishes_amazon_price_per_group` — completed
    groups have `amazon_price` populated; row join (in pipeline test)
    propagates it to all member rows.

`tests/test_serp_cache_stats.py`:

12. `test_stats_count_hits_and_misses` — controlled hits/misses produce
    expected counters.
13. `test_stats_count_expired_separately_from_misses` — entry past TTL
    counts as `expired`, not `miss`.
14. `test_cache_invalidate_by_signature` — removes only matching rows.
15. `test_cache_invalidate_by_age` — removes only rows older than
    threshold.

## Documentation requirements

- [ ] `README.md` § 3: insert step 5.7 "Partial SERP enrichment" after
  the canonical-groups step (T-310). Cover the three modes with one
  worked example each.
- [ ] `README.md` § 4: add "Preview mode for big manifests" subsection
  with a copy-pasteable command:
  ```
  python -m pipeline.run_pipeline \
    --input data/big_manifest.xlsx --output output/reports \
    --execution-mode preview --serp-preview-limit 20
  ```
- [ ] `README.md` § 5: every new setting in the config table.
- [ ] `enrichment/serp_orchestrator.py` module docstring: explain why
  value coverage is the metric to watch, with the formula.
- [ ] State-file schema documented at the top of
  `enrichment/serp_state.py`.
- [ ] `tools/cache_invalidate.py` `--help` output covered by a doctest
  or `argparse`-rendered help excerpt in the README.

## Out of scope

- Multi-process / parallel SERP. The rate limit is the bottleneck; one
  worker is fine.
- Async / `asyncio` rewrite. Sync pandas + `requests` matches the rest
  of the pipeline. If we ever need parallelism we'll do it as a
  separate task with a clear motivation.
- Cross-manifest cache keys (i.e. sharing cache by SKU instead of
  signature). T-309's cache key is the signature, which already
  cross-amortises across manifests for free.
- Auto-tuning `SERP_PREVIEW_LIMIT` based on a budget knob in dollars.
  Operator-set for now; revisit after we have telemetry.
- Re-running a previously-failed group automatically. Operators decide:
  use `cache_invalidate` and re-run. Auto-retry of permanent failures
  burns the rate budget.

## Risks & considerations

- **Coverage math is the headline metric** the operator stares at.
  Getting it wrong (row-weighted instead of value-weighted) gives a
  falsely reassuring "95% complete!" on a manifest where 5% of rows
  hold 80% of value. Tests #9 and #10 are guard-rails — never delete
  them.
- **State file divergence.** Two pipelines pointing at the same state
  file with different manifests will collide. Manifest-hash check is
  the safety net; document the failure mode and the recovery
  (`--state-path` override or delete the file).
- **`failed_signatures` can grow unboundedly** across incremental
  runs. Add a cap (configurable, default 1000) and document what
  happens at the cap.
- **Cache stats are per-process** and reset on orchestrator
  construction — they describe one run, not lifetime cache health.
  This is intentional (per-run telemetry) but document it; an operator
  who wants lifetime stats queries the SQLite cache directly.
- **PREVIEW mode is a triage tool, not a final answer.** Document
  prominently that BUY recommendations from a preview run are
  provisional — half the manifest hasn't been priced from live data
  yet, and the catalog/heuristic fallback is in play for those rows.
