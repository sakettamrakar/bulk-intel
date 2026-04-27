"""Tests for cost-related engines and calculations.

Covers two cost components:

* T-101 — platform × category fee table (`PLATFORM_FEES`).
* T-102 — per-condition inspection cost (`INSPECTION_COST_BY_CONDITION`).
"""
from __future__ import annotations

import pandas as pd
import pytest

from config.settings import get_settings
from intelligence.profit import ProfitEngine, compute_profitability


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


# ---------------------------------------------------------------------------
# T-102 inspection cost
# ---------------------------------------------------------------------------


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
    # Compare the same row evaluated with a synthetic ``mock_tested`` condition
    # that mirrors ``unknown``'s sellable_factor but with zero inspection cost.
    # The only difference between the two profit projections must be the
    # inspection cost line.
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

    assert diff_profit == pytest.approx(inspection_cost)


# ---------------------------------------------------------------------------
# T-101 platform × category fees
# ---------------------------------------------------------------------------


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
