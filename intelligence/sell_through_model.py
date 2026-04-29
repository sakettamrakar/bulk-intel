from __future__ import annotations

from dataclasses import dataclass
import pickle
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SellThroughModel:
    """Simple wrapper around a fitted model/pipeline.

    Feature contract:
    category, condition_normalized, brand_known, discount_percentage,
    price_band, mrp, floor_to_mrp_ratio, category_demand_score,
    category_liquidity_score, amazon_bsr, quantity.
    """

    pipeline: object
    feature_cols: list[str]

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        x = df.reindex(columns=self.feature_cols).copy()
        if "amazon_bsr" in x:
            x["amazon_bsr"] = pd.to_numeric(x["amazon_bsr"], errors="coerce").fillna(x["amazon_bsr"].median())
        pred = np.asarray(self.pipeline.predict(x), dtype=float)
        pred = np.clip(pred, 0.0, 1.0)
        # Lightweight confidence proxy: farther from center => higher certainty.
        conf = np.clip(np.abs(pred - 0.5) * 2.0, 0.1, 1.0)
        return pd.DataFrame({"sell_through_pred": pred, "sell_through_conf": conf}, index=df.index)


def load_model(path: Path | str) -> SellThroughModel:
    with Path(path).open("rb") as f:
        return pickle.load(f)
