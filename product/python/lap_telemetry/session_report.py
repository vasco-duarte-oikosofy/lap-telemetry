"""The deterministic Markdown debrief.

Formats the facts payload into something a driver reads in the paddock. It never
computes a new number: if a sentence needs a value, the value is in the facts.

Deterministic by construction — no timestamps, no locale-dependent formatting,
no iteration over unordered maps — so two runs produce the same file and the
tests can assert on whole sections.
"""
from __future__ import annotations

from .session_corner_extras import aggregate_corners
from .session_facts import SessionDebriefFacts

_KIND_TEXT = {
    "recurring": "every lap",
    "inconsistent": "erratic",
    "both": "every lap, and erratic",
}

# How the same three kinds read inside a sentence.
_KIND_PHRASE = {
    "recurring": "on every lap",
    "inconsistent": "but only on some laps",
    "both": "on every lap, with a wide spread",
}

_CHANNEL_TEXT = {
    "abs_active": "ABS activity",
    "tc_active": "traction control activity",
    "slip_angle_rl_deg": "rear slip angle (left)",
    "slip_angle_rr_deg": "rear slip angle (right)",
}

_PHASE_TEXT = {
    "minimum_speed": "minimum speed",
    "entry": "braking point",
    "exit_brake": "brake release",
    "exit_throttle": "throttle",
    "exit": "exit",
}


def report_filename(stem: str) -> str:
    return f"{stem}_debrief.md"


def format_lap_time(seconds: float) -> str:
    """``m:ss.mmm`` — the format a driver reads off a timing screen."""
    if seconds is None:
        return "—"
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:06.3f}"


def corner_label(name: str) -> str:
    """Some models name a corner "2"; read it as "corner 2"."""
    return f"corner {name}" if name.isdigit() else name


def _signed(value: float, digits: int = 3) -> str:
    return f"{value:+.{digits}f}"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _headline(facts: SessionDebriefFacts) -> list[str]:
    pace = facts.consistency.pace
    lines: list[str] = []
    if pace and pace.best_lap_s:
        gap = pace.best_lap_s - facts.session.reference_lap_s
        if gap >= 0:
            lines.append(
                f"Your best lap was **{format_lap_time(pace.best_lap_s)}**, "
                f"{gap:.3f} s off the reference "
                f"{format_lap_time(facts.session.reference_lap_s)}."
            )
        else:
            lines.append(
                f"Your best lap was **{format_lap_time(pace.best_lap_s)}**, "
                f"{abs(gap):.3f} s *under* the reference "
                f"{format_lap_time(facts.session.reference_lap_s)}."
            )
        lines.append(
            f"Across the {pace.clean_laps} clean laps the median was "
            f"{format_lap_time(pace.median_lap_s)} and the spread "
            f"{pace.spread_s:.3f} s (sd {pace.std_dev_s:.3f} s); the speed "
            f"envelope says **{pace.time_available_s:.3f} s** is sitting in "
            f"repeatability alone."
        )
    if facts.priorities:
        top = facts.priorities[0]
        lines.append(
            f"The one to fix is **{corner_label(top.corner_name)}** — "
            f"{top.recurring_loss_s:.3f} s a lap, "
            f"{_KIND_PHRASE.get(top.kind, top.kind)}, "
            f"{_pct(top.share_of_gap)} of your average "
            f"{facts.consistency.pace.mean_gap_s:.3f} s "
            f"gap: *{top.suggestion}*."
            if facts.consistency.pace
            else f"The one to fix is **{corner_label(top.corner_name)}**: *{top.suggestion}*."
        )
    return lines


def _lap_table(facts: SessionDebriefFacts) -> list[str]:
    best = facts.consistency.pace.best_lap_s if facts.consistency.pace else 0.0
    lines = [
        "| seg | lap | time | vs reference | vs best | clean |",
        "|---:|---:|---:|---:|---:|:---|",
    ]
    for lap in facts.laps:
        vs_best = f"{_signed(lap.lap_time_s - best)}" if best else "—"
        lines.append(
            f"| {lap.segment_index} | {lap.lap_number} | "
            f"{format_lap_time(lap.lap_time_s)} | {_signed(lap.delta_s)} | "
            f"{vs_best} | {'yes' if lap.clean else 'traffic'} |"
        )
    return lines


def _consistency(facts: SessionDebriefFacts) -> list[str]:
    pace = facts.consistency.pace
    if not pace:
        return ["No clean lap was available for consistency."]
    return [
        "| metric | value |",
        "|---|---:|",
        f"| clean laps | {pace.clean_laps} |",
        f"| best | {format_lap_time(pace.best_lap_s)} |",
        f"| median | {format_lap_time(pace.median_lap_s)} |",
        f"| worst clean | {format_lap_time(pace.worst_clean_lap_s)} |",
        f"| mean vs reference | {_signed(pace.mean_gap_s)} s |",
        f"| spread | {pace.spread_s:.3f} s |",
        f"| standard deviation | {pace.std_dev_s:.3f} s |",
        f"| speed envelope | {format_lap_time(pace.envelope_lap_s)} |",
        f"| time available | {pace.time_available_s:.3f} s |",
        "",
        "The envelope is the fastest speed you reached in every metre of the "
        "lap, put end to end in one lap. It is **optimistic** by construction: "
        "it assumes the car changes speed instantly, so it is not a target for "
        "one lap — it is the size of the prize for repeating what you already "
        "did.",
    ]


def _priorities(facts: SessionDebriefFacts) -> list[str]:
    if not facts.priorities:
        return ["No corner stood out as a repeatable loss on the clean laps."]
    lines: list[str] = []
    for priority in facts.priorities[:3]:
        lines.append(
            f"{priority.rank}. **{corner_label(priority.corner_name)}** — "
            f"{priority.recurring_loss_s:.3f} s per lap "
            f"({_KIND_TEXT.get(priority.kind, priority.kind)}, "
            f"{_pct(priority.share_of_gap)} of the gap)  \n"
            f"   {priority.suggestion}"
        )
        evidence = priority.evidence
        # Only show the evidence when it supports the loss: "108.9 against
        # 136.3 km/h" explains 0.7 s, "71.0 against 65.0" beside a loss invites
        # "but I was faster".
        supported = (evidence.get("driver_value") is not None
                     and evidence.get("reference_value") is not None
                     and evidence["driver_value"] < evidence["reference_value"])
        if supported:
            lines.append(
                f"  \n   {_PHASE_TEXT.get(priority.phase, priority.phase)}: "
                f"{evidence['driver_value']:.1f} {evidence.get('unit', '')} "
                f"against {evidence['reference_value']:.1f} "
                f"{evidence.get('unit', '')}"
                + (f" · gear {evidence['driver_gear']} vs "
                   f"{evidence['reference_gear']}"
                   if evidence.get("driver_gear")
                   and evidence["driver_gear"] != evidence.get("reference_gear") else "")
            )
    rest = len(facts.priorities) - 3
    if rest > 0:
        lines.append(f"\nThe other {rest} corners are in the appendix below.")
    return lines


def _corner_table(facts: SessionDebriefFacts) -> list[str]:
    verdicts = {p.corner_id: p.rank for p in facts.priorities}
    reference = {c.corner_id: c for c in facts.reference_corners}
    clean = [lap for lap in facts.laps if lap.clean]
    mine = aggregate_corners(clean)

    speeds: dict[str, tuple[float, float]] = {}
    for lap in clean:
        for item in lap.phases:
            if item.phase != "minimum_speed":
                continue
            driver, ref = speeds.get(item.corner_id, (0.0, 0.0))
            count = sum(1 for lap2 in clean for p2 in lap2.phases
                        if p2.corner_id == item.corner_id and p2.phase == "minimum_speed")
            speeds[item.corner_id] = (driver + item.driver_value / count,
                                      ref + item.reference_value / count)

    lines = [
        "| corner | apex m | min speed | ref | gear | ref gear "
        "| line offset m | verdict |",
        "|---|---:|---:|---:|---:|---:|---:|:---|",
    ]
    for corner_id, extra in mine.items():
        ref_extra = reference.get(corner_id)
        speed = speeds.get(corner_id)
        offset = None
        if extra.lateral_at_apex_m is not None and ref_extra \
                and ref_extra.lateral_at_apex_m is not None:
            offset = extra.lateral_at_apex_m - ref_extra.lateral_at_apex_m
        rank = verdicts.get(corner_id)
        lines.append(
            f"| {corner_label(extra.corner_name)} | {extra.apex_distance_m:.0f} | "
            f"{f'{speed[0]:.1f}' if speed else '—'} | "
            f"{f'{speed[1]:.1f}' if speed else '—'} | "
            f"{extra.gear_at_apex or '—'} | "
            f"{(ref_extra.gear_at_apex if ref_extra else None) or '—'} | "
            f"{_signed(offset, 2) if offset is not None else '—'} | "
            f"{f'#{rank} fix' if rank else '—'} |"
        )
    return lines


def _excluded(facts: SessionDebriefFacts) -> list[str]:
    if not facts.excluded:
        return ["Every segment of the session was analysed."]
    lines = [
        "| seg | lap | duration | status | reason |",
        "|---:|---:|---:|---|---|",
    ]
    for item in facts.excluded:
        lines.append(
            f"| {item.segment_index} | {item.lap_number} | "
            f"{item.duration_s:.1f} s | {item.status} | {item.reason} |"
        )
    return lines


def _not_measurable(facts: SessionDebriefFacts) -> list[str]:
    if not facts.session.unmeasurable_channels:
        return ["Every channel this debrief needs was measurable."]
    lines: list[str] = []
    for channel, reason in sorted(facts.session.unmeasurable_channels.items()):
        label = _CHANNEL_TEXT.get(channel, channel)
        lines.append(f"- **{label}** (`{channel}`) — {reason}")
    return lines


def _how_to_read(facts: SessionDebriefFacts) -> list[str]:
    return [
        f"- **Reference lap** ({format_lap_time(facts.session.reference_lap_s)}) "
        "is the curated fastest lap for this track and car. Every "
        "`vs reference` number is measured against it.",
        "- **Session best** is your own fastest clean lap in this session. "
        "`vs best` says how repeatable you were; it says nothing about the "
        "target.",
        "- **Clean laps** exclude traffic and mistakes. Only clean laps feed "
        "the consistency numbers and the priorities.",
        "- **Excluded laps** were never analysed: an out-lap, an in-lap, a pit "
        "stop, an incomplete segment or a broken recording.",
        "- Every number here also exists in the machine-readable "
        f"`{facts.session.stem}_debrief.json` next to this file.",
    ]


def render_session_report(facts: SessionDebriefFacts) -> str:
    """Render the whole report. Pure formatting, no analysis."""
    session = facts.session
    car = session.car_slug or session.vehicle_name
    title = f"# Session debrief — {session.track} / {car}"
    subtitle = (f"{session.eligible_laps} eligible laps, {session.clean_laps} clean · "
                f"reference lap {format_lap_time(session.reference_lap_s)} · "
                f"session best "
                f"{format_lap_time(facts.consistency.pace.best_lap_s) if facts.consistency.pace else '—'}")

    parts: list[str] = [title, "", subtitle, ""]
    headline = _headline(facts)
    if headline:
        parts += ["## Headline", ""] + ["\n".join(headline), ""]
    parts += ["## Lap by lap", ""] + _lap_table(facts) + [""]
    parts += ["## Consistency", ""] + _consistency(facts) + [""]
    parts += ["## What to change", ""] + _priorities(facts) + [""]
    parts += ["## Corners", ""] + _corner_table(facts) + [""]
    parts += ["## Excluded laps", ""] + _excluded(facts) + [""]
    parts += ["## Not measurable", ""] + _not_measurable(facts) + [""]
    parts += ["## How to read this", ""] + _how_to_read(facts) + [""]
    return "\n".join(parts).rstrip() + "\n"
