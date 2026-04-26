"""Add external pricing fields to a cleaned manifest.

The enrichment layer is intentionally pluggable: it depends on the
``PriceProvider`` ``Protocol`` rather than any concrete data source.
Today we ship two simple providers (lookup-table and MRP-heuristic)
but a future scraper or API client can drop in without touching the
rest of the pipeline.

Output columns added:
    market_price     — observed online selling price.
    wholesale_price  — bulk/B2B price (optional).
    enrichment_source — provider name(s) that produced the values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from utils.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class PriceProvider(Protocol):
    """Strategy interface for resolving market and wholesale prices.

    Implementations should be side-effect free and idempotent so they
    can be cached or invoked in parallel later.
    """

    name: str

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None]:
        """Return ``(market_price, wholesale_price)`` for a manifest row.

        Either field may be ``None`` if the provider has no signal.
        """
        ...


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LookupTablePriceProvider:
    """Resolve prices from an in-memory ``{sku: (market, wholesale)}`` table.

    Useful for manual overrides and unit tests, and serves as the seam
    a future external API would replace.
    """

    table: Mapping[str, tuple[float | None, float | None]]
    name: str = "lookup_table"

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None]:
        sku = row.get("sku")
        if not isinstance(sku, str):
            return (None, None)
        return self.table.get(sku, (None, None))


@dataclass(frozen=True)
class MRPHeuristicPriceProvider:
    """Estimate market price as a constant fraction of MRP.

    Acts as a deterministic fallback when no real market data exists
    so the rest of the pipeline always has something to score.
    """

    # Anchors the "new-condition" online selling price.  Condition
    # factors in profit.py mark this down for refurb / used / as-is /
    # not-tested goods so we don't double-discount.
    market_pct_of_mrp: float = 0.80
    wholesale_pct_of_mrp: float | None = None
    name: str = "mrp_heuristic"

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None]:
        mrp = row.get("mrp")
        if mrp is None or pd.isna(mrp):
            return (None, None)
        market = float(mrp) * self.market_pct_of_mrp
        wholesale = (
            float(mrp) * self.wholesale_pct_of_mrp
            if self.wholesale_pct_of_mrp is not None
            else None
        )
        return (market, wholesale)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class Enricher:
    """Apply a chain of :class:`PriceProvider` strategies to a manifest.

    Providers are consulted in order; the first non-``None`` value wins
    for each field.  This lets callers prefer authoritative sources and
    fall back to heuristics when data is missing.
    """

    providers: list[PriceProvider]

    def enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``df`` with enrichment columns populated."""
        if not self.providers:
            raise ValueError("Enricher requires at least one PriceProvider.")

        logger.info(
            "Enriching %d rows with providers: %s",
            len(df),
            [p.name for p in self.providers],
        )
        out = df.copy()
        market = np.full(len(out), np.nan)
        wholesale = np.full(len(out), np.nan)
        sources: list[str] = ["" for _ in range(len(out))]

        for idx, row in out.iterrows():
            row_market, row_wholesale, source_label = self._resolve_row(row)
            market[idx] = row_market if row_market is not None else np.nan
            wholesale[idx] = row_wholesale if row_wholesale is not None else np.nan
            sources[idx] = source_label

        out["market_price"] = market
        out["wholesale_price"] = wholesale
        out["enrichment_source"] = sources

        logger.info(
            "Market prices resolved=%d/%d; wholesale resolved=%d/%d",
            out["market_price"].notna().sum(),
            len(out),
            out["wholesale_price"].notna().sum(),
            len(out),
        )
        return out

    def _resolve_row(
        self, row: pd.Series
    ) -> tuple[float | None, float | None, str]:
        market: float | None = None
        wholesale: float | None = None
        contributing: list[str] = []

        for provider in self.providers:
            if market is not None and wholesale is not None:
                break
            try:
                m, w = provider.lookup(row)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Provider '%s' failed for sku=%s", provider.name, row.get("sku"))
                continue

            if market is None and m is not None:
                market = float(m)
                contributing.append(provider.name)
            if wholesale is None and w is not None:
                wholesale = float(w)
                if provider.name not in contributing:
                    contributing.append(provider.name)

        return market, wholesale, "+".join(contributing)


def enrich_manifest(
    df: pd.DataFrame, providers: list[PriceProvider] | None = None
) -> pd.DataFrame:
    """Convenience wrapper using a sensible default provider chain."""
    if providers is None:
        providers = [MRPHeuristicPriceProvider()]
    return Enricher(providers).enrich(df)
