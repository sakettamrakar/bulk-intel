"""Tests for cost-related engines and calculations."""
from __future__ import annotations

import pandas as pd
import pytest

from config.settings import get_settings
from intelligence.profit import ProfitEngine

def _row(**overrides) -> dict:
    base = {
        "sku": "x",
        "quantity": 1,
        "floor_price": 100.0,
        "mrp": 200.0,
        "condition_normalized": "unknown",
    }
    base.update(overrides)
    return base

def test_inspection_cost_applied_for_unknown():
    df = pd.DataFrame([_row(condition_normalized="unknown", quantity=10)])
    engine = ProfitEngine(get_settings())
    out = engine.compute(df)
    # per-unit rate is 50.0 for unknown
    assert out.loc[0, "inspection_cost"] == 500.0

def test_inspection_cost_applied_for_not_tested():
    df = pd.DataFrame([_row(condition_normalized="not_tested", quantity=10)])
    engine = ProfitEngine(get_settings())
    out = engine.compute(df)
    # per-unit rate is 50.0 for not_tested
    assert out.loc[0, "inspection_cost"] == 500.0

def test_no_inspection_cost_for_tested_items():
    df = pd.DataFrame([_row(condition_normalized="tested", quantity=10)])
    engine = ProfitEngine(get_settings())
    out = engine.compute(df)
    # per-unit rate is 0.0 for tested
    assert out.loc[0, "inspection_cost"] == 0.0

def test_inspection_cost_affects_profit_calculation():
    # Evaluate with unknown condition which adds 50 inspection cost.
    # Note: we compare unknown vs tested to keep sellable_factor the same (both unknown and untested may default to a certain factor, but let's test directly on expected_profit by modifying just the inspection cost manually via mock, or comparing against something that has same sellable_factor).
    # Since condition directly affects sellable_qty in config, we can't directly compare profit between two different conditions without revenue changing.
    # A cleaner test: compare expected_cost of tested vs unknown. The difference should be exactly the inspection cost difference (since expected_revenue might be the same). Let's use 'unknown' (sellable_factor 0.50) and a mock condition or just use 'unknown' with 0 cost vs 50 cost.

    # Let's override the settings to ensure both have same sellable factor
    settings = get_settings()
    settings.condition_to_sell_through["mock_tested"] = settings.condition_to_sell_through["unknown"]
    settings.inspection_cost_by_condition["mock_tested"] = 0.0

    df_with_cost = pd.DataFrame([_row(condition_normalized="unknown", quantity=1)])
    df_no_cost = pd.DataFrame([_row(condition_normalized="mock_tested", quantity=1)])

    engine = ProfitEngine(settings)
    out_with_cost = engine.compute(df_with_cost)
    out_no_cost = engine.compute(df_no_cost)

    diff_profit = out_no_cost.loc[0, "expected_profit"] - out_with_cost.loc[0, "expected_profit"]
    inspection_cost = out_with_cost.loc[0, "inspection_cost"]

    # Due to floating point math, check using pytest.approx
    assert diff_profit == pytest.approx(inspection_cost)
