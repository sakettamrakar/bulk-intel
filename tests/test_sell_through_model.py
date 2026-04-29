from __future__ import annotations

import pickle

import pandas as pd

from intelligence.profit import compute_profitability
from intelligence.sell_through_model import SellThroughModel


class Dummy:
    def predict(self, x):
        return [0.7] * len(x)


def _row():
    return pd.DataFrame([{"sku": "A", "quantity": 10, "floor_price": 10, "mrp": 100, "real_price": 60, "category": "kitchen", "condition_normalized": "new"}])


def test_pipeline_works_without_model_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = compute_profitability(_row())
    assert "expected_profit" in out.columns


def test_model_predict_in_range():
    m = SellThroughModel(Dummy(), ["category"])
    out = m.predict(pd.DataFrame([{"category": "kitchen"}]))
    assert 0 <= out.iloc[0]["sell_through_pred"] <= 1


def test_model_loaded_when_present(tmp_path, monkeypatch):
    model_path = tmp_path / "data/models/sell_through_v1.pkl"
    model_path.parent.mkdir(parents=True)
    with model_path.open("wb") as f:
        pickle.dump(SellThroughModel(Dummy(), ["category"]), f)
    monkeypatch.chdir(tmp_path)
    out = compute_profitability(_row())
    assert "sell_through_pred" in out.columns


def test_training_script_runs_on_synthetic_data(tmp_path):
    from tools.train_sell_through import main
    hist = tmp_path / "h.csv"
    hist.write_text("sku,category,condition_normalized,brand,mrp,floor_price,amazon_bsr,discount_percentage,quantity,realised_units_sold,expected_units_sold\nA,kitchen,new,abc,1000,300,100,20,5,4,5\nB,kitchen,new,abc,900,300,120,20,5,4,5\nC,kitchen,new,abc,800,300,130,20,5,4,5\nD,kitchen,new,abc,700,300,140,20,5,4,5\nE,kitchen,new,abc,600,300,150,20,5,4,5\nF,kitchen,new,abc,500,300,160,20,5,4,5\nG,kitchen,new,abc,400,300,170,20,5,4,5\nH,kitchen,new,abc,300,200,180,20,5,4,5\nI,kitchen,new,abc,1200,300,190,20,5,4,5\nJ,kitchen,new,abc,1100,300,200,20,5,4,5\n", encoding="utf-8")
    outp = tmp_path / "m.pkl"
    import sys
    sys.argv = ["x", "--history", str(hist), "--out", str(outp)]
    main()
    assert outp.exists()
