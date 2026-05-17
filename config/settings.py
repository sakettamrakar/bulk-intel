"""Central configuration values for the engine.

Everything that a domain expert might want to tune lives here so that
business logic stays free of magic numbers.  ``get_settings`` returns
an immutable bundle that can be passed through the pipeline.

The defaults are tuned for liquidation marketplaces (e.g. Bulk4Traders)
where ``floor_price`` represents what the buyer pays and ``mrp``
represents the brand's printed retail price.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

_log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Scoring weights
# --------------------------------------------------------------------------

SCORING_WEIGHTS: Mapping[str, float] = {
    # Higher discount vs MRP => more room to sell profitably.
    "discount_percentage": 0.20,
    # Bigger gap between floor and observed market price => stronger margin.
    "market_gap": 0.15,
    # Demand signal proxied via category.
    "demand_score": 0.10,
    # Category liquidity (how fast things move).
    "category_liquidity": 0.10,
    # Recognised brands move faster.
    "brand_score": 0.10,
    # Higher price items typically have higher absolute margins.
    "price_band": 0.10,
    # Strongest single demand signal.
    "bsr": 0.25,
}

# BSR bands → 0-100 sellability bonus.  Lower BSR (top of category) = higher
# bonus.  Buckets are per top-level category since a BSR of 50,000 means very
# different things in "Kitchen" vs "Books".
BSR_BUCKETS: Mapping[str, list[tuple[int, float]]] = {
    "electronics": [(1000, 95), (10000, 80), (50000, 60), (200000, 40), (1_000_000, 25)],
    "kitchen":     [(500,  95), (5000,  80), (25000, 60), (100_000, 40), (500_000, 25)],
    "apparel":     [(2000, 95), (20000, 80), (100_000, 60), (500_000, 40), (2_000_000, 25)],
    "_default":    [(1000, 95), (10000, 80), (50000, 60), (200000, 40), (1_000_000, 25)],
}

# Default sellability bonus when no BSR is available.
DEFAULT_BSR_SCORE: float = 50.0

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

PRICING_STRATEGY: Mapping[str, float] = {
    # Liquidation buyers can't realise the full Amazon listed price; this is
    # the conservative discount applied to amazon_price before it competes
    # with the wholesale and fallback anchors in pricing.py.
    "amazon_discount_factor": 0.70,
    # When neither amazon nor wholesale price is available, anchor real_price
    # at this fraction of MRP.
    "fallback_pct_of_mrp": 0.45,
}

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
    # Stddev of the per-row sell-through fraction used by the Monte Carlo
    # confidence-interval engine (T-306).  Operator-judgement default until
    # T-205/T-302 measure realised variance.
    "sell_through_stddev": 0.10,
    # Stddev of the per-row return rate used by the Monte Carlo CI engine.
    "return_rate_stddev": 0.05,
    # Monte Carlo sample count per row.  1000 is the spec default; reduce to
    # 500 if the runtime cost is unacceptable on very large manifests.
    "mc_samples": 1000,
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
# Homogeneity and product matching
# --------------------------------------------------------------------------

HOMOGENEITY_FILLER_TOKENS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "for", "with", "and", "or",
    "new", "open", "box", "lot", "pack", "set",
    "black", "white", "blue", "red", "grey", "gray", "silver",
    "small", "medium", "large", "xl", "xxl",
    "ml", "g", "kg", "cm", "mm", "inch", "in",
})

HOMOGENEITY_MODEL_TOKEN_PATTERN: str = (
    r"\b(?:[A-Z]{1,5}-?\d{2,6}[A-Z0-9-]*|\d{2,3}[A-Z]{2,5}|[BX]0[A-Z0-9]{8})\b"
)

HOMOGENEITY_SKU_FUZZ_CUTOFF: int = 88

HOMOGENEITY_THRESHOLDS: Mapping[str, float] = {
    "highly_homogeneous": 0.85,
    "moderately_homogeneous": 0.60,
    "mixed": 0.30,
}

MATCH_TOKEN_WEIGHTS: Mapping[str, float] = {
    "model": 0.50,
    "brand": 0.30,
    "product_type": 0.15,
    "extra_tokens": 0.05,
}

MATCH_ACCEPT_THRESHOLD: float = 0.80
MATCH_WEAK_THRESHOLD: float = 0.65
MATCH_BRAND_MISMATCH_OVERRIDE: float = 0.92

# --------------------------------------------------------------------------
# Optional structured SERP price provider
# --------------------------------------------------------------------------

SERP_PROVIDER_ENABLED: bool = False
SERP_API_KEY_ENV: str = "SERPAPI_API_KEY"
SERP_BACKEND: str = "serpapi"
SERP_RATE_LIMIT_PER_SEC: float = 1.0
SERP_TIMEOUT_S: float = 8.0
SERP_MAX_RETRIES: int = 3
SERP_CACHE_PATH: str = ".cache/serp_cache.sqlite"
SERP_CACHE_TTL_HOURS: int = 24 * 7
SERP_RESULTS_PER_QUERY: int = 5
SERP_ALLOW_WEAK_FALLBACK: bool = False

SEARCH_SIGNATURE_DROP_TOKENS: frozenset[str] = frozenset({
    "black", "white", "blue", "red", "grey", "gray", "silver", "gold",
    "rose", "rosegold", "green", "yellow", "pink", "orange", "purple",
    "brown", "beige", "cream", "ivory", "navy",
    "small", "medium", "large", "xs", "s", "m", "l", "xl", "xxl",
    "pack", "packs", "set", "sets", "piece", "pieces", "pcs",
    "combo", "kit", "left", "right", "wireless", "bluetooth",
})
CANONICAL_TITLE_MAX_LEN: int = 80
MIN_GROUP_QUANTITY_FOR_SEARCH: int = 2

SERP_PREVIEW_LIMIT: int = 10
SERP_STATE_PATH: str = ".cache/serp_state.json"
SERP_VALUE_COVERAGE_TARGET: float = 0.80

PLAYWRIGHT_FALLBACK_ENABLED: bool = False
PLAYWRIGHT_HEADLESS: bool = False
PLAYWRIGHT_MAX_QUERIES_PER_RUN: int = 10
PLAYWRIGHT_RATE_LIMIT_SECONDS: float = 8.0
PLAYWRIGHT_RATE_LIMIT_JITTER_SECONDS: float = 2.0
PLAYWRIGHT_PROFILE_PATH: str = ".cache/playwright/profile"
PLAYWRIGHT_PAGE_TIMEOUT_S: float = 15.0
PLAYWRIGHT_CAPTCHA_TIMEOUT_S: float = 180.0

# --------------------------------------------------------------------------
# Domain heuristics (kept here so non-engineers can tweak)
# --------------------------------------------------------------------------

# Demand = "How many people want this category?"
# Influenced by search volume, total transactions. High demand does NOT
# guarantee fast inventory clearance if seller density is too high.
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

# Category liquidity = "How fast can a single seller's inventory clear?"
# Influenced by seller density and marketplace velocity. For example,
# electronics has very high demand but ~thousands of competing sellers,
# resulting in lower liquidity per seller.
CATEGORY_LIQUIDITY_SCORE: Mapping[str, float] = {
    "electronics": 40.0,
    "appliances": 55.0,
    "apparel": 75.0,
    "home": 65.0,
    "kitchen": 55.0,
    "kitchenware": 55.0,
    "cooking": 55.0,
    "pots_pans": 60.0,
    "beauty": 55.0,
    "toys": 70.0,
    "books": 60.0,
    "stationery": 50.0,
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

# Curated list of brands that move noticeably faster on Indian marketplaces.
# Maintained approx. April 2026.
KNOWN_BRANDS: frozenset[str] = frozenset({
    # ---------- Electronics & mobile ----------
    "samsung", "apple", "sony", "lg", "boat", "philips", "realme", "xiaomi",
    "mi", "redmi", "oneplus", "oppo", "vivo", "lenovo", "dell", "hp",
    "asus", "acer", "jbl", "noise", "boult", "nothing", "fastrack", "fire-boltt",
    "pebble", "ambrane", "ptron", "mivi", "zebronics", "iball", "micromax",
    "lava", "intex", "syska", "portronics", "bose", "sennheiser", "marshall",
    "jabra", "skullcandy", "infinity", "anker", "spigen", "belkin", "dji",
    "gopro", "canon", "nikon", "fujifilm", "panasonic", "hitachi", "daikin",
    "voltas", "bluestar", "mitsubishi", "o_general", "carrier", "toshiba",

    # ---------- Home appliances & kitchen ----------
    "prestige", "bajaj", "havells", "milton", "cello", "pigeon", "bergner",
    "butterfly", "lifelong", "solimo", "amazon_basics", "amazonbasics",
    "crystal", "tosaa", "blowhot", "longway", "surya", "stovekraft",
    "wonderchef", "whirlpool", "lloyd", "haier", "godrej", "bosch",
    "siemens", "croma", "reliance_digital", "kent", "aquaguard",
    "pureit", "livpure", "eureka_forbes", "agaro", "inalsa", "morphy_richards",
    "kenstar", "usha", "crompton", "orient", "v_guard", "vguard", "ifb",
    "kutchina", "glen", "faber", "hindware", "sunflame", "elica", "borosil",
    "tupperware", "la_opala", "treo", "nayasa", "signoraware", "polyset",
    "jaypee", "supreme", "nilkamal", "cello_furniture",

    # ---------- Apparel & footwear ----------
    "nike", "adidas", "puma", "levis", "hm", "zara", "uniqlo", "decathlon",
    "titan", "fossil", "casio", "skagen", "tommy_hilfiger", "us_polo", "us_polo_assn",
    "allen_solly", "louis_philippe", "van_heusen", "peter_england", "raymond",
    "bata", "woodland", "skechers", "reebok", "asics", "fila", "campus",
    "metro_shoes", "liberty", "mochi", "red_tape", "sparx", "lancer",
    "paragon", "relaxo", "flite", "bahamas", "crocs", "biba", "w_for_woman",
    "aurelia", "global_desi", "imara", "soch", "fabindia", "max",
    "pantaloons", "lifestyle", "shoppers_stop", "trends", "zudio",
    "h_and_m", "pepe_jeans", "wrangler", "lee", "flying_machine", "spykar",
    "numero_uno", "mufti", "killer", "jack_and_jones", "madame", "only",
    "vero_moda", "forever_21", "marks_and_spencer",

    # ---------- Beauty & personal care ----------
    "lakme", "loreal", "maybelline", "nivea", "dove", "ponds", "olay",
    "neutrogena", "the_body_shop", "mamaearth", "myglamm", "plum",
    "biotique", "himalaya", "wow", "minimalist", "the_derma_co",
    "garnier", "cetaphil", "pantene", "tresemme", "head_shoulders",
    "clinic_plus", "sunsilk", "matrix", "schwarzkopf", "wella", "revlon",
    "mac", "sugar", "faces_canada", "colorbar", "swiss_beauty", "insight",
    "mcaffeine", "dot_and_key", "earth_rhythm", "skinn", "engaging",
    "fogg", "wild_stone", "denver", "nivea_men", "gillette", "park_avenue",
    "axe", "old_spice", "beardo", "ustaad", "bombay_shaving_company",
    "himalaya_men", "vaseline", "boroline", "vicco", "patanjali",

    # ---------- Home & lifestyle ----------
    "wakefit", "the_sleep_company", "duroflex", "sleepyhead", "centuary",
    "ikea", "urban_ladder", "pepperfry", "home_centre",
    "kurlon", "sleepwell", "peps", "spaces", "bombay_dyeing", "portico",
    "d_decor", "trident", "welspun", "story_at_home", "haus_and_kinder",

    # ---------- Toys & kids ----------
    "lego", "hamleys", "fisher_price", "mattel", "hasbro", "funskool",
    "hot_wheels", "barbie", "nerf", "play_doh", "chicco", "mee_mee",
    "luvlap", "r_for_rabbit", "firstcry", "babyhug", "mothercare",
    "johnsons_baby", "sebamed", "pampers", "mamy_poko", "huggies",

    # ---------- Books & stationery ----------
    "penguin", "harpercollins", "scholastic", "classmate", "navneet",
    "camel", "faber_castell", "pilot", "uni_ball", "reynolds",
    "cello_pens", "parker", "waterman", "cross", "luxor",
    "camlin", "doms", "apsara", "nataraj", "kangaro",
})

# Source brand string (lowercased, alpha-num + underscore) → canonical brand.
# Apply *after* lowercasing, before known-brand lookup.
BRAND_ALIASES: Mapping[str, str] = {
    "amazon_brand_solimo":  "solimo",
    "amazon_basics":        "amazonbasics",
    "amazon_brand":         "amazonbasics",
    "amazonbasics_in":      "amazonbasics",
    "stovekraft_pigeon":    "pigeon",
    "pigeon_by_stovekraft": "pigeon",
    "tommy":                "tommy_hilfiger",
    "us_polo_assn":         "us_polo",
    "uspolo_assn":          "us_polo",
    "h_and_m":              "hm",
    "h_m":                  "hm",
    "levis_strauss":        "levis",
    "v_guard":              "vguard",
    "fab_india":            "fabindia"
}

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
# Channel Routing
# --------------------------------------------------------------------------

CHANNEL_ROUTING_RULES: tuple[Mapping[str, object], ...] = (
    {"condition": {"condition_normalized": ("defective", "salvage")}, "platform": "b2b"},
    {"condition": {"category": "electronics", "brand_known": True, "price_band": ("MID", "HIGH")}, "platform": "amazon"},
    {"condition": {"category": "electronics"}, "platform": "flipkart"},
    {"condition": {"category": ("apparel", "home")}, "platform": "meesho"},
    {"condition": {"category": "beauty"}, "platform": "amazon"},
    {"condition": {"category": ("kitchen", "kitchenware", "appliances")}, "platform": "flipkart"},
    {"condition": {}, "platform": "amazon"},
)

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

# --------------------------------------------------------------------------
# Return Rate Model
# --------------------------------------------------------------------------

# Per-category fraction of sold units that are returned.  Returned units
# generate full reverse-logistics cost and (often) cannot be re-listed
# at full price; we model both effects below.
# Sources: Amazon India return policies + operator experience (Q1 2026).
CATEGORY_RETURN_RATE: Mapping[str, float] = {
    "electronics":  0.13,
    "appliances":   0.10,
    "kitchen":      0.07,
    "kitchenware":  0.07,
    "home":         0.06,
    "apparel":      0.22,    # sizing + colour mismatch dominate
    "beauty":       0.10,
    "toys":         0.08,
    "books":        0.04,
    "stationery":   0.03,
    "unknown":      0.10,
}

# Cost of handling a return as a fraction of the unit sale price
# (reverse shipping + restocking + partial write-off blended).
# Empirically ~30% across platforms based on operator experience.
RETURN_HANDLING_COST_PCT: float = 0.30

# Fallback return rate for unknown categories.
DEFAULT_RETURN_RATE: float = 0.10

# --------------------------------------------------------------------------
# Capital cost / holding period (T-303)
# --------------------------------------------------------------------------

# Expected days of inventory holding from purchase to last unit cleared.
# Pulled from operator's category-specific historical clearance curves.
# Tune annually as marketplace velocity shifts.
CATEGORY_HOLDING_DAYS: Mapping[str, int] = {
    "electronics":  60,
    "appliances":   75,
    "kitchen":      90,
    "kitchenware":  90,
    "home":         90,
    "apparel":     120,    # seasonal, slow
    "beauty":       60,
    "toys":        100,
    "books":       180,    # long tail
    "stationery":  120,
    "unknown":      90,
}

# Annualised cost of capital + storage (warehouse rent + WIP financing).
# Basis: ~6 % RBI repo + ~12 % blended warehouse rent / WIP financing for a
# typical Indian SMB liquidator.  Self-funded operators may use 10 %; leveraged
# operators 20 %+.  Tune per operator.
CAPITAL_COST_PER_YEAR_PCT: float = 0.18

DEFAULT_HOLDING_DAYS: int = 90

@dataclass(frozen=True)
class Settings:
    """Immutable bundle of tunables passed through the pipeline."""

    platform_fees: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in PLATFORM_FEES.items()}
    )
    default_platform: str = DEFAULT_PLATFORM
    fallback_operating_cost_pct: float = FALLBACK_OPERATING_COST_PCT
    ancillary_revenue_fee_pct: float = ANCILLARY_REVENUE_FEE_PCT

    pricing_strategy: Mapping[str, float] = field(default_factory=lambda: dict(PRICING_STRATEGY))
    scoring_weights: Mapping[str, float] = field(default_factory=lambda: dict(SCORING_WEIGHTS))
    bsr_buckets: Mapping[str, list[tuple[int, float]]] = field(
        default_factory=lambda: {k: list(v) for k, v in BSR_BUCKETS.items()}
    )
    default_bsr_score: float = DEFAULT_BSR_SCORE
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
    category_return_rate: Mapping[str, float] = field(default_factory=lambda: dict(CATEGORY_RETURN_RATE))
    return_handling_cost_pct: float = RETURN_HANDLING_COST_PCT
    default_return_rate: float = DEFAULT_RETURN_RATE
    category_holding_days: Mapping[str, int] = field(
        default_factory=lambda: dict(CATEGORY_HOLDING_DAYS)
    )
    capital_cost_per_year_pct: float = CAPITAL_COST_PER_YEAR_PCT
    default_holding_days: int = DEFAULT_HOLDING_DAYS
    channel_routing_rules: tuple[Mapping[str, object], ...] = field(
        default_factory=lambda: tuple(CHANNEL_ROUTING_RULES)
    )
    brand_aliases: Mapping[str, str] = field(default_factory=lambda: dict(BRAND_ALIASES))
    homogeneity_filler_tokens: frozenset[str] = field(default_factory=lambda: frozenset(HOMOGENEITY_FILLER_TOKENS))
    homogeneity_model_token_pattern: str = HOMOGENEITY_MODEL_TOKEN_PATTERN
    homogeneity_sku_fuzz_cutoff: int = HOMOGENEITY_SKU_FUZZ_CUTOFF
    homogeneity_thresholds: Mapping[str, float] = field(default_factory=lambda: dict(HOMOGENEITY_THRESHOLDS))
    match_token_weights: Mapping[str, float] = field(default_factory=lambda: dict(MATCH_TOKEN_WEIGHTS))
    match_accept_threshold: float = MATCH_ACCEPT_THRESHOLD
    match_weak_threshold: float = MATCH_WEAK_THRESHOLD
    match_brand_mismatch_override: float = MATCH_BRAND_MISMATCH_OVERRIDE
    serp_provider_enabled: bool = SERP_PROVIDER_ENABLED
    serp_api_key_env: str = SERP_API_KEY_ENV
    serp_backend: str = SERP_BACKEND
    serp_rate_limit_per_sec: float = SERP_RATE_LIMIT_PER_SEC
    serp_timeout_s: float = SERP_TIMEOUT_S
    serp_max_retries: int = SERP_MAX_RETRIES
    serp_cache_path: str = SERP_CACHE_PATH
    serp_cache_ttl_hours: int = SERP_CACHE_TTL_HOURS
    serp_results_per_query: int = SERP_RESULTS_PER_QUERY
    serp_allow_weak_fallback: bool = SERP_ALLOW_WEAK_FALLBACK
    search_signature_drop_tokens: frozenset[str] = field(default_factory=lambda: frozenset(SEARCH_SIGNATURE_DROP_TOKENS))
    canonical_title_max_len: int = CANONICAL_TITLE_MAX_LEN
    min_group_quantity_for_search: int = MIN_GROUP_QUANTITY_FOR_SEARCH
    serp_preview_limit: int = SERP_PREVIEW_LIMIT
    serp_state_path: str = SERP_STATE_PATH
    serp_value_coverage_target: float = SERP_VALUE_COVERAGE_TARGET
    playwright_fallback_enabled: bool = PLAYWRIGHT_FALLBACK_ENABLED
    playwright_headless: bool = PLAYWRIGHT_HEADLESS
    playwright_max_queries_per_run: int = PLAYWRIGHT_MAX_QUERIES_PER_RUN
    playwright_rate_limit_seconds: float = PLAYWRIGHT_RATE_LIMIT_SECONDS
    playwright_rate_limit_jitter_seconds: float = PLAYWRIGHT_RATE_LIMIT_JITTER_SECONDS
    playwright_profile_path: str = PLAYWRIGHT_PROFILE_PATH
    playwright_page_timeout_s: float = PLAYWRIGHT_PAGE_TIMEOUT_S
    playwright_captcha_timeout_s: float = PLAYWRIGHT_CAPTCHA_TIMEOUT_S


DEFAULT_PRIORS_PATH: str = "config/priors/latest.json"


def _load_priors_if_exists(path: str | os.PathLike[str]) -> Mapping[str, Any]:
    """Return parsed priors JSON, or an empty dict if the file is missing.

    Never raises on missing file — operators may run the engine before any
    feedback loop has been kicked off.  Malformed JSON or unexpected keys
    are logged and ignored.
    """
    p = Path(path)
    if not p.exists():
        _log.info("priors file %s missing — using in-code defaults", p)
        return {}
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("failed to read priors %s (%s) — using defaults", p, exc)
        return {}
    if not isinstance(data, dict):
        _log.warning("priors %s is not an object — using defaults", p)
        return {}
    return data


def get_settings() -> Settings:
    """Return the default ``Settings`` bundle.

    Honours the ``BULK_INTEL_PRIORS_PATH`` env var (falling back to
    ``config/priors/latest.json``) for the T-305 outcome feedback loop:
    if the file exists, three keys override the module-level constants:

    * ``category_return_rate``
    * ``category_holding_days``
    * ``condition_to_sell_through``

    All other Settings fields keep their in-code defaults.  Missing or
    malformed files are silently ignored.
    """
    priors_path = os.getenv("BULK_INTEL_PRIORS_PATH", DEFAULT_PRIORS_PATH)
    overrides = _load_priors_if_exists(priors_path)

    if not overrides:
        return Settings()

    kwargs: dict[str, Any] = {}
    if isinstance(overrides.get("category_return_rate"), dict):
        kwargs["category_return_rate"] = dict(overrides["category_return_rate"])
    if isinstance(overrides.get("category_holding_days"), dict):
        kwargs["category_holding_days"] = {
            k: int(v) for k, v in overrides["category_holding_days"].items()
        }
    if isinstance(overrides.get("condition_to_sell_through"), dict):
        kwargs["condition_to_sell_through"] = {
            k: dict(v) for k, v in overrides["condition_to_sell_through"].items()
        }

    env_enabled = os.getenv("BULK_INTEL_SERP_PROVIDER_ENABLED")
    if env_enabled is not None:
        kwargs["serp_provider_enabled"] = env_enabled.lower() in {"1", "true", "yes", "on"}
    env_pw = os.getenv("BULK_INTEL_PLAYWRIGHT_FALLBACK")
    if env_pw is not None:
        kwargs["playwright_fallback_enabled"] = env_pw.lower() in {"1", "true", "yes", "on"}
    env_pw_headless = os.getenv("BULK_INTEL_PLAYWRIGHT_HEADLESS")
    if env_pw_headless is not None:
        kwargs["playwright_headless"] = env_pw_headless.lower() in {"1", "true", "yes", "on"}

    return Settings(**kwargs)
