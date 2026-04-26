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
    df = _prep(tiny_manifest_df)
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
