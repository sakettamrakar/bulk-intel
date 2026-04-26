"""Clean product names and extract structured attributes.

The cleaner takes the canonical manifest produced by the ingestion
layer and adds derived fields the rest of the pipeline depends on:

* ``product_name_clean`` — noise-stripped, title-cased.
* ``brand`` — inferred from the product name when absent.
* ``category`` — inferred from keyword matching when absent.
* ``keywords`` — list of distinctive tokens for downstream search /
  duplicate detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from config.settings import Settings, get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


# Tokens that appear in manifests but carry no semantic value.
_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(open\s*box|customer\s*return|used|refurb(ished)?|salvage)\b", re.I),
    re.compile(r"\b(brand\s*new|new\s*in\s*box|sealed)\b", re.I),
    re.compile(r"\b(lot\s*of\s*\d+|pack\s*of\s*\d+|set\s*of\s*\d+)\b", re.I),
    re.compile(r"[\(\[][^\)\]]*[\)\]]"),     # parenthetical noise
    re.compile(r"[\*#~`]+"),                   # decorative chars
    re.compile(r"\s{2,}"),                     # collapse whitespace
)

_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on",
    "by", "at", "from", "size", "color", "colour", "pcs", "pc", "pack",
    "set", "lot", "new", "used",
})

# Heuristic keyword → category mapping.  Order matters: first match wins.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("electronics", ("phone", "mobile", "laptop", "tablet", "headphone",
                     "earbud", "earphone", "speaker", "tv", "monitor",
                     "camera", "smartwatch", "router", "charger", "cable")),
    ("kitchen",     ("mixer", "grinder", "kettle", "toaster", "cookware",
                     "pan", "pressure cooker", "blender", "microwave")),
    ("home",        ("bedsheet", "pillow", "curtain", "lamp", "vacuum",
                     "iron", "fan", "heater", "rug")),
    ("apparel",     ("shirt", "tshirt", "jeans", "trouser", "kurta",
                     "saree", "jacket", "shoe", "sneaker", "dress")),
    ("beauty",      ("shampoo", "lotion", "cream", "perfume", "lipstick",
                     "foundation", "serum", "moisturiser", "moisturizer")),
    ("toys",        ("toy", "puzzle", "lego", "doll", "rc car", "board game")),
    ("books",       ("book", "novel", "textbook")),
    ("stationery",  ("pen", "pencil", "notebook", "diary", "stapler")),
)


@dataclass(frozen=True)
class ManifestCleaner:
    """Apply text cleaning and attribute extraction to a manifest."""

    settings: Settings

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``df`` augmented with cleaned fields."""
        logger.info("Cleaning %d rows", len(df))
        out = df.copy()

        out["product_name_clean"] = out["product_name"].map(self._clean_name)
        out["keywords"] = out["product_name_clean"].map(self._extract_keywords)
        out["brand"] = self._fill_brand(out)
        out["category"] = self._fill_category(out)

        # Standardise numeric fields: clip negatives to NaN, ensure floats.
        for col in ("mrp", "floor_price"):
            out[col] = pd.to_numeric(out[col], errors="coerce")
            out.loc[out[col] <= 0, col] = np.nan

        out["quantity"] = (
            pd.to_numeric(out["quantity"], errors="coerce").fillna(1).astype(int)
        )

        logger.info(
            "Cleaning complete. Brands resolved=%d, categories resolved=%d",
            out["brand"].notna().sum(),
            (out["category"].fillna("unknown") != "unknown").sum(),
        )
        return out

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_name(name: object) -> str:
        if not isinstance(name, str) or not name.strip():
            return ""
        cleaned = name
        for pattern in _NOISE_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = re.sub(r"[^\w\s\-/&]+", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned.title()

    @staticmethod
    def _extract_keywords(name: str) -> list[str]:
        if not name:
            return []
        tokens = (t.lower().strip("-/&") for t in name.split())
        keywords = [t for t in tokens if t and t not in _STOPWORDS and len(t) > 2]
        # Dedupe while preserving order.
        seen: set[str] = set()
        out: list[str] = []
        for token in keywords:
            if token not in seen:
                seen.add(token)
                out.append(token)
        return out

    # ------------------------------------------------------------------
    # Attribute extraction
    # ------------------------------------------------------------------

    def _fill_brand(self, df: pd.DataFrame) -> pd.Series:
        known = self.settings.known_brands
        existing = df["brand"].astype("string").str.lower().str.strip()

        def infer(row: pd.Series) -> str | None:
            current = row["brand_lc"]
            if isinstance(current, str) and current and current != "<na>":
                return current.title()
            for token in row["keywords"]:
                if token in known:
                    return token.title()
            return None

        work = df.assign(brand_lc=existing)
        return work.apply(infer, axis=1).astype("string")

    def _fill_category(self, df: pd.DataFrame) -> pd.Series:
        existing = df["category"].astype("string").str.lower().str.strip()

        def infer(row: pd.Series) -> str:
            current = row["category_lc"]
            if isinstance(current, str) and current and current != "<na>":
                if current in self.settings.category_demand:
                    return current
            haystack = " ".join(row["keywords"])
            for cat, kws in _CATEGORY_KEYWORDS:
                if any(_keyword_hit(kw, haystack) for kw in kws):
                    return cat
            return "unknown"

        work = df.assign(category_lc=existing)
        return work.apply(infer, axis=1).astype("string")


def clean_manifest(df: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Functional wrapper around :class:`ManifestCleaner`."""
    return ManifestCleaner(settings or get_settings()).clean(df)


def _keyword_hit(keyword: str, haystack: str) -> bool:
    """Token-prefix match so plurals/variants ("earbuds") still hit "earbud".

    Multi-word keywords ("pressure cooker") are matched as a contiguous
    substring with whitespace boundaries.
    """
    if " " in keyword:
        return f" {keyword} " in f" {haystack} "
    return any(token.startswith(keyword) for token in haystack.split())


def supported_categories() -> Iterable[str]:
    """Return the set of categories the heuristic resolver can produce."""
    return tuple(cat for cat, _ in _CATEGORY_KEYWORDS) + ("unknown",)
