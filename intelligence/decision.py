"""Buy / Skip decision engine with explainable reasoning.

Combines sellability, risk, and projected margin against the
configured thresholds to produce a recommendation plus a list of
human-readable reasons.  The reasoning is the primary value for the
operator: every decision must be defensible.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.settings import Settings, get_settings
from intelligence.scoring import apply_confidence_gate
from utils.logging import get_logger

logger = get_logger(__name__)

BUY = "BUY"
SKIP = "SKIP"
REVIEW = "REVIEW"


@dataclass(frozen=True)
class DecisionEngine:
    """Apply threshold rules to produce ``recommendation`` + ``reasoning``."""

    settings: Settings

    def decide(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``df`` with decision columns appended.

        Columns added:
            - ``recommendation``: one of ``BUY``, ``REVIEW``, ``SKIP``.
            - ``reasoning``: ``;``-separated explanation tokens.
        """
        logger.info("Deciding %d rows", len(df))
        out = df.copy()
        thresholds = self.settings.decision_thresholds

        recs: list[str] = []
        reasons: list[str] = []

        for _, row in out.iterrows():
            recommendation, why = self._decide_row(row, thresholds)
            recs.append(recommendation)
            reasons.append("; ".join(why))

        out["recommendation"] = recs
        out["reasoning"] = reasons

        logger.info(
            "Decisions: BUY=%d, REVIEW=%d, SKIP=%d",
            recs.count(BUY),
            recs.count(REVIEW),
            recs.count(SKIP),
        )

        out = apply_confidence_gate(out, self.settings)

        out.attrs["lot_summary"] = self._calculate_lot_summary(out, thresholds)

        return out

    # ------------------------------------------------------------------
    # Lot-level summary logic
    # ------------------------------------------------------------------

    def _calculate_lot_summary(self, df: pd.DataFrame, thresholds: dict) -> dict:
        summary = {}

        qty_col = df.get("quantity", pd.Series([1]*len(df)))
        qty = pd.to_numeric(qty_col, errors="coerce").fillna(1)
        total_items = float(qty.sum())

        expected_sellable = float(df.get("expected_sellable_qty", pd.Series([0.0]*len(df))).sum())
        expected_revenue = float(df.get("expected_revenue", pd.Series([0.0]*len(df))).sum())
        expected_profit = float(df.get("expected_profit", pd.Series([0.0]*len(df))).sum())

        roi_series = pd.to_numeric(df.get("expected_roi_pct", pd.Series([0.0]*len(df))), errors="coerce").dropna()
        roi_low = float(roi_series.quantile(0.25)) if not roi_series.empty else 0.0
        roi_median = float(roi_series.quantile(0.50)) if not roi_series.empty else 0.0
        roi_high = float(roi_series.quantile(0.75)) if not roi_series.empty else 0.0

        cond_norm = df.get("condition_normalized", pd.Series(["unknown"]*len(df)))
        unknown_qty = float(qty[cond_norm == "unknown"].sum())
        high_unknown_condition_pct = (unknown_qty / total_items) * 100 if total_items > 0 else 0.0

        unreliable = df.get("unreliable_match", pd.Series([False]*len(df)))
        unreliable_qty = float(qty[unreliable].sum())
        low_match_confidence_pct = (unreliable_qty / total_items) * 100 if total_items > 0 else 0.0

        high_price_uncertainty = bool(low_match_confidence_pct > 20.0 or high_unknown_condition_pct > 20.0)

        margin = (expected_profit / expected_revenue) * 100 if expected_revenue > 0 else 0.0
        min_expected_roi = thresholds.get("min_expected_roi_pct", 25.0)
        min_expected_margin = thresholds.get("min_expected_margin_pct", 15.0)
        min_sellable = thresholds.get("min_sellable_count", 10.0)

        roi_pass = roi_median > min_expected_roi
        margin_pass = margin > min_expected_margin
        sellable_pass = expected_sellable > min_sellable

        gates = [roi_pass, margin_pass, sellable_pass]
        passes = sum(gates)

        if all(gates):
            decision = BUY
        elif passes >= 2:
            decision = REVIEW
        else:
            decision = SKIP

        # "Defective" buckets are confirmed-bad inventory; ``not_tested`` is
        # uninspected (mostly functional after testing) and tracked separately
        # so the operator can distinguish "needs inspection" from "broken".
        defect_qty = float(qty[cond_norm.isin(["defective", "salvage"])].sum())
        defect_prob = (defect_qty / total_items) * 100 if total_items > 0 else 0.0

        untested_qty = float(qty[cond_norm.isin(["not_tested", "as_is"])].sum())
        untested_pct = (untested_qty / total_items) * 100 if total_items > 0 else 0.0

        known_brands = self.settings.known_brands
        brand_col = df.get("brand", pd.Series([""]*len(df))).astype(str).str.lower()
        known_brand_qty = float(qty[brand_col.isin(known_brands)].sum())
        known_brand_mix = (known_brand_qty / total_items) * 100 if total_items > 0 else 0.0

        reasons = []
        if roi_median > 40:
            reasons.append("High ROI")
        elif roi_median < min_expected_roi:
            reasons.append("Low ROI")

        if known_brand_mix > 30:
            reasons.append("Strong brand mix")
        elif known_brand_mix < 10:
            reasons.append("Weak brand mix")

        if defect_prob > 30:
            reasons.append("High defect probability")
        elif defect_prob < 10 and untested_pct < 30:
            reasons.append("Low sell-through risk")

        if untested_pct > 50:
            reasons.append("Lot is largely untested — inspection cost dominates")

        if not reasons:
            reasons.append("Mixed metrics")

        summary.update({
            "total_items": round(total_items, 2),
            "expected_sellable": round(expected_sellable, 2),
            "expected_revenue": round(expected_revenue, 2),
            "roi_low": round(roi_low, 2),
            "roi_median": round(roi_median, 2),
            "roi_high": round(roi_high, 2),
            "high_unknown_condition_pct": round(high_unknown_condition_pct, 2),
            "untested_pct": round(untested_pct, 2),
            "defect_pct": round(defect_prob, 2),
            "low_match_confidence_pct": round(low_match_confidence_pct, 2),
            "high_price_uncertainty": high_price_uncertainty,
            "margin": round(margin, 2),
            "decision": decision,
            "decision_reasons": reasons
        })

        return summary

    # ------------------------------------------------------------------
    # Per-row decision logic
    # ------------------------------------------------------------------

    def _decide_row(
        self, row: pd.Series, thresholds
    ) -> tuple[str, list[str]]:
        sellability = _safe_float(row.get("sellability_score"))
        risk = _safe_float(row.get("risk_score"))
        margin = _safe_float(row.get("expected_margin_pct"))
        roi = _safe_float(row.get("expected_roi_pct"))
        profit = _safe_float(row.get("expected_profit"))

        reasons: list[str] = []
        score_pass = sellability >= thresholds["buy_score_min"]
        risk_pass = risk <= thresholds["risk_score_max"]
        margin_pass = margin >= thresholds["min_expected_margin_pct"]
        roi_pass = roi >= thresholds.get("min_expected_roi_pct", 0.0)
        profit_pass = profit > 0

        if score_pass:
            reasons.append(f"sellability {sellability:.0f} ≥ {thresholds['buy_score_min']:.0f}")
        else:
            reasons.append(
                f"sellability {sellability:.0f} below threshold {thresholds['buy_score_min']:.0f}"
            )

        if risk_pass:
            reasons.append(f"risk {risk:.0f} ≤ {thresholds['risk_score_max']:.0f}")
        else:
            reasons.append(
                f"risk {risk:.0f} exceeds threshold {thresholds['risk_score_max']:.0f}"
            )

        if margin_pass:
            reasons.append(f"margin {margin:.1f}% ≥ {thresholds['min_expected_margin_pct']:.1f}%")
        else:
            reasons.append(
                f"margin {margin:.1f}% below {thresholds['min_expected_margin_pct']:.1f}%"
            )

        roi_threshold = thresholds.get("min_expected_roi_pct", 0.0)
        if roi_pass:
            reasons.append(f"ROI {roi:.1f}% ≥ {roi_threshold:.1f}%")
        else:
            reasons.append(f"ROI {roi:.1f}% below {roi_threshold:.1f}%")

        if not profit_pass:
            reasons.append("expected profit non-positive")

        gates = [score_pass, risk_pass, margin_pass, roi_pass, profit_pass]
        passes = sum(gates)

        if all(gates):
            recommendation = BUY
        elif passes >= 3 and risk_pass and profit_pass:
            recommendation = REVIEW
        else:
            recommendation = SKIP

        return recommendation, reasons


def decide(df: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Functional wrapper around :class:`DecisionEngine`."""
    return DecisionEngine(settings or get_settings()).decide(df)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(value) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
