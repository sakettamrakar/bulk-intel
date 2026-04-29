"""Resolve Amazon Best-Seller Rank (BSR) for manifest items.

Two implementation strategies are supported:
1. Static catalog field: lookup BSR from a static snapshot (e.g., top-1k catalog).
2. Live scraping: per-row request to Amazon's product page. (Not implemented in v1)

Currently, we ship Strategy 1 via `FuzzyCatalogBSRProvider`.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class BSRProvider(Protocol):
    """Strategy interface for resolving BSR."""

    name: str

    def lookup(self, row: pd.Series) -> float | None:
        """Return the BSR (lower is better) or None if unknown."""
        ...


@dataclass(frozen=True)
class FuzzyCatalogBSRProvider:
    """Resolve BSR by fuzzy matching product names against a catalog."""
    catalog: list[dict]
    name: str = "fuzzy_catalog_bsr"
    confidence_threshold: float = 0.6

    def lookup(self, row: pd.Series) -> float | None:
        name = row.get("product_name_clean") or row.get("product_name")
        if not isinstance(name, str) or not name:
            return None

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
            bsr = best_match.get("bsr")
            if bsr is not None:
                return float(bsr)

        return None
