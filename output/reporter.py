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
    "sku_cluster_id",
    "product_name_clean",
    "brand",
    "raw_category",
    "normalized_category",
    "condition_normalized",
    "quantity",
    "platform",
    "mrp",
    "floor_price",
    "amazon_price",
    "real_price",
    "wholesale_price",
    "match_confidence",
    "unreliable_match",
    "discount_percentage",
    "market_gap",
    "sellability_score",
    "risk_score",
    "expected_revenue",
    "expected_cost",
    "acquisition_cost",
    "platform_fee_pct",
    "ancillary_revenue_fee_pct",
    "platform_fee_amount",
    "inspection_cost",
    "transport_cost",
    "return_rate",
    "return_provision",
    "holding_days",
    "holding_cost",
    "expected_profit",
    "expected_profit_p5",
    "expected_profit_p50",
    "expected_profit_p95",
    "expected_margin_pct",
    "expected_roi_pct",
    "expected_roi_p5",
    "expected_roi_p95",
    "prob_profit_positive",
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
        """Persist outputs and return ``{"csv": path, "summary": path, "rollup": path}``.

        The CSV is sorted by descending sellability so operators can triage from the top.
        """
        self.out_dir.mkdir(parents=True, exist_ok=True)
        ranked = self._rank(df)
        rollup = self._build_rollup(df)

        csv_path = self.out_dir / f"{base_name}.csv"
        rollup_path = self.out_dir / f"{base_name}_rollup.csv"
        summary_path = self.out_dir / f"{base_name}_summary.txt"
        json_path = self.out_dir / f"{base_name}_summary.json"

        ranked.to_csv(csv_path, index=False)
        logger.info("Wrote ranked CSV: %s", csv_path)

        if not rollup.empty:
            rollup.to_csv(rollup_path, index=False)
            logger.info("Wrote rollup CSV: %s", rollup_path)

        summary_path.write_text(self._build_summary(ranked), encoding="utf-8")
        logger.info("Wrote summary: %s", summary_path)

        outputs = {"csv": csv_path, "summary": summary_path}
        if not rollup.empty:
            outputs["rollup"] = rollup_path

        lot_summary = df.attrs.get("lot_summary", {})
        if lot_summary:
            import json
            json_path.write_text(json.dumps(lot_summary, indent=2), encoding="utf-8")
            logger.info("Wrote JSON summary: %s", json_path)
            outputs["json"] = json_path

        return outputs

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
    def _build_rollup(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        if "sku_cluster_id" in df.columns and df["sku_cluster_id"].notna().any():
            group_key_col = "sku_cluster_id"
        elif "sku" in df.columns and df["sku"].nunique() / len(df) < 0.5:
            group_key_col = "sku"
        elif "brand" in df.columns and "product_name_clean" in df.columns:
            group_key_col = "group_key"
            df = df.copy()
            df["group_key"] = df["brand"].fillna("").astype(str) + " | " + df["product_name_clean"].fillna("").astype(str)
        elif "product_name_clean" in df.columns:
            group_key_col = "product_name_clean"
        else:
            return pd.DataFrame()

        groups = []
        for key, group in df.groupby(group_key_col):
            units = int(group["quantity"].sum() if "quantity" in group.columns else len(group))
            mrp = round(group["mrp"].mean(), 2) if "mrp" in group.columns else 0.0
            floor_price = round(group["floor_price"].mean(), 2) if "floor_price" in group.columns else 0.0
            real_price = round(group["real_price"].mean(), 2) if "real_price" in group.columns else 0.0
            expected_revenue = group["expected_revenue"].sum() if "expected_revenue" in group.columns else 0.0
            expected_cost = group["expected_cost"].sum() if "expected_cost" in group.columns else 0.0
            expected_profit = group["expected_profit"].sum() if "expected_profit" in group.columns else 0.0
            
            roi_pct = (expected_profit / expected_cost * 100.0) if expected_cost > 0 else 0.0
            
            sellability_score = group["sellability_score"].mean() if "sellability_score" in group.columns else 0.0
            risk_score = group["risk_score"].mean() if "risk_score" in group.columns else 0.0
            
            condition = "unknown"
            if "condition_normalized" in group.columns and not group["condition_normalized"].empty:
                modes = group["condition_normalized"].mode()
                if not modes.empty:
                    condition = str(modes.iloc[0])
            
            recs = group["recommendation"].tolist() if "recommendation" in group.columns else []
            buy_count = recs.count("BUY")
            skip_count = recs.count("SKIP")
            rev_count = recs.count("REVIEW")
            total = len(recs)
            
            if total > 0 and buy_count == total:
                lot_rec = "BUY"
            elif total > 0 and skip_count == total:
                lot_rec = "SKIP"
            elif total > 0 and buy_count > total / 2.0:
                lot_rec = "BUY (majority)"
            elif total > 0 and skip_count > total / 2.0:
                lot_rec = "SKIP (majority)"
            else:
                lot_rec = "REVIEW"
                
            unit_rec_mix = f"BUY:{buy_count} REVIEW:{rev_count} SKIP:{skip_count}"
            
            groups.append({
                "group_key": key,
                "units": units,
                "mrp": mrp,
                "floor_price": floor_price,
                "real_price": real_price,
                "expected_revenue": expected_revenue,
                "expected_cost": expected_cost,
                "expected_profit": expected_profit,
                "expected_roi_pct": round(roi_pct, 2),
                "sellability_score": round(sellability_score, 2),
                "risk_score": round(risk_score, 2),
                "condition_normalized": condition,
                "recommendation": lot_rec,
                "unit_recommendation_mix": unit_rec_mix
            })
            
        if not groups:
            return pd.DataFrame()
            
        rollup_df = pd.DataFrame(groups)
        rollup_df = rollup_df.sort_values(by="expected_profit", ascending=False).reset_index(drop=True)
            
        return rollup_df

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

            # Cost decomposition breakdown
            lines.append(f"  Cost breakdown:")
            acquisition = float(subset.get("acquisition_cost", pd.Series([0.0])).sum(skipna=True))
            platform_fees = float(subset.get("platform_fee_amount", pd.Series([0.0])).sum(skipna=True))
            inspection = float(subset.get("inspection_cost", pd.Series([0.0])).sum(skipna=True))
            transport = float(subset.get("transport_cost", pd.Series([0.0])).sum(skipna=True))
            returns = float(subset.get("return_provision", pd.Series([0.0])).sum(skipna=True))
            holding = float(subset.get("holding_cost", pd.Series([0.0])).sum(skipna=True))

            acq_pct = (acquisition / cost * 100.0) if cost > 0 else 0.0
            plat_pct = (platform_fees / cost * 100.0) if cost > 0 else 0.0
            insp_pct = (inspection / cost * 100.0) if cost > 0 else 0.0
            trans_pct = (transport / cost * 100.0) if cost > 0 else 0.0
            ret_pct = (returns / cost * 100.0) if cost > 0 else 0.0
            hold_pct = (holding / cost * 100.0) if cost > 0 else 0.0

            lines.append(f"    acquisition      : {acquisition:>12,.2f} ({acq_pct:>5.1f}%)")
            lines.append(f"    platform fees    : {platform_fees:>12,.2f} ({plat_pct:>5.1f}%)")
            lines.append(f"    inspection       : {inspection:>12,.2f} ({insp_pct:>5.1f}%)")
            lines.append(f"    transport        : {transport:>12,.2f} ({trans_pct:>5.1f}%)")
            lines.append(f"    return provision : {returns:>12,.2f} ({ret_pct:>5.1f}%)")
            lines.append(f"    holding cost     : {holding:>12,.2f} ({hold_pct:>5.1f}%)")
            lines.append(f"    --------")
            lines.append(f"    total cost       : {cost:>12,.2f}")
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
