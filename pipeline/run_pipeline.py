"""End-to-end pipeline: ingest → clean → enrich → score → decide → report.

The orchestrator is a thin coordinator — every real decision lives in
the stage modules so we can test them in isolation.  The same class
will eventually be wrapped by a FastAPI handler for the SaaS layer.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import pandas as pd

from config.settings import Settings, get_settings
from enrichment.bsr_provider import BSRProvider, FuzzyCatalogBSRProvider
from enrichment.enricher import (
    Enricher,
    MRPHeuristicPriceProvider,
    PriceProvider,
    FuzzyCatalogPriceProvider,
)
from enrichment.catalog_loader import load_catalog
from enrichment.serp_cache import SerpCache
from enrichment.serp_orchestrator import ExecutionMode, PartialSerpOrchestrator
from enrichment.serp_price_provider import SerpAmazonPriceProvider
from ingestion.loader import ManifestLoader
from intelligence.channel import ChannelRouter
from intelligence.decision import DecisionEngine
from intelligence.grouping import build_canonical_groups
from intelligence.homogeneity import HomogeneityEngine
from intelligence.pricing import PricingEngine
from intelligence.profit import ProfitEngine
from intelligence.scenario import compute_scenarios
from intelligence.scoring import ScoringEngine
from output.reporter import Reporter
from processing.cleaner import ManifestCleaner
from utils.logging import get_logger

logger = get_logger(__name__)


_DEFAULT_CATALOG_PATH = os.environ.get("BULK_INTEL_CATALOG_PATH", "data/catalog/india_top1k_v1.json")

def _get_default_providers():
    return (
        FuzzyCatalogPriceProvider(
            catalog=load_catalog(_DEFAULT_CATALOG_PATH),
            confidence_threshold=0.6,
        ),
        MRPHeuristicPriceProvider(),
    )

def _get_default_bsr_providers():
    return (
        FuzzyCatalogBSRProvider(
            catalog=load_catalog(_DEFAULT_CATALOG_PATH),
            confidence_threshold=0.6,
        ),
    )

@dataclass
class Pipeline:
    """Wire all the stages together with sensible defaults.

    Each stage is injected so tests, notebooks, and the future API
    layer can swap implementations (e.g. a real scraping price
    provider) without changing the orchestration.
    """

    settings: Settings = field(default_factory=get_settings)
    providers: Sequence[PriceProvider] = field(
        default_factory=_get_default_providers
    )
    bsr_providers: Sequence[BSRProvider] | None = field(
        default_factory=_get_default_bsr_providers
    )

    def run(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        execution_mode: ExecutionMode | str = ExecutionMode.PREVIEW,
        serp_preview_limit: int | None = None,
    ) -> dict[str, Path]:
        """Run the full pipeline and return paths to the written reports."""
        logger.info("Pipeline start: input=%s output=%s", input_path, output_dir)

        loader = ManifestLoader()
        cleaner = ManifestCleaner(self.settings)
        enricher = Enricher(
            providers=self._price_providers(),
            bsr_providers=list(self.bsr_providers) if self.bsr_providers else None
        )
        homogeneity = HomogeneityEngine(self.settings)
        pricing = PricingEngine(self.settings)
        scoring = ScoringEngine(self.settings)
        profit = ProfitEngine(self.settings)
        decision = DecisionEngine(self.settings)
        reporter = Reporter(Path(output_dir))

        df = loader.load(input_path)
        df = cleaner.clean(df)
        df = ChannelRouter(self.settings).route(df)
        df = homogeneity.annotate(df)
        groups = build_canonical_groups(df, self.settings)
        df.attrs["_groups"] = groups
        df = enricher.enrich(df)
        df, groups = self._apply_group_serp(df, groups, ExecutionMode(execution_mode), serp_preview_limit)
        df = pricing.compute(df)
        df = scoring.compute(df)
        df = profit.compute(df)
        df = compute_scenarios(df, self.settings)
        df = decision.decide(df)
        df.attrs["_groups"] = groups
        if groups.attrs.get("search_execution_summary"):
            df.attrs["search_execution_summary"] = groups.attrs["search_execution_summary"]

        outputs = reporter.write(df, base_name=Path(input_path).stem + "_report")
        logger.info("Pipeline complete: %s", outputs)
        return outputs

    def run_dataframe(
        self,
        df: pd.DataFrame,
        execution_mode: ExecutionMode | str = ExecutionMode.PREVIEW,
        serp_preview_limit: int | None = None,
    ) -> pd.DataFrame:
        """Run all in-memory stages (skipping I/O) — useful for tests/notebooks."""
        df = ManifestCleaner(self.settings).clean(df)
        df = ChannelRouter(self.settings).route(df)
        df = HomogeneityEngine(self.settings).annotate(df)
        groups = build_canonical_groups(df, self.settings)
        df.attrs["_groups"] = groups
        df = Enricher(
            providers=self._price_providers(),
            bsr_providers=list(self.bsr_providers) if self.bsr_providers else None
        ).enrich(df)
        df, groups = self._apply_group_serp(df, groups, ExecutionMode(execution_mode), serp_preview_limit)
        df = PricingEngine(self.settings).compute(df)
        df = ScoringEngine(self.settings).compute(df)
        df = ProfitEngine(self.settings).compute(df)
        df = compute_scenarios(df, self.settings)
        df = DecisionEngine(self.settings).decide(df)
        df.attrs["_groups"] = groups
        if groups.attrs.get("search_execution_summary"):
            df.attrs["search_execution_summary"] = groups.attrs["search_execution_summary"]
        return df

    def _price_providers(self) -> list[PriceProvider]:
        return list(self.providers)

    def _apply_group_serp(
        self,
        df: pd.DataFrame,
        groups: pd.DataFrame,
        execution_mode: ExecutionMode,
        serp_preview_limit: int | None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        live_serp_enabled = self.settings.serp_provider_enabled or self.settings.playwright_fallback_enabled
        if not live_serp_enabled:
            return df, groups
        if (
            not os.getenv(self.settings.serp_api_key_env)
            and not (
                self.settings.playwright_fallback_enabled
                and os.getenv("BULK_INTEL_PLAYWRIGHT_FALLBACK")
            )
        ):
            logger.info(
                "Live SERP enabled but %s is unset and Playwright fallback is not enabled; skipping group SERP",
                self.settings.serp_api_key_env,
            )
            return df, groups

        cache = SerpCache(self.settings.serp_cache_path, ttl_hours=self.settings.serp_cache_ttl_hours)
        provider = SerpAmazonPriceProvider(settings=self.settings, cache=cache)
        orchestrator = PartialSerpOrchestrator(
            settings=self.settings,
            provider=provider,
            cache=cache,
            state_path=Path(self.settings.serp_state_path),
        )
        groups = orchestrator.enrich(groups, mode=execution_mode, limit=serp_preview_limit)
        out = self._join_group_prices(df, groups)
        out.attrs["_groups"] = groups
        if groups.attrs.get("search_execution_summary"):
            out.attrs["search_execution_summary"] = groups.attrs["search_execution_summary"]
        return out, groups

    @staticmethod
    def _join_group_prices(df: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if groups.empty or "sku" not in out.columns:
            return out
        for _, group in groups.iterrows():
            price = group.get("amazon_price")
            if price is None or pd.isna(price):
                continue
            skus = set(group.get("group_member_skus") or ())
            if not skus:
                continue
            mask = out["sku"].astype(str).isin(skus)
            confidence = float(group.get("match_confidence") or 0.0)
            out.loc[mask, "amazon_price"] = float(price)
            out.loc[mask, "match_confidence"] = confidence
            out.loc[mask, "unreliable_match"] = confidence < 0.6
            out.loc[mask, "enrichment_source"] = "serp_amazon"
        return out


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    execution_mode: ExecutionMode | str = ExecutionMode.PREVIEW,
    serp_preview_limit: int | None = None,
) -> dict[str, Path]:
    """Functional wrapper using default settings and providers."""
    return Pipeline().run(input_path, output_dir, execution_mode, serp_preview_limit)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cli(argv: list[str] | None = None) -> int:
    """``python -m pipeline.run_pipeline --input X --output Y``."""
    parser = argparse.ArgumentParser(
        description="Run the Liquidation Intelligence pipeline on a manifest.",
    )
    parser.add_argument(
        "--input", "-i", required=True, help="Path to manifest CSV/XLSX."
    )
    parser.add_argument(
        "--output", "-o", default="output/reports", help="Directory for reports."
    )
    parser.add_argument(
        "--execution-mode",
        choices=[mode.value for mode in ExecutionMode],
        default=ExecutionMode.PREVIEW.value,
        help="Group-level SERP execution mode when SERP is enabled.",
    )
    parser.add_argument(
        "--serp-preview-limit",
        type=int,
        default=None,
        help="Number of top-value groups to SERP in preview mode.",
    )
    args = parser.parse_args(argv)

    try:
        outputs = run_pipeline(
            args.input,
            args.output,
            execution_mode=args.execution_mode,
            serp_preview_limit=args.serp_preview_limit,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "ManifestStateMismatchError":
            print(f"SERP state mismatch: {exc}")
            return 2
        raise
    print("Wrote:")
    for label, path in outputs.items():
        print(f"  {label}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
