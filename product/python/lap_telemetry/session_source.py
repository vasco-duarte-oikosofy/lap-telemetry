"""Load a recorded session, merging recorder rotation shards.

The recorder writes ``session_<utc>_<track>_<sim>.partN.parquet`` while a
session is open and may leave them behind after a hard kill. Analysis wants one
table, so this module resolves any shard (or the final file) to the full,
ordered set and concatenates it **in memory**: shards are a recording detail,
not something the debrief should materialise as a new file.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


_SHARD_RE = re.compile(r"^(session_.+)\.part(\d+)\.parquet$")


@dataclass
class SessionSource:
    """A session table plus the metadata needed to describe it."""

    table: pa.Table
    meta: dict[str, Any] = field(default_factory=dict)
    shards: list[Path] = field(default_factory=list)
    stem: str = ""

    @property
    def track(self) -> str | None:
        return self.meta.get("track")

    @property
    def vehicle_name(self) -> str | None:
        return self.meta.get("vehicle_name")

    @property
    def sample_rate_hz(self) -> float | None:
        rate = self.meta.get("sample_rate_hz")
        return float(rate) if rate else None

    @property
    def shard_count(self) -> int:
        return len(self.shards) or 1


def shard_group(path: Path) -> tuple[str, list[Path]]:
    """Resolve a session path (optionally a ``.partN.parquet``) to its shards."""
    match = _SHARD_RE.match(path.name)
    if match:
        stem = match.group(1)
        group = [
            p for p in path.parent.glob(f"{stem}.part*.parquet") if _SHARD_RE.match(p.name)
        ]
    else:
        stem = path.stem
        group = []

    if not group:
        return stem, [path]

    group.sort(key=lambda p: int(_SHARD_RE.match(p.name).group(2)))  # type: ignore[union-attr]
    return stem, group


def load_session(path: Path | str) -> SessionSource:
    """Read a session, merging rotation shards in numeric part order."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"session not found: {path}")

    stem, shards = shard_group(path)
    tables = [pq.read_table(shard) for shard in shards]
    table = tables[0] if len(tables) == 1 else pa.concat_tables(tables)

    sidecar = path.parent / f"{stem}.json"
    meta: dict[str, Any] = {}
    if sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}

    return SessionSource(table=table, meta=meta, shards=shards, stem=stem)
