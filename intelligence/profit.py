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
    """Compute expected revenue and profit assuming pipeline defaults.

    Factors in configured costs (operating, transport, acquisition).
    """

    settings: Settings

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``df`` with profitability columns added.

        Sell-through semantics
        ----------------------
        ``expected_sellable_pct`` is the **base/cap** sell-through (an upper
        bound on how much of any lot we expect to clear, even for brand-new
        goods).  Each condition's ``sellable_factor`` is the **ceiling
        imposed by that condition**.  We combine them with ``min`` rather
        than multiplication so we don't double-count the same conservatism:

            effective = min(expected_sellable_pct, condition.sellable_factor)

        That gives a clean reading:

        * ``new``         (factor 1.00) — base 0.65 binds → 65 % clears
        * ``not_tested``  (factor 0.65) — both equal      → 65 % clears
        * ``defective``   (factor 0.20) — condition binds → 20 % clears

        Columns:
            - ``platform_fee_pct``
            - ``expected_sellable_qty``
            - ``expected_sell_price``
            - ``expected_revenue``
            - ``transport_cost``
            - ``inspection_cost``
            - ``expected_cost``
            - ``expected_profit``
            - ``expected_margin_pct``
            - ``expected_roi_pct``
        """
        logger.info("Computing profitability for %d rows", len(df))
        a = self.settings.profit_assumptions
        out = df.copy()

        qty = pd.to_numeric(out.get("quantity", pd.Series(1, index=out.index)), errors="coerce").fillna(1)
        floor = pd.to_numeric(out.get("floor_price", pd.Series(0, index=out.index)), errors="coerce")
        mrp = pd.to_numeric(out.get("mrp", pd.Series(0, index=out.index)), errors="coerce")

        # We now expect real_price to be provided by the PricingEngine
        if "real_price" in out:
            real_price = pd.to_numeric(out["real_price"], errors="coerce")
        else:
            real_price = mrp * a["expected_sell_price_vs_mrp"]

        sellable_factor = self._condition_multipliers(out)

        # min(base, condition_factor) — see docstring for rationale.
        base_sellable_pct = a.get("expected_sellable_pct", 0.65)
        effective_sellable_pct = np.minimum(base_sellable_pct, sellable_factor)
        sellable_qty = (qty * effective_sellable_pct).round(2)

        # No double discounting: real_price is the final expected_sell_price
        expected_sell_price = real_price

        # ``price_realization_factor`` defaults to 1.0 (off): the haircut
        # vs MRP is already encoded in ``real_price`` from pricing.py.
        # Operators who want to model clearance/promo erosion separately
        # can drop this below 1.0.
        price_realization = a.get("price_realization_factor", 1.0)
        lot_cost = qty * floor

        transport_cost = self._resolve_transport_cost(out, qty)

        with np.errstate(invalid="ignore"):
            expected_revenue = sellable_qty * expected_sell_price * price_realization
            acquisition_cost = qty * floor * (1.0 + a.get("acquisition_overhead_pct", 0.05))
            platform_fee_pct_series = self._resolve_platform_fee_pct(out)
            platform_fee_pct = platform_fee_pct_series.values
            ancillary_pct = self.settings.ancillary_revenue_fee_pct
            operating_cost = expected_revenue * (platform_fee_pct + ancillary_pct)
            inspection_cost = self._resolve_inspection_cost(out, qty)
            expected_cost = acquisition_cost + operating_cost + transport_cost + inspection_cost
            expected_profit = expected_revenue - expected_cost
            margin_pct = np.where(
                expected_revenue > 0,
                (expected_profit / expected_revenue) * 100.0,
                np.nan,
            )

        with np.errstate(invalid="ignore", divide="ignore"):
            roi_pct = np.where(
                lot_cost > 0,
                ((expected_revenue - lot_cost) / lot_cost) * 100.0,
                np.nan,
            )

        out["transport_cost"] = transport_cost.round(2)
        out["platform_fee_pct"] = platform_fee_pct_series.round(4)
        out["expected_sellable_qty"] = sellable_qty
        out["expected_sell_price"] = expected_sell_price.round(2)
        out["expected_revenue"] = expected_revenue.round(2)
        out["inspection_cost"] = inspection_cost.round(2)
        out["expected_cost"] = expected_cost.round(2)
        out["expected_profit"] = expected_profit.round(2)
        out["expected_margin_pct"] = pd.Series(margin_pct, index=out.index).round(2)
        out["expected_roi_pct"] = pd.Series(roi_pct, index=out.index).round(2)

        logger.debug(
            "Profit summary: total expected profit=%.2f over %d rows",
            float(out["expected_profit"].sum(skipna=True) or 0.0),
            len(out),
        )
        return out


    def _resolve_inspection_cost(self, df: pd.DataFrame, qty: pd.Series) -> pd.Series:
        """Per-row inspection cost = qty × per-condition ₹/unit."""
        table = self.settings.inspection_cost_by_condition
        if "condition_normalized" in df.columns:
            col = df["condition_normalized"].fillna("unknown")
        else:
            col = pd.Series(["unknown"] * len(df), index=df.index)
        per_unit = col.map(lambda c: table.get(c, table["unknown"])).astype(float)
        return qty * per_unit

    def _resolve_platform_fee_pct(self, df: pd.DataFrame) -> pd.Series:
        """Return per-row platform commission fraction.

        Looks up ``PLATFORM_FEES[platform][category]`` with these fallbacks:
          1. exact (platform, category)
          2. ``PLATFORM_FEES[platform]["__default__"]``
          3. ``FALLBACK_OPERATING_COST_PCT``
        """
        def get_fee(row):
            platform = row.get("platform", self.settings.default_platform)
            if pd.isna(platform):
                platform = self.settings.default_platform

            # fallback for category
            category = row.get("category", row.get("normalized_category", "unknown"))
            if pd.isna(category):
                category = "unknown"

            platform_fees = self.settings.platform_fees.get(platform)
            if not platform_fees:
                return self.settings.fallback_operating_cost_pct

            fee = platform_fees.get(category)
            if fee is not None:
                return fee

            fee = platform_fees.get("__default__")
            if fee is not None:
                return fee

            return self.settings.fallback_operating_cost_pct

        return df.apply(get_fee, axis=1)

    def _condition_multipliers(
        self, df: pd.DataFrame
    ) -> pd.Series:
        """Return per-row ``sellable_factor`` (ceiling imposed by condition).

        Combined with the base ``expected_sellable_pct`` via ``min`` in
        :meth:`compute` to avoid double-counting.
        """
        factors = self.settings.condition_to_sell_through
        if "condition_normalized" in df.columns:
            col = df["condition_normalized"].fillna("unknown")
        else:
            col = pd.Series(["unknown"] * len(df), index=df.index)
        sellable = col.map(lambda c: factors.get(c, factors["unknown"])["sellable_factor"]).astype(float)
        return sellable

    def _resolve_transport_cost(self, df: pd.DataFrame, qty: pd.Series) -> pd.Series:
        tier_map = self.settings.category_weight_tier
        cost_map = self.settings.transport_cost_per_unit
        default_tier = self.settings.default_weight_tier
        if "category" in df.columns:
            cat = df["category"].astype("string").str.lower().fillna("unknown")
        elif "normalized_category" in df.columns:
            cat = df["normalized_category"].astype("string").str.lower().fillna("unknown")
        else:
            cat = pd.Series(["unknown"] * len(df), index=df.index)
        tier = cat.map(lambda c: tier_map.get(c, default_tier))
        per_unit = tier.map(lambda t: cost_map.get(t, cost_map[default_tier])).astype(float)
        return qty * per_unit


def compute_profitability(
    df: pd.DataFrame, settings: Settings | None = None
) -> pd.DataFrame:
    """Functional wrapper around :class:`ProfitEngine`."""
    return ProfitEngine(settings or get_settings()).compute(df)
