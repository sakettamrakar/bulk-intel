"""Persist scored manifests and produce a human-readable summary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from utils.logging import get_logger

logger = get_logger(__name__)


# Columns surfaced to the operator (in order).  Extra columns from the
# raw manifest still flow through but won't lead the report.
PRIMARY_COLUMNS: tuple[str, ...] = (
    "sku",
    "product_name_clean",
    "brand",
    "category",
    "quantity",
    "mrp",
    "floor_price",
    "market_price",
    "wholesale_price",
    "discount_percentage",
    "market_gap",
    "sellability_score",
    "risk_score",
    "expected_revenue",
    "expected_profit",
    "expected_margin_pct",
    "recommendation",
    "reasoning",
)


@dataclass(frozen=True)
class Reporter:
    """Write a ranked CSV and a plain-text summary to ``out_dir``."""

    out_dir: Path

    def write(self, df: pd.DataFrame, base_name: str = "manifest_report") -> dict[str, Path]:
        """Persist outputs and return ``{"csv": path, "summary": path}``.

        The CSV is sorted by descending sellability so operators can
        triage from the top.
        """
        self.out_dir.mkdir(parents=True, exist_ok=True)
        ranked = self._rank(df)

        csv_path = self.out_dir / f"{base_name}.csv"
        summary_path = self.out_dir / f"{base_name}_summary.txt"

        ranked.to_csv(csv_path, index=False)
        logger.info("Wrote ranked CSV: %s", csv_path)

        summary_path.write_text(self._build_summary(ranked), encoding="utf-8")
        logger.info("Wrote summary: %s", summary_path)

        return {"csv": csv_path, "summary": summary_path}

    # ------------------------------------------------------------------

    @staticmethod
    def _rank(df: pd.DataFrame) -> pd.DataFrame:
        ordered = [c for c in PRIMARY_COLUMNS if c in df.columns]
        extras = [c for c in df.columns if c not in ordered]
        ranked = df[ordered + extras].copy()
        if "sellability_score" in ranked.columns:
            ranked = ranked.sort_values(
                by=["sellability_score", "expected_profit"],
                ascending=[False, False],
                na_position="last",
            ).reset_index(drop=True)
        return ranked

    @staticmethod
    def _build_summary(df: pd.DataFrame) -> str:
        total = len(df)
        if total == 0:
            return "No rows in manifest.\n"

        rec = df.get("recommendation", pd.Series(dtype="string")).fillna("")
        buy = int((rec == "BUY").sum())
        review = int((rec == "REVIEW").sum())
        skip = int((rec == "SKIP").sum())

        total_profit = float(df.get("expected_profit", pd.Series(dtype=float)).sum(skipna=True))
        total_revenue = float(df.get("expected_revenue", pd.Series(dtype=float)).sum(skipna=True))
        avg_margin = float(df.get("expected_margin_pct", pd.Series(dtype=float)).mean(skipna=True) or 0.0)

        top_buys = df[df["recommendation"] == "BUY"].head(5) if "recommendation" in df.columns else df.head(0)

        lines: list[str] = []
        lines.append("=" * 72)
        lines.append("LIQUIDATION INTELLIGENCE — MANIFEST SUMMARY")
        lines.append("=" * 72)
        lines.append(f"Total rows           : {total}")
        lines.append(f"Recommendation BUY   : {buy}")
        lines.append(f"Recommendation REVIEW: {review}")
        lines.append(f"Recommendation SKIP  : {skip}")
        lines.append("")
        lines.append(f"Projected revenue    : {total_revenue:,.2f}")
        lines.append(f"Projected profit     : {total_profit:,.2f}")
        lines.append(f"Average margin       : {avg_margin:.2f}%")
        lines.append("")
        lines.append("Top BUY candidates:")
        if top_buys.empty:
            lines.append("  (none — review thresholds in config/settings.py)")
        else:
            for _, row in top_buys.iterrows():
                lines.append(
                    f"  - {row.get('sku', ''):<14} "
                    f"{str(row.get('product_name_clean',''))[:48]:<48} "
                    f"sell={row.get('sellability_score', 0):>5.1f} "
                    f"risk={row.get('risk_score', 0):>5.1f} "
                    f"profit={row.get('expected_profit', 0):>10.2f}"
                )
        lines.append("=" * 72)
        return "\n".join(lines) + "\n"


def write_outputs(
    df: pd.DataFrame, out_dir: str | Path, base_name: str = "manifest_report"
) -> dict[str, Path]:
    """Convenience wrapper around :class:`Reporter`."""
    return Reporter(Path(out_dir)).write(df, base_name=base_name)
