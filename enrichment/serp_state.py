"""JSON run-state for partial SERP execution.

Schema:
``manifest_hash`` is the SHA-256 of sorted search signatures for the current
groups DataFrame. ``completed_signatures`` and ``failed_signatures`` are
signature tuples used by incremental mode to resume safely. Writes are
atomic: state is written to ``*.tmp`` and then replaced into place.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class SerpRunState:
    """Persisted state for resumable group-level SERP runs."""

    manifest_hash: str
    started_at: str
    last_updated_at: str
    completed_signatures: tuple[str, ...]
    failed_signatures: tuple[str, ...]
    mode: str
    mid_run_backend_switch: bool = False


def load_state(path: Path) -> SerpRunState | None:
    """Load state JSON, returning ``None`` if absent or invalid."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return SerpRunState(
            manifest_hash=str(data["manifest_hash"]),
            started_at=str(data["started_at"]),
            last_updated_at=str(data["last_updated_at"]),
            completed_signatures=tuple(data.get("completed_signatures", ())),
            failed_signatures=tuple(data.get("failed_signatures", ())),
            mode=str(data["mode"]),
            mid_run_backend_switch=bool(data.get("mid_run_backend_switch", False)),
        )
    except (KeyError, TypeError):
        return None


def save_state(state: SerpRunState, path: Path) -> None:
    """Atomically write state JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = asdict(state)
    payload["completed_signatures"] = list(state.completed_signatures)
    payload["failed_signatures"] = list(state.failed_signatures)
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
