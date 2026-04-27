"""Per-row ROI stress-tests under low/median/high scenarios.

For each row the engine projects a single deterministic ROI in
``intelligence/profit.py``.  This module layers three "what if"
scenarios on top so an operator can see how sensitive each line item
is to sell-through and price-realisation assumptions.

Output columns (added in place):
    - ``scenario_roi_low``    : pessimistic (50 % sell-through, 60 % realisation)
    - ``scenario_roi_median`` : base case (65 %, 75 %)
    - ``scenario_roi_high``   : optimistic (80 %, 90 %)

Distinct from the *lot-level* quartile keys ``roi_low``/``roi_median``
/``roi_high`` in :data:`out.attrs["lot_summary"]` (which describe the
spread of ``expected_roi_pct`` across the manifest, not per-row stress
tests) — name them differently to avoid downstream confusion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import Settings, get_settings


SCENARIOS: dict[str, dict[str, float]] = {
    "low":    {"sell_through": 0.50, "price_realization": 0.60},
    "median": {"sell_through": 0.65, "price_realization": 0.75},
    "high":   {"sell_through": 0.80, "price_realization": 0.90},
}


def compute_scenarios(
    df: pd.DataFrame, settings: Settings | None = None
) -> pd.DataFrame:
    """Add ``scenario_roi_low/median/high`` columns to ``df``.

    Args:
        df: A profit-enriched manifest (must contain ``quantity``,
            ``floor_price`` and either ``real_price`` or ``mrp``).
        settings: Optional override; falls back to :func:`get_settings`.

    Returns:
        A copy of ``df`` with three new ROI columns expressed as
        percentages of ``lot_cost = quantity * floor_price``.
    """
    out = df.copy()
    a = (settings or get_settings()).profit_assumptions

    qty = pd.to_numeric(out.get("quantity", pd.Series(1, index=out.index)), errors="coerce").fillna(1)
    floor = pd.to_numeric(out.get("floor_price", pd.Series(0, index=out.index)), errors="coerce")
    mrp = pd.to_numeric(out.get("mrp", pd.Series(0, index=out.index)), errors="coerce")

    if "real_price" in out:
        real_price = pd.to_numeric(out["real_price"], errors="coerce")
    else:
        real_price = mrp * a.get("expected_sell_price_vs_mrp", 0.45)

    lot_cost = qty * floor

    for scenario_name, params in SCENARIOS.items():
        expected_revenue = real_price * qty * params["sell_through"] * params["price_realization"]
        with np.errstate(invalid="ignore", divide="ignore"):
            roi = np.where(
                lot_cost > 0,
                ((expected_revenue - lot_cost) / lot_cost) * 100.0,
                np.nan,
            )
        out[f"scenario_roi_{scenario_name}"] = pd.Series(roi, index=out.index).round(2)

    return out
