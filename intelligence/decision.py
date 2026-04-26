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
        return out

    # ------------------------------------------------------------------
    # Per-row decision logic
    # ------------------------------------------------------------------

    def _decide_row(
        self, row: pd.Series, thresholds
    ) -> tuple[str, list[str]]:
        sellability = _safe_float(row.get("sellability_score"))
        risk = _safe_float(row.get("risk_score"))
        margin = _safe_float(row.get("expected_margin_pct"))
        profit = _safe_float(row.get("expected_profit"))

        reasons: list[str] = []
        score_pass = sellability >= thresholds["buy_score_min"]
        risk_pass = risk <= thresholds["risk_score_max"]
        margin_pass = margin >= thresholds["min_expected_margin_pct"]
        profit_pass = profit > 0

        # Positive signals — recorded only when the gate is cleared so the
        # narrative reads as a justification, not a checklist.
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

        if not profit_pass:
            reasons.append("expected profit non-positive")

        gates = [score_pass, risk_pass, margin_pass, profit_pass]
        passes = sum(gates)

        if all(gates):
            recommendation = BUY
        elif passes >= 2 and risk_pass:
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
