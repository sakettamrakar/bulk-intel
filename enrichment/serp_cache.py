"""SQLite cache for structured SERP price lookups.

The cache is single-writer and keyed by a content hash of normalized title
plus backend name. It does not implement cross-process locking; pipeline
runs are expected to be single-process.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable


class SerpCache:
    """Small SQLite-backed cache for SERP lookup payloads."""

    def __init__(
        self,
        path: str | Path,
        ttl_hours: int,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self.path = Path(path)
        self.ttl_seconds = int(ttl_hours * 3600)
        self._now_fn = now_fn or time.time
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get(self, key: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT payload, created_at FROM serp_cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        payload, created_at = row
        if self._now() - int(created_at) > self.ttl_seconds:
            return None
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def set(self, key: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO serp_cache(key, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (key, encoded, int(self._now())),
            )
            conn.commit()

    def purge(self, now: int | None = None) -> None:
        cutoff = int(now if now is not None else self._now()) - self.ttl_seconds
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM serp_cache WHERE created_at < ?", (cutoff,))
            conn.commit()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS serp_cache (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _now(self) -> float:
        return float(self._now_fn())


def cache_key(normalized_title: str, backend_name: str) -> str:
    """Return SHA-256 cache key for a normalized title/backend pair."""
    material = f"{normalized_title}|{backend_name}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()
