# Graph Report - bulk-intel  (2026-05-03)

## Corpus Check
- 57 files · ~246,065 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 688 nodes · 1764 edges · 52 communities detected
- Extraction: 42% EXTRACTED · 58% INFERRED · 0% AMBIGUOUS · INFERRED: 1023 edges (avg confidence: 0.62)
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
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
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
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 222 edges
2. `ProfitEngine` - 62 edges
3. `ManifestCleaner` - 47 edges
4. `get_settings()` - 43 edges
5. `ScoringEngine` - 41 edges
6. `MRPHeuristicPriceProvider` - 38 edges
7. `ManifestLoader` - 38 edges
8. `PricingEngine` - 38 edges
9. `BSRProvider` - 37 edges
10. `Enricher` - 37 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Lot homogeneity scoring and SKU clustering.  Homogeneity is measured as entropy`  [INFERRED]
  config\settings.py → intelligence\homogeneity.py
- `Annotate rows with cluster ids and compute lot-level scores.` --uses--> `Settings`  [INFERRED]
  intelligence\homogeneity.py → config\settings.py
- `Return ``df`` with SKU, brand, and category cluster ids.` --uses--> `Settings`  [INFERRED]
  intelligence\homogeneity.py → config\settings.py
- `Return homogeneity scores and labels for SKU, brand, and category.` --uses--> `Settings`  [INFERRED]
  intelligence\homogeneity.py → config\settings.py
- `Lowercase, strip punctuation, drop fillers, and preserve model tokens.` --uses--> `Settings`  [INFERRED]
  intelligence\homogeneity.py → config\settings.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (78): BSRProvider, FuzzyCatalogBSRProvider, Resolve Amazon Best-Seller Rank (BSR) for manifest items.  Two implementation, Strategy interface for resolving BSR., Return the BSR (lower is better) or None if unknown., Resolve BSR by fuzzy matching product names against a catalog., DecisionEngine, Apply threshold rules to produce ``recommendation`` + ``reasoning``. (+70 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (72): ChannelRouter, _predicate_matches(), Assigns each row a target platform based on deterministic rules., Assigns a platform for liquidation marketplace listing., Return a copy of df with a ``platform`` column populated., _extract_keywords(), _keyword_hit(), _normalize_condition() (+64 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (43): Protocol, RuntimeError, cache_key(), SQLite cache for structured SERP price lookups.  The cache is single-writer and, Small SQLite-backed cache for SERP lookup payloads., Return SHA-256 cache key for a normalized title/backend pair., SerpCache, BS4SerpProvider (+35 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (57): compute_profitability(), ProfitEngine, Compute expected revenue and profit assuming pipeline defaults.      Factors i, Functional wrapper around :class:`ProfitEngine`., Return a copy of ``df`` with ``sellability_score`` and ``risk_score``., get_settings(), _load_priors_if_exists(), Central configuration values for the engine.  Everything that a domain expert (+49 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (29): Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col, _beta_samples(), _master_seed(), Deterministic profitability simulator.  Given pricing fields and configurable, Vectorised Monte Carlo CIs for profit and ROI per row.          Models two ran, Per-row inspection cost = qty × per-condition ₹/unit., Return per-row platform commission fraction.          Looks up ``PLATFORM_FEES, Return a copy of ``df`` with profitability columns added.          Sell-throug (+21 more)

### Community 5 - "Community 5"
Cohesion: 0.1
Nodes (38): ManifestCleaner, Lowercase + alias-resolve a raw brand string., Apply text cleaning and attribute extraction to a manifest., Return a copy of ``df`` augmented with cleaned fields., _brand_score(), compute_match_score(), _decision(), extract_model_tokens() (+30 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (32): clean_manifest(), Functional wrapper around :class:`ManifestCleaner`., _canon_key(), list_supported_aliases(), load_manifest(), _pick_deepest_category(), Read raw manifest files and produce a normalized ``DataFrame``.  The ingestion, Convenience wrapper around :class:`ManifestLoader` for one-off loads. (+24 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (25): decide(), Buy / Skip decision engine with explainable reasoning.  Combines sellability,, Functional wrapper around :class:`DecisionEngine`., _safe_float(), compute_pricing_metrics(), Compute deterministic pricing metrics for the manifest.  These metrics are pur, Functional wrapper around :class:`PricingEngine`., compute_scores() (+17 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (27): annotate_homogeneity(), _canonical_model_token(), _cluster_counts(), cluster_skus(), compute_homogeneity_score(), _exact_cluster_id(), _extract_model_tokens(), _has_cluster_columns() (+19 more)

### Community 9 - "Community 9"
Cohesion: 0.1
Nodes (28): aggregate_by_category(), _bump_version(), diff_priors(), main(), _parse_args(), T-305 — outcome feedback loop CLI.  Ingests a realised-outcomes CSV, computes, Human-readable summary of how the priors moved., Bayesian-style shrinkage: ``(alpha * prior + n * observed) / (alpha + n)``. (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (19): load_model(), Simple wrapper around a fitted model/pipeline.      Feature contract:     cat, SellThroughModel, Dummy, _row(), test_model_loaded_when_present(), test_model_predict_in_range(), test_pipeline_works_without_model_artifact() (+11 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (13): load_catalog(), Load and validate JSON catalogs., Load and validate a catalog JSON.      Validates schema_version, rates_as_of (wa, cli(), _get_default_bsr_providers(), _get_default_providers(), run_pipeline(), Tests for catalog loader. (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.17
Nodes (14): _build_rollup(), _build_summary(), _rank(), Persist scored manifests and produce a human-readable summary., Convenience wrapper around :class:`Reporter`., Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``., write_outputs(), test_rollup_prefers_sku_cluster_id_over_noisy_sku() (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.29
Nodes (8): cli(), Backtest harness for threshold calibration.  usage: python -m tools.backtest --m, run_backtest(), Tests for the backtest harness., test_backtest_runs_on_example_data(), test_confusion_matrix_counts_match_synthetic(), test_predicted_vs_actual_correlation_in_range(), test_threshold_sweep_monotonicity()

### Community 15 - "Community 15"
Cohesion: 0.28
Nodes (7): _configure_root(), _EnvRedactionFilter, get_logger(), Centralized logging configuration.  A single place to configure log formatting, Configure the root logger once per process., Configure the root logger once per process., Return a module-level logger with shared configuration.      Args:         na

### Community 16 - "Community 16"
Cohesion: 0.33
Nodes (5): Pytest fixtures shared across the test suite., Return the bundled sample manifest CSV path., A minimal canonical-schema DataFrame for unit tests., sample_manifest_path(), tiny_manifest_df()

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Return parsed priors JSON, or an empty dict if the file is missing.      Never

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Return a module-level logger with shared configuration.      Args:         na

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Strategy interface for resolving market and wholesale prices.      Implementat

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Resolve prices by fuzzy matching product names against a catalog.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Estimate market price as a constant fraction of MRP.      Acts as a determinis

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Apply a chain of :class:`PriceProvider` strategies to a manifest.      Provide

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Return a copy of ``df`` with enrichment columns populated.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Convenience wrapper using a sensible default provider chain.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Vectorised pricing-metric calculator.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Functional wrapper around :class:`PricingEngine`.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

## Knowledge Gaps
- **130 isolated node(s):** `Create a Jules session for a single task with automated PR creation.`, `List available sources (GitHub repos).`, `Create a Jules session for a task.`, `Central configuration values for the engine.  Everything that a domain expert`, `Immutable bundle of tunables passed through the pipeline.` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (1 nodes): `Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Return parsed priors JSON, or an empty dict if the file is missing.      Never`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Return a module-level logger with shared configuration.      Args:         na`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Strategy interface for resolving market and wholesale prices.      Implementat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Resolve prices by fuzzy matching product names against a catalog.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Estimate market price as a constant fraction of MRP.      Acts as a determinis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Apply a chain of :class:`PriceProvider` strategies to a manifest.      Provide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Return a copy of ``df`` with enrichment columns populated.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Convenience wrapper using a sensible default provider chain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Vectorised pricing-metric calculator.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Functional wrapper around :class:`PricingEngine`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 14`?**
  _High betweenness centrality (0.394) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 3` to `Community 1`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `ProfitEngine` connect `Community 3` to `Community 0`, `Community 1`, `Community 10`, `Community 4`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 219 inferred relationships involving `Settings` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `PriceProvider`) actually correct?**
  _`Settings` has 219 INFERRED edges - model-reasoned connections that need verification._
- **Are the 50 inferred relationships involving `ProfitEngine` (e.g. with `Settings` and `Shared utilities for the Liquidation Intelligence Engine.`) actually correct?**
  _`ProfitEngine` has 50 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `ManifestCleaner` (e.g. with `MatchFeatures` and `MatchResult`) actually correct?**
  _`ManifestCleaner` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `get_settings()` (e.g. with `.get()` and `decide()`) actually correct?**
  _`get_settings()` has 39 INFERRED edges - model-reasoned connections that need verification._