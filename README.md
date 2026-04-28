# bulk-intel — Liquidation Intelligence Engine

A production-grade Python pipeline that ingests liquidation marketplace
manifests (e.g. Bulk4Traders), scores each line item, projects
profitability, and emits **Buy / Review / Skip** recommendations with
explainable reasoning — both **per-row** and at the **lot level**.

The system is designed to evolve into a SaaS product: a clean
architecture with deterministic, testable rules today, and seams for
ML scoring, web scraping, fuzzy catalog matching, and a FastAPI layer
tomorrow.

---

## 1. System overview

```
                ┌──────────────────────────────────────────────┐
                │           Liquidation Intelligence            │
                │                  Engine (LIE)                 │
                └──────────────────────────────────────────────┘

  Manifest CSV/XLSX
        │
        ▼
  ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ Ingestion  │ ─► │  Cleaning  │ ─► │ Enrichment │
  │  loader.py │    │ cleaner.py │    │ enricher.py│
  └────────────┘    └────────────┘    └────────────┘
        │                 │                  │
        │  raw_category    brand /        amazon_price /
        │  + alias map    normalized_     wholesale_price
        │                 category +      + match_confidence
        │                 condition       + unreliable_match
        ▼                 ▼                  ▼
  ┌──────────────────────────────────────────────────────────┐
  │                  Intelligence Layer                       │
  │                                                           │
  │  pricing.py ─► scoring.py ─► profit.py ─► scenario.py    │
  │  real_price    sellability   revenue /     low / median / │
  │  + discount /  + risk +      ROI / margin  high ROI       │
  │  market_gap    price_band                  scenarios      │
  │                                                           │
  │                              ─► decision.py               │
  │                                  per-row BUY/REVIEW/SKIP  │
  │                                  + lot-level decision     │
  │                                  + decision_reasons       │
  └──────────────────────────────────────────────────────────┘
        │
        ▼
  ┌────────────┐   ranked CSV
  │   Output   │ ─►  per-basket plain-text summary
  │ reporter.py│    JSON lot summary (machine-readable)
  └────────────┘
```

Key principles:

- **Single canonical schema** between every stage (defined in
  `ingestion/loader.py`).  Real-world manifests carry alias columns
  (`Tag Number`, `MRP ( in INR )`, hierarchical `Category L1..L6`) —
  the loader normalizes them and preserves the full breadcrumb in
  `raw_category`.
- **Pure stage modules**: each stage is a small, type-hinted, testable
  unit with no I/O outside ingestion + reporting.
- **Configurable, not hard-coded**: weights, thresholds, condition
  factors, profit assumptions, and category priors all live in
  `config/settings.py`.
- **Pluggable enrichment**: `PriceProvider` Protocol now returns
  `(amazon_price, wholesale_price, match_confidence)`.  Drop-in
  providers ship for in-memory lookup, MRP heuristic, and fuzzy
  catalog matching — a future scraper or external API plugs in
  without touching the rest of the pipeline.
- **Condition-aware economics**: liquidation goods are normalized to
  one of seven buckets (`new`, `like_new`, `used_good`, `used_fair`,
  `not_tested`, `defective`, `unknown`).  Each carries a
  `sellable_factor` and `risk_score`; "Not Tested" inventory is
  treated as untested-but-mostly-functional, distinct from confirmed
  `defective`.
- **Explicit price uncertainty**: `match_confidence` and
  `unreliable_match` flow through to the lot summary so an operator
  knows when the engine is interpolating.
- **Per-row + lot-level decisions**: the per-row decision column
  ranks individual items; the lot-level JSON summary tells you
  whether to buy the *whole* lot, with quartile ROI and explanatory
  reasons.
- **Deterministic before ML**: rule-based scoring today; the same
  inputs/outputs let an ML model replace `intelligence/scoring.py`
  later without disturbing surrounding code.

---

## 2. Folder structure

```
bulk-intel/
├── README.md
├── CLAUDE.md                        # Project conventions for contributors
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── __init__.py
│   └── settings.py                  # Weights, thresholds, condition factors
├── ingestion/
│   ├── __init__.py
│   └── loader.py                    # CSV/XLSX → canonical DataFrame
├── processing/
│   ├── __init__.py
│   └── cleaner.py                   # Text cleanup + brand/category/condition
├── enrichment/
│   ├── __init__.py
│   └── enricher.py                  # PriceProvider strategies (incl. fuzzy)
├── intelligence/
│   ├── __init__.py
│   ├── pricing.py                   # real_price + discount / gap metrics
│   ├── scoring.py                   # Sellability + condition-aware risk
│   ├── profit.py                    # Revenue / margin / ROI simulator
│   ├── scenario.py                  # Per-row low/median/high ROI scenarios
│   └── decision.py                  # Per-row + lot-level decisions
├── output/
│   ├── __init__.py
│   └── reporter.py                  # Ranked CSV + summary + JSON lot file
├── pipeline/
│   ├── __init__.py
│   └── run_pipeline.py              # Orchestrator + CLI
├── utils/
│   ├── __init__.py
│   └── logging.py                   # Centralised logger
├── data/
│   ├── sample_manifest.csv          # 15-row demo manifest
│   └── e8c20...xlsx                 # Real Bulk4Traders manifest (1,367 rows)
└── tests/
    ├── conftest.py
    ├── test_loader.py
    ├── test_cleaner.py
    ├── test_pricing_and_scoring.py
    ├── test_real_manifest_schema.py     # Tag Number, MRP ( in INR ), Cat L1..Ln
    ├── test_condition_aware_economics.py # Condition → sell-through / risk
    └── test_pipeline.py                  # End-to-end + JSON lot summary keys
```

---

## 3. Data flow

1. **Ingestion** (`ingestion/loader.py`)
   - Reads `.csv`, `.xlsx`, `.xls`.
   - Aliases ~25 source column variants to the canonical schema
     (`Tag Number`/`Inventory ID` → `sku`, `MRP ( in INR )` → `mrp`, …).
   - Combines hierarchical `Category L1..Ln` columns into a single
     breadcrumb `raw_category` (e.g. `"Others > Kitchenware > Mixer"`)
     and drops the per-level columns.
   - Coerces numerics, drops fully-empty rows, defaults `quantity = 1`.
2. **Cleaning** (`processing/cleaner.py`)
   - Strips manifest noise (`Open Box`, `Lot of N`, parentheticals…).
   - Title-cases product names; extracts keywords.
   - Infers `brand` and `normalized_category` when missing
     (`category` is kept as an alias of `normalized_category`).
   - Normalizes free-text condition labels into one of seven canonical
     buckets: `new`, `like_new`, `used_good`, `used_fair`,
     `not_tested`, `defective`, `unknown`.
3. **Enrichment** (`enrichment/enricher.py`)
   - Resolves `amazon_price`, `wholesale_price`, `match_confidence`,
     `unreliable_match` via a chain of `PriceProvider`s.  Default
     chain: `MRPHeuristicPriceProvider`.  A `FuzzyCatalogPriceProvider`
     ships out of the box for `difflib`-based matching against an
     in-memory catalog.
   - The MRP heuristic anchors **new-condition** retail price
     (default `0.80 × MRP`); condition factors mark down sell-through
     downstream so we don't double-discount.
4. **Pricing intelligence** (`intelligence/pricing.py`)
   - Computes `real_price = min(amazon_price × 0.7, wholesale_price,
     mrp × 0.45)` — the most pessimistic of available anchors so
     downstream profit projections lean conservative.
   - Adds `discount_percentage`, `price_ratio`, `market_gap`,
     `wholesale_gap`.
5. **Scoring** (`intelligence/scoring.py`)
   - `sellability_score` (0–100) — weighted sum of discount,
     market_gap, demand_score, category_liquidity, brand_score, and
     a price-band signal (LOW / MID / HIGH).
   - `risk_score` (0–100) — weighted sum of missing-data,
     low-quantity, category risk, thin-margin, **and condition risk**
     (e.g. `not_tested` adds +60, `defective` adds +90 before
     weighting).
6. **Profitability** (`intelligence/profit.py`)
   - Projects `expected_sellable_qty`, `expected_sell_price`,
     `expected_revenue`, `transport_cost`, `inspection_cost`,
     `platform_fee_pct`, `expected_cost`, `expected_profit`,
     `expected_margin_pct`, `expected_roi_pct`.
   - Operating cost is `platform_fees[platform][category] +
     ancillary_revenue_fee_pct` (T-101); inspection cost is
     `qty × inspection_cost_by_condition[condition]` (T-102);
     transport cost is
     `qty × transport_cost_per_unit[category_weight_tier]` (T-103).
   - Uses `real_price` directly (no double-discount on price).
   - Combines the base `expected_sellable_pct` with the condition's
     `sellable_factor` via **`min(base, condition_factor)`**, not
     multiplication, so the more binding constraint wins and we don't
     stack the same conservatism twice.
   - `price_realization_factor` defaults to `1.0` (off); the realistic
     discount vs MRP is already baked into `real_price`.
   - ROI = `(revenue − lot_cost) / lot_cost` where
     `lot_cost = quantity × floor_price`.
7. **Scenario stress test** (`intelligence/scenario.py`)
   - Adds `scenario_roi_low`, `scenario_roi_median`, `scenario_roi_high`
     per row.  Default scenarios:
     pessimistic (50 %, 60 %), base (65 %, 75 %), optimistic (80 %, 90 %)
     for `(sell_through, price_realization)`.
8. **Decision** (`intelligence/decision.py`)
   - **Per-row**: five gates (sellability ≥ min, risk ≤ max, margin ≥
     min, ROI ≥ min, profit > 0).  All five → `BUY`; ≥ 3 with risk +
     profit OK → `REVIEW`; otherwise `SKIP`.  Each row carries a
     `reasoning` string with the per-gate verdict.
   - **Lot-level** (in `df.attrs["lot_summary"]`): three gates
     (median ROI, margin, total expected sellable units).  Emits a
     dict with `total_items`, `expected_sellable`, `expected_revenue`,
     `roi_low/median/high` (quartiles), `untested_pct`, `defect_pct`,
     `high_unknown_condition_pct`, `low_match_confidence_pct`,
     `high_price_uncertainty`, `margin`, `decision`, and human-readable
     `decision_reasons`.
9. **Output** (`output/reporter.py`)
   - Writes a ranked CSV sorted by sellability with all derived
     columns (incl. `condition_normalized`, `expected_roi_pct`,
     `scenario_roi_*`, `match_confidence`, `unreliable_match`).
   - Plain-text summary breaks out **per-basket economics**
     (BUY / REVIEW: revenue, cost, profit, ROI) plus the top 10 BUY
     candidates.
   - JSON lot summary file (`*_summary.json`) for dashboards and
     downstream automation.

---

## 4. How to run

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### CLI

```bash
# Demo manifest (15 rows)
python -m pipeline.run_pipeline \
  --input data/sample_manifest.csv \
  --output output/reports

# Real Bulk4Traders manifest (1,367 rows, all "Not Tested")
python -m pipeline.run_pipeline \
  --input data/e8c203803afa10d11e3844dd57636779.xlsx \
  --output output/reports
```

Each run produces three files in `--output`:

```
<input_stem>_report.csv          # ranked, fully scored line items
<input_stem>_report_summary.txt  # human-readable per-basket economics
<input_stem>_report_summary.json # machine-readable lot summary
```

Example JSON lot summary (real manifest):

```json
{
  "total_items": 1367,
  "expected_sellable": 574.14,
  "expected_revenue": 529320.22,
  "roi_low": -33.78,
  "roi_median": -19.83,
  "roi_high": -2.17,
  "untested_pct": 100.0,
  "defect_pct": 0.0,
  "high_unknown_condition_pct": 0.0,
  "low_match_confidence_pct": 0.0,
  "high_price_uncertainty": false,
  "margin": -52.31,
  "decision": "SKIP",
  "decision_reasons": [
    "Low ROI",
    "Strong brand mix",
    "Lot is largely untested — inspection cost dominates"
  ]
}
```

The lot decision can be `SKIP` while individual rows are `BUY` —
the per-row CSV is the cherry-pick list, while the lot JSON answers
"should I buy the *whole* lot?".

### Programmatic use

```python
from pipeline.run_pipeline import Pipeline
from enrichment.enricher import (
    LookupTablePriceProvider,
    FuzzyCatalogPriceProvider,
    MRPHeuristicPriceProvider,
)

catalog = [
    {"product_name": "Pigeon Mixer Grinder",
     "amazon_price": 3500.0, "wholesale_price": 2400.0},
    # …
]

pipe = Pipeline(
    providers=[
        # Highest priority: explicit per-SKU overrides.
        LookupTablePriceProvider({"B4T-0001": (8500.0, None, 1.0)}),
        # Next: fuzzy match against a catalog (returns confidence).
        FuzzyCatalogPriceProvider(catalog=catalog, confidence_threshold=0.6),
        # Fallback: deterministic MRP heuristic.
        MRPHeuristicPriceProvider(market_pct_of_mrp=0.80),
    ]
)
outputs = pipe.run("data/sample_manifest.csv", "output/reports")
```

### Tests

```bash
pytest
```

---

## 5. Configuration

Open `config/settings.py` to tune behaviour. Common knobs:

| Setting                                              | Effect                                                          |
| ---------------------------------------------------- | --------------------------------------------------------------- |
| `SCORING_WEIGHTS`                                    | Sellability sub-component weights (discount, market_gap, demand, liquidity, brand, price_band) |
| `RISK_WEIGHTS`                                       | Risk sub-component weights (incl. `condition_risk`)             |
| `INSPECTION_COST_BY_CONDITION`                       | Inspection cost per unit applied by condition                   |
| `PROFIT_ASSUMPTIONS["expected_sellable_pct"]`        | Base/cap sell-through. Combined with the per-condition `sellable_factor` via `min(base, condition_factor)` so the more binding constraint wins (no multiplicative double-counting) |
| `PROFIT_ASSUMPTIONS["expected_sell_price_vs_mrp"]`   | Anchor when no real price available                             |
| `PROFIT_ASSUMPTIONS["price_realization_factor"]`     | Optional extra haircut on revenue. Defaults to **1.0 (off)** because `real_price` already encodes the realistic-vs-MRP discount. Drop below 1.0 to model clearance/promo erosion |
| `PLATFORM_FEES` / `ANCILLARY_REVENUE_FEE_PCT`        | Logistics + fees as % of revenue                                |
| `PROFIT_ASSUMPTIONS["acquisition_overhead_pct"]`     | Hidden costs of acquiring the lot                               |
| `DECISION_THRESHOLDS["buy_score_min"]`               | Min sellability score for BUY                                   |
| `DECISION_THRESHOLDS["risk_score_max"]`              | Max risk score for BUY/REVIEW                                   |
| `DECISION_THRESHOLDS["min_expected_margin_pct"]`     | Min margin-on-revenue for BUY                                   |
| `DECISION_THRESHOLDS["min_expected_roi_pct"]`        | Min ROI-on-cost for BUY                                         |
| `DECISION_THRESHOLDS["min_buy_match_confidence"]`    | Min match confidence for BUY (missing column defaults to 1.0)   |
| `CONDITION_TO_SELL_THROUGH`                          | Per-condition `(sellable_factor, risk_score)` map               |
| `DEMAND_SCORE` / `CATEGORY_LIQUIDITY_SCORE` / `CATEGORY_RISK_SCORE` | Per-category demand / liquidity / risk priors        |
| `CATEGORY_WEIGHT_TIER`                               | Maps categories to weight tiers (`small`, `medium`, `bulky`, `weightless`) |
| `TRANSPORT_COST_PER_UNIT`                            | Defines ₹/unit transport cost per weight tier                   |
| `KNOWN_BRANDS`                                       | Brand recognition list                                          |

Set `BULK_INTEL_LOG_LEVEL=DEBUG` for verbose stage logs.

### Condition buckets (`CONDITION_TO_SELL_THROUGH`)

| Bucket       | Sellable factor | Risk score | Notes                                                    |
| ------------ | --------------- | ---------- | -------------------------------------------------------- |
| `new`        | 1.00            | 10         | Sealed / brand-new / NIB                                 |
| `like_new`   | 0.90            | 25         | Open box, customer return                                |
| `used_good`  | 0.75            | 40         | Refurbished / good condition                             |
| `used_fair`  | 0.60            | 60         | Pre-owned / fair                                         |
| `not_tested` | 0.65            | 60         | Untested but mostly functional after inspection (Amazon-return inventory) |
| `defective`  | 0.20            | 90         | Confirmed broken / salvage / as-is                       |
| `unknown`    | 0.50            | 60         | Manifest didn't carry a recognisable label               |

---

## 6. Extension points

- **Real market prices**: implement a class with the `PriceProvider`
  Protocol — `name: str` and
  `lookup(row) -> (amazon, wholesale, confidence)` — and pass it into
  `Pipeline(providers=[...])`. No other module changes.
- **Fuzzy catalog matching**: `FuzzyCatalogPriceProvider` already does
  `difflib`-based name matching with a configurable confidence
  threshold; feed it any list of `{product_name, amazon_price,
  wholesale_price}` dicts.
- **New condition labels**: add a row to `CONDITION_TO_SELL_THROUGH`
  in `config/settings.py` and a regex to `_CONDITION_PATTERNS` in
  `processing/cleaner.py`.  Pattern order matters — put more specific
  patterns (e.g. `not\s*tested`) before more general ones (e.g.
  `defective|salvage|as[-\s]?is`).  Risk + profit pick it up
  automatically.
- **New source schemas**: add aliases to `COLUMN_ALIASES` in
  `ingestion/loader.py`; for hierarchical category columns the
  loader's `_retain_raw_category` already handles `Category L1..Ln`.
- **ML scoring**: replace `ScoringEngine.compute` with a model call;
  inputs (cleaned + priced DataFrame) and outputs
  (`sellability_score`, `risk_score`) are stable contracts.
- **API layer**: wrap `Pipeline.run_dataframe` in a FastAPI endpoint;
  `requirements.txt` already includes the optional `fastapi` extras.
  The JSON lot summary is designed to be the API response body.
- **Dashboard**: the ranked CSV + JSON summary are designed to feed
  directly into a Streamlit / Looker / Metabase front-end.

---

## 7. Contributing

Project conventions live in `CLAUDE.md`.  Highlights:

- Update `README.md`, module docstrings, and the config table in the
  same commit as any behaviour change.
- Every externally visible behaviour change ships with a regression
  test under `tests/`.
- Stages stay pure: only `ingestion` and `output` perform I/O.

### Audit + roadmap (`docs/`)

- [`docs/audit/2026-04-27-liquidation-framework-audit.md`](docs/audit/2026-04-27-liquidation-framework-audit.md)
  — six-layer professional-framework audit (input / demand / price / cost /
  channel / decision), gap analysis, and verdict.
- [`docs/wbs/`](docs/wbs/) — Work Breakdown Structure of 19 self-contained
  tasks (T-101..T-306) across three phases. Every task file is pickable by
  any LLM or contributor and contains: motivation, files to modify,
  specifications, acceptance criteria, test requirements, documentation
  requirements, dependencies, and out-of-scope.
  - [Phase 1](docs/wbs/README.md#phase-1--cost-engine-truth-p0-must-ship-before-any-real-money-is-spent)
    — cost-engine truth (P0).
  - [Phase 2](docs/wbs/README.md#phase-2--scale--calibration-p1)
    — scale & calibration.
  - [Phase 3](docs/wbs/README.md#phase-3--self-improving-intelligence-p2)
    — self-improving intelligence.

---

## 8. License

MIT.
