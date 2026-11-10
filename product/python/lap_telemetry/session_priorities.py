"""Ranked, deduplicated improvement priorities — and how to fix each one.

Slice 03 produced two rankings and slice 04 produced the channel facts. This is
the only module that decides what the driver should *change*, and it does so
without a model: every suggestion is computed from a measured delta, and when no
delta explains the loss the priority says exactly that.

Everything is expressed in seconds per lap so the score stays auditable:

    score = recurring_loss_s + SPREAD_WEIGHT * spread_s

Deduplicated per corner: a corner can produce four phase facts and appear in
both rankings, and a driver must never be handed five homework items for one
turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .coach.facts import CornerLoss
from .session_corner_extras import CornerExtras


SPREAD_WEIGHT = 0.35
# Below this a corner is not worth a sentence.
_MIN_RECURRING_S = 0.02
_MIN_SPREAD_S = 0.10
# A clause needs this much of a delta before it is worth stating.
_MIN_DISTANCE_M = 3.0
_MIN_SPEED_KPH = 1.0
_MIN_TRAIL_M = 5.0
# Beyond this, an entry/exit delta is a detection artefact, not advice.
_MAX_PLAUSIBLE_DISTANCE_M = 60.0


def _ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        return f"{value}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


@dataclass
class Priority:
    """One opportunity: where, how much, and what to change."""

    rank: int
    corner_id: str
    corner_name: str
    apex_distance_m: float
    phase: str
    kind: str
    recurring_loss_s: float
    spread_s: float
    share_of_gap: float
    score: float
    laps: int
    laps_affected: int
    suggestion: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "apex_distance_m": self.apex_distance_m,
            "phase": self.phase,
            "kind": self.kind,
            "recurring_loss_s": round(self.recurring_loss_s, 3),
            "spread_s": round(self.spread_s, 3),
            "share_of_gap": round(self.share_of_gap, 3),
            "score": round(self.score, 3),
            "laps": self.laps,
            "laps_affected": self.laps_affected,
            "suggestion": self.suggestion,
            "evidence": self.evidence,
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _mode(values: list[int]) -> int | None:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _plausible(distance_m: float) -> float | None:
    """A timing delta worth coaching; anything longer is a detection artefact."""
    if _MIN_DISTANCE_M <= abs(distance_m) <= _MAX_PLAUSIBLE_DISTANCE_M:
        return distance_m
    return None


def _clause_gear(driver: CornerExtras | None, reference: CornerExtras | None) -> str | None:
    if driver is None or reference is None:
        return None
    mine, theirs = driver.gear_at_apex, reference.gear_at_apex
    if not mine or not theirs or mine == theirs:
        return None
    if mine > theirs:
        return (f"one gear lower at the apex "
                f"({_ordinal(theirs)}, not {_ordinal(mine)})")
    return (f"one gear higher at the apex "
            f"({_ordinal(theirs)}, not {_ordinal(mine)})")


def _speed_deficit(items: list[CornerLoss]) -> float:
    if not items:
        return 0.0
    return _mean([item.reference_value for item in items]) - _mean(
        [item.driver_value for item in items])


def _clause_min_speed(phases: list[CornerLoss]) -> str | None:
    deficit = _speed_deficit([i for i in phases if i.phase == "minimum_speed"])
    if deficit >= _MIN_SPEED_KPH:
        return f"carry {deficit:.0f} km/h more minimum speed"
    return None


def _clause_exit_speed(phases: list[CornerLoss]) -> str | None:
    """The speed the driver exits with, when the exit is what costs the time."""
    deficit = _speed_deficit([i for i in phases if i.phase.startswith("exit")])
    if deficit >= _MIN_SPEED_KPH:
        return f"carry {deficit:.0f} km/h more speed onto the straight"
    return None


def _clause_entry(phases: list[CornerLoss]) -> str | None:
    deltas = [_plausible(item.entry_distance_delta_m)
              for item in phases if item.phase == "entry"]
    delta = _median([d for d in deltas if d is not None])
    if delta is not None and delta > 0:
        return f"brake {delta:.0f} m later"
    return None


def _clause_exit(phases: list[CornerLoss]) -> str | None:
    """A phase that happens earlier for the driver is one that happens too early.

    ``exit_distance_delta_m`` is ``reference - driver``, so positive means the
    driver's exit is at a smaller distance: they released the brake (or got on
    the throttle) before the reference did.
    """
    for kind, wording in (("exit_brake", "hold the brake {d:.0f} m longer"),
                          ("exit_throttle", "back on the throttle {d:.0f} m earlier"),
                          ("exit", "get back on the throttle {d:.0f} m earlier")):
        deltas = [_plausible(item.exit_distance_delta_m)
                  for item in phases if item.phase == kind]
        delta = _median([d for d in deltas if d is not None])
        if delta is not None and delta > 0:
            return wording.format(d=delta)
    return None


def _clause_trail(driver: CornerExtras | None, reference: CornerExtras | None) -> str | None:
    if driver is None or reference is None:
        return None
    mine = driver.trail_brake_depth_m
    theirs = reference.trail_brake_depth_m
    if mine is None or theirs is None:
        return None
    extra = theirs - mine
    if extra >= _MIN_TRAIL_M:
        return f"hold the brake {extra:.0f} m past the apex"
    return None


_CLAUSE_ORDER = {
    "minimum_speed": ("min_speed", "gear", "trail", "entry", "exit_speed"),
    "entry": ("entry", "min_speed", "gear", "trail", "exit_speed"),
    "exit_brake": ("exit", "exit_speed", "trail", "gear", "entry"),
    "exit_throttle": ("exit", "exit_speed", "gear", "trail", "entry"),
    "exit": ("exit", "exit_speed", "trail", "gear", "entry"),
}


def suggest_change(
    phases: list[CornerLoss],
    driver_extra: CornerExtras | None,
    reference_extra: CornerExtras | None,
    *,
    loss_s: float | None = None,
    headline_phase: str | None = None,
) -> str:
    """The deterministic fix for one corner, from measured deltas only.

    Clauses are ordered by their relevance to the phase that is actually costing
    the time: telling a driver to "carry more minimum speed" when their loss is
    on the brake release would be advice about a different corner.
    """
    by_name = {
        "min_speed": _clause_min_speed(phases),
        "exit_speed": _clause_exit_speed(phases),
        "gear": _clause_gear(driver_extra, reference_extra),
        "entry": _clause_entry(phases),
        "exit": _clause_exit(phases),
        "trail": _clause_trail(driver_extra, reference_extra),
    }
    if headline_phase is None:
        profitable = [item for item in phases if item.loss_s > 0]
        headline_phase = (max(profitable, key=lambda item: item.loss_s).phase
                          if profitable else "minimum_speed")
    order = _CLAUSE_ORDER.get(headline_phase, _CLAUSE_ORDER["minimum_speed"])
    chosen = [by_name[name] for name in order if by_name[name]]
    # Both speed clauses measure the same deficit through different phases; say
    # it once.
    if by_name["min_speed"] and by_name["exit_speed"] in chosen:
        chosen.remove(by_name["exit_speed"])
    # Two clauses that open with the same words ("hold the brake 7 m longer" and
    # "hold the brake 9 m past the apex") are one instruction said twice.
    unique: list[str] = []
    for clause in chosen:
        opening = " ".join(clause.split()[:2])
        if any(" ".join(kept.split()[:2]) == opening for kept in unique):
            continue
        unique.append(clause)
    chosen = unique[:2]
    if chosen:
        return " and ".join(chosen)
    loss = loss_s if loss_s is not None else max(
        (p.loss_s for p in phases if p.loss_s > 0), default=0.0)
    return (f"losing {loss:.1f} s here with no single measurable cause — "
            f"watch this corner on the data")


def _kind(recurring: float, spread: float, laps: int, affected: int) -> str:
    """'slow every lap', 'erratic', or both — a claim the numbers must support."""
    consistent = laps > 0 and affected / laps >= 0.6
    is_recurring = recurring >= 0.10 and consistent
    is_erratic = spread >= 0.20
    if is_recurring and is_erratic:
        return "both"
    if is_recurring:
        return "recurring"
    return "inconsistent"


def _aggregate_corners(laps: list) -> dict[str, CornerExtras]:
    """One representative channel set per corner: dominant gear, median trail."""
    collected: dict[str, list[CornerExtras]] = {}
    for lap in laps:
        for extra in getattr(lap, "corners", []):
            collected.setdefault(extra.corner_id, []).append(extra)

    aggregated: dict[str, CornerExtras] = {}
    for corner_id, items in collected.items():
        first = items[0]
        gears = [i.gear_at_apex for i in items if i.gear_at_apex]
        trails = [i.trail_brake_depth_m for i in items if i.trail_brake_depth_m is not None]
        aggregated[corner_id] = CornerExtras(
            corner_id=corner_id,
            corner_name=first.corner_name,
            apex_distance_m=first.apex_distance_m,
            window_source=first.window_source,
            gear_at_apex=_mode(gears),
            gear_at_exit=_mode([i.gear_at_exit for i in items if i.gear_at_exit]),
            trail_brake_depth_m=_median(trails),
            lateral_at_apex_m=_median(
                [i.lateral_at_apex_m for i in items if i.lateral_at_apex_m is not None]),
        )
    return aggregated


def build_priorities(
    laps: list,
    reference_corners: list[CornerExtras],
    *,
    total_gap_s: float | None = None,
) -> list[Priority]:
    """One ranked opportunity per corner, from the clean laps only."""
    clean = [lap for lap in laps if getattr(lap, "clean", True)]
    if total_gap_s is None:
        total_gap_s = _mean([lap.delta_s for lap in clean])

    reference = {extra.corner_id: extra for extra in reference_corners}
    grouped: dict[str, list[CornerLoss]] = {}
    extras = _aggregate_corners(clean)
    for lap in clean:
        for item in lap.phases:
            grouped.setdefault(item.corner_id, []).append(item)

    priorities: list[Priority] = []
    for corner_id, items in grouped.items():
        by_phase: dict[str, list[CornerLoss]] = {}
        for item in items:
            by_phase.setdefault(item.phase, []).append(item)

        means = {name: _mean([i.loss_s for i in phase_items])
                 for name, phase_items in by_phase.items()}
        headline_phase, recurring = max(means.items(), key=lambda kv: kv[1])
        headline = by_phase[headline_phase]

        # Spread is measured on the minimum-speed window: the only window that
        # is disjoint per corner, so it cannot double count a neighbour.
        spread_phase = by_phase.get("minimum_speed", headline)
        losses = [i.loss_s for i in spread_phase]
        spread = (max(losses) - min(losses)) if len(losses) >= 2 else 0.0

        if recurring < _MIN_RECURRING_S and spread < _MIN_SPREAD_S:
            continue

        extra = extras.get(corner_id)
        ref_extra = reference.get(corner_id)
        driver_value = _mean([i.driver_value for i in headline])
        reference_value = _mean([i.reference_value for i in headline])
        evidence: dict[str, Any] = {
            "phase": headline_phase,
            "driver_value": round(driver_value, 1),
            "reference_value": round(reference_value, 1),
            "unit": headline[0].unit,
        }
        if extra and extra.gear_at_apex:
            evidence["driver_gear"] = extra.gear_at_apex
        if ref_extra and ref_extra.gear_at_apex:
            evidence["reference_gear"] = ref_extra.gear_at_apex

        priorities.append(Priority(
            rank=0,
            corner_id=corner_id,
            corner_name=items[0].corner_name,
            apex_distance_m=items[0].apex_distance_m,
            phase=headline_phase,
            kind=_kind(recurring, spread,
                       len(headline),
                       sum(1 for i in headline if i.loss_s > 0.05)),
            recurring_loss_s=max(0.0, recurring),
            spread_s=spread,
            share_of_gap=0.0,
            score=max(0.0, recurring) + SPREAD_WEIGHT * spread,
            laps=len(spread_phase),
            laps_affected=sum(1 for i in spread_phase if i.loss_s > 0.05),
            suggestion=suggest_change(items, extra, ref_extra, loss_s=max(0.0, recurring),
                                      headline_phase=headline_phase),
            evidence=evidence,
        ))

    priorities.sort(key=lambda p: p.score, reverse=True)
    for index, priority in enumerate(priorities, start=1):
        priority.rank = index
        if total_gap_s and total_gap_s > 0:
            priority.share_of_gap = min(1.0, priority.recurring_loss_s / total_gap_s)
    return priorities
