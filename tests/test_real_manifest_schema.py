"""Regression tests for real-manifest schema handling.

These cover Bulk4Traders-shaped inputs (Tag Number, MRP ( in INR ),
hierarchical Category L1..Ln columns) and condition normalization.
"""
from __future__ import annotations

import pandas as pd

from ingestion.loader import load_manifest
from processing.cleaner import clean_manifest


def _write_b4t_csv(tmp_path):
    p = tmp_path / "b4t.csv"
    p.write_text(
        "Title,Tag Number,Category L1,Category L2,Category L3,Brand,MRP ( in INR ),Quantity,Grade,Floor Price\n"
        "Pigeon Mixer Grinder,bb-1,Others,Kitchenware,Mixer,Pigeon,4500,1,Not Tested,800\n"
        "Lifelong Gas Stove 2 Burner,bb-2,Others,Cooking items,,Lifelong,3000,1,As-Is,500\n"
        "Random Misc Item,bb-3,Others,,,Brand,1000,2,New,300\n"
    )
    return p


def test_loader_aliases_b4t_columns(tmp_path):
    df = load_manifest(_write_b4t_csv(tmp_path))
    assert df["sku"].tolist() == ["bb-1", "bb-2", "bb-3"]
    assert df["mrp"].tolist() == [4500.0, 3000.0, 1000.0]
    assert df["quantity"].tolist() == [1, 1, 2]
    assert df["floor_price"].tolist() == [800.0, 500.0, 300.0]


def test_loader_retains_hierarchical_categories(tmp_path):
    df = load_manifest(_write_b4t_csv(tmp_path))
    assert df.loc[0, "raw_category"] == "Others > Kitchenware > Mixer"
    assert df.loc[1, "raw_category"] == "Others > Cooking items"
    assert df.loc[2, "raw_category"] == "Others"


def test_cleaner_normalizes_condition(tmp_path):
    df = load_manifest(_write_b4t_csv(tmp_path))
    df = clean_manifest(df)
    assert df.loc[0, "condition_normalized"] == "defective"
    assert df.loc[1, "condition_normalized"] == "defective"
    assert df.loc[2, "condition_normalized"] == "new"


def test_cleaner_keeps_existing_category_when_known(tmp_path):
    """If `category` is already populated and recognised, don't overwrite it."""
    df = pd.DataFrame(
        {
            "sku": ["x"],
            "product_name": ["Random unrelated text"],
            "category": ["kitchen"],
            "brand": ["Pigeon"],
            "quantity": [1],
            "mrp": [1000],
            "floor_price": [200],
            "condition": ["New"],
        }
    )
    cleaned = clean_manifest(df)
    assert cleaned.loc[0, "category"] == "kitchen"
