"""Tests for the rollup logic."""
import pandas as pd
from output.reporter import Reporter
from pathlib import Path

def test_rollup_file_present(tmp_path):
    df = pd.DataFrame([
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "brand": "apple", "mrp": 100, "floor_price": 50, "real_price": 80, "expected_revenue": 80, "expected_cost": 50, "expected_profit": 30, "expected_roi_pct": 60.0, "sellability_score": 80, "risk_score": 20, "condition_normalized": "new", "recommendation": "BUY"}
    ] * 5)
    reporter = Reporter(tmp_path)
    base_name = "test"
    outs = reporter.write(df, base_name=base_name)
    assert "rollup" in outs
    assert (tmp_path / "test_rollup.csv").exists()

def test_rollup_aggregates_units():
    df = pd.DataFrame([
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "brand": "apple"}
    ] * 5)
    rollup = Reporter._build_rollup(df)
    assert len(rollup) == 1
    assert rollup.iloc[0]["units"] == 5

def test_rollup_profit_sums_match_per_row():
    # 5 rows worth profit 30 each -> sum 150
    df = pd.DataFrame([
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "brand": "apple", "expected_profit": 33.33}
    ] * 5)
    rollup = Reporter._build_rollup(df)
    assert abs(rollup.iloc[0]["expected_profit"] - (33.33 * 5)) < 0.01

def test_rollup_roi_uses_summed_amounts_not_mean():
    df = pd.DataFrame([
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "expected_revenue": 100, "expected_cost": 50, "expected_profit": 50, "expected_roi_pct": 100.0},
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "expected_revenue": 200, "expected_cost": 150, "expected_profit": 50, "expected_roi_pct": 33.33}
    ])
    rollup = Reporter._build_rollup(df)
    # Summed revenue = 300, Summed cost = 200, profit = 100
    # Expected ROI = 100/200 * 100 = 50.0%
    assert rollup.iloc[0]["expected_roi_pct"] == 50.0

def test_rollup_recommendation_majority_logic():
    # 3 BUY, 1 SKIP
    df = pd.DataFrame([
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "recommendation": "BUY"},
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "recommendation": "BUY"},
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "recommendation": "BUY"},
        {"sku": "SKU1", "quantity": 1, "product_name_clean": "Phone", "recommendation": "SKIP"}
    ])
    rollup = Reporter._build_rollup(df)
    assert rollup.iloc[0]["recommendation"] == "BUY (majority)"
