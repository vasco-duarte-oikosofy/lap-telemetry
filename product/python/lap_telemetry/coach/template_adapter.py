"""Deterministic template adapter — generates coaching phrases without an LLM.

Uses pre-defined phrase templates with fact interpolation to produce
coaching utterances with zero LLM latency. Follows the same rules as
the LLM prompt (gain-first ordering, same-corner dedup, TTS output rules).

See template-phrase-spec.md for the full specification.
"""
from __future__ import annotations

from .facts import CornerLoss, LapComparisonFacts
from .fuel_facts import FuelFacts

# ── Number spelling (TTS rule: spell out 1–10) ────────────────────────────

_SPELL_OUT = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def _spell_number(n: int) -> str:
    """Spell out 1–10, keep digits for 11+."""
    n = abs(int(round(n)))
    return _SPELL_OUT.get(n, str(n))


# ── Time formatting ───────────────────────────────────────────────────────


def format_time(loss_s: float) -> str:
    """Format a loss_s value into natural spoken English for TTS.

    Returns phrases like 'a tenth', 'two tenths', 'half a second',
    'one point two seconds'.
    """
    t = abs(loss_s)
    t = round(t, 2)

    if t < 0.10:
        hundredths = round(t * 100)
        if hundredths <= 1:
            return "a hundredth"
        return f"{_spell_number(hundredths)} hundredths"
    if t == 0.10:
        return "a tenth"
    if t < 0.20:
        return "just over a tenth"
    if t < 0.50 and t % 0.10 == 0:
        tenths = int(round(t * 10))
        return f"{_spell_number(tenths)} tenths"
    if t < 0.50:
        tenths = int(round(t * 10))
        return f"{_spell_number(tenths)} tenths"
    if t == 0.50:
        return "half a second"
    if t < 0.75:
        tenths = int(round(t * 10))
        return f"{_spell_number(tenths)} tenths"
    if t == 0.75:
        return "three quarters of a second"
    if t < 1.00:
        tenths = int(round(t * 10))
        return f"{_spell_number(tenths)} tenths"
    if t == 1.00:
        return "one second"
    if t < 2.00:
        decimal_tenth = int(round(t * 10) % 10)
        return f"one point {_spell_number(decimal_tenth)} seconds"
    n = int(round(t))
    return f"{_spell_number(n)} seconds"


# ── Helpers ────────────────────────────────────────────────────────────────


def _speed_diff(cl: CornerLoss) -> str:
    """Absolute speed difference as a spoken number + unit."""
    return f"{_spell_number(int(round(abs(cl.driver_value - cl.reference_value))))} kilometres per hour"


def _delta(delta_m: float) -> str:
    """Absolute delta distance as a spoken number + unit."""
    return f"{_spell_number(int(round(abs(delta_m))))} metres"


# ── Single-phrase builders (one phase, no dedup) ──────────────────────────

# These produce complete sentences like:
#   "You lost two tenths at the apex of turn three. You carried eleven
#    kilometres per hour less."
# Each returns the full phrase including the lead sentence and detail clause.

# --- Loss phrases ---


def _loss_minimum_speed(cl: CornerLoss) -> str:
    time = format_time(cl.loss_s)
    spd = _speed_diff(cl)
    if cl.apex_offset_m is not None and cl.apex_offset_m != 0:
        d = _delta(cl.apex_offset_m)
        direction = "earlier" if cl.apex_offset_m > 0 else "later"
        return (f"You lost {time} at the apex of {cl.corner_name}. "
                f"You carried {spd} less, and hit the apex {d} {direction}.")
    return f"You lost {time} at the apex of {cl.corner_name}. You carried {spd} less."


def _loss_entry(cl: CornerLoss) -> str:
    time = format_time(cl.loss_s)
    if cl.entry_distance_delta_m is not None and cl.entry_distance_delta_m != 0:
        d = _delta(cl.entry_distance_delta_m)
        if cl.entry_distance_delta_m > 0:
            return f"You lost {time} braking for {cl.corner_name}. You lifted {d} earlier."
        return f"You lost {time} braking for {cl.corner_name}. You braked {d} later."
    return f"You lost {time} going into {cl.corner_name}."


def _loss_exit_brake(cl: CornerLoss) -> str:
    time = format_time(cl.loss_s)
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m < 0:
            return f"You lost {time} exiting {cl.corner_name}. You released the brakes {d} later."
        return f"You lost {time} exiting {cl.corner_name}. You released the brakes {d} earlier."
    return f"You lost {time} exiting {cl.corner_name}."


def _loss_exit_throttle(cl: CornerLoss) -> str:
    time = format_time(cl.loss_s)
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m < 0:
            return f"You lost {time} getting on the power at {cl.corner_name}. You got back on throttle {d} later."
        return f"You lost {time} getting on the power at {cl.corner_name}. You got back on throttle {d} earlier."
    return f"You lost {time} getting on the power at {cl.corner_name}."


def _loss_exit(cl: CornerLoss) -> str:
    time = format_time(cl.loss_s)
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m < 0:
            return f"You lost {time} exiting {cl.corner_name}. You got back on throttle {d} later."
        return f"You lost {time} exiting {cl.corner_name}. You got back on throttle {d} earlier."
    return f"You lost {time} exiting {cl.corner_name}."


# --- Gain phrases ---


def _gain_minimum_speed(cl: CornerLoss) -> str:
    time = format_time(abs(cl.loss_s))
    spd = _speed_diff(cl)
    if cl.apex_offset_m is not None and cl.apex_offset_m != 0:
        d = _delta(cl.apex_offset_m)
        direction = "earlier" if cl.apex_offset_m > 0 else "later"
        return (f"You gained {time} at the apex of {cl.corner_name}. "
                f"You carried {spd} more, hitting the apex {d} {direction}.")
    return f"You gained {time} at the apex of {cl.corner_name}. You carried {spd} more."


def _gain_entry(cl: CornerLoss) -> str:
    time = format_time(abs(cl.loss_s))
    if cl.entry_distance_delta_m is not None and cl.entry_distance_delta_m != 0:
        d = _delta(cl.entry_distance_delta_m)
        if cl.entry_distance_delta_m < 0:
            return f"You gained {time} going into {cl.corner_name}. You braked {d} later."
        return f"You gained {time} going into {cl.corner_name}. You lifted {d} earlier."
    return f"You gained {time} going into {cl.corner_name}. You carried more speed into the corner."


def _gain_exit_brake(cl: CornerLoss) -> str:
    time = format_time(abs(cl.loss_s))
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m > 0:
            return f"You gained {time} exiting {cl.corner_name}. You released the brakes {d} earlier."
        return f"You gained {time} exiting {cl.corner_name}. You released the brakes {d} later."
    return f"You gained {time} exiting {cl.corner_name}."


def _gain_exit_throttle(cl: CornerLoss) -> str:
    time = format_time(abs(cl.loss_s))
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m > 0:
            return f"You gained {time} getting on the power at {cl.corner_name}. You got back on throttle {d} earlier."
        return f"You gained {time} getting on the power at {cl.corner_name}. You got back on throttle {d} later."
    return f"You gained {time} getting on the power at {cl.corner_name}."


def _gain_exit(cl: CornerLoss) -> str:
    time = format_time(abs(cl.loss_s))
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m > 0:
            return f"You gained {time} exiting {cl.corner_name}. You got back on throttle {d} earlier."
        return f"You gained {time} exiting {cl.corner_name}. You got back on throttle {d} later."
    return f"You gained {time} exiting {cl.corner_name}."


_PHASE_LOSS = {
    "minimum_speed": _loss_minimum_speed,
    "entry": _loss_entry,
    "exit_brake": _loss_exit_brake,
    "exit_throttle": _loss_exit_throttle,
    "exit": _loss_exit,
}

_PHASE_GAIN = {
    "minimum_speed": _gain_minimum_speed,
    "entry": _gain_entry,
    "exit_brake": _gain_exit_brake,
    "exit_throttle": _gain_exit_throttle,
    "exit": _gain_exit,
}


# ── Dedup detail clauses ──────────────────────────────────────────────────
#
# For same-corner dedup, we build a lead sentence (time + location) and
# then append detail clauses from ALL phases (including dominant) joined
# with commas and "and" before the last:
#
#   "You lost X exiting turn 3. You released the brakes four metres later,
#    carried eleven kilometres per hour less through the apex, and got back
#    on throttle nine metres later."
#
# Detail clauses are verb phrases WITHOUT "You" prefix or period.
# For minimum_speed, we add "through the apex" or "hitting the apex X m Y"
# when it's a supporting phase (not dominant) to clarify which phase it is.


# --- Loss detail clauses ---


def _loss_detail_minimum_speed(cl: CornerLoss, is_dominant: bool) -> str:
    """Loss detail for minimum_speed phase in dedup context."""
    spd = _speed_diff(cl)
    suffix = "" if is_dominant else " through the apex"
    if cl.apex_offset_m is not None and cl.apex_offset_m != 0:
        d = _delta(cl.apex_offset_m)
        direction = "earlier" if cl.apex_offset_m > 0 else "later"
        hit_clause = f", hitting it {d} {direction}"
        return f"carried {spd} less{suffix}{hit_clause}"
    return f"carried {spd} less{suffix}"


def _loss_detail_entry(cl: CornerLoss) -> str | None:
    """Loss detail for entry phase."""
    if cl.entry_distance_delta_m is not None and cl.entry_distance_delta_m != 0:
        d = _delta(cl.entry_distance_delta_m)
        if cl.entry_distance_delta_m > 0:
            return f"lifted {d} earlier"
        return f"braked {d} later"
    # No delta: entry detail isn't very useful as a supporting clause
    return "carried less speed into the corner"


def _loss_detail_exit_brake(cl: CornerLoss) -> str | None:
    """Loss detail for exit_brake phase."""
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m < 0:
            return f"released the brakes {d} later"
        return f"released the brakes {d} earlier"
    return None


def _loss_detail_exit_throttle(cl: CornerLoss) -> str | None:
    """Loss detail for exit_throttle phase."""
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m < 0:
            return f"got back on throttle {d} later"
        return f"got back on throttle {d} earlier"
    return None


def _loss_detail_exit(cl: CornerLoss) -> str:
    """Loss detail for generic exit phase."""
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m < 0:
            return f"got back on throttle {d} later"
        return f"got back on throttle {d} earlier"
    return None


# --- Gain detail clauses ---


def _gain_detail_minimum_speed(cl: CornerLoss, is_dominant: bool) -> str:
    """Gain detail for minimum_speed phase in dedup context."""
    spd = _speed_diff(cl)
    suffix = "" if is_dominant else " through the apex"
    if cl.apex_offset_m is not None and cl.apex_offset_m != 0:
        d = _delta(cl.apex_offset_m)
        direction = "earlier" if cl.apex_offset_m > 0 else "later"
        hit_clause = f", hitting the apex {d} {direction}"
        return f"carried {spd} more{suffix}{hit_clause}"
    return f"carried {spd} more{suffix}"


def _gain_detail_entry(cl: CornerLoss) -> str | None:
    """Gain detail for entry phase."""
    if cl.entry_distance_delta_m is not None and cl.entry_distance_delta_m != 0:
        d = _delta(cl.entry_distance_delta_m)
        if cl.entry_distance_delta_m < 0:
            return f"braked {d} later"
        return f"lifted {d} earlier"
    return "carried more speed into the corner"


def _gain_detail_exit_brake(cl: CornerLoss) -> str | None:
    """Gain detail for exit_brake phase."""
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m > 0:
            return f"released the brakes {d} earlier"
        return f"released the brakes {d} later"
    return None


def _gain_detail_exit_throttle(cl: CornerLoss) -> str | None:
    """Gain detail for exit_throttle phase."""
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m > 0:
            return f"got back on throttle {d} earlier"
        return f"got back on throttle {d} later"
    return None


def _gain_detail_exit(cl: CornerLoss) -> str:
    """Gain detail for generic exit phase."""
    if cl.exit_distance_delta_m is not None and cl.exit_distance_delta_m != 0:
        d = _delta(cl.exit_distance_delta_m)
        if cl.exit_distance_delta_m > 0:
            return f"got back on throttle {d} earlier"
        return f"got back on throttle {d} later"
    return None


def _loss_detail(cl: CornerLoss, is_dominant: bool = False) -> str | None:
    """Get loss detail clause for a phase in dedup context."""
    phase = cl.phase
    if phase == "minimum_speed":
        return _loss_detail_minimum_speed(cl, is_dominant)
    if phase == "entry":
        return _loss_detail_entry(cl)
    if phase == "exit_brake":
        return _loss_detail_exit_brake(cl)
    if phase == "exit_throttle":
        return _loss_detail_exit_throttle(cl)
    if phase == "exit":
        return _loss_detail_exit(cl)
    return None


def _gain_detail(cl: CornerLoss, is_dominant: bool = False) -> str | None:
    """Get gain detail clause for a phase in dedup context."""
    phase = cl.phase
    if phase == "minimum_speed":
        return _gain_detail_minimum_speed(cl, is_dominant)
    if phase == "entry":
        return _gain_detail_entry(cl)
    if phase == "exit_brake":
        return _gain_detail_exit_brake(cl)
    if phase == "exit_throttle":
        return _gain_detail_exit_throttle(cl)
    if phase == "exit":
        return _gain_detail_exit(cl)
    return None


# ── Lead sentence location phrases ─────────────────────────────────────────


def _lead_location(cl: CornerLoss) -> str:
    """Location phrase for a lead sentence based on phase and deltas."""
    phase = cl.phase
    if phase == "minimum_speed":
        return f"at the apex of {cl.corner_name}"
    if phase == "entry":
        if cl.entry_distance_delta_m is not None and cl.entry_distance_delta_m != 0:
            return f"braking for {cl.corner_name}"
        return f"going into {cl.corner_name}"
    if phase == "exit_brake":
        return f"exiting {cl.corner_name}"
    if phase == "exit_throttle":
        return f"getting on the power at {cl.corner_name}"
    # exit or unknown
    return f"exiting {cl.corner_name}"


# ── Same-corner deduplication ─────────────────────────────────────────────


def _dedup_corner(items: list[CornerLoss], is_gain: bool) -> str:
    """Combine multiple phases for the same corner into one coaching point.

    Format:
        Lead sentence: "You lost/gained {time} {location}."
        Detail sentence: "You {detail1}, {detail2}, and {detail3}."
    """
    if not items:
        return ""

    # Sort by abs(loss_s) descending — dominant first
    sorted_items = sorted(items, key=lambda c: abs(c.loss_s), reverse=True)
    dominant = sorted_items[0]
    verb = "gained" if is_gain else "lost"
    time = format_time(abs(dominant.loss_s))
    location = _lead_location(dominant)
    lead = f"You {verb} {time} {location}."

    # Single phase — use the full phrase builder
    if len(sorted_items) == 1:
        builder = _PHASE_GAIN if is_gain else _PHASE_LOSS
        return builder[dominant.phase](dominant)

    # Multiple phases — build lead + detail sentence
    detail_fn = _gain_detail if is_gain else _loss_detail
    details: list[str] = []

    for i, item in enumerate(sorted_items):
        is_dom = (i == 0)
        d = detail_fn(item, is_dominant=is_dom)
        if d is not None:
            details.append(d)

    if not details:
        return lead

    if len(details) == 1:
        return f"{lead} You {details[0]}."

    # 2+ details: "You {d1}, and {d2}." or "You {d1}, {d2}, and {d3}."
    if len(details) == 2:
        return f"{lead} You {details[0]}, and {details[1]}."
    # 3+
    all_but_last = ", ".join(details[:-1])
    return f"{lead} You {all_but_last}, and {details[-1]}."


# ── Corner ordering ─────────────────────────────────────────────────────────


def _corner_order(
    by_corner: dict[str, list[CornerLoss]], is_gain: bool
) -> list[str]:
    """Return corner_ids ordered by dominance (biggest impact first)."""
    def _dominant_loss(items: list[CornerLoss]) -> float:
        return max(abs(c.loss_s) for c in items)

    corners_with_dominance = [
        (corner_id, _dominant_loss(items))
        for corner_id, items in by_corner.items()
    ]
    corners_with_dominance.sort(key=lambda x: x[1], reverse=True)
    return [cid for cid, _ in corners_with_dominance]


def _all_corners_by_magnitude(
    gain_by_corner: dict[str, list[CornerLoss]],
    loss_by_corner: dict[str, list[CornerLoss]],
    lap_delta_s: float,
) -> list[tuple[str, list[CornerLoss], bool]]:
    """Return (corner_id, items, is_gain) sorted by dominant impact.

    When lap_delta_s <= 0 (driver on pace or faster): gains first, then losses,
    each group sorted by magnitude.
    When lap_delta_s > 0 (driver slower): all corners interleaved by magnitude
    so the most impactful moment — gain or loss — comes first.
    """
    entries: list[tuple[str, list[CornerLoss], bool, float]] = []
    for cid, items in gain_by_corner.items():
        dom = max(abs(c.loss_s) for c in items)
        entries.append((cid, items, True, dom))
    for cid, items in loss_by_corner.items():
        dom = max(abs(c.loss_s) for c in items)
        entries.append((cid, items, False, dom))

    if lap_delta_s > 0:
        # Worst loss leads unconditionally; remaining items sorted by magnitude
        loss_entries = sorted([e for e in entries if not e[2]], key=lambda x: x[3], reverse=True)
        gain_entries = sorted([e for e in entries if e[2]], key=lambda x: x[3], reverse=True)
        if loss_entries:
            rest = sorted(loss_entries[1:] + gain_entries, key=lambda x: x[3], reverse=True)
            entries = [loss_entries[0]] + rest
        else:
            entries.sort(key=lambda x: x[3], reverse=True)
    else:
        # Gain-first: gains before losses, each group sorted by magnitude
        entries.sort(key=lambda x: (not x[2], -x[3]))

    return [(cid, items, is_gain) for cid, items, is_gain, _ in entries]


# ── Word-limit truncation ──────────────────────────────────────────────────


def _truncate_to_word_limit(text: str, max_words: int) -> str:
    """Truncate text to max_words, dropping whole sentences from the end.

    Never splits a sentence mid-way.
    """
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text

    # Split into sentences (by '. ')
    sentences = [s.strip() for s in text.replace(". ", ".\x00").split("\x00") if s.strip()]
    # Handle case where last sentence doesn't end with '. '
    if not text.endswith(".\x00") and sentences:
        # Re-split the last sentence if needed
        last = sentences[-1].rstrip(".")
        if "." in last:
            # There are more periods inside — re-split
            parts = [p.strip() for p in text.split(".") if p.strip()]
            sentences = [p + "." if not p.endswith(".") else p for p in parts]

    kept: list[str] = []
    count = 0
    for sentence in sentences:
        sent_words = sentence.split()
        if count + len(sent_words) <= max_words:
            kept.append(sentence)
            count += len(sent_words)
        else:
            break

    result = " ".join(kept)
    if result and not result.endswith("."):
        result += "."
    return result


# ── Public API ─────────────────────────────────────────────────────────────


class TemplateAdapter:
    """Deterministic coaching utterance generator — no LLM, no network.

    Generates phrases from structured fact data using pre-defined templates
    with gain-first ordering, same-corner dedup, and TTS output rules.
    """

    @staticmethod
    def generate(facts: LapComparisonFacts) -> str:
        """Generate a coaching utterance from lap comparison facts.

        Args:
            facts: Structured lap comparison facts with losses and gains.

        Returns:
            A coaching utterance string, or empty string if no meaningful
            coaching point exists.
        """
        losses = facts.top_losses or []
        gains = facts.top_gains or []

        if not losses and not gains:
            return ""

        # Group by corner_id
        loss_by_corner: dict[str, list[CornerLoss]] = {}
        for cl in losses:
            loss_by_corner.setdefault(cl.corner_id, []).append(cl)

        gain_by_corner: dict[str, list[CornerLoss]] = {}
        for cl in gains:
            gain_by_corner.setdefault(cl.corner_id, []).append(cl)

        # Identify the worst loss phrase before ordering (for hard guarantee below)
        worst_loss_phrase: str | None = None
        if loss_by_corner:
            worst_cid = max(
                loss_by_corner,
                key=lambda k: max(abs(c.loss_s) for c in loss_by_corner[k]),
            )
            worst_loss_phrase = _dedup_corner(loss_by_corner[worst_cid], is_gain=False)

        # Build phrases in magnitude order (interleaved when driver is slower)
        lap_delta = facts.lap_time_delta_s if facts.lap_time_delta_s is not None else 0.0
        ordered = _all_corners_by_magnitude(gain_by_corner, loss_by_corner, lap_delta)
        phrases = [_dedup_corner(items, is_gain) for _, items, is_gain in ordered]

        result = " ".join(p for p in phrases if p)

        # Apply word-limit truncation
        max_words = facts.constraints.get("max_words", 60)
        result = _truncate_to_word_limit(result, max_words)

        # Hard guarantee: worst loss lead sentence must appear when driver is slower.
        # Check only the lead (first sentence), not the full phrase — truncation may
        # have kept the lead but stripped the detail clause, and a full-phrase check
        # would incorrectly re-append, duplicating the lead sentence (bug 18).
        if worst_loss_phrase:
            worst_loss_lead = worst_loss_phrase.split(". ")[0] + "."
            if worst_loss_lead not in result:
                result = (result.rstrip() + " " + worst_loss_phrase).strip()

        return result

    @staticmethod
    def generate_fuel_phrase(facts: FuelFacts) -> str:
        """Generate a fuel engineer utterance from fuel facts.

        Args:
            facts: FuelFacts data structure.

        Returns:
            A fuel status utterance string, or empty string if no data.
        """
        status = facts.fuel_status

        if status == "UNKNOWN":
            return ""

        if status == "CRITICAL":
            return "Fuel critical. Pit this lap."

        # Non-race sessions always say "Fuel OK."
        if facts.session_type != "race":
            return "Fuel OK."

        laps_remaining = facts.laps_of_fuel_remaining
        race_remaining = facts.race_laps_remaining

        if laps_remaining is None:
            return f"Fuel status {status.lower()}. No fuel data available."

        laps_r = int(round(laps_remaining))
        laps_str = _spell_number(laps_r) if laps_r <= 10 else str(laps_r)

        if status == "OK":
            # If margin > 5 laps, just say "Fuel OK."
            if race_remaining is not None and (laps_remaining - race_remaining) > 5:
                return "Fuel OK."
            if race_remaining is not None:
                race_str = _spell_number(race_remaining) if race_remaining <= 10 else str(race_remaining)
                return f"Fuel OK. {laps_str} laps remaining, {race_str} laps to go."
            return f"Fuel OK. {laps_str} laps remaining."

        # WARNING
        if race_remaining is not None:
            race_str = _spell_number(race_remaining) if race_remaining <= 10 else str(race_remaining)
            return f"Warning: {laps_str} laps of fuel remaining, {race_str} laps to go."
        return f"Warning: {laps_str} laps of fuel remaining."