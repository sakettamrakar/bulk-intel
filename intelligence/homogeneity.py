"""Lot homogeneity scoring and SKU clustering.

Homogeneity is measured as entropy concentration over cluster counts:
``score = 1 - H / ln(N)`` where ``H = -sum(p_i * ln(p_i))`` and ``N`` is
the number of distinct clusters. A single cluster scores 1.0; a uniform
spread across many clusters scores 0.0.

SKU clustering is deliberately conservative. Product titles are cleaned
with filler-token removal, model identifiers are preserved with
``Settings.homogeneity_model_token_pattern``, and titles collapse only when
they share a model token or have no model tokens and clear the configured
RapidFuzz token-sort cutoff. The default cutoff of 88 keeps common wording
variants together without merging unrelated model numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

import pandas as pd
from rapidfuzz import fuzz

from config.settings import Settings, get_settings


@dataclass(frozen=True)
class HomogeneityEngine:
    """Annotate rows with cluster ids and compute lot-level scores."""

    settings: Settings

    def annotate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return ``df`` with SKU, brand, and category cluster ids."""
        out = df.copy()
        titles = [
            str(row.get("product_name_clean") or row.get("product_name") or "")
            for _, row in out.iterrows()
        ]
        out["sku_cluster_id"] = cluster_skus(titles, self.settings)
        out["brand_cluster_id"] = out.get("brand", pd.Series([""] * len(out))).map(
            lambda value: _exact_cluster_id(value, "brand_unknown")
        )
        out["category_cluster_id"] = out.get(
            "normalized_category", out.get("category", pd.Series(["unknown"] * len(out)))
        ).map(lambda value: _exact_cluster_id(value, "category_unknown"))
        return out

    def lot_scores(self, df: pd.DataFrame) -> dict[str, float | str]:
        """Return homogeneity scores and labels for SKU, brand, and category."""
        annotated = df if _has_cluster_columns(df) else self.annotate(df)
        output: dict[str, float | str] = {}
        for prefix, column in (
            ("sku", "sku_cluster_id"),
            ("brand", "brand_cluster_id"),
            ("category", "category_cluster_id"),
        ):
            counts = _cluster_counts(annotated, column)
            score = round(compute_homogeneity_score(counts), 6)
            output[f"{prefix}_homogeneity"] = score
            output[f"{prefix}_homogeneity_label"] = interpret_homogeneity(score, self.settings)
        return output


def normalize_for_clustering(title: str, settings: Settings) -> str:
    """Lowercase, strip punctuation, drop fillers, and preserve model tokens."""
    if not isinstance(title, str) or not title.strip():
        return ""

    model_tokens = _extract_model_tokens(title, settings)
    model_set = set(model_tokens)
    text = re.sub(r"[^A-Za-z0-9]+", " ", title).lower()
    parts: list[str] = []
    seen: set[str] = set()

    for raw in text.split():
        token = raw.strip()
        if not token or token in settings.homogeneity_filler_tokens:
            continue
        token_upper = token.upper()
        if token_upper in model_set:
            token = token_upper
        elif token_upper in model_set or _canonical_model_token(token_upper) in model_set:
            token = _canonical_model_token(token_upper)
        if token not in seen:
            seen.add(token)
            parts.append(token)

    for token in model_tokens:
        if token not in seen:
            seen.add(token)
            parts.append(token)

    return " ".join(parts)


def cluster_skus(titles: list[str], settings: Settings) -> list[str]:
    """Greedy deterministic SKU clustering using model tokens and RapidFuzz."""
    normalized = [normalize_for_clustering(title, settings) for title in titles]
    model_sets = [set(_extract_model_tokens(title, settings)) for title in titles]

    unique_titles = sorted(set(normalized))
    representatives: list[str] = []
    rep_models: list[set[str]] = []
    title_to_cluster: dict[str, str] = {}

    for title in unique_titles:
        idx = normalized.index(title)
        title_models = model_sets[idx]
        chosen: str | None = None
        for cluster_idx, rep in enumerate(representatives):
            rep_model_set = rep_models[cluster_idx]
            if title_models or rep_model_set:
                if title_models.intersection(rep_model_set):
                    chosen = f"c{cluster_idx}"
                    break
                continue
            if fuzz.token_sort_ratio(title, rep) >= settings.homogeneity_sku_fuzz_cutoff:
                chosen = f"c{cluster_idx}"
                break
        if chosen is None:
            chosen = f"c{len(representatives)}"
            representatives.append(title)
            rep_models.append(title_models)
        title_to_cluster[title] = chosen

    return [title_to_cluster[title] for title in normalized]


def compute_homogeneity_score(counts: pd.Series) -> float:
    """Return entropy concentration score in ``[0, 1]``."""
    if counts is None or counts.empty:
        return 0.0
    values = pd.to_numeric(counts, errors="coerce").dropna()
    values = values[values > 0]
    if values.empty:
        return 0.0
    n_clusters = len(values)
    if n_clusters == 1:
        return 1.0
    total = float(values.sum())
    if total <= 0:
        return 0.0
    probabilities = values.astype(float) / total
    entropy = -float((probabilities * probabilities.map(math.log)).sum())
    score = 1.0 - (entropy / math.log(n_clusters))
    return max(0.0, min(1.0, score))


def interpret_homogeneity(score: float, settings: Settings) -> str:
    """Map a score to a qualitative lot-homogeneity label."""
    thresholds = settings.homogeneity_thresholds
    if score >= thresholds["highly_homogeneous"]:
        return "Highly homogeneous"
    if score >= thresholds["moderately_homogeneous"]:
        return "Moderately homogeneous"
    if score >= thresholds["mixed"]:
        return "Mixed lot"
    return "Highly fragmented"


def _extract_model_tokens(title: str, settings: Settings) -> tuple[str, ...]:
    if not isinstance(title, str):
        return ()
    pattern = re.compile(settings.homogeneity_model_token_pattern, re.I)
    tokens: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(title.upper()):
        token = _canonical_model_token(match.group(0))
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tuple(tokens)


def _canonical_model_token(token: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", token.upper())


def _exact_cluster_id(value: object, fallback: str) -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip().lower()
    return text or fallback


def _cluster_counts(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([], dtype=float)
    if "quantity" not in df.columns:
        return df[column].value_counts(dropna=False)
    qty = pd.to_numeric(df["quantity"], errors="coerce").fillna(1)
    work = pd.DataFrame({"cluster": df[column], "quantity": qty})
    return work.groupby("cluster", dropna=False)["quantity"].sum()


def _has_cluster_columns(df: pd.DataFrame) -> bool:
    return {"sku_cluster_id", "brand_cluster_id", "category_cluster_id"}.issubset(df.columns)


def annotate_homogeneity(df: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Functional wrapper around :class:`HomogeneityEngine`."""
    return HomogeneityEngine(settings or get_settings()).annotate(df)
