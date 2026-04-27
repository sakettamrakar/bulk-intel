import pandas as pd
import pytest

from config.settings import Settings
from intelligence.profit import ProfitEngine

def test_transport_cost_by_weight_tier():
    # Kitchenware maps to 'bulky' which is 150.0. Qty = 1
    df = pd.DataFrame([
        {"sku": "SKU1", "category": "kitchenware", "quantity": 1, "floor_price": 100, "mrp": 200, "real_price": 150}
    ])
    settings = Settings()
    engine = ProfitEngine(settings)
    out = engine.compute(df)

    assert "transport_cost" in out.columns
    assert float(out.iloc[0]["transport_cost"]) == 150.0

def test_transport_cost_by_category():
    # 'apparel' maps to 'small' (25.0)
    # 'appliances' maps to 'bulky' (150.0)
    df = pd.DataFrame([
        {"sku": "SKU1", "category": "apparel", "quantity": 1, "floor_price": 100, "mrp": 200, "real_price": 150},
        {"sku": "SKU2", "category": "appliances", "quantity": 1, "floor_price": 100, "mrp": 200, "real_price": 150}
    ])
    settings = Settings()
    engine = ProfitEngine(settings)
    out = engine.compute(df)

    assert float(out.iloc[0]["transport_cost"]) == 25.0
    assert float(out.iloc[1]["transport_cost"]) == 150.0

    # expected_cost = acquisition_cost + operating_cost + transport_cost
    # Both have same floor_price and real_price, so acquisition_cost and operating_cost are equal.
    # Therefore, bulky expected_cost should be > small expected_cost
    assert float(out.iloc[1]["expected_cost"]) > float(out.iloc[0]["expected_cost"])

def test_transport_fallback_for_unknown_category():
    # Unknown/synthetic category falls back to "medium" (60.0)
    df = pd.DataFrame([
        {"sku": "SKU1", "category": "synthetic_category", "quantity": 1, "floor_price": 100, "mrp": 200, "real_price": 150}
    ])
    settings = Settings()
    engine = ProfitEngine(settings)
    out = engine.compute(df)

    assert float(out.iloc[0]["transport_cost"]) == 60.0

def test_transport_cost_affects_profit():
    # Test transport cost scales with quantity
    # 'stationery' maps to 'small' (25.0).
    df = pd.DataFrame([
        {"sku": "SKU1", "category": "stationery", "quantity": 1, "floor_price": 100, "mrp": 200, "real_price": 150},
        {"sku": "SKU2", "category": "stationery", "quantity": 10, "floor_price": 100, "mrp": 200, "real_price": 150}
    ])
    settings = Settings()
    engine = ProfitEngine(settings)
    out = engine.compute(df)

    assert float(out.iloc[0]["transport_cost"]) == 25.0
    assert float(out.iloc[1]["transport_cost"]) == 250.0

def test_zero_transport_for_digital_goods():
    # 'digital' maps to 'weightless' (0.0)
    df = pd.DataFrame([
        {"sku": "SKU1", "category": "digital", "quantity": 5, "floor_price": 100, "mrp": 200, "real_price": 150}
    ])
    settings = Settings()
    engine = ProfitEngine(settings)
    out = engine.compute(df)

    assert float(out.iloc[0]["transport_cost"]) == 0.0
