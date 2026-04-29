"""Tests for the Amazon BSR provider."""
from __future__ import annotations

import pandas as pd
import pytest

from config.settings import Settings
from enrichment.bsr_provider import FuzzyCatalogBSRProvider
from intelligence.scoring import compute_scores

@pytest.fixture
def test_catalog():
    return [
        {"product_name": "Pigeon Mixer Grinder", "bsr": 500},
        {"product_name": "Samsung Galaxy S22", "bsr": 50000},
        {"product_name": "Generic T-Shirt", "bsr": 2000000},
        {"product_name": "Book Title", "bsr": 1000}, # Missing from specific bands, falls to _default
        {"product_name": "Missing BSR Item"}, # No bsr
    ]

@pytest.fixture
def provider(test_catalog):
    return FuzzyCatalogBSRProvider(catalog=test_catalog)


def test_fuzzy_catalog_bsr_provider(provider):
    # Perfect match
    df = pd.Series({"product_name": "Pigeon Mixer Grinder", "sku": "A1"})
    assert provider.lookup(df) == 500.0

    # Fuzzy match
    df = pd.Series({"product_name": "pigeon mixer", "sku": "A2"})
    assert provider.lookup(df) == 500.0

    # Item with no bsr in catalog
    df = pd.Series({"product_name": "Missing BSR Item", "sku": "A3"})
    assert provider.lookup(df) is None

    # Unmatched item
    df = pd.Series({"product_name": "Unknown Brand Toaster", "sku": "A4"})
    assert provider.lookup(df) is None


def test_bsr_lookup_by_category_band():
    """BSR=500 in kitchen -> 95-band score."""
    settings = Settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "amazon_bsr": 500.0,
            "category": "kitchen",
            "quantity": 10,
            "discount_percentage": 50.0,
        }
    ])
    df_scored = compute_scores(df, settings)

    df_missing = pd.DataFrame([
        {
            "sku": "A2",
            "category": "kitchen",
            "quantity": 10,
            "discount_percentage": 50.0,
        }
    ])
    df_missing_scored = compute_scores(df_missing, settings)

    diff = df_scored.loc[0, "sellability_score"] - df_missing_scored.loc[0, "sellability_score"]
    assert pytest.approx(diff, 0.01) == 11.25


def test_bsr_default_when_missing():
    """row without BSR -> DEFAULT_BSR_SCORE (50)."""
    settings = Settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "category": "kitchen",
            "quantity": 10,
            "discount_percentage": 50.0,
            "market_gap": 10.0,
        }
    ])
    df_scored = compute_scores(df, settings)

    df_explicit = pd.DataFrame([
        {
            "sku": "A1",
            "category": "kitchen",
            "amazon_bsr": None,
            "quantity": 10,
            "discount_percentage": 50.0,
            "market_gap": 10.0,
        }
    ])
    df_explicit_scored = compute_scores(df_explicit, settings)

    assert df_scored.loc[0, "sellability_score"] == df_explicit_scored.loc[0, "sellability_score"]


def test_lower_bsr_higher_sellability():
    """Two identical rows differing only in BSR; the lower BSR scores higher."""
    settings = Settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "amazon_bsr": 500.0, # Top tier for kitchen (95)
            "category": "kitchen",
            "quantity": 10,
            "discount_percentage": 50.0,
        },
        {
            "sku": "A2",
            "amazon_bsr": 500000.0, # Bottom tier for kitchen (25)
            "category": "kitchen",
            "quantity": 10,
            "discount_percentage": 50.0,
        }
    ])
    df_scored = compute_scores(df, settings)

    assert df_scored.loc[df_scored["sku"] == "A1", "sellability_score"].iloc[0] > \
           df_scored.loc[df_scored["sku"] == "A2", "sellability_score"].iloc[0]


def test_per_category_bsr_thresholds():
    """BSR=50,000 in books vs kitchen; assert different band scores."""
    settings = Settings()
    df = pd.DataFrame([
        {
            "sku": "KITCHEN",
            "amazon_bsr": 50000.0,
            "category": "kitchen",
            "quantity": 10,
            "discount_percentage": 50.0,
        },
        {
            "sku": "BOOKS",
            "amazon_bsr": 50000.0,
            "category": "books",
            "quantity": 10,
            "discount_percentage": 50.0,
        }
    ])
    df_scored = compute_scores(df, settings)

    settings_dict = {
        "demand_score": {"kitchen": 50.0, "books": 50.0},
        "category_liquidity": {"kitchen": 50.0, "books": 50.0},
    }
    s = Settings(
        demand_score=settings_dict["demand_score"],
        category_liquidity=settings_dict["category_liquidity"]
    )
    df_scored_isolated = compute_scores(df, s)

    k_isolated = df_scored_isolated.loc[df_scored_isolated["sku"] == "KITCHEN", "sellability_score"].iloc[0]
    b_isolated = df_scored_isolated.loc[df_scored_isolated["sku"] == "BOOKS", "sellability_score"].iloc[0]

    assert b_isolated > k_isolated
