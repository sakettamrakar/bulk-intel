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
        │            extraction         wholesale_price
        ▼                 ▼                  ▼
  ┌──────────────────────────────────────────────────┐
  │              Intelligence Layer                  │
  │                                                  │
  │  pricing.py ─► scoring.py ─► profit.py ─► decision.py
  │  discount/      sellability   revenue/       BUY /
  │  market_gap     risk          margin         REVIEW /
  │                                              SKIP + why
  └──────────────────────────────────────────────────┘
        │
        ▼
  ┌────────────┐
  │   Output   │ ─►  ranked CSV + plain-text summary
  │ reporter.py│
  └────────────┘
```

Key principles:

- **Single canonical schema** between every stage (defined in
  `ingestion/loader.py`).
- **Pure stage modules**: each stage is a small, type-hinted, testable
  unit with no I/O outside ingestion + reporting.
- **Configurable, not hard-coded**: weights, thresholds, and
  assumptions live in `config/settings.py`.
- **Pluggable enrichment**: `PriceProvider` Protocol means a future
  scraper or external API drops in without touching the pipeline.
- **Deterministic before ML**: rule-based scoring today; the same
  inputs/outputs let an ML model replace `intelligence/scoring.py`
  later without disturbing surrounding code.

---

## 2. Folder structure

```
bulk-intel/
├── README.md
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── __init__.py
│   └── settings.py                  # Weights, thresholds, assumptions
├── ingestion/
│   ├── __init__.py
│   └── loader.py                    # CSV/XLSX → canonical DataFrame
├── processing/
│   ├── __init__.py
│   └── cleaner.py                   # Text cleanup + brand/category
├── enrichment/
│   ├── __init__.py
│   └── enricher.py                  # PriceProvider strategies
├── intelligence/
│   ├── __init__.py
│   ├── pricing.py                   # Discount / gap metrics
│   ├── scoring.py                   # Sellability + risk
│   ├── profit.py                    # Revenue / margin simulator
│   └── decision.py                  # BUY / REVIEW / SKIP + reasoning
├── output/
│   ├── __init__.py
│   └── reporter.py                  # Ranked CSV + summary report
├── pipeline/
│   ├── __init__.py
│   └── run_pipeline.py              # Orchestrator + CLI
├── utils/
│   ├── __init__.py
│   └── logging.py                   # Centralised logger
├── data/
│   └── sample_manifest.csv          # 15-row demo manifest
└── tests/
    ├── conftest.py
    ├── test_loader.py
    ├── test_cleaner.py
    ├── test_pricing_and_scoring.py
    └── test_pipeline.py
```

---

## 3. Data flow

1. **Ingestion** (`ingestion/loader.py`)
   - Reads `.csv`, `.xlsx`, `.xls`.
   - Aliases ~20 source column variants to the canonical schema.
   - Coerces numerics, drops fully-empty rows, defaults `quantity = 1`.
2. **Cleaning** (`processing/cleaner.py`)
   - Strips manifest noise (`Open Box`, `Lot of N`, parentheticals…).
   - Title-cases product names.
   - Extracts keywords; infers `brand` and `category` when missing.
3. **Enrichment** (`enrichment/enricher.py`)
   - Resolves `market_price` and `wholesale_price` via a chain of
     `PriceProvider`s (lookup table → MRP heuristic by default).
4. **Pricing intelligence** (`intelligence/pricing.py`)
   - `discount_percentage`, `price_ratio`, `market_gap`, `wholesale_gap`.
5. **Scoring** (`intelligence/scoring.py`)
   - `sellability_score` (0–100) — weighted sum of discount, market
     gap, category demand, and brand strength.
   - `risk_score` (0–100) — weighted sum of missing-data,
     low-quantity, category risk, and thin-margin penalties.
6. **Profitability** (`intelligence/profit.py`)
   - Projects `expected_revenue`, `expected_cost`, `expected_profit`
     and `expected_margin_pct` using `PROFIT_ASSUMPTIONS`.
7. **Decision** (`intelligence/decision.py`)
   - Combines score + risk + margin against thresholds.
   - Emits `BUY` / `REVIEW` / `SKIP` and a `reasoning` string with the
     defensible explanation for each decision.
8. **Output** (`output/reporter.py`)
   - Writes a ranked CSV (sorted by sellability) and a plain-text
     summary with totals and the top BUY candidates.

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
python -m pipeline.run_pipeline \
  --input data/sample_manifest.csv \
  --output output/reports
```

This produces:

```
output/reports/sample_manifest_report.csv
output/reports/sample_manifest_report_summary.txt
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

| Setting                                   | Effect                                |
| ----------------------------------------- | ------------------------------------- |
| `SCORING_WEIGHTS`                         | Sellability sub-component weights      |
| `RISK_WEIGHTS`                            | Risk sub-component weights             |
| `PROFIT_ASSUMPTIONS["expected_sellable_pct"]` | % of inventory expected to sell    |
| `PROFIT_ASSUMPTIONS["operating_cost_pct"]`    | Logistics + fees as % of revenue   |
| `DECISION_THRESHOLDS["buy_score_min"]`    | Min sellability score for BUY          |
| `DECISION_THRESHOLDS["risk_score_max"]`   | Max risk score for BUY/REVIEW          |
| `CATEGORY_DEMAND_SCORE` / `CATEGORY_RISK_SCORE` | Per-category demand / risk priors |
| `KNOWN_BRANDS`                            | Brand recognition list                 |

Set `BULK_INTEL_LOG_LEVEL=DEBUG` for verbose stage logs.

---

## 6. Extension points

- **Real market prices**: implement a new class with the
  `PriceProvider` Protocol (`name`, `lookup(row) -> (market, wholesale)`)
  and pass it into `Pipeline(providers=[...])`. No other module changes.
- **ML scoring**: replace `ScoringEngine.compute` with a model call;
  inputs (cleaned + priced DataFrame) and outputs (`sellability_score`,
  `risk_score`) are stable contracts.
- **API layer**: wrap `Pipeline.run_dataframe` in a FastAPI endpoint;
  `requirements.txt` already includes the optional `fastapi` extras.
- **Dashboard**: the ranked CSV + summary text are designed to feed
  directly into a Streamlit / Looker / Metabase front-end.

---

## 7. License

MIT.
