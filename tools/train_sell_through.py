"""Train a sell-through model from historical outcomes.

Usage:
python -m tools.train_sell_through --history data/historical/*.csv --out data/models/sell_through_v1.pkl
"""
from __future__ import annotations

import argparse
import glob
import pickle
from pathlib import Path

import pandas as pd

from intelligence.sell_through_model import SellThroughModel

FEATURE_COLS = [
    "category", "condition_normalized", "brand_known", "discount_percentage", "price_band",
    "mrp", "floor_to_mrp_ratio", "category_demand_score", "category_liquidity_score", "amazon_bsr", "quantity",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    files = []
    for p in args.history:
        files.extend(glob.glob(p))
    frames = [pd.read_csv(f) for f in files if f.endswith('.csv')]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(df) < 10:
        raise SystemExit("Need at least 10 rows of history")

    target = (pd.to_numeric(df.get("realised_units_sold", 0), errors="coerce").fillna(0) /
              pd.to_numeric(df.get("expected_units_sold", 1), errors="coerce").replace(0, 1).fillna(1)).clip(0, 1)
    x = df.copy()
    x["brand_known"] = x.get("brand", "").astype(str).str.len() > 0
    x["price_band"] = pd.cut(pd.to_numeric(x.get("mrp", 0), errors="coerce").fillna(0), [-1, 300, 1000, 1e12], labels=["LOW", "MID", "HIGH"]).astype(str)
    x["floor_to_mrp_ratio"] = (pd.to_numeric(x.get("floor_price", 0), errors="coerce").fillna(0) /
                               pd.to_numeric(x.get("mrp", 1), errors="coerce").replace(0, 1).fillna(1))
    x["category_demand_score"] = 50.0
    x["category_liquidity_score"] = 50.0

    wrapped = SellThroughModel(pipeline=_fit_model(x[FEATURE_COLS], target), feature_cols=FEATURE_COLS)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        pickle.dump(wrapped, f)


if __name__ == "__main__":
    main()


class _FallbackMeanModel:
    def __init__(self, mean: float):
        self.mean = float(mean)

    def predict(self, x):
        return [self.mean] * len(x)


def _fit_model(x, y):
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder

        cat_cols = ["category", "condition_normalized", "price_band"]
        num_cols = [c for c in FEATURE_COLS if c not in cat_cols]
        pre = ColumnTransformer([
            ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat_cols),
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num_cols),
        ])
        pipe = Pipeline([("pre", pre), ("model", GradientBoostingRegressor(random_state=42))])
        pipe.fit(x, y)
        return pipe
    except Exception:
        return _FallbackMeanModel(float(y.mean()))
