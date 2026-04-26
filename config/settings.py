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
    "missing_data_penalty": 0.30,
    # Low quantity is hard to absorb fixed handling cost.
    "low_quantity_penalty": 0.20,
    # Categories with high return rates / fragility.
    "category_risk": 0.15,
    # Floor price not meaningfully below MRP.
    "thin_margin_penalty": 0.10,
    # "Not Tested" / "As-Is" / refurbished items carry inspection risk.
    "condition_risk": 0.25,
}

# --------------------------------------------------------------------------
# Profitability assumptions (configurable, deterministic)
# --------------------------------------------------------------------------

PROFIT_ASSUMPTIONS: Mapping[str, float] = {
    # Fraction of units we expect to actually sell.
    "expected_sellable_pct": 0.65,
    # Fraction of MRP at which we expect average sell-through (anchor when
    # no observed market price is available).  Liquidation-grade goods
    # typically clear at ~40-50% of MRP, not retail price.
    "expected_sell_price_vs_mrp": 0.45,
    # Operating costs as a fraction of revenue (logistics, returns, platform fees).
    "operating_cost_pct": 0.25,
    # Floor multiplier to absorb hidden costs of acquiring the lot.
    "acquisition_overhead_pct": 0.05,
}

# --------------------------------------------------------------------------
# Decision thresholds (0–100 scoring scale)
# --------------------------------------------------------------------------

DECISION_THRESHOLDS: Mapping[str, float] = {
    "buy_score_min": 60.0,
    "risk_score_max": 60.0,
    "min_expected_margin_pct": 15.0,
    "min_expected_roi_pct": 25.0,
}

# --------------------------------------------------------------------------
# Condition-aware factors
#
# Liquidation manifests label item condition very differently across
# marketplaces.  We map each to:
#   - sell_price_factor : multiplier on expected sell price (vs new).
#   - sellable_factor   : multiplier on the sell-through assumption.
#   - risk_score        : 0–100 risk contribution from condition alone.
# --------------------------------------------------------------------------

CONDITION_FACTORS: Mapping[str, Mapping[str, float]] = {
    "new":          {"sell_price_factor": 1.00, "sellable_factor": 1.00, "risk_score": 10.0},
    "sealed":       {"sell_price_factor": 1.00, "sellable_factor": 1.00, "risk_score": 10.0},
    "open_box":     {"sell_price_factor": 0.85, "sellable_factor": 0.90, "risk_score": 35.0},
    "refurbished":  {"sell_price_factor": 0.75, "sellable_factor": 0.85, "risk_score": 50.0},
    "used":         {"sell_price_factor": 0.60, "sellable_factor": 0.75, "risk_score": 55.0},
    "as_is":        {"sell_price_factor": 0.55, "sellable_factor": 0.60, "risk_score": 70.0},
    "not_tested":   {"sell_price_factor": 0.65, "sellable_factor": 0.70, "risk_score": 60.0},
    "salvage":      {"sell_price_factor": 0.35, "sellable_factor": 0.40, "risk_score": 90.0},
    "unknown":      {"sell_price_factor": 0.65, "sellable_factor": 0.70, "risk_score": 60.0},
}

# --------------------------------------------------------------------------
# Domain heuristics (kept here so non-engineers can tweak)
# --------------------------------------------------------------------------

CATEGORY_DEMAND_SCORE: Mapping[str, float] = {
    "electronics": 90.0,
    "appliances": 75.0,
    "apparel": 75.0,
    "home": 70.0,
    "kitchen": 70.0,
    "kitchenware": 70.0,
    "cooking": 70.0,
    "pots_pans": 70.0,
    "beauty": 80.0,
    "toys": 65.0,
    "books": 40.0,
    "stationery": 35.0,
    "unknown": 50.0,
}

CATEGORY_RISK_SCORE: Mapping[str, float] = {
    "electronics": 70.0,  # high return rate, fragile
    "appliances": 55.0,
    "apparel": 45.0,      # sizing returns
    "home": 35.0,
    "kitchen": 40.0,
    "kitchenware": 40.0,
    "cooking": 40.0,
    "pots_pans": 35.0,
    "beauty": 55.0,       # expiry risk
    "toys": 50.0,
    "books": 25.0,
    "stationery": 20.0,
    "unknown": 60.0,
}

KNOWN_BRANDS: frozenset[str] = frozenset(
    {
        # Global tech / lifestyle
        "samsung", "apple", "sony", "lg", "boat", "philips", "nike", "adidas",
        "puma", "levis", "hm", "zara", "lakme", "loreal", "nivea", "dove",
        # Indian household / kitchen / appliances
        "prestige", "bajaj", "havells", "milton", "cello", "pigeon", "bergner",
        "butterfly", "lifelong", "solimo", "amazon_basics", "amazonbasics",
        "crystal", "tosaa", "blowhot", "longway", "surya", "stovekraft",
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
    condition_factors: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in CONDITION_FACTORS.items()}
    )
    known_brands: frozenset[str] = field(default_factory=lambda: frozenset(KNOWN_BRANDS))


def get_settings() -> Settings:
    """Return the default ``Settings`` bundle.

    Tests and notebooks may construct a ``Settings`` directly with overrides;
    production callers should always go through this function so future
    enhancements (env-var loading, YAML config) have a single seam.
    """
    return Settings()
