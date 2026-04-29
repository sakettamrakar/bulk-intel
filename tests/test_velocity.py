from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config.settings import get_settings
from intelligence.velocity import estimate_velocity
from tools.velocity_update import main as velocity_main


def test_sku_with_history_uses_per_sku_velocity():
    store = {"skus": {"A": {"observations": 5, "mean_sell_through_30d": 0.8, "last_observed": "2026-04-20"}}}
    row = pd.Series({"sku": "A", "category": "kitchen", "condition_normalized": "new"})
    v, c = estimate_velocity(row, store, get_settings())
    assert v == 0.8
    assert c > 0.9


def test_unseen_sku_falls_back_to_category():
    store = {"skus": {}, "category": {"kitchen": {"observations": 10, "mean_sell_through_30d": 0.6, "last_observed": "2026-04-20"}}}
    row = pd.Series({"sku": "X", "category": "kitchen", "condition_normalized": "new"})
    v, c = estimate_velocity(row, store, get_settings())
    assert v == 0.6
    assert 0 < c < 1


def test_no_history_falls_back_to_static_prior():
    row = pd.Series({"sku": "X", "category": "unknown", "condition_normalized": "not_tested"})
    v, c = estimate_velocity(row, {}, get_settings())
    assert v == 0.65
    assert c == 0.0


def test_velocity_confidence_scales_with_observations():
    row = pd.Series({"sku": "A", "category": "kitchen", "condition_normalized": "new"})
    low, low_c = estimate_velocity(row, {"skus": {"A": {"observations": 3, "mean_sell_through_30d": 0.5}}}, get_settings())
    high, high_c = estimate_velocity(row, {"skus": {"A": {"observations": 12, "mean_sell_through_30d": 0.5}}}, get_settings())
    assert low == high == 0.5
    assert low_c < high_c


def test_velocity_update_is_idempotent(tmp_path, monkeypatch):
    outcomes = tmp_path / "o.csv"
    outcomes.write_text("sku,category,condition_normalized,realised_units_sold,expected_units_sold\nA,kitchen,new,8,10\n", encoding="utf-8")
    store = tmp_path / "store.json"
    import sys
    monkeypatch.setattr(sys, "argv", ["x", "--outcomes", str(outcomes), "--store", str(store)])
    velocity_main()
    first = json.loads(store.read_text())
    monkeypatch.setattr(sys, "argv", ["x", "--outcomes", str(outcomes), "--store", str(store)])
    velocity_main()
    second = json.loads(store.read_text())
    assert first == second
