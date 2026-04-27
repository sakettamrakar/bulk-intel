"""Rule-based sellability and risk scoring.

Both scores are produced on a 0–100 scale.  Weights live in
``config.settings`` so a domain expert can re-tune without touching
this code.  The implementation is intentionally vectorised over pandas
so it remains fast on six-figure manifests.

This module also includes the `apply_confidence_gate` function to
downgrade items with low match confidence from BUY to REVIEW.
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

        if "real_price" in out:
            real_price = pd.to_numeric(out["real_price"], errors="coerce")
        else:
            mrp = pd.to_numeric(out.get("mrp", pd.Series(0, index=out.index)), errors="coerce")
            real_price = mrp * self.settings.profit_assumptions.get("expected_sell_price_vs_mrp", 0.45)

        out["price_band"] = self._classify_price_band(real_price)
        out["sellability_score"] = self._sellability(out, real_price).round(2)
        out["risk_score"] = self._risk(out).round(2)

        logger.debug(
            "Score summary: sellability mean=%.2f, risk mean=%.2f",
            float(out["sellability_score"].mean(skipna=True) or 0.0),
            float(out["risk_score"].mean(skipna=True) or 0.0),
        )
        return out

    def _classify_price_band(self, real_price: pd.Series) -> pd.Series:
        return pd.cut(
            real_price,
            bins=[-np.inf, 300, 1000, np.inf],
            labels=["LOW", "MID", "HIGH"]
        )

    def _price_band_score(self, real_price: pd.Series) -> pd.Series:
        return pd.cut(
            real_price,
            bins=[-np.inf, 300, 1000, np.inf],
            labels=[40.0, 70.0, 100.0]
        ).astype(float)

    # ------------------------------------------------------------------
    # Sellability
    # ------------------------------------------------------------------

    def _sellability(self, df: pd.DataFrame, real_price: pd.Series) -> pd.Series:
        weights = self.settings.scoring_weights

        discount = _normalise(df.get("discount_percentage", pd.Series(0, index=df.index)), 0, 80)
        market_gap = _normalise(df.get("market_gap", pd.Series(0, index=df.index)), 0, 60)

        category_col = df.get("category", pd.Series("unknown", index=df.index)).astype("string").str.lower()
        demand_score = category_col.map(self.settings.demand_score).fillna(50.0)
        category_liquidity = category_col.map(self.settings.category_liquidity).fillna(50.0)

        brand_score = self._brand_score(df.get("brand", pd.Series([""]*len(df))))
        price_band_score = self._price_band_score(real_price)

        return (
            discount * weights.get("discount_percentage", 0.0)
            + market_gap * weights.get("market_gap", 0.0)
            + demand_score * weights.get("demand_score", 0.0)
            + category_liquidity * weights.get("category_liquidity", 0.0)
            + brand_score * weights.get("brand_score", 0.0)
            + price_band_score * weights.get("price_band", 0.0)
        )

    def _brand_score(self, brand: pd.Series) -> pd.Series:
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
        factors = self.settings.condition_to_sell_through
        col = (
            df.get("condition_normalized")
            if "condition_normalized" in df.columns
            else pd.Series(["unknown"] * len(df), index=df.index)
        )
        return col.map(lambda c: factors.get(c, factors["unknown"])["risk_score"]).astype(float)

    @staticmethod
    def _missing_data_penalty(df: pd.DataFrame) -> pd.Series:
        critical = ["mrp", "floor_price", "category", "brand"]
        # Use .get to avoid KeyError if columns don't exist
        existing = [c for c in critical if c in df.columns]
        missing_existing = df[existing].isna().sum(axis=1) if existing else pd.Series(0, index=df.index)
        missing_total = missing_existing + (len(critical) - len(existing))
        # 0 missing → 0; all 4 missing → 100
        return (missing_total / len(critical)) * 100.0

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


def apply_confidence_gate(df: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Downgrade rows with low match confidence from BUY to REVIEW.

    Adds a `confidence_gate_applied` boolean column to the DataFrame and appends
    a note to `reasoning` if the row is gated. Should be called after the
    initial per-row decisions are made.
    """
    settings = settings or get_settings()
    out = df.copy()
    min_conf = settings.decision_thresholds.get("min_buy_match_confidence", 0.6)

    match_confidence = pd.to_numeric(out.get("match_confidence", pd.Series([1.0] * len(out), index=out.index)), errors="coerce").fillna(1.0)

    # Identify rows that fail the confidence gate
    fails_gate = match_confidence < min_conf
    out["confidence_gate_applied"] = False

    if fails_gate.any():
        # Only downgrade if it's currently BUY
        needs_downgrade = fails_gate & (out.get("recommendation", pd.Series(["SKIP"] * len(out), index=out.index)) == "BUY")

        # Apply downgrade
        if "recommendation" in out:
            out.loc[needs_downgrade, "recommendation"] = "REVIEW"
            out.loc[needs_downgrade, "confidence_gate_applied"] = True

            # Update reasoning
            reasoning = out.loc[needs_downgrade, "reasoning"].fillna("")
            out.loc[needs_downgrade, "reasoning"] = reasoning.apply(
                lambda r: r + f"; match confidence below {min_conf:.2f} — price is synthetic" if r else f"match confidence below {min_conf:.2f} — price is synthetic"
            )

    return out


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
