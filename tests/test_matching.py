from __future__ import annotations

import pytest
import pandas as pd

from config.settings import Settings
from enrichment.enricher import FuzzyCatalogPriceProvider
from intelligence.matching import compute_match_score, extract_model_tokens


def _row(title: str, brand: str = "Logitech", category: str = "electronics") -> dict:
    return {
        "product_name_clean": title,
        "brand": brand,
        "normalized_category": category,
    }


def _candidate(title: str, brand: str = "Logitech", category: str = "electronics") -> dict:
    return {
        "title": title,
        "brand": brand,
        "category": category,
    }


def test_identical_titles_score_one():
    result = compute_match_score(
        _row("Logitech Wireless Mouse", "Logitech"),
        _candidate("Logitech Wireless Mouse", "Logitech"),
        Settings(),
    )
    assert result.score >= 0.99
    assert result.decision == "accept"


def test_logitech_m185_variants_accept():
    result = compute_match_score(
        _row("Logitech Wireless Mouse M185"),
        _candidate("Logitech M185 Mouse Black"),
        Settings(),
    )
    assert result.decision == "accept"


def test_different_models_same_brand_reject():
    result = compute_match_score(
        _row("Logitech M185 Mouse"),
        _candidate("Logitech M720 Mouse"),
        Settings(),
    )
    assert result.decision in {"weak", "reject"}
    assert result.features.model < 0.5


def test_brand_mismatch_hard_rejects():
    result = compute_match_score(
        _row("Sony WH-1000XM5 Headphones", "Sony"),
        _candidate("Boat Rockerz 550 Headphones", "Boat"),
        Settings(),
    )
    assert result.decision == "reject"
    assert "brand_mismatch" in result.reasons


def test_category_mismatch_hard_rejects():
    result = compute_match_score(
        _row("Logitech M185 Mouse", "Logitech", "electronics"),
        _candidate("Logitech M185 Mouse", "Logitech", "apparel"),
        Settings(),
    )
    assert result.decision == "reject"
    assert "category_mismatch" in result.reasons


def test_weak_band_when_only_one_feature_strong():
    result = compute_match_score(
        _row("Logitech Mouse Wireless"),
        _candidate("Logitech Mouse Wireless Pro"),
        Settings(),
    )
    assert 0.65 <= result.score < 0.80
    assert result.decision == "weak"


def test_score_is_deterministic():
    row = _row("Logitech Wireless Mouse M185")
    candidate = _candidate("Logitech M185 Mouse Black")
    scores = [compute_match_score(row, candidate, Settings()).score for _ in range(10)]
    assert len(set(scores)) == 1


def test_score_features_sum_to_weighted_total():
    settings = Settings()
    result = compute_match_score(
        _row("Logitech Wireless Mouse M185"),
        _candidate("Logitech M185 Mouse Black"),
        settings,
    )
    weighted = sum(
        settings.match_token_weights[key] * getattr(result.features, key)
        for key in settings.match_token_weights
    )
    assert result.score == pytest.approx(weighted, abs=1e-5)


def test_extract_model_tokens_canonical_examples():
    tokens = extract_model_tokens(
        "M185 WH-1000XM5 WH1000XM5 RTX3060 B07VR7VY1Y USB 4K the",
        Settings(),
    )
    assert "M185" in tokens
    assert "WH1000XM5" in tokens
    assert "RTX3060" in tokens
    assert "B07VR7VY1Y" in tokens
    assert "USB" not in tokens
    assert "4K" not in tokens
    assert "THE" not in tokens


def test_brand_alias_override():
    result = compute_match_score(
        _row("Sony WH1000XM5 Headphones", "Sony"),
        _candidate("Sonny WH1000XM5 Headphones", "Sonny"),
        Settings(),
    )
    assert result.score >= 0.92
    assert result.decision == "accept"
    assert "brand_mismatch_override" in result.reasons


def test_fuzzy_catalog_provider_uses_new_scorer():
    provider = FuzzyCatalogPriceProvider(
        catalog=[
            {
                "product_name": "Logitech M185 Mouse Black",
                "brand": "Logitech",
                "category": "electronics",
                "amazon_price": 899.0,
                "wholesale_price": 550.0,
            }
        ],
        confidence_threshold=0.8,
    )
    amazon, wholesale, confidence = provider.lookup(pd.Series(_row("Logitech Wireless Mouse M185")))
    assert amazon == 899.0
    assert wholesale == 550.0
    assert confidence > 0.8
