# bulk-intel — Liquidation Intelligence Engine

A production-grade Python pipeline that ingests liquidation marketplace
manifests (e.g. Bulk4Traders), scores each line item, projects
profitability, and emits **Buy / Review / Skip** recommendations with
explainable reasoning.

The system is designed to evolve into a SaaS product: a clean
architecture with deterministic, testable rules today, and seams for
ML scoring, web scraping, and a FastAPI layer tomorrow.

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
        │            brand/category     market_price
        │            condition          wholesale_price
        │            normalization
        ▼                 ▼                  ▼
  ┌──────────────────────────────────────────────────────┐
  │                Intelligence Layer                    │
  │                                                      │
  │  pricing.py ─► scoring.py ─► profit.py ─► decision.py│
  │  discount/      sellability   revenue/       BUY /    │
  │  market_gap     risk +        margin / ROI   REVIEW / │
  │                 condition     condition-     SKIP +   │
  │                 risk          aware          why      │
  └──────────────────────────────────────────────────────┘
        │
        ▼
  ┌────────────┐
  │   Output   │ ─►  ranked CSV + per-basket summary (BUY / REVIEW)
  │ reporter.py│
  └────────────┘
```

Key principles:

- **Single canonical schema** between every stage (defined in
  `ingestion/loader.py`).  Real-world manifests carry alias columns
  (`Tag Number`, `MRP ( in INR )`, hierarchical `Category L1..L6`) —
  the loader collapses them to the canonical names.
- **Pure stage modules**: each stage is a small, type-hinted, testable
  unit with no I/O outside ingestion + reporting.
- **Configurable, not hard-coded**: weights, thresholds, condition
  factors, and assumptions live in `config/settings.py`.
- **Pluggable enrichment**: `PriceProvider` Protocol means a future
  scraper or external API drops in without touching the pipeline.
- **Condition-aware economics**: liquidation goods (`Open Box`,
  `Refurbished`, `Used`, `As-Is`, `Not Tested`, `Salvage`) get
  per-bucket sell-price, sell-through, and risk multipliers — so an
  "as-is" item isn't priced at retail.
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
│   └── enricher.py                  # PriceProvider strategies
├── intelligence/
│   ├── __init__.py
│   ├── pricing.py                   # Discount / gap metrics
│   ├── scoring.py                   # Sellability + condition-aware risk
│   ├── profit.py                    # Revenue / margin / ROI simulator
│   └── decision.py                  # BUY / REVIEW / SKIP + reasoning
├── output/
│   ├── __init__.py
│   └── reporter.py                  # Ranked CSV + per-basket summary
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
    ├── test_condition_aware_economics.py # Condition → price/qty/risk
    └── test_pipeline.py
```

---

## 3. Data flow

1. **Ingestion** (`ingestion/loader.py`)
   - Reads `.csv`, `.xlsx`, `.xls`.
   - Aliases ~25 source column variants to the canonical schema
     (`Tag Number`/`Inventory ID` → `sku`, `MRP ( in INR )` → `mrp`, …).
   - Collapses hierarchical category columns (`Category L1..L6`) to the
     deepest non-placeholder level (skips "Others" / "Misc" / "N/A").
   - Coerces numerics, drops fully-empty rows, defaults `quantity = 1`.
2. **Cleaning** (`processing/cleaner.py`)
   - Strips manifest noise (`Open Box`, `Lot of N`, parentheticals…).
   - Title-cases product names.
   - Extracts keywords; infers `brand` and `category` when missing.
   - Normalizes free-text condition labels into one of nine canonical
     buckets (`new`, `sealed`, `open_box`, `refurbished`, `used`,
     `as_is`, `not_tested`, `salvage`, `unknown`).
3. **Enrichment** (`enrichment/enricher.py`)
   - Resolves `market_price` and `wholesale_price` via a chain of
     `PriceProvider`s (lookup table → MRP heuristic by default).
   - The MRP heuristic anchors **new-condition** retail price
     (default 0.80 × MRP); condition factors mark it down later so we
     don't double-discount.
4. **Pricing intelligence** (`intelligence/pricing.py`)
   - `discount_percentage`, `price_ratio`, `market_gap`, `wholesale_gap`.
5. **Scoring** (`intelligence/scoring.py`)
   - `sellability_score` (0–100) — weighted sum of discount, market
     gap, category demand, and brand strength.
   - `risk_score` (0–100) — weighted sum of missing-data,
     low-quantity, category risk, thin-margin **and condition risk**
     (e.g. `not_tested` adds +60, `salvage` adds +90 before weighting).
6. **Profitability** (`intelligence/profit.py`)
   - Projects `expected_revenue`, `expected_cost`, `expected_profit`,
     `expected_margin_pct` and `expected_roi_pct` using
     `PROFIT_ASSUMPTIONS` × `CONDITION_FACTORS`.  Condition affects
     both the realised sell price *and* the sell-through fraction.
7. **Decision** (`intelligence/decision.py`)
   - Five gates: sellability ≥ min, risk ≤ max, margin ≥ min,
     **ROI ≥ min**, and projected profit > 0.
   - All five gates pass → `BUY`; ≥ 3 pass with risk + profit OK →
     `REVIEW`; otherwise `SKIP`.
   - Emits a `reasoning` string with the per-gate verdict so every
     decision is defensible.
8. **Output** (`output/reporter.py`)
   - Writes a ranked CSV sorted by sellability with all derived columns
     (including `condition_normalized` and `expected_roi_pct`).
   - Plain-text summary breaks out **per-basket economics**
     (BUY / REVIEW: revenue, cost, profit, ROI) plus the top 10 BUY
     candidates — not a misleading grand total over all rows.

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

Each run produces two files in `--output`:

```
<input_stem>_report.csv         # ranked, fully scored line items
<input_stem>_report_summary.txt # per-basket economics + top BUY picks
```

Sample summary (real manifest):

```
Total rows           : 1367
  BUY                : 147
  REVIEW             : 419
  SKIP               : 801

--- BUY basket (147 items) ---
  projected revenue:     124,503.07
  projected cost   :      87,971.49
  projected profit :      36,530.76
  projected ROI    :          41.5%

--- REVIEW basket (419 items) ---
  projected revenue:     338,027.96
  projected cost   :     304,100.61
  projected profit :      33,925.32
  projected ROI    :          11.2%
```

### Programmatic use

```python
from pipeline.run_pipeline import Pipeline
from enrichment.enricher import LookupTablePriceProvider, MRPHeuristicPriceProvider

pipe = Pipeline(
    providers=[
        LookupTablePriceProvider({"B4T-0001": (8500.0, None)}),  # manual override
        MRPHeuristicPriceProvider(market_pct_of_mrp=0.80),       # fallback
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

| Setting                                            | Effect                                                 |
| -------------------------------------------------- | ------------------------------------------------------ |
| `SCORING_WEIGHTS`                                  | Sellability sub-component weights                      |
| `RISK_WEIGHTS`                                     | Risk sub-component weights (incl. `condition_risk`)    |
| `PROFIT_ASSUMPTIONS["expected_sellable_pct"]`      | % of inventory expected to sell (before condition mul.) |
| `PROFIT_ASSUMPTIONS["expected_sell_price_vs_mrp"]` | Anchor when no market price available                  |
| `PROFIT_ASSUMPTIONS["operating_cost_pct"]`         | Logistics + fees as % of revenue                       |
| `DECISION_THRESHOLDS["buy_score_min"]`             | Min sellability score for BUY                          |
| `DECISION_THRESHOLDS["risk_score_max"]`            | Max risk score for BUY/REVIEW                          |
| `DECISION_THRESHOLDS["min_expected_margin_pct"]`   | Min margin-on-revenue for BUY                          |
| `DECISION_THRESHOLDS["min_expected_roi_pct"]`      | Min ROI-on-cost for BUY                                |
| `CONDITION_FACTORS`                                | Per-condition `(sell_price_factor, sellable_factor, risk_score)` |
| `CATEGORY_DEMAND_SCORE` / `CATEGORY_RISK_SCORE`    | Per-category demand / risk priors                      |
| `KNOWN_BRANDS`                                     | Brand recognition list                                 |

Set `BULK_INTEL_LOG_LEVEL=DEBUG` for verbose stage logs.

---

## 6. Extension points

- **Real market prices**: implement a new class with the
  `PriceProvider` Protocol (`name`, `lookup(row) -> (market, wholesale)`)
  and pass it into `Pipeline(providers=[...])`. No other module changes.
- **New condition labels**: add a row to `CONDITION_FACTORS` in
  `config/settings.py` and a regex to `_CONDITION_PATTERNS` in
  `processing/cleaner.py`.  Risk + profit pick it up automatically.
- **New source schemas**: add aliases to `COLUMN_ALIASES` in
  `ingestion/loader.py`; for hierarchical category columns the loader's
  `_collapse_category_levels` already handles `Category L1..Ln`.
- **ML scoring**: replace `ScoringEngine.compute` with a model call;
  inputs (cleaned + priced DataFrame) and outputs (`sellability_score`,
  `risk_score`) are stable contracts.
- **API layer**: wrap `Pipeline.run_dataframe` in a FastAPI endpoint;
  `requirements.txt` already includes the optional `fastapi` extras.
- **Dashboard**: the ranked CSV + summary text are designed to feed
  directly into a Streamlit / Looker / Metabase front-end.

---

## 7. Contributing

Project conventions live in `CLAUDE.md`.  Highlights:

- Update `README.md`, module docstrings, and the config table in the
  same commit as any behaviour change.
- Every externally visible behaviour change ships with a regression
  test under `tests/`.
- Stages stay pure: only `ingestion` and `output` perform I/O.

---

## 8. License

MIT.
