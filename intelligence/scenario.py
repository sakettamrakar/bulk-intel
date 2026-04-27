import pandas as pd
import numpy as np
from config.settings import get_settings

def compute_scenarios(df: pd.DataFrame) -> pd.DataFrame:
    """Computes ROI scenarios (LOW, MEDIAN, HIGH) varying sell_through and price_realization."""
    out = df.copy()
    settings = get_settings()
    a = settings.profit_assumptions

    qty = pd.to_numeric(out.get("quantity", pd.Series(1, index=out.index)), errors="coerce").fillna(1)
    floor = pd.to_numeric(out.get("floor_price", pd.Series(0, index=out.index)), errors="coerce")
    mrp = pd.to_numeric(out.get("mrp", pd.Series(0, index=out.index)), errors="coerce")

    if "real_price" in out:
        real_price = pd.to_numeric(out["real_price"], errors="coerce")
    else:
        real_price = mrp * a.get("expected_sell_price_vs_mrp", 0.45)

    lot_cost = qty * floor

    scenarios = {
        "low": {"sell_through": 0.50, "price_realization": 0.60},
        "median": {"sell_through": 0.65, "price_realization": 0.75},
        "high": {"sell_through": 0.80, "price_realization": 0.90},
    }

    for scenario_name, params in scenarios.items():
        st = params["sell_through"]
        pr = params["price_realization"]

        expected_revenue = real_price * qty * st * pr

        with np.errstate(invalid="ignore", divide="ignore"):
            roi = np.where(
                lot_cost > 0,
                ((expected_revenue - lot_cost) / lot_cost) * 100.0,
                np.nan
            )

        out[f"roi_{scenario_name}"] = pd.Series(roi, index=out.index).round(2)

    return out
