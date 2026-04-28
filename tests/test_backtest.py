"""Tests for the backtest harness."""
import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from tools.backtest import run_backtest, cli

def test_backtest_runs_on_example_data(tmp_path, caplog):
    # Ensure no error
    report_path = tmp_path / "report.json"
    manifest_path = "data/sample_manifest.csv"
    outcomes_path = "data/historical/EXAMPLE_lot_outcomes.csv"
    
    # Check if files exist
    if not Path(manifest_path).exists() or not Path(outcomes_path).exists():
        pytest.skip("Data files not present; assuming CI isolation without data dir.")
        
    ret = cli(["--manifest", manifest_path, "--outcomes", outcomes_path, "--report", str(report_path)])
    assert ret == 0
    assert report_path.exists()
    
    with open(report_path, "r") as f:
        data = json.load(f)
    assert "confusion_matrix" in data
    assert "predicted_vs_actual" in data
    assert "threshold_sweep" in data
    assert "recommended_thresholds" in data

def test_confusion_matrix_counts_match_synthetic(tmp_path):
    man_path = tmp_path / "manifest.csv"
    manifest2 = pd.DataFrame([
        {"sku": "SKU_BUY_PROF", "product_name": "Galaxy S22", "mrp": 1000, "floor_price": 10, "condition": "new", "quantity": 1},
        {"sku": "SKU_BUY_LOSS", "product_name": "Galaxy S22", "mrp": 1000, "floor_price": 10, "condition": "new", "quantity": 1},
        {"sku": "SKU_SKIP_PROF", "product_name": "Broken Toy", "mrp": 10, "floor_price": 100, "condition": "new", "quantity": 1},
        {"sku": "SKU_SKIP_CORR", "product_name": "Broken Toy", "mrp": 10, "floor_price": 100, "condition": "new", "quantity": 1},
    ])
    manifest2.to_csv(man_path, index=False)
    
    outcomes = pd.DataFrame([
        # BUY-profitable
        {"sku": "SKU_BUY_PROF", "realised_units_sold": 1, "realised_avg_sale_price": 200, "realised_returns": 0, "realised_total_cost": 100, "realised_holding_days": 10},
        # BUY-loss
        {"sku": "SKU_BUY_LOSS", "realised_units_sold": 1, "realised_avg_sale_price": 50, "realised_returns": 0, "realised_total_cost": 100, "realised_holding_days": 10},
        # SKIP-would-profit
        {"sku": "SKU_SKIP_PROF", "realised_units_sold": 1, "realised_avg_sale_price": 200, "realised_returns": 0, "realised_total_cost": 100, "realised_holding_days": 10},
        # SKIP-correct
        {"sku": "SKU_SKIP_CORR", "realised_units_sold": 1, "realised_avg_sale_price": 50, "realised_returns": 0, "realised_total_cost": 100, "realised_holding_days": 10},
    ])
    out_path = tmp_path / "outcomes.csv"
    outcomes.to_csv(out_path, index=False)
    
    res = run_backtest(man_path, out_path)
    
    cm = res["confusion_matrix"]
    assert cm["BUY-profitable"] == 1
    assert cm["BUY-loss"] == 1
    assert cm["SKIP-would-profit"] == 1
    assert cm["SKIP-correct"] == 1

def test_predicted_vs_actual_correlation_in_range(tmp_path):
    manifest = pd.DataFrame([
        {"sku": "S1", "product_name": "A", "mrp": 1000, "floor_price": 100, "condition": "new", "quantity": 1},
        {"sku": "S2", "product_name": "B", "mrp": 2000, "floor_price": 200, "condition": "new", "quantity": 1},
    ])
    man_path = tmp_path / "man.csv"
    manifest.to_csv(man_path, index=False)
    
    outcomes = pd.DataFrame([
        {"sku": "S1", "realised_units_sold": 1, "realised_avg_sale_price": 200, "realised_returns": 0, "realised_total_cost": 100, "realised_holding_days": 10},
        {"sku": "S2", "realised_units_sold": 1, "realised_avg_sale_price": 400, "realised_returns": 0, "realised_total_cost": 200, "realised_holding_days": 10},
    ])
    out_path = tmp_path / "out.csv"
    outcomes.to_csv(out_path, index=False)
    
    res = run_backtest(man_path, out_path)
    corr = res["predicted_vs_actual"]["roi_correlation"]
    assert -1.0 <= corr <= 1.0

def test_threshold_sweep_monotonicity(tmp_path):
    manifest = pd.DataFrame([
        {"sku": "S1", "product_name": "Galaxy S22", "mrp": 1000, "floor_price": 10, "condition": "new", "quantity": 1},
    ])
    man_path = tmp_path / "man.csv"
    manifest.to_csv(man_path, index=False)
    outcomes = pd.DataFrame([
        {"sku": "S1", "realised_units_sold": 1, "realised_avg_sale_price": 800, "realised_returns": 0, "realised_total_cost": 100, "realised_holding_days": 10},
    ])
    out_path = tmp_path / "out.csv"
    outcomes.to_csv(out_path, index=False)
    
    res = run_backtest(man_path, out_path)
    vals = list(res["threshold_sweep"]["buy_score_min"].values())
    buys = [v["buys"] for v in vals]
    assert sorted(buys, reverse=True) == buys
