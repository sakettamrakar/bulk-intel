# Graph Report - 9f179cf5971f9249  (2026-04-29)

## Corpus Check
- 50 files · ~236,483 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 521 nodes · 1204 edges · 45 communities detected
- Extraction: 43% EXTRACTED · 57% INFERRED · 0% AMBIGUOUS · INFERRED: 687 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
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
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 138 edges
2. `ProfitEngine` - 58 edges
3. `get_settings()` - 40 edges
4. `compute_profitability()` - 37 edges
5. `ScoringEngine` - 37 edges
6. `ManifestLoader` - 34 edges
7. `PricingEngine` - 34 edges
8. `MRPHeuristicPriceProvider` - 33 edges
9. `ManifestCleaner` - 33 edges
10. `Enricher` - 32 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Buy / Skip decision engine with explainable reasoning.  Combines sellability,`  [INFERRED]
  config\settings.py → intelligence\decision.py
- `Settings` --uses--> `Return a copy of ``df`` with decision columns appended.          Columns added`  [INFERRED]
  config\settings.py → intelligence\decision.py
- `Functional wrapper around :class:`DecisionEngine`.` --uses--> `Settings`  [INFERRED]
  intelligence\decision.py → config\settings.py
- `Settings` --uses--> `Compute deterministic pricing metrics for the manifest.  These metrics are pur`  [INFERRED]
  config\settings.py → intelligence\pricing.py
- `Settings` --uses--> `Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col`  [INFERRED]
  config\settings.py → intelligence\pricing.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (70): FuzzyCatalogBSRProvider, Resolve Amazon Best-Seller Rank (BSR) for manifest items.  Two implementation, Resolve BSR by fuzzy matching product names against a catalog., _predicate_matches(), Assigns each row a target platform based on deterministic rules., Assigns a platform for liquidation marketplace listing., Return a copy of df with a ``platform`` column populated., _keyword_hit() (+62 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (65): _beta_samples(), compute_profitability(), _master_seed(), ProfitEngine, Deterministic profitability simulator.  Given pricing fields and configurable, Vectorised Monte Carlo CIs for profit and ROI per row.          Models two ran, Compute expected revenue and profit assuming pipeline defaults.      Factors i, Per-row inspection cost = qty × per-condition ₹/unit. (+57 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (54): BSRProvider, Strategy interface for resolving BSR., Return the BSR (lower is better) or None if unknown., ChannelRouter, ManifestCleaner, Return a copy of ``df`` augmented with cleaned fields., DecisionEngine, enrich_manifest() (+46 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (28): aggregate_by_category(), _bump_version(), diff_priors(), main(), _parse_args(), T-305 — outcome feedback loop CLI.  Ingests a realised-outcomes CSV, computes, Human-readable summary of how the priors moved., Bayesian-style shrinkage: ``(alpha * prior + n * observed) / (alpha + n)``. (+20 more)

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (19): load_model(), Simple wrapper around a fitted model/pipeline.      Feature contract:     cat, SellThroughModel, Dummy, _row(), test_model_loaded_when_present(), test_model_predict_in_range(), test_pipeline_works_without_model_artifact() (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (20): cli(), Backtest harness for threshold calibration.  usage: python -m tools.backtest --m, run_backtest(), _canon_key(), list_supported_aliases(), _pick_deepest_category(), Read raw manifest files and produce a normalized ``DataFrame``.  The ingestion, Return the deepest non-empty, non-placeholder level value.      If only placeh (+12 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (24): clean_manifest(), Functional wrapper around :class:`ManifestCleaner`., load_manifest(), Convenience wrapper around :class:`ManifestLoader` for one-off loads., Cleaner tests — text normalisation, brand/category inference., test_brand_alias_amazon_brand_solimo_to_solimo(), test_brand_alias_pigeon_by_stovekraft_to_pigeon(), test_clean_infers_brand_from_keywords() (+16 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (22): decide(), Functional wrapper around :class:`DecisionEngine`., compute_pricing_metrics(), Compute deterministic pricing metrics for the manifest.  These metrics are pur, Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col, Functional wrapper around :class:`PricingEngine`., compute_scores(), Functional wrapper around :class:`ScoringEngine`. (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (12): Buy / Skip decision engine with explainable reasoning.  Combines sellability,, Return a copy of ``df`` with decision columns appended.          Columns added, _safe_float(), apply_confidence_gate(), _low_quantity_penalty(), _missing_data_penalty(), _normalise(), Rule-based sellability and risk scoring.  Both scores are produced on a 0–100 (+4 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (12): load_catalog(), Load and validate JSON catalogs., Load and validate a catalog JSON.      Validates schema_version, rates_as_of (wa, cli(), _get_default_bsr_providers(), _get_default_providers(), run_pipeline(), test_catalog_age_warning() (+4 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (13): _build_rollup(), _build_summary(), _rank(), Persist scored manifests and produce a human-readable summary., Convenience wrapper around :class:`Reporter`., Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``., write_outputs(), Tests for the rollup logic. (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.47
Nodes (5): create_session(), list_sources(), main(), List available sources (GitHub repos)., Create a Jules session for a task.

### Community 13 - "Community 13"
Cohesion: 0.33
Nodes (5): Pytest fixtures shared across the test suite., Return the bundled sample manifest CSV path., A minimal canonical-schema DataFrame for unit tests., sample_manifest_path(), tiny_manifest_df()

### Community 14 - "Community 14"
Cohesion: 0.53
Nodes (5): Tests for condition-aware risk and profitability., _row(), test_profit_uses_condition_factors(), test_risk_score_increases_with_worse_condition(), test_roi_column_present_and_signed_correctly()

### Community 15 - "Community 15"
Cohesion: 0.4
Nodes (5): _configure_root(), get_logger(), Centralized logging configuration.  A single place to configure log formatting, Configure the root logger once per process., Return a module-level logger with shared configuration.      Args:         na

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (3): main(), Create a Jules session for a single task with automated PR creation., send_task_to_jules()

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Strategy interface for resolving market and wholesale prices.      Implementat

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Resolve prices by fuzzy matching product names against a catalog.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Estimate market price as a constant fraction of MRP.      Acts as a determinis

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Apply a chain of :class:`PriceProvider` strategies to a manifest.      Provide

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Return a copy of ``df`` with enrichment columns populated.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Convenience wrapper using a sensible default provider chain.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Vectorised pricing-metric calculator.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Functional wrapper around :class:`PricingEngine`.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

## Knowledge Gaps
- **101 isolated node(s):** `Create a Jules session for a single task with automated PR creation.`, `List available sources (GitHub repos).`, `Create a Jules session for a task.`, `Central configuration values for the engine.  Everything that a domain expert`, `Immutable bundle of tunables passed through the pipeline.` (+96 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (1 nodes): `Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Strategy interface for resolving market and wholesale prices.      Implementat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Resolve prices by fuzzy matching product names against a catalog.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Estimate market price as a constant fraction of MRP.      Acts as a determinis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Apply a chain of :class:`PriceProvider` strategies to a manifest.      Provide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Return a copy of ``df`` with enrichment columns populated.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Convenience wrapper using a sensible default provider chain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Vectorised pricing-metric calculator.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Functional wrapper around :class:`PricingEngine`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.320) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 1` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Why does `ProfitEngine` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Are the 135 inferred relationships involving `Settings` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `ChannelRouter`) actually correct?**
  _`Settings` has 135 INFERRED edges - model-reasoned connections that need verification._
- **Are the 46 inferred relationships involving `ProfitEngine` (e.g. with `Settings` and `Shared utilities for the Liquidation Intelligence Engine.`) actually correct?**
  _`ProfitEngine` has 46 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `get_settings()` (e.g. with `decide()` and `compute_pricing_metrics()`) actually correct?**
  _`get_settings()` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `compute_profitability()` (e.g. with `get_settings()` and `test_profit_uses_condition_factors()`) actually correct?**
  _`compute_profitability()` has 33 INFERRED edges - model-reasoned connections that need verification._