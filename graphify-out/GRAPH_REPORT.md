# Graph Report - .  (2026-04-27)

## Corpus Check
- 53 files · ~213,782 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 225 nodes · 437 edges · 15 communities detected
- Extraction: 59% EXTRACTED · 41% INFERRED · 0% AMBIGUOUS · INFERRED: 179 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Pipeline Manifest|Pipeline Manifest]]
- [[_COMMUNITY_Condition Settings|Condition Settings]]
- [[_COMMUNITY_Clean Keywords|Clean Keywords]]
- [[_COMMUNITY_Risk Sellability|Risk Sellability]]
- [[_COMMUNITY_Loader Read|Loader Read]]
- [[_COMMUNITY_Pricing Metrics|Pricing Metrics]]
- [[_COMMUNITY_Load Loader|Load Loader]]
- [[_COMMUNITY_Init Lookuptablepriceprovider|Init Lookuptablepriceprovider]]
- [[_COMMUNITY_Summary Reporter|Summary Reporter]]
- [[_COMMUNITY_Decision Decide|Decision Decide]]
- [[_COMMUNITY_Manifest Sample|Manifest Sample]]
- [[_COMMUNITY_Configure Logger|Configure Logger]]
- [[_COMMUNITY_Fuzzycatalogpriceprovider Lookup|Fuzzycatalogpriceprovider Lookup]]
- [[_COMMUNITY_End Pipeline|End Pipeline]]
- [[_COMMUNITY_Category Combine|Category Combine]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 39 edges
2. `Shared utilities for the Liquidation Intelligence Engine.` - 21 edges
3. `ScoringEngine` - 21 edges
4. `ManifestLoader` - 17 edges
5. `DecisionEngine` - 17 edges
6. `Pipeline` - 17 edges
7. `ManifestCleaner` - 17 edges
8. `ProfitEngine` - 16 edges
9. `Enricher` - 15 edges
10. `MRPHeuristicPriceProvider` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Buy / Skip decision engine with explainable reasoning.  Combines sellability,` --uses--> `Settings`  [INFERRED]
  C:\GIT\bulk-intel\intelligence\decision.py → C:\GIT\bulk-intel\config\settings.py
- `Return a copy of ``df`` with decision columns appended.          Columns added` --uses--> `Settings`  [INFERRED]
  C:\GIT\bulk-intel\intelligence\decision.py → C:\GIT\bulk-intel\config\settings.py
- `Rule-based sellability and risk scoring.  Both scores are produced on a 0–100` --uses--> `Settings`  [INFERRED]
  C:\GIT\bulk-intel\intelligence\scoring.py → C:\GIT\bulk-intel\config\settings.py
- `Compute sellability + risk scores for a pricing-enriched manifest.` --uses--> `Settings`  [INFERRED]
  C:\GIT\bulk-intel\intelligence\scoring.py → C:\GIT\bulk-intel\config\settings.py
- `Return a copy of ``df`` with ``sellability_score`` and ``risk_score``.` --uses--> `Settings`  [INFERRED]
  C:\GIT\bulk-intel\intelligence\scoring.py → C:\GIT\bulk-intel\config\settings.py

## Communities

### Community 0 - "Pipeline Manifest"
Cohesion: 0.16
Nodes (28): decide(), DecisionEngine, enrich_manifest(), Enricher, MRPHeuristicPriceProvider, PriceProvider, Add external pricing fields to a cleaned manifest.  The enrichment layer is in, Estimate market price as a constant fraction of MRP.      Acts as a determinis (+20 more)

### Community 1 - "Condition Settings"
Cohesion: 0.11
Nodes (21): Functional wrapper around :class:`DecisionEngine`., Apply threshold rules to produce ``recommendation`` + ``reasoning``., compute_profitability(), Deterministic profitability simulator.  Given pricing fields and configurable, Return per-row ``sellable_factor`` (ceiling imposed by condition).          Co, Functional wrapper around :class:`ProfitEngine`., Compute expected revenue and profit assuming pipeline defaults., Return a copy of ``df`` with profitability columns added.          Sell-throug (+13 more)

### Community 2 - "Clean Keywords"
Cohesion: 0.11
Nodes (17): clean_manifest(), _keyword_hit(), ManifestCleaner, _normalize_condition(), Clean product names and extract structured attributes.  The cleaner takes the, Functional wrapper around :class:`ManifestCleaner`., Map free-text condition labels to a canonical bucket., Token-prefix match so plurals/variants ("earbuds") still hit "earbud".      Mu (+9 more)

### Community 4 - "Risk Sellability"
Cohesion: 0.18
Nodes (10): _low_quantity_penalty(), _missing_data_penalty(), _normalise(), Rule-based sellability and risk scoring.  Both scores are produced on a 0–100, Per-row risk contribution from the normalized condition bucket., Linearly map ``[lo, hi]`` onto ``[0, 100]``, clipped, NaN-safe., Compute sellability + risk scores for a pricing-enriched manifest., Return a copy of ``df`` with ``sellability_score`` and ``risk_score``. (+2 more)

### Community 5 - "Loader Read"
Cohesion: 0.16
Nodes (11): _canon_key(), list_supported_aliases(), ManifestLoader, _pick_deepest_category(), Read raw manifest files and produce a normalized ``DataFrame``.  The ingestion, Return the deepest non-empty, non-placeholder level value.      If only placeh, Lower-case, snake-case a column name for alias lookup., Return the source column aliases recognised by the loader. (+3 more)

### Community 6 - "Pricing Metrics"
Cohesion: 0.2
Nodes (13): compute_pricing_metrics(), Compute deterministic pricing metrics for the manifest.  These metrics are pur, Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col, Functional wrapper around :class:`PricingEngine`., compute_scores(), Functional wrapper around :class:`ScoringEngine`., _prep(), Tests for pricing, scoring and decision modules. (+5 more)

### Community 7 - "Load Loader"
Cohesion: 0.19
Nodes (14): load_manifest(), Convenience wrapper around :class:`ManifestLoader` for one-off loads., Loader tests — schema normalisation and missing-data handling., test_load_coerces_numeric_with_garbage(), test_load_drops_fully_empty_rows(), test_load_handles_quantity_default(), test_load_sample_csv_canonical_schema(), Regression tests for real-manifest schema handling.  These cover Bulk4Traders- (+6 more)

### Community 8 - "Init Lookuptablepriceprovider"
Cohesion: 0.17
Nodes (3): LookupTablePriceProvider, Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b, Shared utilities for the Liquidation Intelligence Engine.

### Community 9 - "Summary Reporter"
Cohesion: 0.32
Nodes (6): _build_summary(), _rank(), Persist scored manifests and produce a human-readable summary., Convenience wrapper around :class:`Reporter`., Persist outputs and return ``{"csv": path, "summary": path}``.          The CS, write_outputs()

### Community 10 - "Decision Decide"
Cohesion: 0.29
Nodes (3): Buy / Skip decision engine with explainable reasoning.  Combines sellability,, Return a copy of ``df`` with decision columns appended.          Columns added, _safe_float()

### Community 11 - "Manifest Sample"
Cohesion: 0.33
Nodes (5): Pytest fixtures shared across the test suite., Return the bundled sample manifest CSV path., A minimal canonical-schema DataFrame for unit tests., sample_manifest_path(), tiny_manifest_df()

### Community 12 - "Configure Logger"
Cohesion: 0.4
Nodes (5): _configure_root(), get_logger(), Centralized logging configuration.  A single place to configure log formatting, Configure the root logger once per process., Return a module-level logger with shared configuration.      Args:         na

### Community 13 - "Fuzzycatalogpriceprovider Lookup"
Cohesion: 0.67
Nodes (2): FuzzyCatalogPriceProvider, Resolve prices by fuzzy matching product names against a catalog.

### Community 14 - "End Pipeline"
Cohesion: 0.67
Nodes (2): End-to-end pipeline smoke test., test_pipeline_end_to_end()

### Community 15 - "Category Combine"
Cohesion: 1.0
Nodes (1): Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.

## Knowledge Gaps
- **40 isolated node(s):** `Central configuration values for the engine.  Everything that a domain expert`, `Immutable bundle of tunables passed through the pipeline.`, `Return the default ``Settings`` bundle.      Tests and notebooks may construct`, `Add external pricing fields to a cleaned manifest.  The enrichment layer is in`, `Strategy interface for resolving market and wholesale prices.      Implementat` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Fuzzycatalogpriceprovider Lookup`** (3 nodes): `FuzzyCatalogPriceProvider`, `.lookup()`, `Resolve prices by fuzzy matching product names against a catalog.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `End Pipeline`** (3 nodes): `End-to-end pipeline smoke test.`, `test_pipeline_end_to_end()`, `test_pipeline.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Category Combine`** (1 nodes): `Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Condition Settings` to `Pipeline Manifest`, `Clean Keywords`, `Risk Sellability`, `Pricing Metrics`, `Init Lookuptablepriceprovider`, `Decision Decide`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Why does `ManifestLoader` connect `Loader Read` to `Init Lookuptablepriceprovider`, `Pipeline Manifest`, `Load Loader`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Why does `Shared utilities for the Liquidation Intelligence Engine.` connect `Init Lookuptablepriceprovider` to `Pipeline Manifest`, `Condition Settings`, `Clean Keywords`, `Risk Sellability`, `Loader Read`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `Settings` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `DecisionEngine`) actually correct?**
  _`Settings` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Shared utilities for the Liquidation Intelligence Engine.` (e.g. with `Settings` and `Enricher`) actually correct?**
  _`Shared utilities for the Liquidation Intelligence Engine.` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `ScoringEngine` (e.g. with `Settings` and `Shared utilities for the Liquidation Intelligence Engine.`) actually correct?**
  _`ScoringEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ManifestLoader` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `Pipeline`) actually correct?**
  _`ManifestLoader` has 9 INFERRED edges - model-reasoned connections that need verification._