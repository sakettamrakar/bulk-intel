from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from intelligence.velocity import load_velocity_store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outcomes", required=True)
    ap.add_argument("--store", default="data/velocity/store.json")
    args = ap.parse_args()

    store_path = Path(args.store)
    store = load_velocity_store(store_path)
    ingested = set(store.get("ingested_files", []))
    if str(Path(args.outcomes).resolve()) in ingested:
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
        return

    df = pd.read_csv(args.outcomes)

    df["sell_through"] = (pd.to_numeric(df.get("realised_units_sold", 0), errors="coerce").fillna(0) /
                          pd.to_numeric(df.get("expected_units_sold", 1), errors="coerce").replace(0, 1).fillna(1)).clip(0, 1)
    df["category"] = df.get("category", "unknown").astype(str).str.lower()
    df["condition_normalized"] = df.get("condition_normalized", "unknown").astype(str)

    for _, row in df.sort_values(by=["sku"]).iterrows():
        _update_bucket(store.setdefault("skus", {}), str(row.get("sku", "")), row["sell_through"])
        _update_bucket(store.setdefault("category", {}), row["category"], row["sell_through"])
        _update_bucket(store.setdefault("category_condition", {}), f"{row['category']}|{row['condition_normalized']}", row["sell_through"])

    ingested.add(str(Path(args.outcomes).resolve()))
    store["ingested_files"] = sorted(ingested)
    store["schema_version"] = 1
    store["as_of"] = date.today().isoformat()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def _update_bucket(root: dict, key: str, val: float) -> None:
    bucket = root.setdefault(key, {"observations": 0, "sum_sell_through": 0.0, "sum_sq": 0.0})
    bucket["observations"] += 1
    bucket["sum_sell_through"] += float(val)
    bucket["sum_sq"] += float(val) ** 2
    n = bucket["observations"]
    mean = bucket["sum_sell_through"] / n
    var = max(0.0, (bucket["sum_sq"] / n) - (mean ** 2))
    bucket["mean_sell_through_30d"] = round(mean, 6)
    bucket["mean_sell_through_90d"] = round(mean, 6)
    bucket["stddev_sell_through"] = round(var ** 0.5, 6)
    bucket["last_observed"] = date.today().isoformat()


if __name__ == "__main__":
    main()
