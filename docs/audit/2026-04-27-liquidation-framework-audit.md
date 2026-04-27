# Liquidation Intelligence Framework Audit — 2026-04-27

| Field | Value |
|---|---|
| Audit date (UTC) | 2026-04-27T15:12:56Z |
| Repo commit at audit | `d15f859` (claude/liquidation-intelligence-scaffold-wi2tT) |
| Test manifest | `data/e8c203803afa10d11e3844dd57636779.xlsx` (1,367 rows, 100 % "Not Tested" Bulk4Traders kitchen lot) |
| Auditor | Claude (Opus 4.7) |
| Framework | Six-layer professional liquidation framework: Input · Demand · Price · Cost · Channel · Decision |

---

## 1. System summary (how it currently works)

The pipeline is eight pure stages, each producing/consuming a typed `pandas.DataFrame`:

1. **Ingestion** (`ingestion/loader.py`) — CSV/XLSX → 25-alias canonical schema. Combines `Category L1..Ln` into a `>` breadcrumb (`raw_category`).
2. **Cleaning** (`processing/cleaner.py`) — noise stripping, brand inference (≈ 30-name `KNOWN_BRANDS`), category inference (8-category keyword map), condition normalisation (7 buckets).
3. **Enrichment** (`enrichment/enricher.py`) — `PriceProvider` chain returning `(amazon_price, wholesale_price, match_confidence)`. Default chain is the synthetic `MRPHeuristicPriceProvider` (`amazon = 0.80 × MRP`).
4. **Pricing** (`intelligence/pricing.py`) — `real_price = min(amazon × 0.7, wholesale, mrp × 0.45)`. Computes `discount_percentage`, `price_ratio`, `market_gap`.
5. **Scoring** (`intelligence/scoring.py`) — `sellability_score` and `risk_score` (each 0–100), weights configured.
6. **Profit** (`intelligence/profit.py`) — sell-through is `min(expected_sellable_pct, condition.sellable_factor)`, revenue = `sellable_qty × real_price × price_realization`, cost = `qty × floor × 1.05 + revenue × 0.25`.
7. **Scenario** (`intelligence/scenario.py`) — `scenario_roi_low/median/high` per row.
8. **Decision** (`intelligence/decision.py`) — per-row 5-gate BUY/REVIEW/SKIP + lot-level decision in JSON.

Output: ranked CSV + per-basket plain-text summary + machine-readable JSON lot summary.

---

## 2. Layer scores

| # | Layer                | Score |
|---|----------------------|------:|
| 1 | Input / Ingestion    | 6/10  |
| 2 | Demand Intelligence  | 3/10  |
| 3 | Price Intelligence   | 4/10  |
| 4 | Cost Engine          | 3/10  |
| 5 | Channel Routing      | 0/10  |
| 6 | Decision Engine      | 7/10  |
|   | **TOTAL**            | **23/60** |
|   | Grade                | **Weak** |

### Layer 1 — Input / Ingestion (6/10)
✅ multi-format read, alias map (25 entries), hierarchical category breadcrumb, junk-row drop, condition normalisation.
⚠️ `KNOWN_BRANDS` only 30 entries (Indian liquidation has hundreds); 8-category keyword map is shallow; brand string normalisation absent ("Amazon Brand - Solimo" / "Solimo" / "AmazonBasics" treated as different).
❌ no UPC/ASIN/EAN/model-number identity resolution; no SKU dedup; no unit-of-measure parsing; multi-language/Hinglish untested.

### Layer 2 — Demand Intelligence (3/10)
❌ `DEMAND_SCORE` and `CATEGORY_LIQUIDITY_SCORE` carry **identical values** in `config/settings.py:117-131` — two scoring weights backed by one signal.
❌ no real demand data: no Amazon BSR, Flipkart rank, Google Trends, search volume, sales-history, seasonality, or SKU velocity.
✅ `price_band` (LOW/MID/HIGH at 300/1000) gives a small directional signal.

### Layer 3 — Price Intelligence (4/10)
✅ `PriceProvider` Protocol with confidence is a clean seam.
⚠️ `FuzzyCatalogPriceProvider` exists but no catalog is wired in.
❌ no real price source; default chain is `0.80 × MRP` clamped to `0.45 × MRP` — entire system is functionally a function of MRP.
❌ no buy-box / multi-seller / historical-trend awareness.

### Layer 4 — Cost Engine (3/10) — **most consequential gap**
| Cost | Implemented? |
|---|---|
| Purchase cost | ✅ explicit |
| Acquisition overhead (5 %) | ✅ |
| Platform fees (Amazon/Flipkart/Meesho) | ❌ folded into flat `operating_cost_pct = 0.25` |
| Transport (category × weight) | ❌ |
| Sorting / packaging | ❌ |
| Inspection cost for `not_tested` | ❌ named in lot summary but never costed |
| Defect / damage buffer (independent of condition) | ❌ |
| Return rate (post-sale) | ❌ |
| Storage / holding cost | ❌ |
| GST / tax line item | ❌ |
| Reverse logistics for unsold | ❌ |

### Layer 5 — Channel Routing (0/10)
Feature absent. One decision per row, one set of fee/return assumptions, no Amazon-vs-Flipkart-vs-Meesho-vs-B2B logic. Inputs partially present (`brand`, `category`, `condition_normalized`, `price_band`) but nothing consumes them for routing.

### Layer 6 — Decision Engine (7/10) — best layer
✅ per-row 5-gate logic, lot-level summary with quartile ROI, explainable reasoning, scenario stress-test, untested-vs-defective separation, match-confidence flagging.
❌ thresholds are magic numbers (60/60/15/25); no calibration against realised outcomes; no probabilistic/CI output; no learning loop.

---

## 3. Gap analysis

### Critical (will cause real losses)
1. **Cost engine collapses 8 cost streams into one flat 25 %.** Real Amazon fees vary 5–30 % by category; returns vary 5–30 % by category; transport varies by weight. Single flat number is miscalibrated by 10+ percentage points either way.
2. **No real price signal anywhere.** Every revenue projection is a function of MRP, not market.
3. **No inspection cost for `not_tested` items**, despite the lot summary naming inspection as the dominant cost. Decision is overconfident on Bulk4Traders-style "Not Tested" lots specifically.
4. **No return-rate model.** Apparel and electronics lots will look profitable on paper and bleed cash on returns.

### Medium (limits scale)
5. Channel routing absent — operator must manually decide where to sell every BUY.
6. `DEMAND_SCORE` and `CATEGORY_LIQUIDITY_SCORE` identical maps (duplicate signal).
7. `KNOWN_BRANDS` is 30 entries vs 200+ relevant Indian brands.
8. No SKU dedup / lot-level rollup (412 identical Pigeon items scored 412×).
9. Threshold calibration unprincipled (60/60/15/25 are guesses).
10. Hard-coded constants in `pricing.py` (`× 0.7`, `× 0.45`) not in `config/settings.py`.

### Minor
11. Brand string normalisation ("Solimo" variants).
12. `CATEGORY_RISK_SCORE` apparel=45 underweights sizing-return risk.
13. `min_sellable_count = 10` literal in `decision.py:96` (should be config).
14. No CLI flag to override the provider chain.
15. No persistent run-history (no run-over-run diff).
16. JSON summary lacks per-condition breakdown of qty / projected-profit.

---

## 4. Verdict

**Can this system make money? UNSTABLE.**

- As a **per-lot triage / ranking tool** — yes. Relative ranking within a lot is ~correct because `floor / mrp`, brand recognition, and category demand are decent proxies. Use it to cherry-pick the top 30–40 % of items.
- As a **go/no-go decision tool** — no. Absolute profit/ROI numbers can't be trusted because real fees vary 5–30 % (engine assumes 25 %), real returns vary 5–30 % (engine assumes 0 %), real prices vary by demand (engine uses 0.45 × MRP), and inspection cost is unmodelled. A 37 % projected BUY-basket ROI is consistent with a real outcome between –5 % and +60 %.

**Biggest risk**: Cost engine. A single `operating_cost_pct = 0.25` is the load-bearing wall and substitutes for eight separate cost streams. Apply this engine to an apparel lot and projected ROI will be off by 20+ percentage points.

**Biggest strength**: Decision-engine architecture. Per-row + lot-level decisions, explainable reasoning, scenarios, confidence flagging, calibration knobs in one config, hierarchical category preservation, condition-aware risk. Add the four Phase-1 cost components and this becomes a real tool.

---

## 5. Real-manifest result snapshot at audit

Run on `data/e8c203803afa10d11e3844dd57636779.xlsx` at commit `d15f859`:

| Bucket | Items | Cost | Profit | ROI |
|---|---:|---:|---:|---:|
| BUY    | 566 | ₹420,980 | ₹157,183 | **37.3 %** |
| REVIEW | 407 | ₹260,137 | ₹21,389  | 8.2 %  |
| SKIP   | 394 | ₹265,841 | -₹33,280 | -12.5 % |

Lot-level decision: REVIEW. Median row ROI 65 %. Decision reasons: "High ROI", "Strong brand mix", "Lot is largely untested — inspection cost dominates".

> **Caveat**: these numbers are with `operating_cost_pct = 0.25` as a flat substitute for all post-purchase costs. Real ROI on this lot, after Amazon kitchen-category fees (~15–20 %) + transport (5–8 % of revenue for bulky kitchen items) + reverse logistics + ~8 % return rate + inspection of 1,367 untested items at ₹50/unit (~₹68 K = 16 % of cost), is plausibly closer to 0–10 %.

---

## 6. Fix plan headline

| Phase | Goal | Tasks | Headline impact |
|---|---|---|---|
| **1** | Make absolute ROI numbers trustable | T-101 .. T-106 | Decompose cost engine, add inspection / transport / returns, gate on price uncertainty |
| **2** | Scale beyond a single platform / lot | T-201 .. T-207 | Channel routing, real catalog, calibration, lot rollup |
| **3** | Self-improving intelligence | T-301 .. T-306 | Real demand data, ML sell-through, feedback loop, confidence intervals |

See `docs/wbs/` for the full Work Breakdown Structure. Each task is self-contained and pickable by any LLM.
