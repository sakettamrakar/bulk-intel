"""Cleaner tests — text normalisation, brand/category inference."""
from __future__ import annotations

from processing.cleaner import clean_manifest


def test_clean_strips_noise_and_titlecases(tiny_manifest_df):
    cleaned = clean_manifest(tiny_manifest_df)
    assert "Samsung Galaxy Buds Wireless Earbuds" in cleaned.loc[0, "product_name_clean"]
    # No double spaces, no parentheticals.
    assert "  " not in cleaned.loc[0, "product_name_clean"]


def test_clean_infers_brand_from_keywords(tiny_manifest_df):
    cleaned = clean_manifest(tiny_manifest_df)
    assert cleaned.loc[0, "brand"].lower() == "samsung"


def test_clean_infers_category_from_keywords(tiny_manifest_df):
    cleaned = clean_manifest(tiny_manifest_df)
    assert cleaned.loc[0, "category"] == "electronics"
    assert cleaned.loc[1, "category"] == "stationery"


def test_clean_keywords_are_deduplicated_and_lowercased(tiny_manifest_df):
    cleaned = clean_manifest(tiny_manifest_df)
    keywords = cleaned.loc[0, "keywords"]
    assert keywords == list(dict.fromkeys(keywords))
    assert all(k == k.lower() for k in keywords)


def test_brand_alias_amazon_brand_solimo_to_solimo():
    import pandas as pd
    from config.settings import Settings
    df = pd.DataFrame([{"product_name": "Something", "brand": "Amazon Brand - Solimo", "category": "unknown", "quantity": 1, "condition": "New", "mrp": 100, "floor_price": 50}])
    cleaned = clean_manifest(df, Settings())
    assert cleaned.loc[0, "brand"].lower() == "solimo"


def test_brand_alias_pigeon_by_stovekraft_to_pigeon():
    import pandas as pd
    from config.settings import Settings
    df = pd.DataFrame([{"product_name": "Something", "brand": "Pigeon by Stovekraft", "category": "unknown", "quantity": 1, "condition": "New", "mrp": 100, "floor_price": 50}])
    cleaned = clean_manifest(df, Settings())
    assert cleaned.loc[0, "brand"].lower() == "pigeon"


def test_unknown_brand_passthrough():
    import pandas as pd
    from config.settings import Settings
    df = pd.DataFrame([{"product_name": "Something", "brand": "Random Corp 123", "category": "unknown", "quantity": 1, "condition": "New", "mrp": 100, "floor_price": 50}])
    cleaned = clean_manifest(df, Settings())
    assert cleaned.loc[0, "brand"] == "Random_Corp_123".title()


def test_known_brand_count_grows_after_t203():
    from config.settings import KNOWN_BRANDS, BRAND_ALIASES
    assert len(KNOWN_BRANDS) >= 200
    assert len(BRAND_ALIASES) >= 14
