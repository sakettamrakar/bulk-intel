"""Tests for condition-aware risk and profitability."""
from __future__ import annotations

import pandas as pd

from intelligence.profit import compute_profitability
from intelligence.scoring import compute_scores


def _row(**overrides) -> dict:
    base = {
        "sku": "x",
        "product_name": "Sample Mixer",
        "product_name_clean": "Sample Mixer",
        "brand": "pigeon",
        "category": "kitchen",
        "quantity": 1,
        "mrp": 1000.0,
        "floor_price": 200.0,
        "market_price": 800.0,
        "wholesale_price": float("nan"),
        "discount_percentage": 80.0,
        "price_ratio": 0.20,
        "market_gap": 75.0,
        "wholesale_gap": float("nan"),
        "condition_normalized": "new",
    }
    base.update(overrides)
    return base


def test_profit_uses_condition_factors():
    df = pd.DataFrame(
        [_row(condition_normalized="new"), _row(sku="y", condition_normalized="not_tested")]
    )
    out = compute_profitability(df)
    new_price = out.loc[0, "expected_sell_price"]
    nt_price = out.loc[1, "expected_sell_price"]
    assert nt_price < new_price, "Not-tested items should price below new"

    new_qty = out.loc[0, "expected_sellable_qty"]
    nt_qty = out.loc[1, "expected_sellable_qty"]
    assert nt_qty < new_qty, "Not-tested items should have lower sell-through"


def test_risk_score_increases_with_worse_condition():
    df = pd.DataFrame(
        [
            _row(condition_normalized="new"),
            _row(sku="y", condition_normalized="not_tested"),
            _row(sku="z", condition_normalized="salvage"),
        ]
    )
    scored = compute_scores(df)
    risks = scored["risk_score"].tolist()
    assert risks[0] < risks[1] < risks[2]


def test_roi_column_present_and_signed_correctly():
    # Floor price near MRP → cost > revenue → negative ROI
    bad = _row(floor_price=900.0, market_price=500.0, discount_percentage=10.0, market_gap=-80.0)
    # Steep discount → positive ROI
    good = _row(sku="g", floor_price=100.0, market_price=800.0)
    out = compute_profitability(pd.DataFrame([bad, good]))
    assert "expected_roi_pct" in out.columns
    assert out.loc[0, "expected_roi_pct"] < 0
    assert out.loc[1, "expected_roi_pct"] > 0
