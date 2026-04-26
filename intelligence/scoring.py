"""Rule-based sellability and risk scoring.

Both scores are produced on a 0–100 scale.  Weights live in
``config.settings`` so a domain expert can re-tune without touching
this code.  The implementation is intentionally vectorised over pandas
so it remains fast on six-figure manifests.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.settings import Settings, get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ScoringEngine:
    """Compute sellability + risk scores for a pricing-enriched manifest."""

    settings: Settings

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``df`` with ``sellability_score`` and ``risk_score``."""
        logger.info("Scoring %d rows", len(df))
        out = df.copy()

        out["sellability_score"] = self._sellability(out).round(2)
        out["risk_score"] = self._risk(out).round(2)

        logger.debug(
            "Score summary: sellability mean=%.2f, risk mean=%.2f",
            float(out["sellability_score"].mean(skipna=True) or 0.0),
            float(out["risk_score"].mean(skipna=True) or 0.0),
        )
        return out

    # ------------------------------------------------------------------
    # Sellability
    # ------------------------------------------------------------------

    def _sellability(self, df: pd.DataFrame) -> pd.Series:
        weights = self.settings.scoring_weights
        discount = _normalise(df["discount_percentage"], 0, 80)
        market_gap = _normalise(df["market_gap"], 0, 60)
        category_demand = (
            df["category"].str.lower().map(self.settings.category_demand).fillna(50.0)
        )
        brand_strength = self._brand_strength(df["brand"])

        return (
            discount * weights["discount_percentage"]
            + market_gap * weights["market_gap"]
            + category_demand * weights["category_demand"]
            + brand_strength * weights["brand_strength"]
        )

    def _brand_strength(self, brand: pd.Series) -> pd.Series:
        known = self.settings.known_brands
        lc = brand.astype("string").str.lower().fillna("")
        return lc.map(lambda b: 90.0 if b in known else (60.0 if b else 30.0))

    # ------------------------------------------------------------------
    # Risk
    # ------------------------------------------------------------------

    def _risk(self, df: pd.DataFrame) -> pd.Series:
        weights = self.settings.risk_weights

        missing = self._missing_data_penalty(df)
        low_qty = self._low_quantity_penalty(df["quantity"])
        category_risk = (
            df["category"].str.lower().map(self.settings.category_risk).fillna(60.0)
        )
        thin_margin = self._thin_margin_penalty(df["discount_percentage"])
        condition_risk = self._condition_risk(df)

        return (
            missing * weights["missing_data_penalty"]
            + low_qty * weights["low_quantity_penalty"]
            + category_risk * weights["category_risk"]
            + thin_margin * weights["thin_margin_penalty"]
            + condition_risk * weights.get("condition_risk", 0.0)
        )

    def _condition_risk(self, df: pd.DataFrame) -> pd.Series:
        """Per-row risk contribution from the normalized condition bucket."""
        factors = self.settings.condition_factors
        col = (
            df.get("condition_normalized")
            if "condition_normalized" in df.columns
            else pd.Series(["unknown"] * len(df), index=df.index)
        )
        return col.map(lambda c: factors.get(c, factors["unknown"])["risk_score"]).astype(float)

    @staticmethod
    def _missing_data_penalty(df: pd.DataFrame) -> pd.Series:
        critical = ["mrp", "floor_price", "category", "brand"]
        missing = df[critical].isna().sum(axis=1)
        # 0 missing → 0; all 4 missing → 100
        return (missing / len(critical)) * 100.0

    @staticmethod
    def _low_quantity_penalty(qty: pd.Series) -> pd.Series:
        q = pd.to_numeric(qty, errors="coerce").fillna(1)
        # Quantity of 1 → 80 risk; quantity ≥ 25 → 0 risk.
        scaled = np.clip(1.0 - (q - 1) / 24.0, 0.0, 1.0) * 80.0
        return pd.Series(scaled, index=qty.index)

    @staticmethod
    def _thin_margin_penalty(discount: pd.Series) -> pd.Series:
        d = pd.to_numeric(discount, errors="coerce").fillna(0)
        # 0% discount → 100; ≥50% discount → 0 (linear in between).
        scaled = np.clip(1.0 - d / 50.0, 0.0, 1.0) * 100.0
        return pd.Series(scaled, index=discount.index)


def compute_scores(df: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Functional wrapper around :class:`ScoringEngine`."""
    return ScoringEngine(settings or get_settings()).compute(df)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(series: pd.Series, lo: float, hi: float) -> pd.Series:
    """Linearly map ``[lo, hi]`` onto ``[0, 100]``, clipped, NaN-safe."""
    s = pd.to_numeric(series, errors="coerce")
    scaled = (s - lo) / (hi - lo)
    return scaled.clip(lower=0.0, upper=1.0).fillna(0.0) * 100.0
