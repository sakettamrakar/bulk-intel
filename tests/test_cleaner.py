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
