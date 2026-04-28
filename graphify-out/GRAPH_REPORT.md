# Graph Report - bulk-intel  (2026-04-28)

## Corpus Check
- 39 files · ~230,538 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 374 nodes · 872 edges · 30 communities detected
- Extraction: 43% EXTRACTED · 57% INFERRED · 0% AMBIGUOUS · INFERRED: 496 edges (avg confidence: 0.62)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 103 edges
2. `ProfitEngine` - 48 edges
3. `ScoringEngine` - 31 edges
4. `ManifestLoader` - 29 edges
5. `PricingEngine` - 29 edges
6. `ManifestCleaner` - 28 edges
7. `get_settings()` - 27 edges
8. `MRPHeuristicPriceProvider` - 27 edges
9. `DecisionEngine` - 27 edges
10. `Enricher` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Buy / Skip decision engine with explainable reasoning.  Combines sellability,`  [INFERRED]
  config\settings.py → intelligence\decision.py
- `Settings` --uses--> `Return a copy of ``df`` with decision columns appended.          Columns added`  [INFERRED]
  config\settings.py → intelligence\decision.py
- `Settings` --uses--> `Functional wrapper around :class:`DecisionEngine`.`  [INFERRED]
  config\settings.py → intelligence\decision.py
- `Settings` --uses--> `Compute deterministic pricing metrics for the manifest.  These metrics are pur`  [INFERRED]
  config\settings.py → intelligence\pricing.py
- `Settings` --uses--> `Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col`  [INFERRED]
  config\settings.py → intelligence\pricing.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.15
Nodes (45): ManifestCleaner, Return a copy of ``df`` augmented with cleaned fields., DecisionEngine, enrich_manifest(), Enricher, FuzzyCatalogPriceProvider, MRPHeuristicPriceProvider, PriceProvider (+37 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (44): ChannelRouter, _predicate_matches(), Assigns each row a target platform based on deterministic rules., Assigns a platform for liquidation marketplace listing., Return a copy of df with a ``platform`` column populated., _keyword_hit(), _normalize_condition(), Clean product names and extract structured attributes.  The cleaner takes the (+36 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (41): compute_profitability(), ProfitEngine, Deterministic profitability simulator.  Given pricing fields and configurable, Per-row inspection cost = qty × per-condition ₹/unit., Return per-row platform commission fraction.          Looks up ``PLATFORM_FEES, Return per-row ``sellable_factor`` (ceiling imposed by condition).          Co, Return per-row return rate (fraction of sold units returned).          Looks u, Compute expected revenue and profit assuming pipeline defaults. (+33 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (27): decide(), Functional wrapper around :class:`DecisionEngine`., compute_pricing_metrics(), Compute deterministic pricing metrics for the manifest.  These metrics are pur, Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col, Functional wrapper around :class:`PricingEngine`., compute_scores(), Functional wrapper around :class:`ScoringEngine`. (+19 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (23): cli(), Backtest harness for threshold calibration.  usage: python -m tools.backtest --m, run_backtest(), load_catalog(), Load and validate JSON catalogs., Load and validate a catalog JSON.      Validates schema_version, rates_as_of (wa, _canon_key(), list_supported_aliases() (+15 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (24): clean_manifest(), Functional wrapper around :class:`ManifestCleaner`., load_manifest(), Convenience wrapper around :class:`ManifestLoader` for one-off loads., Cleaner tests — text normalisation, brand/category inference., test_brand_alias_amazon_brand_solimo_to_solimo(), test_brand_alias_pigeon_by_stovekraft_to_pigeon(), test_clean_infers_brand_from_keywords() (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (12): Buy / Skip decision engine with explainable reasoning.  Combines sellability,, Return a copy of ``df`` with decision columns appended.          Columns added, _safe_float(), apply_confidence_gate(), _low_quantity_penalty(), _missing_data_penalty(), _normalise(), Rule-based sellability and risk scoring.  Both scores are produced on a 0–100 (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.18
Nodes (13): _build_rollup(), _build_summary(), _rank(), Persist scored manifests and produce a human-readable summary., Convenience wrapper around :class:`Reporter`., Persist outputs and return ``{"csv": path, "summary": path}``.          The CS, write_outputs(), Tests for the rollup logic. (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (3): LookupTablePriceProvider, Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b, Shared utilities for the Liquidation Intelligence Engine.

### Community 10 - "Community 10"
Cohesion: 0.47
Nodes (5): create_session(), list_sources(), main(), List available sources (GitHub repos)., Create a Jules session for a task.

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (5): Pytest fixtures shared across the test suite., Return the bundled sample manifest CSV path., A minimal canonical-schema DataFrame for unit tests., sample_manifest_path(), tiny_manifest_df()

### Community 12 - "Community 12"
Cohesion: 0.4
Nodes (5): _configure_root(), get_logger(), Centralized logging configuration.  A single place to configure log formatting, Configure the root logger once per process., Return a module-level logger with shared configuration.      Args:         na

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (3): main(), Create a Jules session for a single task with automated PR creation., send_task_to_jules()

### Community 14 - "Community 14"
Cohesion: 0.67
Nodes (2): End-to-end pipeline smoke test., test_pipeline_end_to_end()

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Vectorised pricing-metric calculator.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Functional wrapper around :class:`PricingEngine`.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

## Knowledge Gaps
- **71 isolated node(s):** `Create a Jules session for a single task with automated PR creation.`, `List available sources (GitHub repos).`, `Create a Jules session for a task.`, `Central configuration values for the engine.  Everything that a domain expert`, `Immutable bundle of tunables passed through the pipeline.` (+66 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (3 nodes): `End-to-end pipeline smoke test.`, `test_pipeline_end_to_end()`, `test_pipeline.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Vectorised pricing-metric calculator.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Functional wrapper around :class:`PricingEngine`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 9`?**
  _High betweenness centrality (0.279) - this node is a cross-community bridge._
- **Why does `ManifestLoader` connect `Community 0` to `Community 9`, `Community 4`, `Community 5`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `ProfitEngine` connect `Community 2` to `Community 0`, `Community 1`, `Community 9`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 100 inferred relationships involving `Settings` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `ChannelRouter`) actually correct?**
  _`Settings` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `ProfitEngine` (e.g. with `Settings` and `Shared utilities for the Liquidation Intelligence Engine.`) actually correct?**
  _`ProfitEngine` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `ScoringEngine` (e.g. with `Settings` and `Shared utilities for the Liquidation Intelligence Engine.`) actually correct?**
  _`ScoringEngine` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `ManifestLoader` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `Pipeline`) actually correct?**
  _`ManifestLoader` has 21 INFERRED edges - model-reasoned connections that need verification._