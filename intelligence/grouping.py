"""Canonical product groups for rollups and SERP execution.

Use row-level ``sku_cluster_id`` when measuring homogeneity or preserving
lossless cluster membership. Use ``group_id`` and ``search_signature`` when
SERP queries, value-weighted prioritisation, or group-level execution state
are needed. Group ids are priority labels within one run; the stable lookup
identity is the search signature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from config.settings import Settings, get_settings
from intelligence.homogeneity import model_tokens, normalize_for_clustering


def build_search_signature(title: str, settings: Settings) -> str:
    """Build a stable, lossy SERP key for a product title."""
    normalized = normalize_for_clustering(title, settings)
    if not normalized:
        return ""
    drop = set(settings.homogeneity_filler_tokens) | set(settings.search_signature_drop_tokens)
    tokens = [token for token in normalized.split() if token.lower() not in drop]
    models = set(model_tokens(title, settings))
    if models:
        brand = _first_known_brand(tokens, settings)
        head = _first_head_token(tokens, brand, models, settings)
        ordered = [part for part in (brand, head, sorted(models)[0]) if part]
    else:
        ordered = _dedupe(tokens)
    return _truncate(" ".join(ordered).strip(), settings.canonical_title_max_len)


def select_canonical_title(titles: list[str], settings: Settings) -> str:
    """Pick the most informative representative title for a group."""
    if not titles:
        return ""

    def score(title: str) -> tuple[int, str]:
        normalized = normalize_for_clustering(title, settings)
        tokens = normalized.split()
        models = model_tokens(title, settings)
        brand_present = _first_known_brand(tokens, settings) != ""
        non_filler = [
            token for token in tokens
            if token.lower() not in settings.homogeneity_filler_tokens
        ]
        value = (3 if models else 0) + (2 if brand_present else 0) + len(non_filler)
        if len(title) > settings.canonical_title_max_len:
            value -= 1
        return value, title

    return sorted(titles, key=lambda title: (-score(title)[0], score(title)[1]))[0]


@dataclass(frozen=True)
class CanonicalGroupingEngine:
    """Build canonical product groups from homogeneity-annotated rows."""

    settings: Settings

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a groups DataFrame keyed on value-ranked group ids."""
        if df.empty:
            return _empty_groups()
        cluster_col = "sku_cluster_id" if "sku_cluster_id" in df.columns else "_row_cluster"
        work = df.copy()
        if cluster_col == "_row_cluster":
            work[cluster_col] = [f"row_{idx}" for idx in range(len(work))]
        work["_title"] = work.apply(
            lambda row: str(row.get("product_name_clean") or row.get("product_name") or ""),
            axis=1,
        )
        work["_search_signature"] = work["_title"].map(
            lambda title: build_search_signature(title, self.settings)
        )
        work["_group_key"] = (
            work[cluster_col].fillna("").astype(str)
            + "|"
            + work["_search_signature"].fillna("").astype(str)
        )

        rows: list[dict] = []
        for _, group in work.groupby("_group_key", sort=True):
            titles = sorted(set(group["_title"].dropna().astype(str)))
            canonical = select_canonical_title(titles, self.settings)
            signature = build_search_signature(canonical, self.settings) or str(group["_search_signature"].iloc[0])
            qty = pd.to_numeric(group.get("quantity", pd.Series([1] * len(group))), errors="coerce").fillna(1)
            floor = pd.to_numeric(group.get("floor_price", pd.Series([0.0] * len(group))), errors="coerce").fillna(0.0)
            group_total_quantity = int(qty.sum())
            group_total_value = float((qty * floor).sum())
            rows.append(
                {
                    "_sort_signature": signature,
                    "search_signature": signature,
                    "canonical_title": canonical,
                    "brand": _mode_or_none(group.get("brand")),
                    "normalized_category": _mode_or_none(
                        group.get("normalized_category", group.get("category"))
                    ),
                    "model_tokens": tuple(sorted(model_tokens(canonical, self.settings))),
                    "variant_count": int(group["_title"].nunique()),
                    "group_total_quantity": group_total_quantity,
                    "group_total_value": group_total_value,
                    "group_member_skus": tuple(_dedupe(group.get("sku", pd.Series(dtype=str)).dropna().astype(str))),
                    "eligible_for_search": group_total_quantity >= self.settings.min_group_quantity_for_search,
                }
            )

        out = pd.DataFrame(rows)
        if out.empty:
            return _empty_groups()
        out = out.sort_values(
            by=["group_total_value", "group_total_quantity", "variant_count", "_sort_signature"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
        out.insert(0, "group_id", [f"g{idx}" for idx in range(len(out))])
        return out.drop(columns=["_sort_signature"])


def build_canonical_groups(
    df: pd.DataFrame, settings: Optional[Settings] = None
) -> pd.DataFrame:
    """Functional wrapper for the orchestrator."""
    return CanonicalGroupingEngine(settings or get_settings()).build(df)


def _first_known_brand(tokens: list[str], settings: Settings) -> str:
    for token in tokens:
        lower = token.lower()
        if lower in settings.known_brands:
            return lower
    return tokens[0].lower() if tokens else ""


def _first_head_token(
    tokens: list[str],
    brand: str,
    models: set[str],
    settings: Settings,
) -> str:
    for token in tokens:
        lower = token.lower()
        if lower == brand or lower in settings.homogeneity_filler_tokens:
            continue
        if token.upper() in models:
            continue
        return lower
    return ""


def _dedupe(values) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[:max_len].rsplit(" ", 1)[0] or value[:max_len]


def _mode_or_none(series) -> str | None:
    if series is None:
        return None
    values = sorted(str(value).strip() for value in series.dropna() if str(value).strip())
    if not values:
        return None
    counts = pd.Series(values).value_counts()
    top_count = counts.max()
    return str(sorted(counts[counts == top_count].index)[0])


def _empty_groups() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "group_id",
            "search_signature",
            "canonical_title",
            "brand",
            "normalized_category",
            "model_tokens",
            "variant_count",
            "group_total_quantity",
            "group_total_value",
            "group_member_skus",
            "eligible_for_search",
        ]
    )
