# Work Breakdown Structure — bulk-intel

This directory tracks the engineering plan that closes the gaps surfaced in
[`docs/audit/2026-04-27-liquidation-framework-audit.md`](../audit/2026-04-27-liquidation-framework-audit.md).

---

## Conventions

Each task is a single Markdown file (`T-NNN-slug.md`) and is **self-contained**
— any LLM (or human) should be able to pick a single file, read it, and
implement the change without needing additional context. Every task ships with:

- **Context & motivation** linking back to the audit gap.
- **Files to create / modify** with absolute paths.
- **Specifications** including config schema and function signatures.
- **Acceptance criteria** that are concrete and testable.
- **Test requirements** with file paths and at least 2–3 cases described.
- **Documentation requirements** per `CLAUDE.md`.
- **Dependencies** on other task IDs.
- **Out of scope** to prevent scope creep.
- **Estimated effort** in hours.

When you pick a task:

1. Create a feature branch off `main`: `feat/T-NNN-slug`.
2. Implement against the acceptance criteria.
3. Ship the documentation update **in the same commit** (per `CLAUDE.md`).
4. Add the regression tests listed in the task.
5. Run `pytest` — must stay green.
6. Run the pipeline against `data/e8c203803afa10d11e3844dd57636779.xlsx` and
   record the new BUY / REVIEW / SKIP distribution in the PR description.
7. Open a PR, link the task file, and tick the acceptance-criteria checklist.

---

## Phase 1 — Cost-engine truth (P0, must ship before any real money is spent)

| ID | Title | Effort | Depends on |
|---|---|---:|---|
| [T-101](phase-1/T-101-platform-fee-table.md) | Decompose `operating_cost_pct` into platform × category fee table | 6 h | — |
| [T-102](phase-1/T-102-inspection-cost.md) | Add inspection cost for `not_tested` / `unknown` | 3 h | — |
| [T-103](phase-1/T-103-transport-cost.md) | Add category-aware transport cost (weight tiers) | 5 h | — |
| [T-104](phase-1/T-104-return-rate-model.md) | Add return-rate model (per category) | 5 h | T-101 |
| [T-105](phase-1/T-105-cost-decomposition-output.md) | Surface cost decomposition in CSV + JSON | 2 h | T-101, T-102, T-103, T-104 |
| [T-106](phase-1/T-106-uncertain-price-gate.md) | Hard gate: low `match_confidence` downgrades BUY → REVIEW | 2 h | — |

**Phase 1 exit criteria**: every BUY recommendation has an auditable per-row
cost breakdown (purchase / platform_fee / transport / inspection / packaging /
return_provision); CSV + JSON outputs include all those columns / keys; backtest
on the real manifest reproduces an ROI that's plausible against a hand-checked
set of 5 SKUs.

## Phase 2 — Scale & calibration (P1)

| ID | Title | Effort | Depends on |
|---|---|---:|---|
| [T-201](phase-2/T-201-channel-router.md) | Channel router (Amazon / Flipkart / Meesho / B2B) | 8 h | T-101 |
| [T-202](phase-2/T-202-distinguish-demand-liquidity.md) | Differentiate `DEMAND_SCORE` from `CATEGORY_LIQUIDITY_SCORE` | 2 h | — |
| [T-203](phase-2/T-203-expand-known-brands.md) | Expand `KNOWN_BRANDS` to 200+ Indian brands; add normalisation | 4 h | — |
| [T-204](phase-2/T-204-sku-rollup.md) | Lot rollup view (group by SKU / product) | 4 h | — |
| [T-205](phase-2/T-205-backtest-harness.md) | Backtest harness for threshold calibration | 8 h | T-101..T-104 |
| [T-206](phase-2/T-206-pricing-constants-to-config.md) | Move `pricing.py` constants to `config/settings.py` | 2 h | — |
| [T-207](phase-2/T-207-real-catalog-seed.md) | Seed `FuzzyCatalogPriceProvider` with real top-1k catalog | 10 h | — |

**Phase 2 exit criteria**: each BUY row carries a recommended channel; thresholds
have been re-calibrated against ≥ 2 historical lots; lot rollup is the default
operator view.

## Phase 3 — Self-improving intelligence (P2)

| ID | Title | Effort | Depends on |
|---|---|---:|---|
| [T-301](phase-3/T-301-amazon-bsr-ingestion.md) | Amazon BSR ingestion provider | 12 h | T-207 |
| [T-302](phase-3/T-302-sku-velocity-model.md) | SKU velocity / sell-through history model | 16 h | T-301 |
| [T-303](phase-3/T-303-capital-cost-holding-period.md) | Capital cost / holding-period model | 6 h | T-104 |
| [T-304](phase-3/T-304-ml-sell-through-model.md) | ML model for sell-through (replaces static condition factor) | 24 h | T-205, T-302 |
| [T-305](phase-3/T-305-outcome-feedback-loop.md) | Outcome feedback loop (closes the prior-update cycle) | 12 h | T-205 |
| [T-306](phase-3/T-306-confidence-intervals.md) | Confidence intervals on every projection | 8 h | T-205 |

**Phase 3 exit criteria**: every BUY decision ships with a 90 % CI on profit /
ROI; engine measurably improves on each new realised lot fed back through T-305.

---

## Status board

Update this section when a task ships.

| ID | Status | Owner | PR / Commit |
|---|---|---|---|
| T-101 | Not started | — | — |
| T-102 | Not started | — | — |
| T-103 | Not started | — | — |
| T-104 | Not started | — | — |
| T-105 | Not started | — | — |
| T-106 | Not started | — | — |
| T-201 | Not started | — | — |
| T-202 | Not started | — | — |
| T-203 | Not started | — | — |
| T-204 | Not started | — | — |
| T-205 | Not started | — | — |
| T-206 | Not started | — | — |
| T-207 | Not started | — | — |
| T-301 | Not started | — | — |
| T-302 | Not started | — | — |
| T-303 | Not started | — | — |
| T-304 | Not started | — | — |
| T-305 | Not started | — | — |
| T-306 | Not started | — | — |
