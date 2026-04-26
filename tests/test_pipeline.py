"""End-to-end pipeline smoke test."""
from __future__ import annotations

from pipeline.run_pipeline import run_pipeline


def test_pipeline_end_to_end(sample_manifest_path, tmp_path):
    outputs = run_pipeline(sample_manifest_path, tmp_path)

    assert outputs["csv"].exists()
    assert outputs["summary"].exists()

    csv_text = outputs["csv"].read_text(encoding="utf-8")
    assert "recommendation" in csv_text
    assert "sellability_score" in csv_text

    summary = outputs["summary"].read_text(encoding="utf-8")
    assert "MANIFEST SUMMARY" in summary
