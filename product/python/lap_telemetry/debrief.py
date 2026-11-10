"""``lap-telemetry debrief`` — whole-session coaching entry point.

Slices 01–02 ship the lap inventory and the per-lap facts. The report and the
conversation land in later slices; until then, anything but ``--list`` and
``--json`` says so instead of pretending.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .lap_inventory_view import format_inventory
from .session_facts import build_session_facts, excluded_laps
from .session_inputs import DebriefInputError, resolve_debrief_inputs
from .session_laps import MIN_ELIGIBLE_LAPS, LapStatus, classify_laps
from .session_source import load_session


def _gate_message(excluded, eligible_count: int) -> str:
    lines = [
        f"lap-telemetry debrief: {eligible_count} eligible lap(s); "
        f"a debrief needs at least {MIN_ELIGIBLE_LAPS}.",
        "",
    ]
    for item in excluded:
        lines.append(
            f"  seg {item.segment_index:>2}  lap {item.lap_number:>2}  "
            f"{item.duration_s:8.3f} s  {item.status:<10}  {item.reason}"
        )
    return "\n".join(lines)


def run(
    path: Path,
    *,
    list_only: bool = False,
    json_only: bool = False,
    report_only: bool = False,
    out_dir: Path | None = None,
    reference: Path | None = None,
    track_model_path: Path | None = None,
    track: str | None = None,
    vehicle_name: str | None = None,
) -> int:
    if not path.exists():
        print(f"lap-telemetry debrief: path not found: {path}", file=sys.stderr)
        return 1

    session = load_session(path)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    if not records:
        print("lap-telemetry debrief: the session contains no laps", file=sys.stderr)
        return 1

    if list_only:
        meta = dict(session.meta)
        meta.setdefault("stem", session.stem)
        print(format_inventory(records, meta, shard_count=session.shard_count))
        return 0

    eligible = [r for r in records if r.status == LapStatus.ELIGIBLE]
    if len(eligible) < MIN_ELIGIBLE_LAPS:
        print(_gate_message(excluded_laps(records), len(eligible)), file=sys.stderr)
        return 1

    try:
        inputs = resolve_debrief_inputs(
            session,
            track=track,
            vehicle_name=vehicle_name,
            reference=reference,
            track_model_path=track_model_path,
        )
    except DebriefInputError as exc:
        print(f"lap-telemetry debrief: {exc}", file=sys.stderr)
        return 1

    facts = build_session_facts(session, records, inputs)

    if json_only:
        print(json.dumps(facts.to_dict(), indent=2))
        return 0

    if report_only:
        destination = _write_report(facts, session, path, out_dir)
        print(destination)
        return 0

    print(
        "lap-telemetry debrief: the coaching conversation is not implemented yet.\n"
        "Use --report-only for the report, --list for the inventory, or --json "
        "for the facts.",
        file=sys.stderr,
    )
    return 1


def _write_report(facts, session, path: Path, out_dir: Path | None) -> Path:
    """Write the Markdown report next to the session, or into ``out_dir``."""
    from .session_report import render_session_report, report_filename

    target_dir = out_dir if out_dir is not None else path.resolve().parent
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / report_filename(session.stem)
    destination.write_text(render_session_report(facts), encoding="utf-8")
    return destination
