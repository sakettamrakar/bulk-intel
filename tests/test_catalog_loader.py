"""Tests for catalog loader."""
import json
from pathlib import Path

import pandas as pd
import pytest

from enrichment.catalog_loader import load_catalog
from pipeline.run_pipeline import Pipeline

def test_load_catalog_happy_path(tmp_path):
    catalog_path = "data/catalog/india_top1k_v1.json"
    if Path(catalog_path).exists():
        items = load_catalog(catalog_path)
        assert len(items) >= 1000

def test_catalog_schema_required_fields(tmp_path):
    bad = tmp_path / "bad.json"
    with open(bad, "w") as f:
        json.dump({"schema_version": 1, "items": [{"product_name": "No price"}]}, f)
        
    with pytest.raises(ValueError, match="missing amazon_price"):
        load_catalog(bad)

def test_catalog_age_warning(tmp_path, caplog):
    import logging
    old = tmp_path / "old.json"
    with open(old, "w") as f:
        json.dump({"schema_version": 1, "rates_as_of": "2020-01-01", "items": [{"product_name": "A", "amazon_price": 100}]}, f)
        
    with caplog.at_level(logging.WARNING):
        load_catalog(old)
        
    assert "older than 90 days" in caplog.text

def test_pipeline_uses_catalog_for_known_skus(tmp_path):
    cat = tmp_path / "cat.json"
    with open(cat, "w") as f:
        json.dump({
            "schema_version": 1,
            "items": [{"product_name": "Unique Test Item", "amazon_price": 777.0, "wholesale_price": 555.0}]
        }, f)
        
    import os
    os.environ["BULK_INTEL_CATALOG_PATH"] = str(cat)
    
    # We must reload default factory because get_settings doesn't rebuild pipeline providers?
    # Actually Pipeline class has a default factory for providers. Let's just pass it manually.
    from enrichment.enricher import FuzzyCatalogPriceProvider, MRPHeuristicPriceProvider
    cat_items = load_catalog(cat)
    pipe = Pipeline(
        providers=[
            FuzzyCatalogPriceProvider(catalog=cat_items, confidence_threshold=0.6),
            MRPHeuristicPriceProvider()
        ]
    )
    
    df = pd.DataFrame([
        {"sku": "A1", "product_name": "Unique Test Item", "mrp": 1000, "floor_price": 100, "condition": "new", "quantity": 1, "brand": "test"}
    ])
    
    res = pipe.run_dataframe(df)
    
    assert res.loc[0, "amazon_price"] == 777.0
    assert res.loc[0, "wholesale_price"] == 555.0
    assert res.loc[0, "match_confidence"] > 0.6
