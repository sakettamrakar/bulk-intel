"""Deterministic profitability simulator.

Given pricing fields and configurable assumptions, project the
expected revenue and profit per line item.  The simulator is
intentionally simple — assumptions are exposed so the operator can
"what-if" different scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.settings import Settings, get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProfitEngine:
    """Compute expected revenue and profit assuming pipeline defaults."""

    settings: Settings

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``df`` with profitability columns added.

        Columns:
            - ``expected_sellable_qty``
            - ``expected_sell_price``
            - ``expected_revenue``
            - ``expected_cost``
            - ``expected_profit``
            - ``expected_margin_pct``
        """
        logger.info("Computing profitability for %d rows", len(df))
        a = self.settings.profit_assumptions
        out = df.copy()

        qty = pd.to_numeric(out["quantity"], errors="coerce").fillna(1)
        floor = pd.to_numeric(out["floor_price"], errors="coerce")
        mrp = pd.to_numeric(out["mrp"], errors="coerce")
        market = pd.to_numeric(out.get("market_price"), errors="coerce")

        sellable_qty = (qty * a["expected_sellable_pct"]).round(2)
        # Prefer market price as the anchor; fall back to MRP × assumption.
        anchor_from_mrp = mrp * a["expected_sell_price_vs_mrp"]
        expected_sell_price = market.where(market.notna(), anchor_from_mrp)

        with np.errstate(invalid="ignore"):
            expected_revenue = sellable_qty * expected_sell_price
            acquisition_cost = qty * floor * (1.0 + a["acquisition_overhead_pct"])
            operating_cost = expected_revenue * a["operating_cost_pct"]
            expected_cost = acquisition_cost + operating_cost
            expected_profit = expected_revenue - expected_cost
            margin_pct = np.where(
                expected_revenue > 0,
                (expected_profit / expected_revenue) * 100.0,
                np.nan,
            )

        out["expected_sellable_qty"] = sellable_qty
        out["expected_sell_price"] = expected_sell_price.round(2)
        out["expected_revenue"] = expected_revenue.round(2)
        out["expected_cost"] = expected_cost.round(2)
        out["expected_profit"] = expected_profit.round(2)
        out["expected_margin_pct"] = pd.Series(margin_pct, index=out.index).round(2)

        logger.debug(
            "Profit summary: total expected profit=%.2f over %d rows",
            float(out["expected_profit"].sum(skipna=True) or 0.0),
            len(out),
        )
        return out


def compute_profitability(
    df: pd.DataFrame, settings: Settings | None = None
) -> pd.DataFrame:
    """Functional wrapper around :class:`ProfitEngine`."""
    return ProfitEngine(settings or get_settings()).compute(df)
