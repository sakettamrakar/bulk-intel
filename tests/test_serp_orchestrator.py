from __future__ import annotations

import json

import pandas as pd
import pytest

from config.settings import Settings
from enrichment.serp_cache import SerpCache
from enrichment.serp_orchestrator import (
    ExecutionMode,
    ManifestStateMismatchError,
    PartialSerpOrchestrator,
    groups_needed_for_value_target,
    rank_groups_for_search,
)
from enrichment.serp_state import SerpRunState, save_state


class FakeProvider:
    name = "serp_amazon"

    def __init__(self, fail_signatures=None):
        self.calls = []
        self.fail_signatures = set(fail_signatures or ())

    def lookup(self, row):
        title = str(row.get("product_name_clean"))
        self.calls.append(title)
        if title in self.fail_signatures:
            raise RuntimeError("timeout")
        return (999.0, None, 0.91)


def test_preview_mode_serps_only_top_n(tmp_path):
    groups = _groups(100)
    provider = FakeProvider()
    out = _orch(tmp_path, provider).enrich(groups, ExecutionMode.PREVIEW, limit=10)
    completed = out[out["serp_completed"]]
    assert len(completed) == 10
    assert set(completed["group_id"]) == {f"g{i}" for i in range(10)}


def test_preview_mode_marks_others_attempted_false(tmp_path):
    out = _orch(tmp_path, FakeProvider()).enrich(_groups(5), ExecutionMode.PREVIEW, limit=2)
    assert out["serp_attempted"].sum() == 2
    assert (~out.loc[~out["serp_completed"], "serp_attempted"]).all()


def test_full_mode_serps_every_eligible_group(tmp_path):
    groups = _groups(5)
    groups.loc[4, "eligible_for_search"] = False
    provider = FakeProvider()
    out = _orch(tmp_path, provider).enrich(groups, ExecutionMode.FULL)
    assert out["serp_completed"].sum() == 4
    assert len(provider.calls) == 4


def test_incremental_resumes_from_state(tmp_path):
    groups = _groups(8)
    provider = FakeProvider()
    orch = _orch(tmp_path, provider)
    orch.enrich(groups, ExecutionMode.PREVIEW, limit=3)
    provider.calls.clear()
    orch.enrich(groups, ExecutionMode.INCREMENTAL)
    assert len(provider.calls) == 5


def test_incremental_refuses_on_manifest_hash_mismatch(tmp_path):
    state = SerpRunState(
        manifest_hash="wrong",
        started_at="2026-01-01T00:00:00+00:00",
        last_updated_at="2026-01-01T00:00:00+00:00",
        completed_signatures=(),
        failed_signatures=(),
        mode="preview",
    )
    save_state(state, tmp_path / "state.json")
    with pytest.raises(ManifestStateMismatchError):
        _orch(tmp_path, FakeProvider()).enrich(_groups(2), ExecutionMode.INCREMENTAL)


def test_state_file_atomic_write_survives_kill(tmp_path):
    (tmp_path / "state.json.tmp").write_text("{not-json", encoding="utf-8")
    out = _orch(tmp_path, FakeProvider()).enrich(_groups(2), ExecutionMode.PREVIEW, limit=1)
    assert out["serp_completed"].sum() == 1
    json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))


def test_rank_is_deterministic_under_permutation():
    settings = Settings()
    groups = _groups(10)
    shuffled = groups.sample(frac=1.0, random_state=7)
    a = rank_groups_for_search(groups, settings)["search_signature"].tolist()
    b = rank_groups_for_search(shuffled, settings)["search_signature"].tolist()
    assert a == b


def test_failed_groups_recorded_in_state_not_completed(tmp_path):
    groups = _groups(2)
    provider = FakeProvider(fail_signatures={"Product 0"})
    out = _orch(tmp_path, provider).enrich(groups, ExecutionMode.FULL)
    failed = out[out["execution_stage"] == "failed"]
    assert len(failed) == 1
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "sig-0" in state["failed_signatures"]
    assert "sig-0" not in state["completed_signatures"]


def test_value_coverage_uses_inventory_value(tmp_path):
    groups = _groups(10)
    groups["group_total_quantity"] = 1
    groups["group_total_value"] = [90.0] + [10.0 / 9.0] * 9
    out = _orch(tmp_path, FakeProvider()).enrich(groups, ExecutionMode.PREVIEW, limit=1)
    summary = out.attrs["search_execution_summary"]
    assert summary["value_coverage_pct"] == 90.0
    assert summary["row_coverage_pct"] == 10.0


def test_groups_needed_for_value_target_correct():
    groups = _groups(4)
    groups["group_total_value"] = [0.6, 0.3, 0.05, 0.05]
    assert groups_needed_for_value_target(groups, Settings(serp_value_coverage_target=0.8)) == 2


def test_orchestrator_publishes_amazon_price_per_group(tmp_path):
    out = _orch(tmp_path, FakeProvider()).enrich(_groups(1), ExecutionMode.FULL)
    assert out.loc[0, "amazon_price"] == 999.0
    assert out.loc[0, "match_confidence"] == 0.91


def _orch(tmp_path, provider):
    settings = Settings(serp_cache_path=str(tmp_path / "cache.sqlite"), serp_state_path=str(tmp_path / "state.json"))
    cache = SerpCache(settings.serp_cache_path, ttl_hours=settings.serp_cache_ttl_hours)
    return PartialSerpOrchestrator(settings, provider, cache, tmp_path / "state.json")


def _groups(n):
    return pd.DataFrame(
        [
            {
                "group_id": f"g{i}",
                "search_signature": f"sig-{i}",
                "canonical_title": f"Product {i}",
                "brand": "Brand",
                "normalized_category": "electronics",
                "model_tokens": (),
                "variant_count": 1,
                "group_total_quantity": 1,
                "group_total_value": float(n - i),
                "group_member_skus": (f"SKU-{i}",),
                "eligible_for_search": True,
            }
            for i in range(n)
        ]
    )
