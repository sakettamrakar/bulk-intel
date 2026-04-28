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
    "discount_percentage": 0.25,
    # Bigger gap between floor and observed market price => stronger margin.
    "market_gap": 0.20,
    # Demand signal proxied via category.
    "demand_score": 0.15,
    # Category liquidity (how fast things move).
    "category_liquidity": 0.15,
    # Recognised brands move faster.
    "brand_score": 0.15,
    # Higher price items typically have higher absolute margins.
    "price_band": 0.10,
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
    # Base/cap sell-through.  Combined with the per-condition
    # ``sellable_factor`` via ``min(base, condition_factor)`` so the more
    # binding constraint wins (no multiplicative double-counting).
    # Even brand-new liquidation inventory rarely clears 100 %; this caps
    # the optimistic end of the distribution.
    "expected_sellable_pct": 0.65,
    # Fraction of MRP at which we expect average sell-through (anchor when
    # no observed market price is available).  Liquidation-grade goods
    # typically clear at ~40-50% of MRP, not retail price.
    "expected_sell_price_vs_mrp": 0.45,
    # Optional extra haircut on revenue to model clearance/promo erosion.
    # Default 1.0 (off) — the realistic-vs-MRP discount is already encoded
    # in ``real_price`` from intelligence/pricing.py.  Drop below 1.0 when
    # modelling end-of-life inventory that has to clear on a deadline.
    "price_realization_factor": 1.0,
    # Floor multiplier to absorb hidden costs of acquiring the lot.
    "acquisition_overhead_pct": 0.05,
}

# --------------------------------------------------------------------------
# Inspection cost
# --------------------------------------------------------------------------

# ₹/unit cost of inspecting and testing a unit before listing.
# Only applied to conditions where the platform listing requires a tested
# product. Values are rough operator estimates; tune per category and labour cost.
INSPECTION_COST_BY_CONDITION: Mapping[str, float] = {
    "tested": 0.0,
    "not_tested": 50.0,
    "unknown": 50.0,
}

# --------------------------------------------------------------------------
# Decision thresholds (0–100 scoring scale)
# --------------------------------------------------------------------------

CONFIDENCE_THRESHOLD_FOR_BUY: float = 0.6

DECISION_THRESHOLDS: Mapping[str, float] = {
    "buy_score_min": 60.0,
    "risk_score_max": 60.0,
    "min_expected_margin_pct": 15.0,
    "min_expected_roi_pct": 25.0,
    "min_buy_match_confidence": CONFIDENCE_THRESHOLD_FOR_BUY,
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

CONDITION_TO_SELL_THROUGH: Mapping[str, Mapping[str, float]] = {
    "new":         {"sellable_factor": 1.00, "risk_score": 10.0},
    "like_new":    {"sellable_factor": 0.90, "risk_score": 25.0},
    "used_good":   {"sellable_factor": 0.75, "risk_score": 40.0},
    "used_fair":   {"sellable_factor": 0.60, "risk_score": 60.0},
    # "Not Tested" Amazon-return inventory is mostly functional after
    # cleaning/inspection (buyer's-remorse returns dominate over defects).
    # Sits between used_good and used_fair; risk reflects inspection cost.
    "not_tested":  {"sellable_factor": 0.65, "risk_score": 60.0},
    "defective":   {"sellable_factor": 0.20, "risk_score": 90.0},
    "unknown":     {"sellable_factor": 0.50, "risk_score": 60.0},
}

# --------------------------------------------------------------------------
# Domain heuristics (kept here so non-engineers can tweak)
# --------------------------------------------------------------------------

DEMAND_SCORE: Mapping[str, float] = {
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

CATEGORY_LIQUIDITY_SCORE: Mapping[str, float] = {
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

# --------------------------------------------------------------------------
# Transport Cost
# --------------------------------------------------------------------------

# Maps each canonical category to a coarse weight tier. Drives
# TRANSPORT_COST_PER_UNIT below. Categories not listed default to "medium".
CATEGORY_WEIGHT_TIER: Mapping[str, str] = {
    "stationery":   "small",
    "books":        "small",
    "beauty":       "small",
    "apparel":      "small",
    "toys":         "medium",
    "electronics":  "medium",
    "home":         "medium",
    "kitchen":      "bulky",
    "kitchenware":  "bulky",
    "appliances":   "bulky",
    "unknown":      "medium",
    "digital":      "weightless",
}

# ₹/unit transport (inbound from manifest origin + outbound to customer/FBA).
# Tier values are ballpark India-tier-1-to-tier-2 rates; tune per region.
TRANSPORT_COST_PER_UNIT: Mapping[str, float] = {
    "weightless": 0.0,
    "small":   25.0,
    "medium":  60.0,
    "bulky":  150.0,
}

DEFAULT_WEIGHT_TIER: str = "medium"



# --------------------------------------------------------------------------
# Platform Fees
# --------------------------------------------------------------------------

# Per-platform, per-category fee as a fraction of revenue.
# Sources cited inline; verify against current rate cards quarterly.
#
# Each entry is the *all-in* commission an operator pays the platform on
# revenue (commission + closing fee + payment-gateway + platform-specific
# fulfilment if not separately modelled).  GST on commission is included.
#
# When a (platform, category) pair is missing, fall back to
# PLATFORM_FEES[platform]["__default__"], then to FALLBACK_OPERATING_COST_PCT.
PLATFORM_FEES: Mapping[str, Mapping[str, float]] = {
    "amazon": {
        # Source: Amazon India Seller Central Fee Schedule (Q1 2026).
        "electronics":  0.085,
        "appliances":   0.115,
        "kitchen":      0.155,
        "kitchenware":  0.155,
        "home":         0.165,
        "apparel":      0.175,
        "beauty":       0.195,
        "toys":         0.155,
        "books":        0.075,
        "stationery":   0.095,
        "__default__":  0.155,
    },
    "flipkart": {
        # Source: Flipkart Seller Hub India (Q1 2026).
        "electronics":  0.090,
        "appliances":   0.110,
        "kitchen":      0.140,
        "kitchenware":  0.140,
        "home":         0.155,
        "apparel":      0.180,
        "beauty":       0.210,
        "toys":         0.150,
        "books":        0.060,
        "stationery":   0.085,
        "__default__":  0.150,
    },
    "meesho": {
        # Source: Meesho Supplier Panel (Q1 2026); flat 0% commission for many
        # categories, monetisation via shipping + ads.  Approximate effective rate.
        "electronics":  0.040,
        "appliances":   0.040,
        "kitchen":      0.030,
        "kitchenware":  0.030,
        "home":         0.030,
        "apparel":      0.020,
        "beauty":       0.030,
        "toys":         0.030,
        "books":        0.020,
        "stationery":   0.020,
        "__default__":  0.030,
    },
    "b2b": {
        # B2B / kabadi reseller channel — operator just absorbs a flat handling fee.
        "__default__":  0.080,
    },
}

DEFAULT_PLATFORM: str = "amazon"

# Last-resort fallback used only when both platform and category are unknown.
# Kept deliberately conservative.
FALLBACK_OPERATING_COST_PCT: float = 0.18

# Payment-gateway / closing-fee / packaging delta over and above the
# platform commission.  Empirically ~3-6 % of revenue across platforms.
ANCILLARY_REVENUE_FEE_PCT: float = 0.04

@dataclass(frozen=True)
class Settings:
    """Immutable bundle of tunables passed through the pipeline."""

    platform_fees: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in PLATFORM_FEES.items()}
    )
    default_platform: str = DEFAULT_PLATFORM
    fallback_operating_cost_pct: float = FALLBACK_OPERATING_COST_PCT
    ancillary_revenue_fee_pct: float = ANCILLARY_REVENUE_FEE_PCT

    scoring_weights: Mapping[str, float] = field(default_factory=lambda: dict(SCORING_WEIGHTS))
    risk_weights: Mapping[str, float] = field(default_factory=lambda: dict(RISK_WEIGHTS))
    profit_assumptions: Mapping[str, float] = field(default_factory=lambda: dict(PROFIT_ASSUMPTIONS))
    decision_thresholds: Mapping[str, float] = field(default_factory=lambda: dict(DECISION_THRESHOLDS))
    demand_score: Mapping[str, float] = field(default_factory=lambda: dict(DEMAND_SCORE))
    category_liquidity: Mapping[str, float] = field(default_factory=lambda: dict(CATEGORY_LIQUIDITY_SCORE))
    category_risk: Mapping[str, float] = field(default_factory=lambda: dict(CATEGORY_RISK_SCORE))
    condition_to_sell_through: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in CONDITION_TO_SELL_THROUGH.items()}
    )
    known_brands: frozenset[str] = field(default_factory=lambda: frozenset(KNOWN_BRANDS))
    category_weight_tier: Mapping[str, str] = field(default_factory=lambda: dict(CATEGORY_WEIGHT_TIER))
    transport_cost_per_unit: Mapping[str, float] = field(default_factory=lambda: dict(TRANSPORT_COST_PER_UNIT))
    default_weight_tier: str = "medium"
    inspection_cost_by_condition: Mapping[str, float] = field(default_factory=lambda: dict(INSPECTION_COST_BY_CONDITION))


def get_settings() -> Settings:
    """Return the default ``Settings`` bundle.

    Tests and notebooks may construct a ``Settings`` directly with overrides;
    production callers should always go through this function so future
    enhancements (env-var loading, YAML config) have a single seam.
    """
    return Settings()
