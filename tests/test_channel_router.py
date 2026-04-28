"""Tests for the ChannelRouter."""
from __future__ import annotations

import pandas as pd

from config.settings import Settings
from intelligence.channel import ChannelRouter


def test_defective_routes_to_b2b():
    df = pd.DataFrame([{"condition_normalized": "defective", "category": "electronics"}])
    assert ChannelRouter(Settings()).route(df).iloc[0]["platform"] == "b2b"


def test_branded_electronics_mid_band_routes_to_amazon():
    # 'apple' is in KNOWN_BRANDS
    df = pd.DataFrame([{
        "condition_normalized": "new",
        "category": "electronics",
        "brand": "apple",
        "price_band": "MID"
    }])
    assert ChannelRouter(Settings()).route(df).iloc[0]["platform"] == "amazon"


def test_low_band_electronics_routes_to_flipkart():
    df = pd.DataFrame([{
        "condition_normalized": "new",
        "category": "electronics",
        "brand": "apple",
        "price_band": "LOW"
    }])
    assert ChannelRouter(Settings()).route(df).iloc[0]["platform"] == "flipkart"


def test_apparel_routes_to_meesho():
    df = pd.DataFrame([{"category": "apparel"}])
    assert ChannelRouter(Settings()).route(df).iloc[0]["platform"] == "meesho"


def test_unknown_category_uses_default_platform():
    # If we supply an empty rule list, it should hit the default.
    settings = Settings(channel_routing_rules=(), default_platform="unknown_default")
    df = pd.DataFrame([{"category": "does_not_exist"}])
    assert ChannelRouter(settings).route(df).iloc[0]["platform"] == "unknown_default"


def test_apparel_on_meesho_more_profitable_than_amazon():
    from intelligence.profit import ProfitEngine
    
    df1 = pd.DataFrame([{
        "category": "apparel", "mrp": 1000.0, "real_price": 500.0, "floor_price": 200.0, 
        "condition_normalized": "new", "platform": "meesho", "quantity": 1, 
        "acquisition_cost": 200.0, "inspection_cost": 0.0, "transport_cost": 0.0, "return_rate": 0.0,
        "sellability_score": 100
    }])
    
    df2 = pd.DataFrame([{
        "category": "apparel", "mrp": 1000.0, "real_price": 500.0, "floor_price": 200.0, 
        "condition_normalized": "new", "platform": "amazon", "quantity": 1,
        "acquisition_cost": 200.0, "inspection_cost": 0.0, "transport_cost": 0.0, "return_rate": 0.0,
        "sellability_score": 100
    }])
    
    pe = ProfitEngine(Settings())
    res1 = pe.compute(df1)
    res2 = pe.compute(df2)
    
    assert res1.iloc[0]["expected_profit"] > res2.iloc[0]["expected_profit"]
