"""T-305 — outcome feedback loop tests."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pandas as pd
import pytest

from tools.feedback_update import (
    aggregate_by_category,
    diff_priors,
    main,
    shrink,
    update_priors,
)


def _write_outcomes(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_current_priors(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "version": "v0",
            "created_at": "2026-04-29",
            "source_observations": 0,
            "category_return_rate": {"books": 0.04, "apparel": 0.22},
            "category_holding_days": {"books": 180, "apparel": 120},
            "condition_to_sell_through": {"new": {"sellable_factor": 1.0, "risk_score": 10.0}},
        }),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Settings loader
# ---------------------------------------------------------------------------


def test_priors_file_loaded_when_present(tmp_path, monkeypatch):
    priors_file = tmp_path / "custom.json"
    priors_file.write_text(
        json.dumps({
            "version": "v9",
            "category_return_rate": {"books": 0.99},
            "category_holding_days": {"books": 999},
            "condition_to_sell_through": {},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("BULK_INTEL_PRIORS_PATH", str(priors_file))
    import config.settings as settings_module
    importlib.reload(settings_module)
    s = settings_module.get_settings()
    assert s.category_return_rate["books"] == 0.99
    assert s.category_holding_days["books"] == 999


def test_priors_fallback_to_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("BULK_INTEL_PRIORS_PATH", str(tmp_path / "nope.json"))
    import config.settings as settings_module
    importlib.reload(settings_module)
    s = settings_module.get_settings()
    assert s.category_return_rate["books"] == 0.04
    assert s.category_holding_days["books"] == 180


# ---------------------------------------------------------------------------
# Bayesian shrinkage
# ---------------------------------------------------------------------------


def test_bayesian_update_shrinks_to_prior_when_n_small():
    out = shrink(prior=0.10, observed=0.50, n=1, alpha=20)
    assert abs(out - 0.10) < abs(out - 0.50)
    assert 0.11 < out < 0.13


def test_bayesian_update_dominated_by_data_when_n_large():
    out = shrink(prior=0.10, observed=0.50, n=200, alpha=20)
    assert abs(out - 0.50) < abs(out - 0.10)
    assert out > 0.40


# ---------------------------------------------------------------------------
# Aggregation + update_priors
# ---------------------------------------------------------------------------


def test_aggregate_by_category_computes_realised_return_rate():
    df = pd.DataFrame([
        {"sku": "A", "category": "books", "quantity": 10,
         "realised_units_sold": 8, "realised_returns": 1, "realised_holding_days": 100},
        {"sku": "B", "category": "books", "quantity": 10,
         "realised_units_sold": 4, "realised_returns": 0, "realised_holding_days": 60},
    ])
    agg = aggregate_by_category(df)
    assert agg["books"]["observations"] == 2
    # 1 / (8+4) = 0.0833
    assert agg["books"]["return_rate"] == pytest.approx(1 / 12, abs=1e-3)


def test_update_priors_only_moves_observed_categories():
    current = {
        "version": "v0",
        "source_observations": 0,
        "category_return_rate": {"books": 0.04, "apparel": 0.22},
        "category_holding_days": {"books": 180, "apparel": 120},
        "condition_to_sell_through": {},
    }
    aggregates = {"books": {"observations": 5, "return_rate": 0.20, "holding_days": 100}}
    new = update_priors(current, aggregates, alpha=20)
    assert new["version"] == "v1"
    assert new["category_return_rate"]["apparel"] == 0.22
    assert new["category_return_rate"]["books"] != 0.04


# ---------------------------------------------------------------------------
# CLI flag behaviour
# ---------------------------------------------------------------------------


def test_apply_flag_required_to_overwrite_latest(tmp_path, capsys):
    outcomes = tmp_path / "outcomes.csv"
    _write_outcomes(outcomes, [
        {"sku": "A", "category": "books", "quantity": 10,
         "realised_units_sold": 8, "realised_returns": 2, "realised_holding_days": 100,
         "realised_avg_sale_price": 50, "realised_total_cost": 200},
    ])
    current = tmp_path / "latest.json"
    _write_current_priors(current)
    original = current.read_text(encoding="utf-8")
    new = tmp_path / "v1.json"

    rc = main([
        "--outcomes", str(outcomes),
        "--current-priors", str(current),
        "--new-priors", str(new),
        "--shrinkage", "20",
    ])
    assert rc == 0
    assert new.exists()
    # No --apply: latest.json must be untouched.
    assert current.read_text(encoding="utf-8") == original


def test_apply_flag_overwrites_latest(tmp_path):
    outcomes = tmp_path / "outcomes.csv"
    _write_outcomes(outcomes, [
        {"sku": "A", "category": "books", "quantity": 10,
         "realised_units_sold": 8, "realised_returns": 2, "realised_holding_days": 100,
         "realised_avg_sale_price": 50, "realised_total_cost": 200},
    ])
    current = tmp_path / "latest.json"
    _write_current_priors(current)
    new = tmp_path / "v1.json"

    rc = main([
        "--outcomes", str(outcomes),
        "--current-priors", str(current),
        "--new-priors", str(new),
        "--apply",
    ])
    assert rc == 0
    latest_payload = json.loads(current.read_text(encoding="utf-8"))
    assert latest_payload["version"] == "v1"


def test_diff_priors_highlights_movement():
    old = {"version": "v0", "source_observations": 0,
           "category_return_rate": {"books": 0.04}, "category_holding_days": {"books": 180}}
    new = {"version": "v1", "source_observations": 5,
           "category_return_rate": {"books": 0.10}, "category_holding_days": {"books": 150}}
    s = diff_priors(old, new)
    assert "books" in s
    assert "v0" in s and "v1" in s
