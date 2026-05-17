# Graph Report - bulk-intel  (2026-05-03)

## Corpus Check
- 67 files · ~258,283 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 885 nodes · 2572 edges · 62 communities detected
- Extraction: 40% EXTRACTED · 60% INFERRED · 0% AMBIGUOUS · INFERRED: 1531 edges (avg confidence: 0.62)
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
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
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
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 299 edges
2. `SerpCache` - 72 edges
3. `ProfitEngine` - 68 edges
4. `ManifestCleaner` - 53 edges
5. `SerpAmazonPriceProvider` - 48 edges
6. `ScoringEngine` - 47 edges
7. `get_settings()` - 45 edges
8. `BSRProvider` - 44 edges
9. `MRPHeuristicPriceProvider` - 44 edges
10. `ManifestLoader` - 44 edges

## Surprising Connections (you probably didn't know these)
- `Operator-assisted Playwright fallback for Google SERP.  Google's ToS prohibits a` --uses--> `Settings`  [INFERRED]
  enrichment\playwright_serp_client.py → config\settings.py
- `Raised when the configured Playwright query cap is reached.` --uses--> `Settings`  [INFERRED]
  enrichment\playwright_serp_client.py → config\settings.py
- `Raised when CAPTCHA cannot be resolved within the configured window.` --uses--> `Settings`  [INFERRED]
  enrichment\playwright_serp_client.py → config\settings.py
- `SerpClient implementation backed by a persistent Chromium context.` --uses--> `Settings`  [INFERRED]
  enrichment\playwright_serp_client.py → config\settings.py
- `Return organic SERP candidates in the shared SerpClient shape.` --uses--> `Settings`  [INFERRED]
  enrichment\playwright_serp_client.py → config\settings.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (125): Assigns a platform for liquidation marketplace listing., Return a copy of df with a ``platform`` column populated., Functional wrapper around :class:`ManifestCleaner`., Map free-text condition labels to a canonical bucket., Token-prefix match so plurals/variants ("earbuds") still hit "earbud".      Mu, Return the set of categories the heuristic resolver can produce., Apply text cleaning and attribute extraction to a manifest., Functional wrapper around :class:`DecisionEngine`. (+117 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (83): BSRProvider, FuzzyCatalogBSRProvider, Resolve Amazon Best-Seller Rank (BSR) for manifest items.  Two implementation, Strategy interface for resolving BSR., Return the BSR (lower is better) or None if unknown., Resolve BSR by fuzzy matching product names against a catalog., ChannelRouter, ManifestCleaner (+75 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (70): main(), Invalidate structured SERP cache rows., build_serp_client(), NullSerpClient, Factory for selecting the active structured SERP backend., SerpClient that returns no live candidates., Pick SerpAPI, Playwright fallback, or null backend., cache_key() (+62 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (79): decide(), Functional wrapper around :class:`DecisionEngine`., compute_pricing_metrics(), Compute deterministic pricing metrics for the manifest.  These metrics are pur, Functional wrapper around :class:`PricingEngine`., compute_profitability(), Functional wrapper around :class:`ProfitEngine`., compute_scores() (+71 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (33): Buy / Skip decision engine with explainable reasoning.  Combines sellability,, Return a copy of ``df`` with decision columns appended.          Columns added, _safe_float(), Return a copy of ``df`` with enrichment columns populated., Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col, _beta_samples(), _master_seed(), Deterministic profitability simulator.  Given pricing fields and configurable (+25 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (47): Enum, BudgetExhausted, CaptchaEncountered, PlaywrightSerpClient, Raised when the configured Playwright query cap is reached., Raised when CAPTCHA cannot be resolved within the configured window., SerpClient implementation backed by a persistent Chromium context., RuntimeError (+39 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (43): _predicate_matches(), Assigns each row a target platform based on deterministic rules., aggregate_by_category(), _bump_version(), diff_priors(), main(), _parse_args(), T-305 — outcome feedback loop CLI.  Ingests a realised-outcomes CSV, computes (+35 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (31): _captcha_screenshot_path(), detect_captcha(), _first_href(), _first_title(), _page_html(), _page_text(), _page_url(), _parse_json_ld() (+23 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (35): Lowercase + alias-resolve a raw brand string., _brand_score(), compute_match_score(), _decision(), extract_model_tokens(), _head_noun(), MatchFeatures, MatchResult (+27 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (32): clean_manifest(), _extract_keywords(), _keyword_hit(), _normalize_condition(), Clean product names and extract structured attributes.  The cleaner takes the, Functional wrapper around :class:`ManifestCleaner`., Map free-text condition labels to a canonical bucket., Token-prefix match so plurals/variants ("earbuds") still hit "earbud".      Mu (+24 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (23): cli(), Backtest harness for threshold calibration.  usage: python -m tools.backtest --m, run_backtest(), load_catalog(), Load and validate JSON catalogs., Load and validate a catalog JSON.      Validates schema_version, rates_as_of (wa, _canon_key(), list_supported_aliases() (+15 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (20): load_model(), Simple wrapper around a fitted model/pipeline.      Feature contract:     cat, SellThroughModel, Dummy, _row(), test_model_loaded_when_present(), test_model_predict_in_range(), test_pipeline_works_without_model_artifact() (+12 more)

### Community 13 - "Community 13"
Cohesion: 0.16
Nodes (15): _build_rollup(), _build_summary(), _rank(), Persist scored manifests and produce a human-readable summary., Convenience wrapper around :class:`Reporter`., Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``., _rollup_from_groups(), write_outputs() (+7 more)

### Community 14 - "Community 14"
Cohesion: 0.33
Nodes (5): Pytest fixtures shared across the test suite., Return the bundled sample manifest CSV path., A minimal canonical-schema DataFrame for unit tests., sample_manifest_path(), tiny_manifest_df()

### Community 15 - "Community 15"
Cohesion: 0.67
Nodes (2): End-to-end pipeline smoke test., test_pipeline_end_to_end()

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Return parsed priors JSON, or an empty dict if the file is missing.      Never

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Load state JSON, returning ``None`` if absent or invalid.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Atomically write state JSON to disk.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Return parsed priors JSON, or an empty dict if the file is missing.      Never

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Small SQLite-backed cache for SERP lookup payloads.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Return SHA-256 cache key for a normalized title/backend pair.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Return parsed priors JSON, or an empty dict if the file is missing.      Never

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Return a module-level logger with shared configuration.      Args:         na

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Strategy interface for resolving market and wholesale prices.      Implementat

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Resolve prices by fuzzy matching product names against a catalog.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Estimate market price as a constant fraction of MRP.      Acts as a determinis

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Apply a chain of :class:`PriceProvider` strategies to a manifest.      Provide

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Return a copy of ``df`` with enrichment columns populated.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Convenience wrapper using a sensible default provider chain.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Vectorised pricing-metric calculator.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Functional wrapper around :class:`PricingEngine`.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Immutable bundle of tunables passed through the pipeline.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Return the default ``Settings`` bundle.      Tests and notebooks may construct

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Write a ranked CSV and a plain-text summary to ``out_dir``.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Persist outputs and return ``{"csv": path, "summary": path}``.          The CS

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Convenience wrapper around :class:`Reporter`.

## Knowledge Gaps
- **147 isolated node(s):** `Create a Jules session for a single task with automated PR creation.`, `List available sources (GitHub repos).`, `Create a Jules session for a task.`, `Central configuration values for the engine.  Everything that a domain expert`, `Immutable bundle of tunables passed through the pipeline.` (+142 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (3 nodes): `End-to-end pipeline smoke test.`, `test_pipeline_end_to_end()`, `test_pipeline.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Return parsed priors JSON, or an empty dict if the file is missing.      Never`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Load state JSON, returning ``None`` if absent or invalid.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Atomically write state JSON to disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Return parsed priors JSON, or an empty dict if the file is missing.      Never`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Small SQLite-backed cache for SERP lookup payloads.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Return SHA-256 cache key for a normalized title/backend pair.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Return parsed priors JSON, or an empty dict if the file is missing.      Never`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Return the default ``Settings`` bundle.      Honours the ``BULK_INTEL_PRIORS_P`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Return a module-level logger with shared configuration.      Args:         na`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Strategy interface for resolving market and wholesale prices.      Implementat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Resolve prices by fuzzy matching product names against a catalog.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Resolve prices from an in-memory ``{sku: (...)}`` table.      Each value may b`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Estimate market price as a constant fraction of MRP.      Acts as a determinis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Apply a chain of :class:`PriceProvider` strategies to a manifest.      Provide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Return a copy of ``df`` with enrichment columns populated.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Convenience wrapper using a sensible default provider chain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Vectorised pricing-metric calculator.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Add pricing metrics to ``df`` and return a new ``DataFrame``.          New col`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Functional wrapper around :class:`PricingEngine`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Immutable bundle of tunables passed through the pipeline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Return the default ``Settings`` bundle.      Tests and notebooks may construct`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Write a ranked CSV and a plain-text summary to ``out_dir``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Persist outputs and return ``{"csv": path, "summary": path}``.          The CS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Convenience wrapper around :class:`Reporter`.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`?**
  _High betweenness centrality (0.428) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 3` to `Community 0`, `Community 2`, `Community 4`, `Community 6`, `Community 8`, `Community 9`, `Community 11`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `SerpCache` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 296 inferred relationships involving `Settings` (e.g. with `Shared utilities for the Liquidation Intelligence Engine.` and `PriceProvider`) actually correct?**
  _`Settings` has 296 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `SerpCache` (e.g. with `ExecutionMode` and `ManifestStateMismatchError`) actually correct?**
  _`SerpCache` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `ProfitEngine` (e.g. with `Settings` and `Shared utilities for the Liquidation Intelligence Engine.`) actually correct?**
  _`ProfitEngine` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `str` (e.g. with `send_task_to_jules()` and `main()`) actually correct?**
  _`str` has 48 INFERRED edges - model-reasoned connections that need verification._