from __future__ import annotations

import pandas as pd

from config.settings import Settings
from ingestion.loader import load_manifest
from intelligence.grouping import (
    CanonicalGroupingEngine,
    build_canonical_groups,
    build_search_signature,
    select_canonical_title,
)
from intelligence.homogeneity import HomogeneityEngine
from pipeline.run_pipeline import Pipeline
from processing.cleaner import clean_manifest


def test_signature_collapses_color_variants():
    settings = Settings()
    assert build_search_signature("Logitech Wireless Mouse M185 Black", settings) == build_search_signature(
        "Logitech Mouse M185 Grey", settings
    )


def test_signature_keeps_model_distinct():
    settings = Settings()
    assert build_search_signature("Logitech M185", settings) != build_search_signature("Logitech M720", settings)


def test_signature_truncated_to_max_len():
    settings = Settings(canonical_title_max_len=20)
    title = "Logitech " + "VeryLongToken " * 30 + "M185"
    assert len(build_search_signature(title, settings)) <= 20


def test_canonical_title_prefers_model_and_brand():
    title = select_canonical_title(["Wireless Mouse", "Mouse M185", "Logitech Mouse M185"], Settings())
    assert title == "Logitech Mouse M185"


def test_canonical_title_is_deterministic():
    titles = ["Beta Product", "Alpha Product"]
    assert select_canonical_title(titles, Settings()) == "Alpha Product"
    assert select_canonical_title(list(reversed(titles)), Settings()) == "Alpha Product"


def test_groups_keyed_by_value_descending():
    df = _homogeneous_df(
        [
            ("A", "Low Item A100", 1, 10.0),
            ("B", "High Item B100", 5, 100.0),
            ("C", "Mid Item C100", 2, 50.0),
        ]
    )
    groups = build_canonical_groups(df, Settings())
    assert groups.loc[0, "group_id"] == "g0"
    assert groups.loc[0, "group_total_value"] == 500.0


def test_group_id_stable_under_row_permutation():
    df = _homogeneous_df(
        [
            ("A", "Low Item A100", 1, 10.0),
            ("B", "High Item B100", 5, 100.0),
            ("C", "Mid Item C100", 2, 50.0),
        ]
    )
    shuffled = df.sample(frac=1.0, random_state=42)
    a = build_canonical_groups(df, Settings())[["group_id", "canonical_title", "group_total_value"]]
    b = build_canonical_groups(shuffled, Settings())[["group_id", "canonical_title", "group_total_value"]]
    assert a.to_dict("records") == b.to_dict("records")


def test_group_total_quantity_and_value_sum_correctly():
    df = _homogeneous_df(
        [
            ("A1", "Logitech Mouse M185 Black", 2, 100.0),
            ("A2", "Logitech Mouse M185 Grey", 3, 120.0),
        ]
    )
    groups = build_canonical_groups(df, Settings())
    assert len(groups) == 1
    assert groups.loc[0, "group_total_quantity"] == 5
    assert groups.loc[0, "group_total_value"] == 560.0


def test_eligible_for_search_threshold():
    df = _homogeneous_df(
        [
            ("A", "Single Item A100", 1, 10.0),
            ("B", "Bulk Item B100", 5, 10.0),
        ]
    )
    groups = build_canonical_groups(df, Settings(min_group_quantity_for_search=2))
    by_title = dict(zip(groups["canonical_title"], groups["eligible_for_search"]))
    assert by_title["Single Item A100"] is False
    assert by_title["Bulk Item B100"] is True


def test_real_manifest_collapses_at_least_10_pct():
    settings = Settings()
    df = clean_manifest(load_manifest("data/e8c203803afa10d11e3844dd57636779.xlsx"), settings)
    df = HomogeneityEngine(settings).annotate(df)
    groups = CanonicalGroupingEngine(settings).build(df)
    assert len(groups) <= len(df) * 0.90


def test_pipeline_publishes_groups_attr(sample_manifest_path, tmp_path):
    pipe = Pipeline()
    df = load_manifest(sample_manifest_path)
    result = pipe.run_dataframe(df)
    groups = result.attrs["_groups"]
    assert not groups.empty
    assert {"canonical_title", "group_total_quantity", "group_total_value", "variant_count"}.issubset(groups.columns)
    outputs = pipe.run(sample_manifest_path, tmp_path)
    rollup = pd.read_csv(outputs["rollup"])
    assert {"canonical_title", "group_total_quantity", "group_total_value", "variant_count"}.issubset(rollup.columns)


def _homogeneous_df(rows):
    df = pd.DataFrame(
        [
            {
                "sku": sku,
                "product_name": title,
                "product_name_clean": title,
                "brand": title.split()[0],
                "normalized_category": "electronics",
                "quantity": qty,
                "floor_price": floor,
            }
            for sku, title, qty, floor in rows
        ]
    )
    return HomogeneityEngine(Settings()).annotate(df)
