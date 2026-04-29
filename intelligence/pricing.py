"""Compute deterministic pricing metrics for the manifest.

These metrics are pure functions of the existing columns; downstream
scoring and decisioning consumes them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from utils.logging import get_logger

logger = get_logger(__name__)

from config.settings import Settings, get_settings

@dataclass(frozen=True)
class PricingEngine:
    """Vectorised pricing-metric calculator.
    
    Depends on Settings for PRICING_STRATEGY.
    """
    settings: Settings = field(default_factory=get_settings)

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add pricing metrics to ``df`` and return a new ``DataFrame``.

        New columns:
            - ``discount_percentage``: ``1 - floor_price / mrp`` (0–100).
            - ``price_ratio``: ``floor_price / mrp`` (0–1).
            - ``market_gap``: ``(real_price - floor_price) / real_price``.
            - ``wholesale_gap``: ``(wholesale_price - floor_price) / wholesale_price``.
        """
        logger.info("Computing pricing metrics for %d rows", len(df))
        out = df.copy()

        floor = pd.to_numeric(out["floor_price"], errors="coerce")
        mrp = pd.to_numeric(out["mrp"], errors="coerce")
        amazon = pd.to_numeric(out.get("amazon_price"), errors="coerce")
        wholesale = pd.to_numeric(out.get("wholesale_price"), errors="coerce")

        fallback_pct = self.settings.pricing_strategy.get("fallback_pct_of_mrp", 0.45)
        fallback_category_price = mrp * fallback_pct

        # Pricing strategy
        # real_price = min(amazon_price * discount, wholesale_price (if available), fallback_category_price)

        real_price = fallback_category_price.copy()

        # apply amazon * discount
        amazon_discount = self.settings.pricing_strategy.get("amazon_discount_factor", 0.70)
        amazon_discounted = amazon * amazon_discount
        amazon_discounted = pd.Series(amazon_discounted, index=out.index)
        amazon_notna = amazon_discounted.notna()
        mask_amazon = amazon_notna & (amazon_discounted < real_price.fillna(np.inf))
        real_price.loc[mask_amazon] = amazon_discounted.loc[mask_amazon]

        # apply wholesale
        wholesale = pd.Series(wholesale, index=out.index)
        wholesale_notna = wholesale.notna()
        mask_wholesale = wholesale_notna & (wholesale < real_price.fillna(np.inf))
        real_price.loc[mask_wholesale] = wholesale.loc[mask_wholesale]

        out["real_price"] = real_price

        with np.errstate(divide="ignore", invalid="ignore"):
            price_ratio = floor / mrp
            discount = (1.0 - price_ratio) * 100.0
            market_gap = (real_price - floor) / real_price * 100.0
            wholesale_gap = (wholesale - floor) / wholesale * 100.0

        out["price_ratio"] = price_ratio.round(4)
        out["discount_percentage"] = discount.round(2)
        out["market_gap"] = market_gap.round(2)
        out["wholesale_gap"] = wholesale_gap.round(2)

        # Negative gaps are valid signals (we'd be buying ABOVE market) but
        # extreme noise from bad data should be clipped to keep scoring stable.
        out["discount_percentage"] = out["discount_percentage"].clip(lower=-100, upper=100)
        out["market_gap"] = out["market_gap"].clip(lower=-100, upper=100)
        out["wholesale_gap"] = out["wholesale_gap"].clip(lower=-100, upper=100)

        logger.debug(
            "Pricing summary: avg_discount=%.2f%%, avg_market_gap=%.2f%%",
            float(out["discount_percentage"].mean(skipna=True) or 0.0),
            float(out["market_gap"].mean(skipna=True) or 0.0),
        )
        return out


def compute_pricing_metrics(df: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Functional wrapper around :class:`PricingEngine`."""
    return PricingEngine(settings=settings or get_settings()).compute(df)
