"""Central configuration values for the engine.

Everything that a domain expert might want to tune lives here so that
business logic stays free of magic numbers.  ``get_settings`` returns
an immutable bundle that can be passed through the pipeline.

The defaults are tuned for liquidation marketplaces (e.g. Bulk4Traders)
where ``floor_price`` represents what the buyer pays and ``mrp``
represents the brand's printed retail price.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

# --------------------------------------------------------------------------
# Scoring weights
# --------------------------------------------------------------------------

SCORING_WEIGHTS: Mapping[str, float] = {
    # Higher discount vs MRP => more room to sell profitably.
    "discount_percentage": 0.35,
    # Bigger gap between floor and observed market price => stronger margin.
    "market_gap": 0.30,
    # Demand signal proxied via category.
    "category_demand": 0.20,
    # Recognised brands move faster.
    "brand_strength": 0.15,
}

RISK_WEIGHTS: Mapping[str, float] = {
    # Missing critical fields make manual triage expensive.
    "missing_data_penalty": 0.40,
    # Low quantity is hard to absorb fixed handling cost.
    "low_quantity_penalty": 0.25,
    # Categories with high return rates / fragility.
    "category_risk": 0.20,
    # Floor price not meaningfully below MRP.
    "thin_margin_penalty": 0.15,
}

# --------------------------------------------------------------------------
# Profitability assumptions (configurable, deterministic)
# --------------------------------------------------------------------------

PROFIT_ASSUMPTIONS: Mapping[str, float] = {
    # Fraction of units we expect to actually sell.
    "expected_sellable_pct": 0.70,
    # Fraction of MRP at which we expect average sell-through.
    "expected_sell_price_vs_mrp": 0.55,
    # Operating costs as a fraction of revenue (logistics, returns, platform fees).
    "operating_cost_pct": 0.18,
    # Floor multiplier to absorb hidden costs of acquiring the lot.
    "acquisition_overhead_pct": 0.05,
}

# --------------------------------------------------------------------------
# Decision thresholds (0–100 scoring scale)
# --------------------------------------------------------------------------

DECISION_THRESHOLDS: Mapping[str, float] = {
    "buy_score_min": 60.0,
    "risk_score_max": 55.0,
    "min_expected_margin_pct": 15.0,
}

# --------------------------------------------------------------------------
# Domain heuristics (kept here so non-engineers can tweak)
# --------------------------------------------------------------------------

CATEGORY_DEMAND_SCORE: Mapping[str, float] = {
    "electronics": 90.0,
    "apparel": 75.0,
    "home": 70.0,
    "kitchen": 70.0,
    "beauty": 80.0,
    "toys": 65.0,
    "books": 40.0,
    "stationery": 35.0,
    "unknown": 50.0,
}

CATEGORY_RISK_SCORE: Mapping[str, float] = {
    "electronics": 70.0,  # high return rate, fragile
    "apparel": 45.0,      # sizing returns
    "home": 35.0,
    "kitchen": 40.0,
    "beauty": 55.0,       # expiry risk
    "toys": 50.0,
    "books": 25.0,
    "stationery": 20.0,
    "unknown": 60.0,
}

KNOWN_BRANDS: frozenset[str] = frozenset(
    {
        "samsung", "apple", "sony", "lg", "boat", "philips", "nike", "adidas",
        "puma", "levis", "hm", "zara", "prestige", "bajaj", "havells",
        "milton", "cello", "lakme", "loreal", "nivea", "dove",
    }
)


@dataclass(frozen=True)
class Settings:
    """Immutable bundle of tunables passed through the pipeline."""

    scoring_weights: Mapping[str, float] = field(default_factory=lambda: dict(SCORING_WEIGHTS))
    risk_weights: Mapping[str, float] = field(default_factory=lambda: dict(RISK_WEIGHTS))
    profit_assumptions: Mapping[str, float] = field(default_factory=lambda: dict(PROFIT_ASSUMPTIONS))
    decision_thresholds: Mapping[str, float] = field(default_factory=lambda: dict(DECISION_THRESHOLDS))
    category_demand: Mapping[str, float] = field(default_factory=lambda: dict(CATEGORY_DEMAND_SCORE))
    category_risk: Mapping[str, float] = field(default_factory=lambda: dict(CATEGORY_RISK_SCORE))
    known_brands: frozenset[str] = field(default_factory=lambda: frozenset(KNOWN_BRANDS))


def get_settings() -> Settings:
    """Return the default ``Settings`` bundle.

    Tests and notebooks may construct a ``Settings`` directly with overrides;
    production callers should always go through this function so future
    enhancements (env-var loading, YAML config) have a single seam.
    """
    return Settings()
