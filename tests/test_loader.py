"""Loader tests — schema normalisation and missing-data handling."""
from __future__ import annotations

import pandas as pd

from ingestion.loader import CANONICAL_COLUMNS, load_manifest


def test_load_sample_csv_canonical_schema(sample_manifest_path):
    df = load_manifest(sample_manifest_path)
    for col in CANONICAL_COLUMNS:
        assert col in df.columns, f"missing canonical column {col}"
    assert len(df) == 15


def test_load_handles_quantity_default(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("SKU,Product,MRP,Floor Price\nX1,Sample item,100,40\n")
    df = load_manifest(p)
    assert df.loc[0, "quantity"] == 1


def test_load_drops_fully_empty_rows(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("SKU,Product,MRP,Floor Price\n,,100,40\nX1,Item,100,40\n")
    df = load_manifest(p)
    assert len(df) == 1
    assert df.loc[0, "sku"] == "X1"


def test_load_coerces_numeric_with_garbage(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("SKU,Product,MRP,Floor Price\nX1,Item,abc,40\n")
    df = load_manifest(p)
    assert pd.isna(df.loc[0, "mrp"])
    assert df.loc[0, "floor_price"] == 40
