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

from enrichment.bsr_provider import BSRProvider
from utils.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class PriceProvider(Protocol):
    """Strategy interface for resolving market and wholesale prices.

    Implementations should be side-effect free and idempotent so they
    can be cached or invoked in parallel later.
    """

    name: str

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None, float]:
        """Return ``(amazon_price, wholesale_price, match_confidence)`` for a manifest row.

        Either field may be ``None`` if the provider has no signal. match_confidence is a float 0.0-1.0.
        """
        ...



import difflib

@dataclass(frozen=True)
class FuzzyCatalogPriceProvider:
    """Resolve prices by fuzzy matching product names against a catalog."""
    catalog: list[dict] # list of dicts with 'product_name', 'amazon_price', 'wholesale_price'
    name: str = "fuzzy_catalog"
    confidence_threshold: float = 0.6

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None, float]:
        name = row.get("product_name_clean") or row.get("product_name")
        if not isinstance(name, str) or not name:
            return (None, None, 0.0)

        best_match = None
        best_ratio = 0.0
        name_lower = name.lower()

        for item in self.catalog:
            cat_name = item.get("product_name", "")
            if not cat_name:
                continue
            ratio = difflib.SequenceMatcher(None, name_lower, cat_name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = item

        if best_match and best_ratio >= self.confidence_threshold:
            amazon = best_match.get("amazon_price")
            wholesale = best_match.get("wholesale_price")
            return (amazon, wholesale, best_ratio)

        return (None, None, best_ratio)

# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LookupTablePriceProvider:
    """Resolve prices from an in-memory ``{sku: (...)}`` table.

    Each value may be a 2-tuple ``(market, wholesale)`` (confidence
    defaults to 1.0) or a 3-tuple ``(market, wholesale, confidence)``
    when the caller wants to encode an explicit match confidence.

    Useful for manual overrides and unit tests, and serves as the seam
    a future external API would replace.
    """

    table: Mapping[
        str,
        tuple[float | None, float | None]
        | tuple[float | None, float | None, float],
    ]
    name: str = "lookup_table"

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None, float]:
        sku = row.get("sku")
        if not isinstance(sku, str):
            return (None, None, 0.0)
        entry = self.table.get(sku)
        if entry is None:
            return (None, None, 0.0)
        if len(entry) == 3:
            return (entry[0], entry[1], float(entry[2]))
        return (entry[0], entry[1], 1.0)


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

    def lookup(self, row: pd.Series) -> tuple[float | None, float | None, float]:
        mrp = row.get("mrp")
        if mrp is None or pd.isna(mrp):
            return (None, None, 0.0)
        market = float(mrp) * self.market_pct_of_mrp
        wholesale = (
            float(mrp) * self.wholesale_pct_of_mrp
            if self.wholesale_pct_of_mrp is not None
            else None
        )
        return (market, wholesale, 1.0)


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
    bsr_providers: list[BSRProvider] | None = None

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
        amazon = np.full(len(out), np.nan)
        wholesale = np.full(len(out), np.nan)
        confidence = np.full(len(out), 0.0)
        unreliable = np.full(len(out), False, dtype=bool)
        sources: list[str] = ["" for _ in range(len(out))]

        for idx, row in out.iterrows():
            row_amazon, row_wholesale, row_conf, source_label = self._resolve_row(row)
            amazon[idx] = row_amazon if row_amazon is not None else np.nan
            wholesale[idx] = row_wholesale if row_wholesale is not None else np.nan
            confidence[idx] = row_conf
            unreliable[idx] = row_conf < 0.6  # Unreliable match if confidence < 0.6
            sources[idx] = source_label

        out["amazon_price"] = amazon
        out["wholesale_price"] = wholesale
        out["match_confidence"] = confidence
        out["unreliable_match"] = unreliable
        out["enrichment_source"] = sources

        if self.bsr_providers:
            bsr_list = []
            for idx, row in out.iterrows():
                bsr = self._resolve_bsr(row)
                bsr_list.append(bsr if bsr is not None else np.nan)
            out["amazon_bsr"] = bsr_list
        else:
            out["amazon_bsr"] = np.nan

        logger.info(
            "Amazon prices resolved=%d/%d; wholesale resolved=%d/%d",
            out["amazon_price"].notna().sum(),
            len(out),
            out["wholesale_price"].notna().sum(),
            len(out),
        )
        return out

    def _resolve_row(
        self, row: pd.Series
    ) -> tuple[float | None, float | None, float, str]:
        amazon: float | None = None
        wholesale: float | None = None
        best_conf = 0.0 # default to 0.0 so unmatched items are marked unreliable
        contributing: list[str] = []

        for provider in self.providers:
            if amazon is not None and wholesale is not None:
                break
            try:
                m, w, conf = provider.lookup(row)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Provider '%s' failed for sku=%s", provider.name, row.get("sku"))
                continue

            if amazon is None and m is not None:
                amazon = float(m)
                best_conf = conf
                contributing.append(provider.name)
            if wholesale is None and w is not None:
                wholesale = float(w)
                # If we matched amazon via fuzzy, we'd have that confidence. Else use this one.
                # Usually wholesale is heuristic/lookup so conf=1.0. If we only have wholesale, best_conf becomes conf.
                best_conf = min(best_conf, conf) if amazon is not None else conf
                if provider.name not in contributing:
                    contributing.append(provider.name)

        return amazon, wholesale, best_conf, "+".join(contributing)

    def _resolve_bsr(self, row: pd.Series) -> float | None:
        if not self.bsr_providers:
            return None
        for provider in self.bsr_providers:
            try:
                val = provider.lookup(row)
                if val is not None:
                    return float(val)
            except Exception:
                logger.exception("BSRProvider '%s' failed for sku=%s", provider.name, row.get("sku"))
        return None


def enrich_manifest(
    df: pd.DataFrame,
    providers: list[PriceProvider] | None = None,
    bsr_providers: list[BSRProvider] | None = None,
) -> pd.DataFrame:
    """Convenience wrapper using a sensible default provider chain."""
    if providers is None:
        providers = [MRPHeuristicPriceProvider()]
    return Enricher(providers, bsr_providers=bsr_providers).enrich(df)
