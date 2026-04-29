"""Tests for the T-306 Monte Carlo confidence-interval engine."""
from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from config.settings import Settings, get_settings
from intelligence.decision import decide
from intelligence.profit import compute_profitability


CI_COLUMNS = (
    "expected_profit_p5",
    "expected_profit_p50",
    "expected_profit_p95",
    "expected_roi_p5",
    "expected_roi_p95",
    "prob_profit_positive",
)


def _profitable_row() -> pd.DataFrame:
    return pd.DataFrame([{
        "sku": "PROF-1",
        "quantity": 50,
        "floor_price": 50.0,
        "real_price": 400.0,
        "mrp": 800.0,
        "platform": "amazon",
        "category": "books",  # low return rate, low transport
        "condition_normalized": "new",
    }])


def _marginal_row() -> pd.DataFrame:
    """A row whose point-estimate profit sits very near zero (≈ ₹17 on ₹1k)."""
    return pd.DataFrame([{
        "sku": "MARG-1",
        "quantity": 10,
        "floor_price": 100.0,
        "real_price": 350.0,
        "mrp": 800.0,
        "platform": "amazon",
        "category": "books",
        "condition_normalized": "new",
    }])


def test_ci_columns_present():
    out = compute_profitability(_profitable_row())
    for col in CI_COLUMNS:
        assert col in out.columns, f"missing {col}"


def test_median_matches_point_estimate():
    out = compute_profitability(_profitable_row())
    median = float(out.iloc[0]["expected_profit_p50"])
    point = float(out.iloc[0]["expected_profit"])
    # Within 5% — Monte Carlo + Beta-mean coupling will not be exact.
    assert median == pytest.approx(point, rel=0.05, abs=50.0)


def test_p95_greater_than_p5():
    out = compute_profitability(_profitable_row())
    p5 = float(out.iloc[0]["expected_profit_p5"])
    p95 = float(out.iloc[0]["expected_profit_p95"])
    assert p95 > p5
    roi5 = float(out.iloc[0]["expected_roi_p5"])
    roi95 = float(out.iloc[0]["expected_roi_p95"])
    assert roi95 > roi5


def test_prob_positive_high_for_profitable_row():
    out = compute_profitability(_profitable_row())
    assert float(out.iloc[0]["prob_profit_positive"]) > 0.9


def test_prob_positive_low_for_marginal_row():
    out = compute_profitability(_marginal_row())
    prob = float(out.iloc[0]["prob_profit_positive"])
    # near break-even: somewhere between 0.2 and 0.8
    assert 0.2 < prob < 0.8


def test_ci_is_deterministic_for_same_manifest():
    df = _profitable_row()
    a = compute_profitability(df)
    b = compute_profitability(df)
    for col in CI_COLUMNS:
        assert float(a.iloc[0][col]) == float(b.iloc[0][col])


def test_lot_summary_includes_bands():
    df = _profitable_row()
    decided = decide(df)
    summary = decided.attrs["lot_summary"]
    assert "profit_band_90pct" in summary
    assert "roi_band_90pct" in summary
    assert "prob_lot_profitable" in summary
    band = summary["profit_band_90pct"]
    assert band["high"] >= band["median"] >= band["low"]


def test_zero_samples_returns_no_ci_values():
    base = get_settings()
    settings = replace(
        base,
        profit_assumptions={**base.profit_assumptions, "mc_samples": 0},
    )
    df = _profitable_row()
    out = compute_profitability(df, settings)
    # When mc_samples = 0 the helper returns empty Series — pandas fills the
    # column with NaN for the existing index of length 1.
    assert pd.isna(out.iloc[0]["expected_profit_p5"])
