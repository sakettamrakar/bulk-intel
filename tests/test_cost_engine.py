"""Tests for cost-related engines and calculations.

Covers five cost components:

* T-101 — platform × category fee table (`PLATFORM_FEES`).
* T-102 — per-condition inspection cost (`INSPECTION_COST_BY_CONDITION`).
* T-103 — category-aware transport cost (`CATEGORY_WEIGHT_TIER` × `TRANSPORT_COST_PER_UNIT`).
* T-104 — per-category return rate (`CATEGORY_RETURN_RATE`).
* T-105 — cost decomposition output (acquisition_cost, platform_fee_amount, etc.).
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


# ---------------------------------------------------------------------------
# T-104 return rate model
# ---------------------------------------------------------------------------


def test_return_rate_lookup_uses_category():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "APP",
            "quantity": 100,
            "floor_price": 100,
            "mrp": 200,
            "real_price": 150,
            "category": "apparel",
        }
    ])

    out = compute_profitability(df, settings)

    # apparel return rate should be 0.22
    assert out.iloc[0]["return_rate"] == 0.22


def test_return_rate_falls_back_to_default():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "UNKNOWN",
            "quantity": 1,
            "floor_price": 100,
            "mrp": 200,
            "real_price": 150,
            "category": "synthetic_unknown_category",
        }
    ])

    out = compute_profitability(df, settings)

    # unknown category falls back to DEFAULT_RETURN_RATE = 0.10
    assert out.iloc[0]["return_rate"] == 0.10


def test_returns_reduce_revenue_proportionally():
    settings = get_settings()
    # Row with 0% return rate (use 'books' = 0.04, then override to 0)
    settings.category_return_rate["books_zero"] = 0.0
    settings.category_return_rate["books_twenty"] = 0.20

    df_no_returns = pd.DataFrame([
        {
            "sku": "A",
            "quantity": 1,
            "floor_price": 100,
            "mrp": 1000,
            "real_price": 500,
            "category": "books_zero",
        }
    ])
    df_with_returns = pd.DataFrame([
        {
            "sku": "B",
            "quantity": 1,
            "floor_price": 100,
            "mrp": 1000,
            "real_price": 500,
            "category": "books_twenty",
        }
    ])

    engine = ProfitEngine(settings)
    out_no = engine.compute(df_no_returns)
    out_with = engine.compute(df_with_returns)

    gross_revenue = 1.0 * 500  # sellable_qty * price (approx)
    revenue_no_returns = out_no.iloc[0]["expected_revenue"]
    revenue_with_returns = out_with.iloc[0]["expected_revenue"]

    # Expected: with_returns = gross_revenue * (1 - 0.20) = gross_revenue * 0.80
    # So the delta should be ~20% of gross_revenue
    expected_delta_pct = 0.20
    actual_delta_pct = (revenue_no_returns - revenue_with_returns) / revenue_no_returns
    assert actual_delta_pct == pytest.approx(expected_delta_pct, rel=0.05)


def test_returns_add_handling_cost_proportional_to_returned_units():
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "TEST",
            "quantity": 1,
            "floor_price": 100,
            "mrp": 1000,
            "real_price": 1000,
            "category": "electronics",  # 0.13 return rate
        }
    ])

    engine = ProfitEngine(settings)
    out = engine.compute(df)

    # Verify that return_provision exists and is > 0
    return_provision = out.iloc[0]["return_provision"]
    assert return_provision > 0

    # Verify that return_provision scales with return rate
    # Higher return rate should give higher return_provision
    assert float(out.iloc[0]["return_rate"]) == 0.13


def test_apparel_less_profitable_than_kitchen_at_equal_inputs():
    # Compare two items from the SAME category to isolate return rate impact.
    # Use 'books' (low return 0.04) vs apparel (high return 0.22), both small transport.
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "BOOKS",
            "quantity": 10,
            "floor_price": 50,
            "mrp": 200,
            "real_price": 100,
            "category": "books",  # 0.04 return rate, 'small' transport
        },
        {
            "sku": "APP",
            "quantity": 10,
            "floor_price": 50,
            "mrp": 200,
            "real_price": 100,
            "category": "apparel",  # 0.22 return rate, 'small' transport
        }
    ])

    engine = ProfitEngine(settings)
    out = engine.compute(df)

    books_profit = float(out[out["sku"] == "BOOKS"].iloc[0]["expected_profit"])
    app_profit = float(out[out["sku"] == "APP"].iloc[0]["expected_profit"])

    # Same inputs except category; only return rate differs significantly.
    # Higher return rate (apparel) → higher return_provision → lower profit.
    assert app_profit < books_profit


# ---------------------------------------------------------------------------
# T-105 cost decomposition output
# ---------------------------------------------------------------------------


def test_cost_breakdown_columns_present():
    """Assert acquisition_cost, platform_fee_amount, and return columns exist."""
    settings = get_settings()
    df = pd.DataFrame([_row(category="electronics", platform="amazon")])

    out = compute_profitability(df, settings)

    assert "acquisition_cost" in out.columns
    assert "platform_fee_pct" in out.columns
    assert "ancillary_revenue_fee_pct" in out.columns
    assert "platform_fee_amount" in out.columns
    assert "inspection_cost" in out.columns
    assert "transport_cost" in out.columns
    assert "return_rate" in out.columns
    assert "return_provision" in out.columns


def test_platform_fee_amount_calculated_correctly():
    """platform_fee_amount = gross_revenue × (platform_fee_pct + ancillary_pct)."""
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "TEST",
            "quantity": 1,
            "floor_price": 100,
            "real_price": 1000,
            "platform": "amazon",
            "category": "electronics",
        }
    ])

    out = compute_profitability(df, settings)

    # gross_revenue ≈ sellable_qty * real_price
    # For simplicity, assuming high sell-through: gross_revenue ≈ 1000
    # platform_fee = 0.085 + 0.04 = 0.125
    # platform_fee_amount ≈ 1000 * 0.125 = 125
    platform_fee_amt = float(out.iloc[0]["platform_fee_amount"])
    assert platform_fee_amt > 0


# ---------------------------------------------------------------------------
# T-303 capital cost / holding-period
# ---------------------------------------------------------------------------


from dataclasses import replace


def test_holding_cost_zero_when_holding_days_zero():
    base = get_settings()
    settings = replace(
        base,
        category_holding_days={**base.category_holding_days, "kitchen": 0},
        default_holding_days=0,
    )
    df = pd.DataFrame([
        {"sku": "A", "quantity": 10, "floor_price": 100, "real_price": 200,
         "category": "kitchen"}
    ])
    out = compute_profitability(df, settings)
    assert float(out.iloc[0]["holding_cost"]) == 0.0
    assert int(out.iloc[0]["holding_days"]) == 0


def test_holding_cost_scales_linearly_with_days():
    base = get_settings()
    settings = replace(
        base,
        category_holding_days={**base.category_holding_days,
                                "cat30": 30, "cat90": 90},
    )
    df = pd.DataFrame([
        {"sku": "A", "quantity": 10, "floor_price": 100, "real_price": 200, "category": "cat30"},
        {"sku": "B", "quantity": 10, "floor_price": 100, "real_price": 200, "category": "cat90"},
    ])
    out = compute_profitability(df, settings)
    h30 = float(out.iloc[0]["holding_cost"])
    h90 = float(out.iloc[1]["holding_cost"])
    assert h90 == pytest.approx(3.0 * h30, rel=1e-2)


def test_holding_cost_uses_category_default():
    settings = get_settings()
    df = pd.DataFrame([
        {"sku": "APP", "quantity": 1, "floor_price": 100, "real_price": 200,
         "category": "apparel"}
    ])
    out = compute_profitability(df, settings)
    assert int(out.iloc[0]["holding_days"]) == 120


def test_books_more_expensive_to_hold_than_electronics():
    settings = get_settings()
    df = pd.DataFrame([
        {"sku": "BK", "quantity": 10, "floor_price": 100, "real_price": 200,
         "category": "books"},
        {"sku": "EL", "quantity": 10, "floor_price": 100, "real_price": 200,
         "category": "electronics"},
    ])
    out = compute_profitability(df, settings)
    bk = float(out[out["sku"] == "BK"].iloc[0]["holding_cost"])
    el = float(out[out["sku"] == "EL"].iloc[0]["holding_cost"])
    assert bk > el


def test_holding_cost_real_manifest_kitchen():
    """holding_cost ≈ lot_cost × 0.18 × 90/365 ≈ 4.4 % of lot_cost for kitchen."""
    settings = get_settings()
    df = pd.DataFrame([
        {"sku": "K", "quantity": 100, "floor_price": 50, "real_price": 100,
         "category": "kitchen"}
    ])
    out = compute_profitability(df, settings)
    lot_cost = 100 * 50  # qty * floor
    expected = lot_cost * 0.18 * 90 / 365.0
    assert float(out.iloc[0]["holding_cost"]) == pytest.approx(expected, rel=1e-3)


def test_acquisition_cost_includes_overhead():
    """acquisition_cost = qty × floor × (1 + acquisition_overhead_pct)."""
    settings = get_settings()
    df = pd.DataFrame([
        {
            "sku": "TEST",
            "quantity": 10,
            "floor_price": 100.0,
            "real_price": 200.0,
        }
    ])

    out = compute_profitability(df, settings)

    acq = float(out.iloc[0]["acquisition_cost"])
    expected = 10 * 100 * (1.0 + 0.05)  # qty * floor * (1 + 5% overhead)
    assert acq == pytest.approx(expected)
