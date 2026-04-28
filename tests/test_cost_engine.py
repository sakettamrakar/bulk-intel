"""Tests for cost-related engines and calculations.

Covers three cost components:

* T-101 — platform × category fee table (`PLATFORM_FEES`).
* T-102 — per-condition inspection cost (`INSPECTION_COST_BY_CONDITION`).
* T-103 — category-aware transport cost (`CATEGORY_WEIGHT_TIER` × `TRANSPORT_COST_PER_UNIT`).
"""
from __future__ import annotations

import pandas as pd
import pytest

from config.settings import Settings, get_settings
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
# T-103 transport cost
# ---------------------------------------------------------------------------


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

    # expected_cost = acquisition_cost + operating_cost + transport_cost + inspection_cost
    # apparel and appliances both ride on amazon platform fee table; apparel
    # has a higher fee (17.5%) than appliances (11.5%), but appliances are
    # bulky transport whereas apparel is small.  At equal real_price=150 the
    # delta in transport (125) dominates the delta in fees (~9), so total
    # cost for appliances must still exceed apparel.
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


def test_higher_platform_fee_lowers_profit_at_equal_transport():
    # Both stationery and apparel map to 'small' transport tier, isolating
    # the platform-fee delta:
    #   stationery → small + amazon fee 9.5%
    #   apparel    → small + amazon fee 17.5%
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "STAT",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 1000,
            "platform": "amazon",
            "category": "stationery",
        },
        {
            "sku": "APP",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 1000,
            "platform": "amazon",
            "category": "apparel",
        }
    ])

    out = compute_profitability(df, settings)

    stat_profit = out[out["sku"] == "STAT"].iloc[0]["expected_profit"]
    app_profit = out[out["sku"] == "APP"].iloc[0]["expected_profit"]

    # Same transport tier; only the platform fee differs.  Higher fee → less profit.
    assert app_profit < stat_profit
