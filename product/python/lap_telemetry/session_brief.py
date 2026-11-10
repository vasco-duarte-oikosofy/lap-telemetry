"""The grounding the coach is allowed to speak from.

The model never sees the facts payload: 18 laps times 9 corners is 338 KB, and
most of it is noise for a conversation. It sees this block instead — a few
kilobytes of the numbers that matter — plus, when the driver names a corner,
that corner's per-lap detail.

Everything here is formatting. If a sentence needs a number, the number is in
the facts.
"""
from __future__ import annotations

from .session_corner_extras import aggregate_corners, median_of
from .session_facts import SessionDebriefFacts
from .session_report import corner_label, format_lap_time

GROUNDING_BUDGET_BYTES = 4096
CORNER_BUDGET_BYTES = 1500
# Above this many laps the table is truncated; the deltas carry the story.
_MAX_LAP_ROWS = 26


def _signed(value: float, digits: int = 3) -> str:
    return f"{value:+.{digits}f}"


def _clip(text: str, budget: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= budget:
        return text
    clipped = encoded[:budget].decode("utf-8", errors="ignore")
    return clipped.rsplit("\n", 1)[0] + "\n… (truncated)\n"


def build_grounding(facts: SessionDebriefFacts) -> str:
    """The compact, complete-enough block the model reasons from."""
    session = facts.session
    pace = facts.consistency.pace
    lines: list[str] = []

    lines += [
        "SESSION",
        f"track: {session.track} | car: {session.car_slug or session.vehicle_name}",
        f"eligible laps: {session.eligible_laps} | clean laps: {session.clean_laps}",
        f"reference lap (curated): {format_lap_time(session.reference_lap_s)}",
    ]
    if pace:
        lines += [
            f"your best clean lap: {format_lap_time(pace.best_lap_s)} "
            f"({_signed(pace.best_lap_s - session.reference_lap_s)} vs reference)",
            f"mean gap to reference: {pace.mean_gap_s:.3f} s over "
            f"{pace.clean_laps} clean laps",
            f"median: {format_lap_time(pace.median_lap_s)} | spread: "
            f"{pace.spread_s:.3f} s | sd: {pace.std_dev_s:.3f} s",
            f"speed envelope: {format_lap_time(pace.envelope_lap_s)} | "
            f"repeatability prize: {pace.time_available_s:.3f} s "
            f"(optimistic, not one-lap achievable)",
        ]

    lines += ["", "LAPS (seg | lap | time | vs reference | clean)"]
    for lap in facts.laps[:_MAX_LAP_ROWS]:
        lines.append(f"{lap.segment_index} | {lap.lap_number} | "
                     f"{format_lap_time(lap.lap_time_s)} | {_signed(lap.delta_s)} | "
                     f"{'yes' if lap.clean else 'no'}")
    if len(facts.laps) > _MAX_LAP_ROWS:
        lines.append(f"… {len(facts.laps) - _MAX_LAP_ROWS} more laps")

    lines += ["", "TOP PRIORITIES (rank | corner | phase | seconds per lap | "
                  "share of gap | kind)"]
    for priority in facts.priorities[:3]:
        lines.append(f"{priority.rank} | {corner_label(priority.corner_name)} | "
                     f"{priority.phase} | {priority.recurring_loss_s:.3f} s | "
                     f"{priority.share_of_gap * 100:.0f}% | {priority.kind}")
        lines.append(f"  fix: {priority.suggestion}")
        evidence = priority.evidence
        if evidence.get("driver_value") is not None:
            gear = ""
            if evidence.get("driver_gear") and evidence.get("reference_gear"):
                gear = (f" | gear {evidence['driver_gear']} vs "
                        f"{evidence['reference_gear']}")
            lines.append(f"  evidence: {priority.phase} "
                         f"{evidence['driver_value']:.1f} {evidence.get('unit', '')} "
                         f"vs {evidence['reference_value']:.1f} "
                         f"{evidence.get('unit', '')}{gear}")

    if facts.consistency.inconsistent_corners:
        lines += ["", "MOST INCONSISTENT CORNERS (spread in seconds)"]
        for corner in facts.consistency.inconsistent_corners[:5]:
            lines.append(f"{corner_label(corner.corner_name)} "
                         f"{corner.spread_s:.3f} s over {corner.samples} laps")

    if facts.excluded:
        lines += ["", "EXCLUDED SEGMENTS (never analysed)"]
        for item in facts.excluded[:8]:
            lines.append(f"seg {item.segment_index} (lap {item.lap_number}): "
                         f"{item.status} — {item.reason}")

    if session.unmeasurable_channels:
        lines += ["", "NOT MEASURABLE IN THIS RECORDING"]
        for channel, reason in sorted(session.unmeasurable_channels.items()):
            lines.append(f"{channel}: {reason}")

    lines += ["", "RULES FOR THE REPLY",
              "- One real positive with a number, then the single biggest loss.",
              "- At most three coaching points. One fix at a time.",
              "- At most 120 words. Exactly one question back.",
              "- Every number you state must appear above."]
    return _clip("\n".join(lines) + "\n", GROUNDING_BUDGET_BYTES)


def find_corner(facts: SessionDebriefFacts, text: str) -> str | None:
    """Which corner, if any, the driver just named."""
    lowered = text.lower()
    for corner in facts.reference_corners:
        name = corner.corner_name.lower()
        if name.isdigit():
            if f"corner {name}" in lowered or f"turn {name}" in lowered:
                return corner.corner_id
        elif name in lowered:
            return corner.corner_id
        if corner.corner_id.lower() in lowered:
            return corner.corner_id
    return None


def corner_block(facts: SessionDebriefFacts, corner_id: str) -> str:
    """The per-lap detail for one corner, when the driver asks about it."""
    reference = {c.corner_id: c for c in facts.reference_corners}.get(corner_id)
    priority = next((p for p in facts.priorities if p.corner_id == corner_id), None)
    if reference is None:
        return ""

    name = corner_label(reference.corner_name)
    lines = [f"CORNER: {name} (apex {reference.apex_distance_m:.0f} m)"]
    if priority:
        lines += [
            f"priority #{priority.rank}: {priority.recurring_loss_s:.3f} s per lap, "
            f"{priority.share_of_gap * 100:.0f}% of the gap, {priority.kind}",
            f"fix: {priority.suggestion}",
        ]
    lines.append(
        f"reference: gear {reference.gear_at_apex or 'n/a'}, "
        f"brake peak {f'{reference.brake_peak:.2f}' if reference.brake_peak is not None else 'n/a'}, "
        f"trail {f'{reference.trail_brake_depth_m:.0f}' if reference.trail_brake_depth_m is not None else 'n/a'} m, "
        f"line {f'{reference.lateral_at_apex_m:.1f}' if reference.lateral_at_apex_m is not None else 'n/a'} m"
    )

    mine = aggregate_corners([lap for lap in facts.laps if lap.clean]).get(corner_id)
    if mine:
        lines.append(f"you: gear {mine.gear_at_apex or 'n/a'}, "
                     f"trail "
                     f"{f'{mine.trail_brake_depth_m:.0f}' if mine.trail_brake_depth_m is not None else 'n/a'} m, "
                     f"line "
                     f"{f'{mine.lateral_at_apex_m:.1f}' if mine.lateral_at_apex_m is not None else 'n/a'} m")

    speeds: list[float] = []
    losses: list[float] = []
    rows = ["", "Per-lap detail (clean laps):",
            "| seg | min speed km/h | ref km/h | gear | brake | trail m | loss s |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for lap in facts.laps:
        if not lap.clean:
            continue
        minimum = next((p for p in lap.phases
                        if p.corner_id == corner_id and p.phase == "minimum_speed"), None)
        if minimum is None:
            continue
        extra = next((c for c in lap.corners if c.corner_id == corner_id), None)
        speeds.append(minimum.driver_value)
        losses.append(minimum.loss_s)
        rows.append(
            f"| {lap.segment_index} | {minimum.driver_value:.1f} | "
            f"{minimum.reference_value:.1f} | "
            f"{extra.gear_at_apex if extra and extra.gear_at_apex else 'n/a'} | "
            f"{f'{extra.brake_peak:.2f}' if extra and extra.brake_peak is not None else 'n/a'} | "
            f"{f'{extra.trail_brake_depth_m:.0f}' if extra and extra.trail_brake_depth_m is not None else 'n/a'} | "
            f"{minimum.loss_s:+.3f} |"
        )

    if speeds:
        spread = max(speeds) - min(speeds)
        loss_spread = max(losses) - min(losses) if len(losses) > 1 else 0.0
        lines += ["", f"minimum speed spread: {spread:.1f} km/h "
                      f"| minimum-speed loss spread: {loss_spread:.3f} s "
                      f"| median speed: {median_of(speeds) or 0.0:.1f} km/h"]
    lines += rows
    return _clip("\n".join(lines) + "\n", CORNER_BUDGET_BYTES)
