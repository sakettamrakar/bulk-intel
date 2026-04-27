"""Read raw manifest files and produce a normalized ``DataFrame``.

The ingestion layer is the only place that should know about file
formats and source-specific column names.  Downstream stages can rely
on the canonical schema documented in :data:`CANONICAL_COLUMNS`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from utils.logging import get_logger

logger = get_logger(__name__)


# Canonical schema produced by the loader.  Downstream modules read these names.
CANONICAL_COLUMNS: tuple[str, ...] = (
    "sku",
    "product_name",
    "category",
    "raw_category",
    "brand",
    "quantity",
    "mrp",
    "floor_price",
    "condition",
)

# Mapping of common source aliases to the canonical column names above.
COLUMN_ALIASES: Mapping[str, str] = {
    # SKU / identifier
    "sku": "sku",
    "item_code": "sku",
    "item_id": "sku",
    "product_id": "sku",
    "asin": "sku",
    "tag_number": "sku",
    "inventory_id": "sku",
    # Product description
    "product_name": "product_name",
    "product": "product_name",
    "description": "product_name",
    "item_description": "product_name",
    "product_description": "product_name",
    "title": "product_name",
    # Category
    "category": "category",
    "product_category": "category",
    "dept": "category",
    "department": "category",
    # Brand
    "brand": "brand",
    "manufacturer": "brand",
    # Quantity
    "quantity": "quantity",
    "qty": "quantity",
    "units": "quantity",
    "stock": "quantity",
    # MRP / RRP
    "mrp": "mrp",
    "mrp_in_inr": "mrp",
    "mrp_inr": "mrp",
    "retail_price": "mrp",
    "rrp": "mrp",
    "list_price": "mrp",
    "msrp": "mrp",
    # Floor / liquidation price
    "floor_price": "floor_price",
    "floor": "floor_price",
    "liquidation_price": "floor_price",
    "starting_bid": "floor_price",
    "reserve_price": "floor_price",
    # Condition
    "condition": "condition",
    "grade": "condition",
    "item_condition": "condition",
}

NUMERIC_COLUMNS: tuple[str, ...] = ("quantity", "mrp", "floor_price")


@dataclass(frozen=True)
class ManifestLoader:
    """Configurable loader for liquidation manifest files.

    The loader is stateless aside from its configuration so multiple
    threads can share a single instance safely.
    """

    sheet_name: str | int | None = 0
    encoding: str = "utf-8"

    def load(self, path: str | Path) -> pd.DataFrame:
        """Read ``path`` and return a normalized manifest ``DataFrame``.

        Args:
            path: Path to a ``.csv``, ``.xlsx`` or ``.xls`` manifest.

        Returns:
            DataFrame with the canonical schema; missing columns are
            present but filled with ``NA``.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the file extension is not supported.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {path}")

        logger.info("Loading manifest: %s", path)
        raw = self._read_raw(path)
        logger.info("Raw rows=%d, columns=%d", len(raw), raw.shape[1])

        normalized = self._normalize_columns(raw)
        normalized = self._coerce_types(normalized)
        normalized = self._handle_missing(normalized)

        logger.info(
            "Normalized rows=%d (after dropping fully-empty); columns=%s",
            len(normalized),
            list(normalized.columns),
        )
        return normalized

    # ------------------------------------------------------------------
    # Implementation details
    # ------------------------------------------------------------------

    def _read_raw(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, encoding=self.encoding)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(path, sheet_name=self.sheet_name)
        raise ValueError(
            f"Unsupported manifest format '{suffix}'. Use .csv, .xls or .xlsx."
        )

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        renamed = df.rename(columns={c: _canon_key(c) for c in df.columns})
        renamed = self._retain_raw_category(renamed)
        rename_map = {c: COLUMN_ALIASES[c] for c in renamed.columns if c in COLUMN_ALIASES}
        renamed = renamed.rename(columns=rename_map)

        # Drop duplicate columns produced by aliasing (keep first).
        renamed = renamed.loc[:, ~renamed.columns.duplicated()]

        # Ensure every canonical column exists.
        for col in CANONICAL_COLUMNS:
            if col not in renamed.columns:
                logger.debug("Adding missing canonical column '%s'", col)
                renamed[col] = pd.NA

        # Reorder so canonical columns come first; preserve any extras.
        extras = [c for c in renamed.columns if c not in CANONICAL_COLUMNS]
        return renamed[list(CANONICAL_COLUMNS) + extras]

    @staticmethod
    def _retain_raw_category(df: pd.DataFrame) -> pd.DataFrame:
        """Combine hierarchical ``Category L1..Ln`` columns into ``raw_category``.

        We deliberately do *not* collapse to a single normalized label here —
        that's the cleaner's job.  Instead we keep the full ``L1 > L2 > L3``
        breadcrumb in ``raw_category`` so downstream stages and reports can
        refer back to the source taxonomy.

        After combining, the per-level ``category_l<n>`` columns are dropped
        to keep the downstream DataFrame tidy (they're fully redundant with
        ``raw_category``).
        """
        level_cols = sorted(
            (c for c in df.columns if re.fullmatch(r"category_l\d+", c) or c == "category"),
        )
        level_only = [c for c in level_cols if c != "category"]
        if not level_cols:
            return df

        df = df.copy()

        def combine_cats(row):
            cats = [str(row[c]).strip() for c in level_cols if pd.notna(row[c]) and str(row[c]).strip()]
            return " > ".join(cats) if cats else pd.NA

        df["raw_category"] = df.apply(combine_cats, axis=1)

        # ``category`` is a working alias the cleaner will overwrite with the
        # normalized label.  Seed it from ``raw_category`` if the source had
        # no flat category column.
        if "category" not in df.columns:
            df["category"] = df["raw_category"]

        if level_only:
            df = df.drop(columns=level_only)

        return df

    def _coerce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in NUMERIC_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in ("sku", "product_name", "category", "brand", "condition"):
            df[col] = df[col].astype("string").str.strip()

        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        # Drop rows that have no product_name AND no sku — they're junk.
        before = len(df)
        df = df.dropna(subset=["product_name", "sku"], how="all").reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            logger.warning("Dropped %d junk rows (no SKU or product name)", dropped)

        # Quantity defaults to 1 (single-item lots are common in manifests).
        df["quantity"] = df["quantity"].fillna(1).astype("Int64")
        return df


def load_manifest(path: str | Path, **kwargs) -> pd.DataFrame:
    """Convenience wrapper around :class:`ManifestLoader` for one-off loads."""
    return ManifestLoader(**kwargs).load(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANON_RE = re.compile(r"[^a-z0-9]+")
_CATEGORY_PLACEHOLDERS: frozenset[str] = frozenset(
    {"others", "other", "misc", "miscellaneous", "n/a", "na", "none", "-"}
)


def _pick_deepest_category(row: pd.Series) -> str | None:
    """Return the deepest non-empty, non-placeholder level value.

    If only placeholder values ("Others", "Misc", ...) exist, return the
    deepest of those so we still surface *something* for the cleaner.
    """
    cells = [v.strip() for v in row.tolist() if isinstance(v, str) and v.strip()]
    if not cells:
        return None
    for value in reversed(cells):
        if value.lower() not in _CATEGORY_PLACEHOLDERS:
            return value
    return cells[-1]


def _canon_key(name: object) -> str:
    """Lower-case, snake-case a column name for alias lookup."""
    s = str(name).strip().lower()
    s = _CANON_RE.sub("_", s).strip("_")
    return s


def list_supported_aliases() -> Iterable[str]:
    """Return the source column aliases recognised by the loader."""
    return sorted(COLUMN_ALIASES.keys())
