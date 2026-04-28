"""Backtest harness for threshold calibration.

usage: python -m tools.backtest --manifest MANIFEST_CSV --outcomes OUTCOMES_CSV [--report report.json]

Joins the engine's per-row predictions (run on the manifest) to realised
outcomes (per the outcomes CSV) by sku, and emits a JSON report.

Confusion matrix definitions:
- BUY-profitable: recommendation == "BUY" and realised unit_profit > 0
- BUY-loss: recommendation == "BUY" and realised unit_profit <= 0
- SKIP-correct: recommendation == "SKIP" and realised unit_profit <= 0
- SKIP-would-profit: recommendation == "SKIP" and realised unit_profit > 0
- REVIEW: excluded from matrix
"""
import argparse
import json
import logging
from pathlib import Path
from typing import Mapping

import pandas as pd

from pipeline.run_pipeline import Pipeline
from config.settings import Settings

logger = logging.getLogger(__name__)

def run_backtest(
    manifest_path: str,
    outcomes_path: str,
    profit_cutoff: float = 0.0
) -> dict:
    
    outcomes_df = pd.read_csv(outcomes_path)
    if "sku" not in outcomes_df.columns:
        raise ValueError("Outcomes CSV must have 'sku' column")
        
    pipeline = Pipeline()
    from ingestion.loader import ManifestLoader
    loader = ManifestLoader()
    df_raw = loader.load(manifest_path)
    
    # We want to run the pipeline but intercept before reporting
    df_scored = pipeline.run_dataframe(df_raw)
    
    # Merge
    merged = pd.merge(df_scored, outcomes_df, on="sku", how="inner")
    
    if merged.empty:
        return {
            "manifest": str(manifest_path),
            "rows_predicted": len(df_scored),
            "rows_with_outcome": 0,
            "confusion_matrix": {},
            "predicted_vs_actual": {},
            "threshold_sweep": {},
            "recommended_thresholds": {}
        }
        
    # Calculate realised metrics
    units_sold = merged["realised_units_sold"]
    returns = merged["realised_returns"].fillna(0)
    cost = merged["realised_total_cost"]
    price = merged["realised_avg_sale_price"]
    
    # Clean zeros
    valid_units = units_sold > 0
    merged["realised_unit_profit"] = 0.0
    merged.loc[valid_units, "realised_unit_profit"] = (
        (price * (units_sold - returns) - cost) / units_sold
    )
    
    # Confusion matrix
    def get_matrix(df_m):
        mat = {"BUY-profitable": 0, "BUY-loss": 0, "SKIP-would-profit": 0, "SKIP-correct": 0}
        
        buy_prof = df_m[(df_m["recommendation"] == "BUY") & (df_m["realised_unit_profit"] > profit_cutoff)]
        buy_loss = df_m[(df_m["recommendation"] == "BUY") & (df_m["realised_unit_profit"] <= profit_cutoff)]
        skip_prof = df_m[(df_m["recommendation"] == "SKIP") & (df_m["realised_unit_profit"] > profit_cutoff)]
        skip_corr = df_m[(df_m["recommendation"] == "SKIP") & (df_m["realised_unit_profit"] <= profit_cutoff)]
        
        mat["BUY-profitable"] = len(buy_prof)
        mat["BUY-loss"] = len(buy_loss)
        mat["SKIP-would-profit"] = len(skip_prof)
        mat["SKIP-correct"] = len(skip_corr)
        return mat
        
    base_matrix = get_matrix(merged)
        
    # Predict vs Actual
    predicted_roi = merged["expected_roi_pct"]
    realised_revenue = price * (units_sold - returns)
    realised_roi = (realised_revenue - cost) / cost * 100.0
    realised_roi = realised_roi.replace([float('inf'), float('-inf')], 0.0).fillna(0.0)
    
    corr = predicted_roi.corr(realised_roi)
    if pd.isna(corr):
        corr = 0.0
        
    profit_pred = merged["expected_profit"]
    profit_actual = realised_revenue - cost
    mae = (profit_pred - profit_actual).abs().mean()
    if pd.isna(mae):
        mae = 0.0
    
    from scipy.stats import linregress
    if len(predicted_roi) > 1 and predicted_roi.std() > 0:
        slope, intercept, r, p, se = linregress(predicted_roi, realised_roi)
    else:
        slope, intercept = 0.0, 0.0
        
    pva = {
        "roi_correlation": round(corr, 4),
        "profit_mae": round(mae, 4),
        "calibration_slope": round(float(slope), 4) if not pd.isna(slope) else 0.0,
        "calibration_intercept": round(float(intercept), 4) if not pd.isna(intercept) else 0.0
    }
    
    # Sweep
    sweep = {
        "buy_score_min": {},
        "min_expected_roi_pct": {},
        "min_expected_margin_pct": {}
    }
    
    def run_sweep(param, values):
        res = {}
        for v in values:
            s_obj = Settings()
            d_thresh = dict(s_obj.decision_thresholds)
            d_thresh[param] = float(v)
            s_obj = Settings(decision_thresholds=d_thresh)
            
            p_sweep = Pipeline(settings=s_obj)
            df_sw = p_sweep.run_dataframe(df_raw)
            sw_m = pd.merge(df_sw, outcomes_df, on="sku", how="inner")
            
            sw_m["realised_unit_profit"] = 0.0
            vv = sw_m["realised_units_sold"] > 0
            sw_m.loc[vv, "realised_unit_profit"] = (
                (sw_m["realised_avg_sale_price"] * (sw_m["realised_units_sold"] - sw_m["realised_returns"].fillna(0)) - sw_m["realised_total_cost"]) / sw_m["realised_units_sold"]
            )
            
            mat = get_matrix(sw_m)
            
            buy_mask = sw_m["recommendation"] == "BUY"
            sw_buy = sw_m.loc[buy_mask]
            if not sw_buy.empty:
                realised_profit = (sw_buy["realised_avg_sale_price"] * (sw_buy["realised_units_sold"] - sw_buy["realised_returns"].fillna(0)) - sw_buy["realised_total_cost"]).sum()
            else:
                realised_profit = 0.0
                
            rec_count = len(sw_buy)
            precision = mat["BUY-profitable"] / rec_count if rec_count > 0 else 0.0
            
            res[str(v)] = {
                "buys": rec_count,
                "precision": round(precision, 4),
                "profit": round(float(realised_profit), 2)
            }
        return res
        
    # Using small sweeps to be faster
    s_buy = [30.0, 45.0, 60.0, 75.0, 90.0]
    sweep["buy_score_min"] = run_sweep("buy_score_min", s_buy)
    
    s_roi = [10.0, 15.0, 25.0, 40.0]
    sweep["min_expected_roi_pct"] = run_sweep("min_expected_roi_pct", s_roi)
    
    s_marg = [5.0, 10.0, 15.0, 25.0]
    sweep["min_expected_margin_pct"] = run_sweep("min_expected_margin_pct", s_marg)
    
    rec = {
        "buy_score_min": 60.0,
        "min_expected_roi_pct": 25.0,
        "min_expected_margin_pct": 15.0
    }
    
    def pick_best(results):
        best_v = None
        best_score = -float('inf')
        for vstr, metrics in results.items():
            score = metrics["profit"] * metrics["precision"]
            if score > best_score:
                best_score = score
                best_v = float(vstr)
        return best_v
        
    rec["buy_score_min"] = pick_best(sweep["buy_score_min"]) or 60.0
    rec["min_expected_roi_pct"] = pick_best(sweep["min_expected_roi_pct"]) or 25.0
    rec["min_expected_margin_pct"] = pick_best(sweep["min_expected_margin_pct"]) or 15.0
    
    return {
        "manifest": str(manifest_path),
        "rows_predicted": len(df_scored),
        "rows_with_outcome": len(merged),
        "confusion_matrix": base_matrix,
        "predicted_vs_actual": pva,
        "threshold_sweep": sweep,
        "recommended_thresholds": rec
    }

def cli(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--outcomes", required=True)
    parser.add_argument("--report", default="backtest_report.json")
    parser.add_argument("--profit-cutoff", type=float, default=0.0)
    args = parser.parse_args(argv)
    
    res = run_backtest(args.manifest, args.outcomes, args.profit_cutoff)
    with open(args.report, "w") as f:
        json.dump(res, f, indent=2)
    print(f"Wrote report to {args.report}")
    return 0

if __name__ == "__main__":
    raise SystemExit(cli())
