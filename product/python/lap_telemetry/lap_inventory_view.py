"""Render the lap inventory as text for ``debrief --list``.

Presentation only: no classification rules live here.
"""
from __future__ import annotations

from typing import Any

from lap_telemetry.lap_signals import yardstick_seconds
from lap_telemetry.session_laps import MIN_ELIGIBLE_LAPS, LapRecord


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(abs(seconds), 60)
    return f"{int(minutes)}:{secs:06.3f}"


def format_inventory(
    records: list[LapRecord],
    meta: dict[str, Any],
    *,
    shard_count: int = 1,
    yardstick_s: float | None = None,
) -> str:
    """Render the human-readable inventory printed by ``debrief --list``."""
    eligible = [r for r in records if r.eligible]
    clean = [r for r in eligible if r.clean]
    if yardstick_s is None:
        yardstick_s = yardstick_seconds([r.duration_s for r in records])

    rate = meta.get("sample_rate_hz")
    rate_text = f"{float(rate):.1f} Hz" if rate else "unknown rate"

    lines = [
        f"session : {meta.get('stem', '?')}",
        f"track   : {meta.get('track') or '?'}",
        f"vehicle : {meta.get('vehicle_name') or '?'}",
        f"shards  : {shard_count}   rate: {rate_text}   yardstick: {_fmt_duration(yardstick_s)}",
        "",
        f"{'seg':>4}  {'lap':>3}  {'frames':>6}  {'duration':>11}  {'status':<10}  reason",
    ]
    for r in records:
        lines.append(
            f"{r.segment_index:>4}  {r.lap_number:>3}  {r.frames:>6}  "
            f"{_fmt_duration(r.duration_s):>11}  {r.status:<10}  {r.reason}"
        )

    summary = (
        f"\n{len(eligible)} of {len(records)} segments eligible "
        f"({len(clean)} clean)."
    )
    if len(eligible) < MIN_ELIGIBLE_LAPS:
        summary += (
            f" A debrief needs at least {MIN_ELIGIBLE_LAPS} eligible laps; "
            "this session is too short or too messy."
        )
    lines.append(summary)
    return "\n".join(lines)
