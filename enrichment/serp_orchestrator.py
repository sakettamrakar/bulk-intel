"""Partial group-level SERP execution and coverage telemetry.

Operators care about value coverage more than row coverage: a handful of
high-value groups can decide whether a liquidation lot is worth deeper work.
Coverage therefore uses ``sum(group_total_value of completed groups) /
sum(group_total_value of all groups) * 100``. Row coverage is still reported
as a secondary quantity-weighted metric.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from config.settings import Settings
from enrichment.serp_cache import SerpCache
from enrichment.serp_price_provider import SerpAmazonPriceProvider
from enrichment.serp_state import SerpRunState, load_state, save_state
from enrichment.playwright_serp_client import BudgetExhausted, CaptchaEncountered, PlaywrightSerpClient


class ExecutionMode(str, Enum):
    """SERP execution scope."""

    PREVIEW = "preview"
    INCREMENTAL = "incremental"
    FULL = "full"


class ManifestStateMismatchError(RuntimeError):
    """Raised when incremental state belongs to a different manifest."""


def rank_groups_for_search(groups: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Sort groups by descending value priority, ineligible groups last."""
    if groups.empty:
        return groups.copy()
    out = groups.copy()
    out["_eligible_sort"] = out.get("eligible_for_search", pd.Series([True] * len(out))).astype(bool)
    out = out.sort_values(
        by=[
            "_eligible_sort",
            "group_total_value",
            "group_total_quantity",
            "variant_count",
            "canonical_title",
        ],
        ascending=[False, False, False, False, True],
    ).drop(columns=["_eligible_sort"])
    return out.reset_index(drop=True)


@dataclass(frozen=True)
class PartialSerpOrchestrator:
    """Execute SERP enrichment for selected canonical groups."""

    settings: Settings
    provider: SerpAmazonPriceProvider
    cache: SerpCache
    state_path: Path
    playwright_client_factory: Callable[[Settings], PlaywrightSerpClient] | None = None

    def enrich(
        self,
        groups: pd.DataFrame,
        mode: ExecutionMode = ExecutionMode.PREVIEW,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Return groups augmented with execution flags and group prices."""
        mode = ExecutionMode(mode)
        out = _with_default_execution_columns(groups.copy())
        if out.empty:
            out.attrs["search_execution_summary"] = self.coverage(out, mode, limit)
            return out

        manifest_hash = manifest_hash_for_groups(out)
        prior = load_state(self.state_path)
        started_at = prior.started_at if prior else _now_iso()
        completed = set(prior.completed_signatures if prior else ())
        failed = set(prior.failed_signatures if prior else ())
        mid_run_backend_switch = bool(getattr(prior, "mid_run_backend_switch", False)) if prior else False

        if mode == ExecutionMode.INCREMENTAL and prior and prior.manifest_hash != manifest_hash:
            raise ManifestStateMismatchError("SERP state manifest_hash does not match current manifest")
        if mode == ExecutionMode.FULL:
            completed = set()
            failed = set()

        ranked = rank_groups_for_search(out, self.settings)
        eligible = ranked[ranked["eligible_for_search"].astype(bool)]
        if mode == ExecutionMode.PREVIEW:
            selected_signatures = set(
                eligible.head(limit or self.settings.serp_preview_limit)["search_signature"].astype(str)
            )
        elif mode == ExecutionMode.INCREMENTAL:
            selected_signatures = set(
                sig for sig in eligible["search_signature"].astype(str) if sig not in completed
            )
        else:
            selected_signatures = set(eligible["search_signature"].astype(str))

        for idx, row in out.iterrows():
            signature = str(row.get("search_signature") or "")
            if signature not in selected_signatures:
                continue
            out.at[idx, "serp_attempted"] = True
            out.at[idx, "last_execution_time"] = _now_iso()
            cache_hits_before = self.cache.stats().hits
            try:
                amazon, _, confidence = self.provider.lookup(_provider_row(row))
            except BudgetExhausted:
                self._save_state(manifest_hash, started_at, completed, failed, mode, mid_run_backend_switch)
                break
            except Exception as exc:
                if self._should_fallback_to_playwright(exc):
                    self._switch_to_playwright()
                    mid_run_backend_switch = True
                    try:
                        amazon, _, confidence = self.provider.lookup(_provider_row(row))
                    except BudgetExhausted:
                        self._save_state(manifest_hash, started_at, completed, failed, mode, mid_run_backend_switch)
                        break
                    except Exception as inner_exc:
                        out.at[idx, "execution_stage"] = "failed"
                        out.at[idx, "error_kind"] = _error_kind(inner_exc)
                        failed.add(signature)
                        self._save_state(manifest_hash, started_at, completed, failed, mode, mid_run_backend_switch)
                        continue
                else:
                    out.at[idx, "execution_stage"] = "failed"
                    out.at[idx, "error_kind"] = _error_kind(exc)
                    failed.add(signature)
                    self._save_state(manifest_hash, started_at, completed, failed, mode, mid_run_backend_switch)
                    continue

            out.at[idx, "cache_hit"] = self.cache.stats().hits > cache_hits_before
            out.at[idx, "serp_completed"] = True
            out.at[idx, "serp_source_found"] = amazon is not None
            out.at[idx, "price_extracted"] = amazon is not None
            out.at[idx, "match_validated"] = amazon is not None and float(confidence) > 0.0
            out.at[idx, "amazon_price"] = amazon
            out.at[idx, "match_confidence"] = float(confidence)
            if amazon is None:
                out.at[idx, "execution_stage"] = "failed"
                out.at[idx, "error_kind"] = "match_reject"
                failed.add(signature)
            else:
                out.at[idx, "execution_stage"] = "priced"
                out.at[idx, "error_kind"] = None
                completed.add(signature)
                failed.discard(signature)
            self._save_state(manifest_hash, started_at, completed, failed, mode, mid_run_backend_switch)

        out.attrs["search_execution_summary"] = self.coverage(out, mode, limit)
        out.attrs["search_execution_summary"]["mid_run_backend_switch"] = mid_run_backend_switch
        return out

    def coverage(
        self,
        groups: pd.DataFrame,
        mode: ExecutionMode = ExecutionMode.PREVIEW,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return manifest-level execution and coverage metrics."""
        if groups.empty:
            total_qty = total_value = 0.0
            completed = groups
        else:
            total_qty = float(pd.to_numeric(groups["group_total_quantity"], errors="coerce").fillna(0).sum())
            total_value = float(pd.to_numeric(groups["group_total_value"], errors="coerce").fillna(0).sum())
            completed = groups[groups.get("serp_completed", pd.Series([False] * len(groups))).astype(bool)]
        completed_qty = float(pd.to_numeric(completed.get("group_total_quantity", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        completed_value = float(pd.to_numeric(completed.get("group_total_value", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        stats = self.cache.stats()
        return {
            "total_manifest_rows": int(total_qty),
            "grouped_products": int(len(groups)),
            "eligible_groups": int(groups.get("eligible_for_search", pd.Series(dtype=bool)).astype(bool).sum()) if not groups.empty else 0,
            "execution_mode": ExecutionMode(mode).value,
            "serp_preview_limit": int(limit or self.settings.serp_preview_limit),
            "serp_completed_count": int(len(completed)),
            "serp_pending_count": int((~groups.get("serp_completed", pd.Series([False] * len(groups))).astype(bool)).sum()) if not groups.empty else 0,
            "serp_failed_count": int((groups.get("execution_stage", pd.Series(dtype=str)) == "failed").sum()) if not groups.empty else 0,
            "row_coverage_pct": round((completed_qty / total_qty * 100.0), 2) if total_qty else 0.0,
            "value_coverage_pct": round((completed_value / total_value * 100.0), 2) if total_value else 0.0,
            "groups_needed_for_value_target": groups_needed_for_value_target(groups, self.settings),
            "serp_backend_used": _backend_used(groups, self.provider),
            "playwright_queries_used": _playwright_queries_used(self.provider),
            "playwright_budget_remaining": max(
                0,
                int(self.settings.playwright_max_queries_per_run) - _playwright_queries_used(self.provider),
            ),
            "captchas_encountered": _captchas_encountered(self.provider),
            "mid_run_backend_switch": False,
            "cache_stats": {
                "hits": stats.hits,
                "misses": stats.misses,
                "expired": stats.expired,
                "size": stats.size,
            },
        }

    def _save_state(
        self,
        manifest_hash: str,
        started_at: str,
        completed: set[str],
        failed: set[str],
        mode: ExecutionMode,
        mid_run_backend_switch: bool = False,
    ) -> None:
        save_state(
            SerpRunState(
                manifest_hash=manifest_hash,
                started_at=started_at,
                last_updated_at=_now_iso(),
                completed_signatures=tuple(sorted(completed)),
                failed_signatures=tuple(sorted(failed)),
                mode=mode.value,
                mid_run_backend_switch=mid_run_backend_switch,
            ),
            self.state_path,
        )

    def _should_fallback_to_playwright(self, exc: Exception) -> bool:
        if not self.settings.playwright_fallback_enabled:
            return False
        if isinstance(exc, (BudgetExhausted, CaptchaEncountered)):
            return False
        text = str(exc).lower()
        return "quota" in text or "429" in text or "401" in text or "403" in text or "4xx" in _error_kind(exc)

    def _switch_to_playwright(self) -> None:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(
            "SerpAPI failed; switching to Playwright fallback for the remainder of this run (cap=%d queries)",
            self.settings.playwright_max_queries_per_run,
        )
        client = (
            self.playwright_client_factory(self.settings)
            if self.playwright_client_factory
            else PlaywrightSerpClient(self.settings)
        )
        object.__setattr__(
            self,
            "provider",
            self.provider.with_client(client),
        )


def manifest_hash_for_groups(groups: pd.DataFrame) -> str:
    signatures = sorted(str(value) for value in groups.get("search_signature", pd.Series(dtype=str)))
    return hashlib.sha256("|".join(signatures).encode("utf-8")).hexdigest()


def groups_needed_for_value_target(groups: pd.DataFrame, settings: Settings) -> int:
    if groups.empty:
        return 0
    ranked = rank_groups_for_search(groups, settings)
    values = pd.to_numeric(ranked["group_total_value"], errors="coerce").fillna(0.0)
    total = float(values.sum())
    if total <= 0:
        return 0
    cumulative = 0.0
    for idx, value in enumerate(values, start=1):
        cumulative += float(value)
        if cumulative / total >= settings.serp_value_coverage_target:
            return idx
    return len(values)


def _backend_used(groups: pd.DataFrame, provider: SerpAmazonPriceProvider) -> str:
    completed = groups[groups.get("serp_completed", pd.Series([False] * len(groups))).astype(bool)] if not groups.empty else groups
    if completed.empty:
        return "none"
    backend = getattr(getattr(provider, "serp_client", None), "backend_name", "none")
    return str(backend or "none")


def _playwright_queries_used(provider: SerpAmazonPriceProvider) -> int:
    client = getattr(provider, "serp_client", None)
    return int(getattr(client, "queries_used", 0) or 0)


def _captchas_encountered(provider: SerpAmazonPriceProvider) -> int:
    client = getattr(provider, "serp_client", None)
    return int(getattr(client, "captchas_encountered", 0) or 0)


def _with_default_execution_columns(groups: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "serp_attempted": False,
        "serp_completed": False,
        "serp_source_found": False,
        "price_extracted": False,
        "match_validated": False,
        "cache_hit": False,
        "execution_stage": "queued",
        "last_execution_time": None,
        "error_kind": None,
        "amazon_price": None,
        "match_confidence": 0.0,
        "matched_titles": None,
        "matched_urls": None,
    }
    for column, value in defaults.items():
        if column not in groups.columns:
            groups[column] = value
    return groups


def _provider_row(group: pd.Series) -> pd.Series:
    return pd.Series(
        {
            "product_name_clean": group.get("canonical_title") or group.get("search_signature"),
            "brand": group.get("brand"),
            "normalized_category": group.get("normalized_category"),
        }
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _error_kind(exc: Exception) -> str:
    text = str(exc).lower()
    if "timeout" in text:
        return "timeout"
    if "429" in text or "rate" in text:
        return "rate_limited"
    if "4" in text:
        return "4xx"
    if "5" in text:
        return "5xx"
    return "parse_error"
