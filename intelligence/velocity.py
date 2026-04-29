from __future__ import annotations

"""Velocity estimator with fallback chain and confidence decay.

Priority:
1) SKU-level if observations >= 3
2) Category+condition aggregate
3) Category aggregate
4) Static prior

Confidence uses min(1, observations/5), scaled for aggregate levels, and decays
linearly to 0 when last_observed is older than 180 days.
"""

from datetime import date
from pathlib import Path
import json

import pandas as pd

from config.settings import Settings


DEFAULT_STORE_PATH = Path("data/velocity/store.json")


def load_velocity_store(path: Path | str = DEFAULT_STORE_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return {"schema_version": 1, "as_of": None, "skus": {}, "category_condition": {}, "category": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def estimate_velocity(row: pd.Series, store: dict, settings: Settings) -> tuple[float, float]:
    factors = settings.condition_to_sell_through
    cond = str(row.get("condition_normalized", "unknown"))
    static = min(settings.profit_assumptions.get("expected_sellable_pct", 0.65), factors.get(cond, factors["unknown"])["sellable_factor"])

    sku = str(row.get("sku", ""))
    cat = str(row.get("category", "unknown")).lower()

    sku_data = store.get("skus", {}).get(sku)
    if sku_data and int(sku_data.get("observations", 0)) >= 3:
        v = float(sku_data.get("mean_sell_through_30d", static))
        c = min(1.0, int(sku_data.get("observations", 0)) / 5.0)
        return v, _decay_confidence(c, sku_data.get("last_observed"))

    cc_key = f"{cat}|{cond}"
    cc = store.get("category_condition", {}).get(cc_key)
    if cc and int(cc.get("observations", 0)) >= 2:
        v = float(cc.get("mean_sell_through_30d", static))
        c = min(1.0, int(cc.get("observations", 0)) / 5.0) * 0.7
        return v, _decay_confidence(c, cc.get("last_observed"))

    cdata = store.get("category", {}).get(cat)
    if cdata and int(cdata.get("observations", 0)) >= 2:
        v = float(cdata.get("mean_sell_through_30d", static))
        c = min(1.0, int(cdata.get("observations", 0)) / 5.0) * 0.5
        return v, _decay_confidence(c, cdata.get("last_observed"))

    return static, 0.0


def _decay_confidence(base: float, last_observed: str | None) -> float:
    if not last_observed:
        return max(0.0, min(1.0, base))
    try:
        d = date.fromisoformat(last_observed)
    except ValueError:
        return max(0.0, min(1.0, base))
    days = (date.today() - d).days
    if days <= 180:
        return max(0.0, min(1.0, base))
    decay = max(0.0, 1.0 - ((days - 180) / 180.0))
    return max(0.0, min(1.0, base * decay))
