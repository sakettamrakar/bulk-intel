import pandas as pd
import pytest

from config.settings import get_settings
from intelligence.profit import compute_profitability

def test_platform_fee_lookup_uses_table_value():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 200,
            "platform": "amazon",
            "category": "electronics",
        }
    ])

    out = compute_profitability(df, settings)

    # expected platform fee = 0.085
    assert out.iloc[0]["platform_fee_pct"] == 0.085

def test_platform_fee_falls_back_to_platform_default():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 200,
            "platform": "amazon",
            "category": "unknown_cat",
        }
    ])

    out = compute_profitability(df, settings)

    # expected platform fee = amazon __default__ = 0.155
    assert out.iloc[0]["platform_fee_pct"] == 0.155

def test_platform_fee_falls_back_to_global_default():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 200,
            "platform": "meta",
            "category": "anything",
        }
    ])

    out = compute_profitability(df, settings)

    # expected platform fee = global fallback = 0.18
    assert out.iloc[0]["platform_fee_pct"] == 0.18

def test_default_platform_used_when_column_missing():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 200,
            "category": "electronics",
        }
    ])

    out = compute_profitability(df, settings)

    # Since platform missing, defaults to amazon. amazon/electronics = 0.085
    assert out.iloc[0]["platform_fee_pct"] == 0.085

def test_apparel_costs_more_than_kitchen():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "A1",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 1000,
            "platform": "amazon",
            "category": "apparel",
        },
        {
            "sku": "A2",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 1000,
            "platform": "amazon",
            "category": "kitchen",
        }
    ])

    out = compute_profitability(df, settings)

    apparel_profit = out[out["sku"] == "A1"].iloc[0]["expected_profit"]
    kitchen_profit = out[out["sku"] == "A2"].iloc[0]["expected_profit"]

    # apparel (17.5%) costs more than kitchen (15.5%) -> apparel profit < kitchen profit
    assert apparel_profit < kitchen_profit
