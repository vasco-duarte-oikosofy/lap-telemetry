"""Consistency metrics for a session: spread, envelope, and the two rankings.

Two questions, kept apart:

- *Is the driver slow here every lap?* → ``recurring_losses`` (a mean).
- *Is the driver erratic here?* → ``inconsistent_corners`` (a spread, in seconds).

A corner can be both, but they need different coaching, so they are never
merged into one score.

Everything is derived from ``LapFacts.phases`` that the comparison core already
produced, plus one pass over two raw columns for the speed envelope. No extra
Node calls, no second analysis.
"""
from __future__ import annotations

import bisect
import statistics
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa

from .coach.facts import CornerLoss
from .session_laps import LapRecord


# A lap counts as "affected" by a recurring loss when it costs at least this.
_AFFECTED_LOSS_S = 0.05
# The envelope interpolates speed on a 1 m grid.
_ENVELOPE_BIN_M = 1.0


@dataclass
class LapPace:
    """How repeatable the driver is, lap to lap."""

    clean_laps: int
    best_lap_s: float
    median_lap_s: float
    worst_clean_lap_s: float
    spread_s: float
    std_dev_s: float
    envelope_lap_s: float
    time_available_s: float
    basis: str = "speed_envelope"

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean_laps": self.clean_laps,
            "best_lap_s": round(self.best_lap_s, 3),
            "median_lap_s": round(self.median_lap_s, 3),
            "worst_clean_lap_s": round(self.worst_clean_lap_s, 3),
            "spread_s": round(self.spread_s, 3),
            "std_dev_s": round(self.std_dev_s, 3),
            "envelope_lap_s": round(self.envelope_lap_s, 3),
            "time_available_s": round(self.time_available_s, 3),
            "basis": self.basis,
        }


@dataclass
class PhaseSpread:
    """Spread of the driver's own value for one corner phase, in its unit."""

    corner_id: str
    corner_name: str
    apex_distance_m: float
    phase: str
    unit: str
    samples: int
    mean: float
    best: float
    worst: float
    spread: float
    std_dev: float
    point_spread_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "apex_distance_m": self.apex_distance_m,
            "phase": self.phase,
            "unit": self.unit,
            "samples": self.samples,
            "mean": round(self.mean, 2),
            "best": round(self.best, 2),
            "worst": round(self.worst, 2),
            "spread": round(self.spread, 2),
            "std_dev": round(self.std_dev, 2),
        }
        if self.point_spread_m is not None:
            data["point_spread_m"] = round(self.point_spread_m, 1)
        return data


@dataclass
class RecurringLoss:
    """A corner phase that costs time on most laps: 'slow every lap'."""

    corner_id: str
    corner_name: str
    apex_distance_m: float
    phase: str
    mean_loss_s: float
    laps: int
    laps_affected: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "apex_distance_m": self.apex_distance_m,
            "phase": self.phase,
            "mean_loss_s": round(self.mean_loss_s, 3),
            "laps": self.laps,
            "laps_affected": self.laps_affected,
        }


@dataclass
class CornerTime:
    """The spread, in seconds, of a corner's delta-t loss across laps."""

    corner_id: str
    corner_name: str
    apex_s_m: float
    samples: int
    mean_loss_s: float
    best_loss_s: float
    worst_loss_s: float
    spread_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "apex_s_m": self.apex_s_m,
            "samples": self.samples,
            "mean_loss_s": round(self.mean_loss_s, 3),
            "best_loss_s": round(self.best_loss_s, 3),
            "worst_loss_s": round(self.worst_loss_s, 3),
            "spread_s": round(self.spread_s, 3),
        }


@dataclass
class Consistency:
    """The consistency section of the debrief payload."""

    pace: LapPace | None = None
    recurring_losses: list[RecurringLoss] = field(default_factory=list)
    inconsistent_corners: list[CornerTime] = field(default_factory=list)
    phase_spread: list[PhaseSpread] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pace": self.pace.to_dict() if self.pace else None,
            "recurring_losses": [r.to_dict() for r in self.recurring_losses],
            "inconsistent_corners": [c.to_dict() for c in self.inconsistent_corners],
            "phase_spread": [s.to_dict() for s in self.phase_spread],
        }


def speed_envelope_optimal(
    table: pa.Table,
    records: list[LapRecord],
    lap_length_m: float,
    *,
    bin_m: float = _ENVELOPE_BIN_M,
) -> tuple[float, int, int]:
    """Theoretical best lap from the driver's own laps.

    Takes the fastest speed observed in every distance bin and integrates
    ``sum(ds / v)``. Sector-free: it needs only ``speed_kph`` and
    ``lap_distance_m``, and uses every clean lap instead of the handful with
    usable sector channels.

    Optimistic by construction (instantaneous speed changes, no acceleration
    limit), which the report must say.

    Returns ``(lap_seconds, uncovered_bins, laps_used)``.
    """
    if lap_length_m <= 0 or not records:
        return (0.0, 0, 0)

    distances = table.column("lap_distance_m").to_pylist()
    speeds = table.column("speed_kph").to_pylist()
    bins = int(lap_length_m / bin_m)
    fastest = [0.0] * (bins + 1)

    used = 0
    for record in records:
        points = sorted(
            (float(d), float(v))
            for d, v in zip(distances[record.start_row:record.end_row],
                            speeds[record.start_row:record.end_row])
            if d is not None and v is not None and 0.0 <= d <= lap_length_m
        )
        if len(points) < 100:
            continue
        used += 1
        xs = [p[0] for p in points]
        vs = [p[1] for p in points]
        for k in range(bins + 1):
            edge = k * bin_m
            j = bisect.bisect_left(xs, edge)
            if j == 0:
                # The first sample sits exactly on the first edge; there is no
                # left neighbour to interpolate from.
                if xs[0] > edge:
                    continue
                value = vs[0]
            elif j >= len(xs):
                if xs[-1] < edge:
                    continue
                value = vs[-1]
            else:
                x0, x1, v0, v1 = xs[j - 1], xs[j], vs[j - 1], vs[j]
                value = v0 if x1 == x0 else v0 + (v1 - v0) * (edge - x0) / (x1 - x0)
            if value > fastest[k]:
                fastest[k] = value

    total = 0.0
    uncovered = 0
    for k in range(bins):
        # A bin can only be crossed as fast as its slower edge.
        speed_kph = min(fastest[k], fastest[k + 1])
        if speed_kph <= 1.0:
            uncovered += 1
            continue
        total += bin_m / (speed_kph / 3.6)
    return (total, uncovered, used)


def lap_pace(laps: list, envelope_lap_s: float) -> LapPace:
    """Lap-to-lap pace summary over the clean laps."""
    clean = sorted(lap.lap_time_s for lap in laps if getattr(lap, "clean", True))
    if not clean:
        return LapPace(0, 0.0, 0.0, 0.0, 0.0, 0.0, envelope_lap_s, 0.0)
    best = clean[0]
    return LapPace(
        clean_laps=len(clean),
        best_lap_s=best,
        median_lap_s=statistics.median(clean),
        worst_clean_lap_s=clean[-1],
        spread_s=clean[-1] - best,
        std_dev_s=statistics.pstdev(clean),
        envelope_lap_s=envelope_lap_s,
        time_available_s=max(0.0, best - envelope_lap_s),
    )


def _group_phases(laps: list) -> dict[tuple[str, str], list[CornerLoss]]:
    grouped: dict[tuple[str, str], list[CornerLoss]] = {}
    for lap in laps:
        for item in lap.phases:
            grouped.setdefault((item.corner_id, item.phase), []).append(item)
    return grouped


def phase_spreads(laps: list) -> list[PhaseSpread]:
    """Spread of each corner phase's own value, ranked by that spread."""
    spreads: list[PhaseSpread] = []
    for (_corner_id, _phase), items in _group_phases(laps).items():
        if len(items) < 2:
            continue
        values = [item.driver_value for item in items]
        points = [item.phase_distance_m for item in items if item.phase_distance_m is not None]
        spreads.append(PhaseSpread(
            corner_id=items[0].corner_id,
            corner_name=items[0].corner_name,
            apex_distance_m=items[0].apex_distance_m,
            phase=items[0].phase,
            unit=items[0].unit,
            samples=len(items),
            mean=statistics.fmean(values),
            best=max(values),
            worst=min(values),
            spread=max(values) - min(values),
            std_dev=statistics.pstdev(values),
            point_spread_m=(max(points) - min(points)) if len(points) >= 2 else None,
        ))
    spreads.sort(key=lambda s: s.spread, reverse=True)
    return spreads


def recurring_losses(laps: list) -> list[RecurringLoss]:
    """Mean loss per corner phase: where time goes on nearly every lap."""
    losses: list[RecurringLoss] = []
    for items in _group_phases(laps).values():
        mean_loss = statistics.fmean(item.loss_s for item in items)
        if mean_loss <= 0:
            continue
        losses.append(RecurringLoss(
            corner_id=items[0].corner_id,
            corner_name=items[0].corner_name,
            apex_distance_m=items[0].apex_distance_m,
            phase=items[0].phase,
            mean_loss_s=mean_loss,
            laps=len(items),
            laps_affected=sum(1 for item in items if item.loss_s > _AFFECTED_LOSS_S),
        ))
    losses.sort(key=lambda r: r.mean_loss_s, reverse=True)
    return losses


def inconsistent_corners(laps: list) -> list[CornerTime]:
    """Spread, in seconds, of each corner's minimum-speed loss across laps.

    The minimum-speed phase is used because its delta-t window (apex to the end
    of the following straight) is disjoint from every other corner's, so corners
    can be compared and ranked without double counting.
    """
    corners: list[CornerTime] = []
    for items in _group_phases(laps).values():
        if items[0].phase != "minimum_speed" or len(items) < 2:
            continue
        values = [item.loss_s for item in items]
        corners.append(CornerTime(
            corner_id=items[0].corner_id,
            corner_name=items[0].corner_name,
            apex_s_m=items[0].apex_distance_m,
            samples=len(items),
            mean_loss_s=statistics.fmean(values),
            best_loss_s=min(values),
            worst_loss_s=max(values),
            spread_s=max(values) - min(values),
        ))
    corners.sort(key=lambda c: c.spread_s, reverse=True)
    return corners


def build_consistency(laps: list, envelope_lap_s: float) -> Consistency:
    """Assemble the consistency section from the analysed laps.

    Only clean laps feed the spreads and the rankings. A traffic lap is real
    data for the reference comparison, but inside a consistency statistic it is
    noise that would send the driver chasing a corner that is fine.
    """
    clean = [lap for lap in laps if getattr(lap, "clean", True)]
    return Consistency(
        pace=lap_pace(clean, envelope_lap_s),
        recurring_losses=recurring_losses(clean),
        inconsistent_corners=inconsistent_corners(clean),
        phase_spread=phase_spreads(clean),
    )
