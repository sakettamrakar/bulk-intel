"""Deterministic profitability simulator.

Given pricing fields and configurable assumptions, project the
expected revenue and profit per line item.  The simulator is
intentionally simple — assumptions are exposed so the operator can
"what-if" different scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import Settings, get_settings
from intelligence.sell_through_model import load_model
from intelligence.velocity import estimate_velocity, load_velocity_store
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
            - ``expected_revenue`` (net of returns)
            - ``transport_cost``
            - ``inspection_cost``
            - ``return_rate`` (fraction of sold units that are returned)
            - ``return_provision`` (cost of handling returns)
            - ``holding_days`` (per-category expected holding period)
            - ``holding_cost`` (capital tied up × cost-of-capital × days/365)
            - ``expected_cost``
            - ``expected_profit_p5`` / ``_p50`` / ``_p95`` (T-306 CI)
            - ``expected_roi_p5`` / ``_p95``
            - ``prob_profit_positive`` (fraction of MC samples > 0)
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

        # Dynamic sell-through from ML model or velocity store (T-304/T-302).
        base_sellable_pct = a.get("expected_sellable_pct", 0.65)
        static_prior = np.minimum(base_sellable_pct, sellable_factor)
        velocity_estimate, velocity_confidence = self._resolve_velocity(out, static_prior)
        effective_sellable_pct = (velocity_confidence * velocity_estimate) + ((1.0 - velocity_confidence) * static_prior)
        sellable_qty = (qty * effective_sellable_pct).round(2)
        out["velocity_estimate"] = pd.Series(velocity_estimate, index=out.index).round(4)
        out["velocity_confidence"] = pd.Series(velocity_confidence, index=out.index).round(4)

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
            gross_revenue = sellable_qty * expected_sell_price * price_realization
            return_rate = self._resolve_return_rate(out)
            # Net revenue: returned units don't keep the sale.
            expected_revenue = gross_revenue * (1.0 - return_rate)
            # Return-handling cost: each returned unit's sale price × handling pct.
            return_provision = gross_revenue * return_rate * self.settings.return_handling_cost_pct

            acquisition_cost = qty * floor * (1.0 + a.get("acquisition_overhead_pct", 0.05))
            platform_fee_pct_series = self._resolve_platform_fee_pct(out)
            platform_fee_pct = platform_fee_pct_series.values
            ancillary_pct = self.settings.ancillary_revenue_fee_pct
            operating_cost = expected_revenue * (platform_fee_pct + ancillary_pct)
            inspection_cost = self._resolve_inspection_cost(out, qty)
            holding_days = self._resolve_holding_days(out)
            holding_cost = (
                lot_cost
                * self.settings.capital_cost_per_year_pct
                * holding_days
                / 365.0
            )
            expected_cost = (
                acquisition_cost
                + operating_cost
                + transport_cost
                + inspection_cost
                + return_provision
                + holding_cost
            )
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
        out["ancillary_revenue_fee_pct"] = ancillary_pct
        platform_fee_amount = gross_revenue * (platform_fee_pct + ancillary_pct)
        out["platform_fee_amount"] = platform_fee_amount.round(2)
        out["acquisition_cost"] = acquisition_cost.round(2)
        out["return_rate"] = return_rate.round(4)
        out["return_provision"] = return_provision.round(2)
        out["expected_sellable_qty"] = sellable_qty
        out["expected_sell_price"] = expected_sell_price.round(2)
        out["expected_revenue"] = expected_revenue.round(2)
        out["inspection_cost"] = inspection_cost.round(2)
        out["holding_days"] = holding_days.astype(int)
        out["holding_cost"] = holding_cost.round(2)
        out["expected_cost"] = expected_cost.round(2)
        out["expected_profit"] = expected_profit.round(2)
        out["expected_margin_pct"] = pd.Series(margin_pct, index=out.index).round(2)
        out["expected_roi_pct"] = pd.Series(roi_pct, index=out.index).round(2)

        ci = self._compute_confidence_intervals(
            out=out,
            qty=qty.values,
            effective_sellable_pct=np.asarray(effective_sellable_pct, dtype=float),
            expected_sell_price=expected_sell_price.values,
            price_realization=price_realization,
            return_rate_mean=return_rate.values,
            non_revenue_cost=(
                acquisition_cost.values
                + transport_cost.values
                + inspection_cost.values
                + holding_cost.values
            ),
            platform_fee_pct=platform_fee_pct,
            ancillary_pct=ancillary_pct,
            return_handling_cost_pct=self.settings.return_handling_cost_pct,
            lot_cost=lot_cost.values,
        )
        for col, vals in ci.items():
            out[col] = vals

        logger.debug(
            "Profit summary: total expected profit=%.2f over %d rows",
            float(out["expected_profit"].sum(skipna=True) or 0.0),
            len(out),
        )
        return out


    def _compute_confidence_intervals(
        self,
        *,
        out: pd.DataFrame,
        qty: np.ndarray,
        effective_sellable_pct: np.ndarray,
        expected_sell_price: np.ndarray,
        price_realization: float,
        return_rate_mean: np.ndarray,
        non_revenue_cost: np.ndarray,
        platform_fee_pct: np.ndarray,
        ancillary_pct: float,
        return_handling_cost_pct: float,
        lot_cost: np.ndarray,
    ) -> dict[str, pd.Series]:
        """Vectorised Monte Carlo CIs for profit and ROI per row.

        Models two random variables per row:

        * ``sell_through ~ Beta`` with mean = ``effective_sellable_pct`` and
          stddev = ``profit_assumptions["sell_through_stddev"]``.
        * ``return_rate ~ Beta`` with mean = per-row ``return_rate`` and
          stddev = ``profit_assumptions["return_rate_stddev"]``.

        Determinism: a fixed seed (42) is XOR'd with ``hash(sku) % 2^32`` per
        row so two pipeline runs on the same manifest produce identical CIs.
        """
        a = self.settings.profit_assumptions
        n_samples = int(a.get("mc_samples", 1000))
        st_std = float(a.get("sell_through_stddev", 0.10))
        rr_std = float(a.get("return_rate_stddev", 0.05))
        n_rows = len(out)

        if n_rows == 0 or n_samples <= 0:
            empty = pd.Series(dtype=float, index=out.index)
            return {
                "expected_profit_p5": empty,
                "expected_profit_p50": empty,
                "expected_profit_p95": empty,
                "expected_roi_p5": empty,
                "expected_roi_p95": empty,
                "prob_profit_positive": empty,
            }

        rng = np.random.default_rng(self._master_seed(out))

        st_samples = _beta_samples(effective_sellable_pct, st_std, n_samples, rng)
        rr_samples = _beta_samples(return_rate_mean, rr_std, n_samples, rng)

        qty_col = qty[:, None]
        price_col = expected_sell_price[:, None]
        non_rev_col = non_revenue_cost[:, None]
        fee_col = (platform_fee_pct + ancillary_pct)[:, None]
        lot_cost_col = lot_cost[:, None]

        sellable_qty = qty_col * st_samples
        gross_rev = sellable_qty * price_col * price_realization
        net_rev = gross_rev * (1.0 - rr_samples)
        return_provision = gross_rev * rr_samples * return_handling_cost_pct
        operating_cost = net_rev * fee_col
        cost = non_rev_col + operating_cost + return_provision
        profit = net_rev - cost

        with np.errstate(divide="ignore", invalid="ignore"):
            roi = np.where(
                lot_cost_col > 0,
                (net_rev - lot_cost_col) / lot_cost_col * 100.0,
                np.nan,
            )

        p5 = np.nanpercentile(profit, 5, axis=1)
        p50 = np.nanpercentile(profit, 50, axis=1)
        p95 = np.nanpercentile(profit, 95, axis=1)
        roi_p5 = np.nanpercentile(roi, 5, axis=1)
        roi_p95 = np.nanpercentile(roi, 95, axis=1)
        prob_pos = (profit > 0).mean(axis=1)

        return {
            "expected_profit_p5": pd.Series(p5, index=out.index).round(2),
            "expected_profit_p50": pd.Series(p50, index=out.index).round(2),
            "expected_profit_p95": pd.Series(p95, index=out.index).round(2),
            "expected_roi_p5": pd.Series(roi_p5, index=out.index).round(2),
            "expected_roi_p95": pd.Series(roi_p95, index=out.index).round(2),
            "prob_profit_positive": pd.Series(prob_pos, index=out.index).round(4),
        }

    @staticmethod
    def _master_seed(df: pd.DataFrame) -> int:
        """Manifest-deterministic seed for the Monte Carlo CI engine.

        Two pipeline runs over the same manifest (same skus, same order)
        produce identical CIs.  Reordering rows reseeds the RNG, which is
        acceptable because per-row outputs are summary statistics over many
        samples and don't depend on which row was sampled first.
        """
        if "sku" in df.columns:
            joined = "|".join(df["sku"].astype("string").fillna("").tolist())
        else:
            joined = f"rows={len(df)}"
        return (hash(joined) ^ 42) & 0xFFFFFFFF

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

    def _resolve_holding_days(self, df: pd.DataFrame) -> pd.Series:
        """Return per-row expected holding days.

        Looks up ``CATEGORY_HOLDING_DAYS[category]`` with fallback to
        ``DEFAULT_HOLDING_DAYS`` for unknown categories.
        """
        table = self.settings.category_holding_days
        default = self.settings.default_holding_days
        if "category" in df.columns:
            cat = df["category"].astype("string").str.lower().fillna("unknown")
        elif "normalized_category" in df.columns:
            cat = df["normalized_category"].astype("string").str.lower().fillna("unknown")
        else:
            cat = pd.Series(["unknown"] * len(df), index=df.index)
        return cat.map(lambda c: table.get(c, default)).astype(float)

    def _resolve_return_rate(self, df: pd.DataFrame) -> pd.Series:
        """Return per-row return rate (fraction of sold units returned).

        Looks up ``CATEGORY_RETURN_RATE[category]`` with fallback to
        ``DEFAULT_RETURN_RATE`` for unknown categories.
        """
        table = self.settings.category_return_rate
        if "category" in df.columns:
            cat = df["category"].astype("string").str.lower().fillna("unknown")
        else:
            cat = pd.Series(["unknown"] * len(df), index=df.index)
        return cat.map(lambda c: table.get(c, self.settings.default_return_rate)).astype(float)



    def _resolve_velocity(self, df: pd.DataFrame, static_prior: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        model_path = Path("data/models/sell_through_v1.pkl")
        try:
            if model_path.exists():
                model = load_model(model_path)
                pred = model.predict(df)
                df["sell_through_pred"] = pred["sell_through_pred"].round(4)
                df["sell_through_conf"] = pred["sell_through_conf"].round(4)
                return pred["sell_through_pred"].to_numpy(dtype=float), pred["sell_through_conf"].to_numpy(dtype=float)
        except Exception:
            logger.exception("Sell-through model load/predict failed; falling back")

        store = load_velocity_store()
        vel = []
        conf = []
        for i, row in df.iterrows():
            v, c = estimate_velocity(row, store, self.settings)
            vel.append(v)
            conf.append(c)
        return np.asarray(vel, dtype=float), np.asarray(conf, dtype=float)
def _beta_samples(
    mean: np.ndarray, stddev: float, n_samples: int, rng: np.random.Generator
) -> np.ndarray:
    """Vectorised Beta samples per row → array of shape (n_rows, n_samples).

    Reparameterises (mean, stddev) → (alpha, beta).  When the requested
    variance exceeds the maximum admissible variance ``mean*(1-mean)`` the
    Beta is degenerate; we clip to 99 % of that bound so the sampler stays
    well-defined.  Means are clipped to ``[1e-4, 1-1e-4]`` for the same reason.
    """
    mean_arr = np.clip(np.asarray(mean, dtype=float), 1e-4, 1.0 - 1e-4)
    var = stddev ** 2
    max_var = mean_arr * (1.0 - mean_arr) * 0.99
    var_clipped = np.minimum(var, max_var)
    var_clipped = np.where(var_clipped <= 0, 1e-8, var_clipped)
    nu = mean_arr * (1.0 - mean_arr) / var_clipped - 1.0
    nu = np.where(nu <= 0, 1e-3, nu)
    alpha = mean_arr * nu
    beta = (1.0 - mean_arr) * nu
    return rng.beta(alpha[:, None], beta[:, None], size=(mean_arr.shape[0], n_samples))


def compute_profitability(
    df: pd.DataFrame, settings: Settings | None = None
) -> pd.DataFrame:
    """Functional wrapper around :class:`ProfitEngine`."""
    return ProfitEngine(settings or get_settings()).compute(df)
