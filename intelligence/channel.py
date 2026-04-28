"""Assigns each row a target platform based on deterministic rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from config.settings import Settings


def _predicate_matches(row: pd.Series, k: str, v: Any, settings: Settings) -> bool:
    if k == "brand_known":
        brand = str(row.get("brand", "")).lower()
        is_known = brand in settings.known_brands
        if isinstance(v, bool):
            return is_known == v
        return False

    val = row.get(k)
    if isinstance(v, (tuple, list, set)):
        return val in v
    return val == v


@dataclass(frozen=True)
class ChannelRouter:
    """Assigns a platform for liquidation marketplace listing."""
    settings: Settings

    def route(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of df with a ``platform`` column populated."""
        out = df.copy()
        platforms = []
        for _, row in out.iterrows():
            platforms.append(self._match_row(row))
        out["platform"] = platforms
        return out

    def _match_row(self, row: pd.Series) -> str:
        for rule in self.settings.channel_routing_rules:
            cond = rule["condition"]
            if all(_predicate_matches(row, k, v, self.settings) for k, v in cond.items()):
                return str(rule["platform"])
        return self.settings.default_platform
