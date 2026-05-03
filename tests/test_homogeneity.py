from __future__ import annotations

import pandas as pd
import pytest

from config.settings import Settings
from ingestion.loader import load_manifest
from intelligence.decision import decide
from intelligence.homogeneity import (
    HomogeneityEngine,
    cluster_skus,
    compute_homogeneity_score,
    interpret_homogeneity,
    normalize_for_clustering,
)
from pipeline.run_pipeline import Pipeline
from output.reporter import Reporter


def test_score_is_one_for_single_cluster():
    assert compute_homogeneity_score(pd.Series([100])) == 1.0


def test_score_is_zero_for_uniform_distribution():
    assert compute_homogeneity_score(pd.Series([10] * 10)) == pytest.approx(0.0)


def test_score_handles_empty_input():
    assert compute_homogeneity_score(pd.Series([], dtype=int)) == 0.0


def test_normalize_preserves_model_tokens():
    settings = Settings()
    assert "M185" in normalize_for_clustering("Logitech Wireless Mouse M185 Black", settings)
    assert "M185" in normalize_for_clustering("Logitech M185 Mouse", settings)


def test_cluster_collapses_logitech_m185_variants():
    settings = Settings()
    titles = [
        "Logitech Wireless Mouse M185 Black",
        "Logitech M185 Mouse",
        "Logitech Mouse M185",
        "Logitech Keyboard K380",
    ]
    clusters = cluster_skus(titles, settings)
    assert len(set(clusters[:3])) == 1
    assert clusters[3] != clusters[0]


def test_cluster_does_not_merge_different_models():
    clusters = cluster_skus(["Logitech M185", "Logitech M720"], Settings())
    assert clusters[0] != clusters[1]


def test_engine_attaches_three_cluster_columns(sample_manifest_path):
    df = Pipeline().run_dataframe(load_manifest(sample_manifest_path))
    assert {"sku_cluster_id", "brand_cluster_id", "category_cluster_id"}.issubset(df.columns)


def test_lot_scores_namespace_in_summary(tiny_manifest_df):
    annotated = HomogeneityEngine(Settings()).annotate(tiny_manifest_df)
    out = decide(annotated)
    homogeneity = out.attrs["lot_summary"]["homogeneity"]
    expected = {
        "sku_homogeneity",
        "brand_homogeneity",
        "category_homogeneity",
        "sku_homogeneity_label",
        "brand_homogeneity_label",
        "category_homogeneity_label",
    }
    assert expected.issubset(homogeneity)
    for key in ("sku_homogeneity", "brand_homogeneity", "category_homogeneity"):
        assert 0.0 <= homogeneity[key] <= 1.0
    labels = {
        "Highly homogeneous",
        "Moderately homogeneous",
        "Mixed lot",
        "Highly fragmented",
    }
    assert homogeneity["sku_homogeneity_label"] in labels


def test_interpret_thresholds_at_boundaries():
    settings = Settings()
    assert interpret_homogeneity(0.85, settings) == "Highly homogeneous"
    assert interpret_homogeneity(0.84999, settings) == "Moderately homogeneous"
    assert interpret_homogeneity(0.60, settings) == "Moderately homogeneous"
    assert interpret_homogeneity(0.59999, settings) == "Mixed lot"
    assert interpret_homogeneity(0.30, settings) == "Mixed lot"
    assert interpret_homogeneity(0.29999, settings) == "Highly fragmented"


def test_real_manifest_category_above_sku_homogeneity():
    df = load_manifest("data/e8c203803afa10d11e3844dd57636779.xlsx")
    settings = Settings()
    engine = HomogeneityEngine(settings)
    from processing.cleaner import clean_manifest

    scores = engine.lot_scores(engine.annotate(clean_manifest(df, settings)))
    assert scores["category_homogeneity"] >= scores["sku_homogeneity"] + 0.10


def test_rollup_prefers_sku_cluster_id_over_noisy_sku():
    df = pd.DataFrame(
        [
            {"sku": "A1", "sku_cluster_id": "c0", "quantity": 1, "product_name_clean": "Logitech M185"},
            {"sku": "A2", "sku_cluster_id": "c0", "quantity": 1, "product_name_clean": "Logitech M185"},
            {"sku": "A3", "sku_cluster_id": "c1", "quantity": 1, "product_name_clean": "Logitech K380"},
        ]
    )
    sku_baseline = df.groupby("sku").size()
    rollup = Reporter._build_rollup(df)
    assert len(rollup) < len(sku_baseline)
    assert set(rollup["group_key"]) == {"c0", "c1"}
