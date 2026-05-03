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
from ingestion.loader import ManifestLoader
from intelligence.channel import ChannelRouter
from intelligence.decision import DecisionEngine
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

    def run(self, input_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
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
        df = enricher.enrich(df)
        df = homogeneity.annotate(df)
        df = pricing.compute(df)
        df = scoring.compute(df)
        df = profit.compute(df)
        df = compute_scenarios(df, self.settings)
        df = decision.decide(df)

        outputs = reporter.write(df, base_name=Path(input_path).stem + "_report")
        logger.info("Pipeline complete: %s", outputs)
        return outputs

    def run_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run all in-memory stages (skipping I/O) — useful for tests/notebooks."""
        df = ManifestCleaner(self.settings).clean(df)
        df = ChannelRouter(self.settings).route(df)
        df = Enricher(
            providers=self._price_providers(),
            bsr_providers=list(self.bsr_providers) if self.bsr_providers else None
        ).enrich(df)
        df = HomogeneityEngine(self.settings).annotate(df)
        df = PricingEngine(self.settings).compute(df)
        df = ScoringEngine(self.settings).compute(df)
        df = ProfitEngine(self.settings).compute(df)
        df = compute_scenarios(df, self.settings)
        df = DecisionEngine(self.settings).decide(df)
        return df

    def _price_providers(self) -> list[PriceProvider]:
        providers = list(self.providers)
        if not self.settings.serp_provider_enabled:
            return providers
        if not os.getenv(self.settings.serp_api_key_env):
            logger.info(
                "SERP provider enabled but %s is unset; skipping provider",
                self.settings.serp_api_key_env,
            )
            return providers
        if any(getattr(provider, "name", "") == "serp_amazon" for provider in providers):
            return providers
        from enrichment.serp_price_provider import SerpAmazonPriceProvider

        serp_provider = SerpAmazonPriceProvider(settings=self.settings)
        insert_at = next(
            (idx for idx, provider in enumerate(providers) if getattr(provider, "name", "") == "mrp_heuristic"),
            len(providers),
        )
        providers.insert(insert_at, serp_provider)
        return providers


def run_pipeline(input_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """Functional wrapper using default settings and providers."""
    return Pipeline().run(input_path, output_dir)


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
    args = parser.parse_args(argv)

    outputs = run_pipeline(args.input, args.output)
    print("Wrote:")
    for label, path in outputs.items():
        print(f"  {label}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
