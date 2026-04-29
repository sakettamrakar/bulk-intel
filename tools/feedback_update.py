"""T-305 — outcome feedback loop CLI.

Ingests a realised-outcomes CSV, computes per-category realised return rate,
holding days, and sell-through, applies a Bayesian-style shrinkage update
against the current priors, and writes a new versioned priors JSON.

usage:
    python -m tools.feedback_update \\
        --outcomes data/historical/lot_X.csv \\
        --current-priors config/priors/latest.json \\
        --new-priors config/priors/v3.json \\
        [--shrinkage 20] \\
        [--apply]

The shrinkage knob trades off responsiveness vs stability: ``new = (alpha *
prior + N * observed) / (alpha + N)`` — small alpha = priors move freely with
each new lot; large alpha = priors barely move on a single observation.

The outcomes CSV must include ``category`` and ``quantity`` columns alongside
the realised columns produced by T-205 (see ``data/historical/EXAMPLE_lot_outcomes.csv``).
If your outcomes file omits them, merge against your manifest first.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = (
    "sku",
    "realised_units_sold",
    "realised_returns",
    "realised_holding_days",
)


def shrink(prior: float, observed: float, n: int, alpha: float) -> float:
    """Bayesian-style shrinkage: ``(alpha * prior + n * observed) / (alpha + n)``.

    With small ``n`` (few observations) the result stays close to the prior;
    with large ``n`` and consistent data, it moves to the empirical value.
    """
    if alpha + n <= 0:
        return prior
    return (alpha * prior + n * observed) / (alpha + n)


def aggregate_by_category(outcomes: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Per-category realised stats from the outcomes frame.

    Returns ``{category: {"observations", "return_rate", "holding_days",
    "sell_through"}}``.  ``sell_through`` only appears when ``quantity`` is
    present.
    """
    if "category" not in outcomes.columns:
        raise ValueError(
            "outcomes CSV is missing a 'category' column — merge it against "
            "the manifest before feeding it into the feedback loop"
        )

    out: dict[str, dict[str, float]] = {}
    grouped = outcomes.groupby(outcomes["category"].astype(str).str.lower())
    for cat, group in grouped:
        units_sold = pd.to_numeric(group["realised_units_sold"], errors="coerce").fillna(0)
        returns = pd.to_numeric(group["realised_returns"], errors="coerce").fillna(0)
        holding_days = pd.to_numeric(group["realised_holding_days"], errors="coerce").dropna()

        sold_total = float(units_sold.sum())
        rate = float(returns.sum() / sold_total) if sold_total > 0 else 0.0

        stats: dict[str, float] = {
            "observations": int(len(group)),
            "return_rate": round(rate, 4),
            "holding_days": round(float(holding_days.mean()), 2) if not holding_days.empty else 0.0,
        }
        if "quantity" in group.columns:
            qty = pd.to_numeric(group["quantity"], errors="coerce").fillna(0)
            qty_total = float(qty.sum())
            if qty_total > 0:
                stats["sell_through"] = round(sold_total / qty_total, 4)
        out[cat] = stats
    return out


def update_priors(
    current: Mapping[str, Any],
    aggregates: Mapping[str, Mapping[str, float]],
    alpha: float,
) -> dict[str, Any]:
    """Apply shrinkage to the priors snapshot and bump the version metadata."""
    new_return = dict(current.get("category_return_rate", {}))
    new_hold = dict(current.get("category_holding_days", {}))

    for cat, stats in aggregates.items():
        n = int(stats.get("observations", 0))
        if cat in new_return:
            new_return[cat] = round(
                shrink(new_return[cat], stats["return_rate"], n, alpha), 4
            )
        if cat in new_hold and stats.get("holding_days", 0) > 0:
            new_hold[cat] = int(round(
                shrink(new_hold[cat], stats["holding_days"], n, alpha)
            ))

    next_version = _bump_version(current.get("version", "v0"))
    total_obs = int(current.get("source_observations", 0)) + sum(
        int(s.get("observations", 0)) for s in aggregates.values()
    )
    return {
        "version": next_version,
        "created_at": pd.Timestamp.utcnow().date().isoformat(),
        "source_observations": total_obs,
        "category_return_rate": new_return,
        "category_holding_days": new_hold,
        "condition_to_sell_through": dict(current.get("condition_to_sell_through", {})),
    }


def _bump_version(current: str) -> str:
    if current.startswith("v") and current[1:].isdigit():
        return f"v{int(current[1:]) + 1}"
    return "v1"


def diff_priors(old: Mapping[str, Any], new: Mapping[str, Any]) -> str:
    """Human-readable summary of how the priors moved."""
    lines: list[str] = [
        f"Priors {old.get('version', '?')} → {new.get('version', '?')} "
        f"(observations: {old.get('source_observations', 0)} → {new.get('source_observations', 0)})",
        "",
    ]
    for key in ("category_return_rate", "category_holding_days"):
        lines.append(f"## {key}")
        old_map = old.get(key, {})
        new_map = new.get(key, {})
        cats = sorted(set(old_map) | set(new_map))
        deltas: list[tuple[str, float, float, float]] = []
        for cat in cats:
            o = float(old_map.get(cat, 0))
            n = float(new_map.get(cat, 0))
            deltas.append((cat, o, n, n - o))
        deltas.sort(key=lambda t: abs(t[3]), reverse=True)
        for cat, o, n, d in deltas:
            if abs(d) < 1e-6:
                continue
            lines.append(f"  {cat:<14} {o:>8.4f}  →  {n:>8.4f}   (Δ {d:+.4f})")
        lines.append("")
    return "\n".join(lines)


def run(
    outcomes_path: Path,
    current_priors_path: Path,
    new_priors_path: Path,
    alpha: float,
    apply: bool,
) -> dict[str, Any]:
    if not outcomes_path.exists():
        raise FileNotFoundError(f"outcomes CSV not found: {outcomes_path}")
    if not current_priors_path.exists():
        raise FileNotFoundError(f"current priors not found: {current_priors_path}")

    outcomes = pd.read_csv(outcomes_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in outcomes.columns]
    if missing:
        raise ValueError(f"outcomes CSV missing required columns: {missing}")

    current = json.loads(current_priors_path.read_text(encoding="utf-8"))
    aggregates = aggregate_by_category(outcomes)
    new_priors = update_priors(current, aggregates, alpha=alpha)

    new_priors_path.parent.mkdir(parents=True, exist_ok=True)
    new_priors_path.write_text(json.dumps(new_priors, indent=2), encoding="utf-8")
    logger.info("wrote %s", new_priors_path)

    print(diff_priors(current, new_priors))

    latest = current_priors_path.parent / "latest.json"
    if apply:
        shutil.copyfile(new_priors_path, latest)
        logger.info("applied: %s -> %s", new_priors_path, latest)
        print(f"\nApplied: {latest} now points to {new_priors['version']}")
    else:
        print("\n(dry-run — pass --apply to overwrite latest.json)")

    return new_priors


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="feedback_update", description=__doc__)
    parser.add_argument("--outcomes", required=True, help="Realised outcomes CSV path")
    parser.add_argument(
        "--current-priors",
        default="config/priors/latest.json",
        help="Path to the priors snapshot to update against",
    )
    parser.add_argument(
        "--new-priors",
        required=True,
        help="Path to write the updated priors snapshot",
    )
    parser.add_argument(
        "--shrinkage",
        type=float,
        default=20.0,
        help="Bayesian shrinkage alpha (default 20). Higher = priors move less per lot.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy the new priors to latest.json (otherwise dry-run only)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv)
    try:
        run(
            outcomes_path=Path(args.outcomes),
            current_priors_path=Path(args.current_priors),
            new_priors_path=Path(args.new_priors),
            alpha=float(args.shrinkage),
            apply=bool(args.apply),
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
