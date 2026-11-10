"""``lap-telemetry debrief`` — whole-session coaching entry point.

Slice 01 ships the lap inventory only. The analysis, report and conversation
land in later slices; until then, anything but ``--list`` says so instead of
pretending.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .lap_inventory_view import format_inventory
from .session_laps import classify_laps
from .session_source import load_session


def run(path: Path, *, list_only: bool = False) -> int:
    if not path.exists():
        print(f"lap-telemetry debrief: path not found: {path}", file=sys.stderr)
        return 1

    if not list_only:
        print(
            "lap-telemetry debrief: full analysis is not implemented yet.\n"
            "Use --list to inspect the session's laps.",
            file=sys.stderr,
        )
        return 1

    session = load_session(path)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    if not records:
        print("lap-telemetry debrief: the session contains no laps", file=sys.stderr)
        return 1

    meta = dict(session.meta)
    meta.setdefault("stem", session.stem)
    print(format_inventory(records, meta, shard_count=session.shard_count))
    return 0
