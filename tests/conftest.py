"""Pytest fixtures shared across the test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make the project root importable when tests are run from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_manifest_path() -> Path:
    """Return the bundled sample manifest CSV path."""
    return ROOT / "data" / "sample_manifest.csv"


@pytest.fixture
def tiny_manifest_df() -> pd.DataFrame:
    """A minimal canonical-schema DataFrame for unit tests."""
    return pd.DataFrame(
        {
            "sku": ["A1", "A2", "A3"],
            "product_name": [
                "Samsung Galaxy Buds Wireless Earbuds",
                "Generic Notebook Diary Set",
                "Nike Running Shoes Mens",
            ],
            "category": [pd.NA, pd.NA, "apparel"],
            "brand": [pd.NA, pd.NA, "Nike"],
            "quantity": [10, 50, 5],
            "mrp": [10000.0, 500.0, 5000.0],
            "floor_price": [3500.0, 100.0, 1900.0],
            "condition": ["New", "New", "Open Box"],
        }
    )
