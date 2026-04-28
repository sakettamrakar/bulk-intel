"""Tests for pricing, scoring and decision modules."""
from __future__ import annotations

import pandas as pd

from enrichment.enricher import MRPHeuristicPriceProvider, enrich_manifest
from intelligence.decision import decide
from intelligence.pricing import compute_pricing_metrics
from intelligence.profit import compute_profitability
from intelligence.scoring import compute_scores
from processing.cleaner import clean_manifest


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_manifest(df)
    df = enrich_manifest(df, [MRPHeuristicPriceProvider(market_pct_of_mrp=0.85)])
    df = compute_pricing_metrics(df)
    return df


def test_pricing_metrics_in_sane_range(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    assert (df["price_ratio"].between(0, 1)).all()
    assert (df["discount_percentage"].between(-100, 100)).all()
    # 35% of 10000 = 3500 floor → 65% discount.
    assert df.loc[0, "discount_percentage"] == 65.0


def test_scoring_produces_0_to_100(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    df = compute_scores(df)
    assert df["sellability_score"].between(0, 100).all()
    assert df["risk_score"].between(0, 100).all()


def test_high_discount_known_brand_scores_higher(tiny_manifest_df):
    # Need equivalent discounts/market gaps to isolate brand score
    df = pd.DataFrame([
        {
            "sku": "A1",
            "product_name": "Samsung Galaxy S22",
            "category": "electronics",
            "brand": "samsung",
            "mrp": 1000.0,
            "floor_price": 200.0, # 80% discount
            "quantity": 10,
            "condition": "New",
        },
        {
            "sku": "A2",
            "product_name": "Generic Phone",
            "category": "electronics",
            "brand": "unknown",
            "mrp": 1000.0,
            "floor_price": 200.0, # 80% discount
            "quantity": 10,
            "condition": "New",
        }
    ])
    df = _prep(df)
    df["amazon_price"] = 800.0
    df = compute_pricing_metrics(df)
    df = compute_scores(df)

    samsung = df.loc[df["sku"] == "A1", "sellability_score"].iloc[0]
    generic = df.loc[df["sku"] == "A2", "sellability_score"].iloc[0]
    assert samsung > generic


def test_decision_engine_emits_recommendation_and_reasoning(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    df = compute_scores(df)
    df = compute_profitability(df)
    df = decide(df)
    assert set(df["recommendation"].unique()).issubset({"BUY", "REVIEW", "SKIP"})
    assert df["reasoning"].str.len().gt(0).all()


def test_profitability_fields_present(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    df = compute_scores(df)
    df = compute_profitability(df)
    for col in (
        "expected_sellable_qty",
        "expected_revenue",
        "expected_profit",
        "expected_margin_pct",
    ):
        assert col in df.columns


def test_high_confidence_items_keep_buy_rating(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    df["match_confidence"] = 0.9
    # Force high sellability/profit to get a BUY
    df["discount_percentage"] = 90.0
    df["market_gap"] = 50.0
    df["mrp"] = 1000.0
    df["floor_price"] = 10.0
    df["quantity"] = 10
    df["condition"] = "New"
    df["brand"] = "samsung"
    df["category"] = "electronics"
    df = compute_pricing_metrics(df)
    df = compute_scores(df)
    df = compute_profitability(df)
    df = decide(df)

    # Check that at least one BUY exists and wasn't downgraded
    buys = df[df["recommendation"] == "BUY"]
    assert len(buys) > 0
    assert not buys.iloc[0]["confidence_gate_applied"]


def test_low_confidence_items_downgraded_to_review(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    df["match_confidence"] = 0.4
    # Force high sellability/profit to ordinarily get a BUY
    df["discount_percentage"] = 90.0
    df["market_gap"] = 50.0
    df["mrp"] = 1000.0
    df["floor_price"] = 10.0
    df["quantity"] = 10
    df["condition"] = "New"
    df["brand"] = "samsung"
    df["category"] = "electronics"
    df = compute_pricing_metrics(df)
    df = compute_scores(df)
    df = compute_profitability(df)

    # We first run decide normally. But wait, `decide()` handles the gate!
    # If the gate is applied, the item won't be a BUY in the final output.
    df = decide(df)

    reviews = df[df["confidence_gate_applied"]]
    assert len(reviews) > 0
    assert reviews.iloc[0]["recommendation"] == "REVIEW"
    assert "price is synthetic" in reviews.iloc[0]["reasoning"]


def test_confidence_threshold_applies_to_all_platforms():
    df = pd.DataFrame([
        {
            "sku": "HIGH_CONF",
            "product_name": "Galaxy S22",
            "mrp": 1000.0,
            "floor_price": 10.0,
            "quantity": 10,
            "condition": "New",
            "brand": "samsung",
            "category": "electronics",
        },
        {
            "sku": "LOW_CONF",
            "product_name": "Galaxy S22",
            "mrp": 1000.0,
            "floor_price": 10.0,
            "quantity": 10,
            "condition": "New",
            "brand": "samsung",
            "category": "electronics",
        }
    ])
    df = _prep(df)

    # We must set match_confidence AFTER enricher, because enricher overwrites it
    # to 1.0 when using MRPHeuristicPriceProvider.
    df.loc[df["sku"] == "HIGH_CONF", "match_confidence"] = 0.8
    df.loc[df["sku"] == "LOW_CONF", "match_confidence"] = 0.2
    df["discount_percentage"] = 90.0 # Force passing score
    df["market_gap"] = 50.0
    df = compute_scores(df)
    df = compute_profitability(df)
    df = decide(df)

    high = df[df["sku"] == "HIGH_CONF"].iloc[0]
    low = df[df["sku"] == "LOW_CONF"].iloc[0]

    assert high["recommendation"] == "BUY"
    assert not high["confidence_gate_applied"]
    assert low["recommendation"] == "REVIEW"
    assert low["confidence_gate_applied"]


def test_confidence_gate_prevents_loss_scenarios(tiny_manifest_df):
    df = _prep(tiny_manifest_df)
    df["match_confidence"] = 0.0
    # Create scenario that passes all other gates
    df["discount_percentage"] = 90.0
    df["market_gap"] = 50.0
    df["mrp"] = 1000.0
    df["floor_price"] = 10.0
    df["quantity"] = 10
    df["condition"] = "New"
    df["brand"] = "samsung"
    df["category"] = "electronics"
    df = compute_pricing_metrics(df)
    df = compute_scores(df)
    df = compute_profitability(df)
    df = decide(df)

    # Despite passing all other gates perfectly, a confidence of 0.0 must yield REVIEW
    row = df.iloc[0]
    assert row["recommendation"] == "REVIEW"
    assert row["confidence_gate_applied"]


def test_demand_and_liquidity_are_not_identical():
    from config.settings import DEMAND_SCORE, CATEGORY_LIQUIDITY_SCORE
    diff_count = 0
    for k in DEMAND_SCORE:
        if DEMAND_SCORE[k] != CATEGORY_LIQUIDITY_SCORE[k]:
            diff_count += 1
    assert diff_count >= 6


def test_electronics_high_demand_low_liquidity():
    from config.settings import DEMAND_SCORE, CATEGORY_LIQUIDITY_SCORE
    assert DEMAND_SCORE["electronics"] > CATEGORY_LIQUIDITY_SCORE["electronics"]


def test_apparel_demand_close_to_liquidity():
    from config.settings import DEMAND_SCORE, CATEGORY_LIQUIDITY_SCORE
    assert abs(DEMAND_SCORE["apparel"] - CATEGORY_LIQUIDITY_SCORE["apparel"]) <= 10

def test_real_price_uses_settings_amazon_discount():
    from config.settings import Settings
    from intelligence.pricing import PricingEngine
    df = pd.DataFrame([
        {"sku": "A1", "mrp": 1000.0, "amazon_price": 500.0, "floor_price": 100.0}
    ])
    s = Settings(pricing_strategy={"amazon_discount_factor": 1.0, "fallback_pct_of_mrp": 0.45})
    df_priced = PricingEngine(s).compute(df)
    assert df_priced.loc[0, "real_price"] == 500.0

def test_real_price_uses_settings_fallback_pct():
    from config.settings import Settings
    from intelligence.pricing import PricingEngine
    df = pd.DataFrame([
        {"sku": "A1", "mrp": 1000.0, "floor_price": 100.0}
    ])
    s = Settings(pricing_strategy={"amazon_discount_factor": 0.7, "fallback_pct_of_mrp": 0.30})
    df_priced = PricingEngine(s).compute(df)
    assert df_priced.loc[0, "real_price"] == 300.0

def test_default_settings_match_legacy_constants():
    from config.settings import Settings
    from intelligence.pricing import PricingEngine
    df = pd.DataFrame([
        {"sku": "A1", "mrp": 1000.0, "amazon_price": 500.0, "floor_price": 100.0}
    ])
    df_priced = PricingEngine(Settings()).compute(df)
    # default amazon_discount is 0.7. So 500 * 0.7 = 350
    # default fallback is 0.45. So 1000 * 0.45 = 450
    # min is 350.
    assert df_priced.loc[0, "real_price"] == 350.0
