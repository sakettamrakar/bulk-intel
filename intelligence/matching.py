"""Shared product match scoring for enrichment providers.

The scorer converts a manifest row and an external listing candidate into
an auditable confidence score. Four feature scores contribute through
``Settings.match_token_weights``: model tokens, brand, product type, and
extra title tokens. Category mismatches are hard rejects, and brand
mismatches are hard rejects unless the weighted raw score clears
``Settings.match_brand_mismatch_override``.

Decision semantics are thresholded after hard rules: scores at or above
``match_accept_threshold`` are ``accept``; scores at or above
``match_weak_threshold`` are ``weak``; everything else is ``reject``. For
example, "Logitech Wireless Mouse M185" against "Logitech M185 Mouse
Black" accepts because the model token and brand match and residual title
tokens remain close.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal, Mapping

from rapidfuzz import fuzz

from config.settings import Settings, get_settings
from intelligence.homogeneity import normalize_for_clustering
from processing.cleaner import ManifestCleaner


@dataclass(frozen=True)
class MatchFeatures:
    """Per-feature similarity in ``[0, 1]``."""

    model: float
    brand: float
    product_type: float
    extra_tokens: float
    brand_mismatch: bool
    category_mismatch: bool


@dataclass(frozen=True)
class MatchResult:
    """Final match score, decision, feature breakdown, and reasons."""

    score: float
    decision: Literal["accept", "weak", "reject"]
    features: MatchFeatures
    reasons: tuple[str, ...]


def extract_model_tokens(title: str, settings: Settings) -> tuple[str, ...]:
    """Return uppercased, deduped model identifiers from free text."""
    if not isinstance(title, str):
        return ()
    pattern = re.compile(settings.homogeneity_model_token_pattern, re.I)
    out: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(title.upper()):
        token = re.sub(r"[^A-Z0-9]", "", match.group(0).upper())
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return tuple(out)


def compute_match_score(
    manifest_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    settings: Settings,
) -> MatchResult:
    """Score a single manifest/candidate pair deterministically."""
    manifest_title = str(
        manifest_row.get("product_name_clean")
        or manifest_row.get("product_name")
        or ""
    )
    candidate_title = str(candidate.get("title") or candidate.get("product_name") or "")

    manifest_brand = _normalize_brand(manifest_row.get("brand"), settings)
    candidate_brand = _normalize_brand(candidate.get("brand"), settings)
    manifest_category = _normalize_category(
        manifest_row.get("normalized_category") or manifest_row.get("category")
    )
    candidate_category = _normalize_category(candidate.get("category"))

    manifest_models = set(extract_model_tokens(manifest_title, settings))
    candidate_models = set(extract_model_tokens(candidate_title, settings))

    title_a = normalize_for_clustering(manifest_title, settings)
    title_b = normalize_for_clustering(candidate_title, settings)
    title_similarity = _ratio(fuzz.token_sort_ratio(title_a, title_b))

    model_score = _model_score(manifest_models, candidate_models, title_similarity)
    brand_score = _brand_score(manifest_brand, candidate_brand)
    product_type_score = _product_type_score(title_a, title_b, manifest_brand, candidate_brand, settings)
    extra_tokens_score = title_similarity

    brand_mismatch = bool(manifest_brand and candidate_brand and manifest_brand != candidate_brand)
    category_mismatch = bool(
        manifest_category
        and candidate_category
        and manifest_category != "unknown"
        and candidate_category != "unknown"
        and manifest_category != candidate_category
    )

    weights = settings.match_token_weights
    raw = (
        weights["model"] * model_score
        + weights["brand"] * brand_score
        + weights["product_type"] * product_type_score
        + weights["extra_tokens"] * extra_tokens_score
    )
    score = max(0.0, min(1.0, raw))

    reasons: list[str] = []
    if category_mismatch:
        score = min(score, 0.49)
        reasons.append("category_mismatch")
    if brand_mismatch and raw < settings.match_brand_mismatch_override:
        score = min(score, 0.59)
        reasons.append("brand_mismatch")
    elif brand_mismatch:
        reasons.append("brand_mismatch_override")

    decision = _decision(score, settings)
    top_features = sorted(
        (
            ("model", model_score),
            ("brand", brand_score),
            ("product_type", product_type_score),
            ("extra_tokens", extra_tokens_score),
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:2]
    reasons.extend(f"{name}={value:.2f}" for name, value in top_features)

    return MatchResult(
        score=round(score, 6),
        decision=decision,
        features=MatchFeatures(
            model=round(model_score, 6),
            brand=round(brand_score, 6),
            product_type=round(product_type_score, 6),
            extra_tokens=round(extra_tokens_score, 6),
            brand_mismatch=brand_mismatch,
            category_mismatch=category_mismatch,
        ),
        reasons=tuple(reasons),
    )


def validate_product_match(
    manifest_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    settings: Settings,
) -> bool:
    """Return ``True`` when the pair is an accepted product match."""
    return compute_match_score(manifest_row, candidate, settings).decision == "accept"


def _model_score(a: set[str], b: set[str], title_similarity: float) -> float:
    if a and b:
        union = a | b
        return len(a & b) / len(union) if union else 0.0
    if not a and not b:
        if title_similarity >= 0.98:
            return 1.0
        if title_similarity >= 0.80:
            return 0.35
    return 0.0


def _brand_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return _ratio(fuzz.token_set_ratio(a, b))


def _product_type_score(
    title_a: str,
    title_b: str,
    brand_a: str,
    brand_b: str,
    settings: Settings,
) -> float:
    token_a = _head_noun(title_a, brand_a, settings)
    token_b = _head_noun(title_b, brand_b, settings)
    if not token_a or not token_b:
        return 0.0
    return _ratio(fuzz.partial_ratio(token_a, token_b))


def _head_noun(title: str, brand: str, settings: Settings) -> str:
    model_tokens = set(extract_model_tokens(title, settings))
    for token in title.split():
        lower = token.lower()
        if lower in settings.homogeneity_filler_tokens:
            continue
        if brand and lower == brand.lower():
            continue
        if token.upper() in model_tokens:
            continue
        return lower
    return ""


def _normalize_brand(value: object, settings: Settings) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return ManifestCleaner(settings)._normalise_brand(text)


def _normalize_category(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text == "<na>":
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _ratio(value: float) -> float:
    return max(0.0, min(1.0, float(value) / 100.0))


def _decision(score: float, settings: Settings) -> Literal["accept", "weak", "reject"]:
    if score >= settings.match_accept_threshold:
        return "accept"
    if score >= settings.match_weak_threshold:
        return "weak"
    return "reject"


def score_product_match(
    manifest_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    settings: Settings | None = None,
) -> MatchResult:
    """Functional wrapper using default settings."""
    return compute_match_score(manifest_row, candidate, settings or get_settings())
