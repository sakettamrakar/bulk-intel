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
    "raw_category",
    "normalized_category",
    "condition_normalized",
    "quantity",
    "mrp",
    "floor_price",
    "amazon_price",
    "real_price",
    "wholesale_price",
    "match_confidence",
    "unreliable_match",
    "discount_percentage",
    "platform_fee_pct",
    "market_gap",
    "sellability_score",
    "risk_score",
    "transport_cost",
    "expected_revenue",
    "inspection_cost",
    "expected_profit",
    "expected_margin_pct",
    "expected_roi_pct",
    "scenario_roi_low",
    "scenario_roi_median",
    "scenario_roi_high",
    "recommendation",
    "confidence_gate_applied",
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
        json_path = self.out_dir / f"{base_name}_summary.json"

        ranked.to_csv(csv_path, index=False)
        logger.info("Wrote ranked CSV: %s", csv_path)

        summary_path.write_text(self._build_summary(ranked), encoding="utf-8")
        logger.info("Wrote summary: %s", summary_path)

        lot_summary = df.attrs.get("lot_summary", {})
        if lot_summary:
            import json
            json_path.write_text(json.dumps(lot_summary, indent=2), encoding="utf-8")
            logger.info("Wrote JSON summary: %s", json_path)
            return {"csv": csv_path, "summary": summary_path, "json": json_path}

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
        counts = {label: int((rec == label).sum()) for label in ("BUY", "REVIEW", "SKIP")}

        lines: list[str] = []
        lines.append("=" * 78)
        lines.append("LIQUIDATION INTELLIGENCE — MANIFEST SUMMARY")
        lines.append("=" * 78)
        lines.append(f"Total rows           : {total}")
        lines.append(f"  BUY                : {counts['BUY']}")
        lines.append(f"  REVIEW             : {counts['REVIEW']}")
        lines.append(f"  SKIP               : {counts['SKIP']}")
        lines.append("")

        for label in ("BUY", "REVIEW"):
            subset = df[rec == label]
            if subset.empty:
                continue
            revenue = float(subset["expected_revenue"].sum(skipna=True))
            cost = float(subset["expected_cost"].sum(skipna=True))
            profit = float(subset["expected_profit"].sum(skipna=True))
            roi = (profit / cost * 100.0) if cost > 0 else 0.0
            lines.append(f"--- {label} basket ({len(subset)} items) ---")
            lines.append(f"  projected revenue: {revenue:>14,.2f}")
            lines.append(f"  projected cost   : {cost:>14,.2f}")
            lines.append(f"  projected profit : {profit:>14,.2f}")
            lines.append(f"  projected ROI    : {roi:>13,.1f}%")
            lines.append("")

        top_buys = df[rec == "BUY"].head(10)
        lines.append("Top BUY candidates (by sellability):")
        if top_buys.empty:
            lines.append("  (none — review thresholds in config/settings.py)")
        else:
            for _, row in top_buys.iterrows():
                name = str(row.get("product_name_clean", ""))[:48]
                lines.append(
                    f"  - {str(row.get('sku', '')):<28} "
                    f"{name:<48} "
                    f"sell={row.get('sellability_score', 0):>5.1f} "
                    f"risk={row.get('risk_score', 0):>5.1f} "
                    f"ROI={row.get('expected_roi_pct', 0):>6.1f}% "
                    f"profit={row.get('expected_profit', 0):>9.2f}"
                )
        lines.append("=" * 78)
        return "\n".join(lines) + "\n"


def write_outputs(
    df: pd.DataFrame, out_dir: str | Path, base_name: str = "manifest_report"
) -> dict[str, Path]:
    """Convenience wrapper around :class:`Reporter`."""
    return Reporter(Path(out_dir)).write(df, base_name=base_name)
