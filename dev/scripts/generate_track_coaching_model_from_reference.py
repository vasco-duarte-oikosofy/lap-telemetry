#!/usr/bin/env python3
"""Generate a reviewable track coaching model from a reference lap.

Primary method (throttle_brake_v1): detects corners via brake application
(>15%) and throttle lift (<90%). Falls back to speed_local_minimum_v1 when
throttle_norm / brake_norm columns are absent.

Brake rule: two brake events are merged into one corner if brake never fully
releases to 0% between them (chicane continuations). Throttle-only lifts are
separate events when brake stays below 15%.

Apex = speed minimum within the corner zone.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.lap_comparator import resample_column


DETECTION_METHOD_V1 = "speed_local_minimum_v1"
DETECTION_METHOD_V2 = "throttle_brake_v1"
CAR_COLUMNS = ("vehicle_id", "car_id", "vehicle_name", "car_name")


@dataclass
class Candidate:
    apex_m: int
    min_speed_kph: float
    prominence_kph: float
    left_peak_kph: float
    right_peak_kph: float
    s_start_m: float = 0.0
    s_end_m: float = 0.0
    entry_speed_kph: float = 0.0
    exit_speed_kph: float = 0.0

    @property
    def speed_drop_kph(self) -> float:
        return self.left_peak_kph - self.min_speed_kph

    @property
    def recovery_kph(self) -> float:
        return self.right_peak_kph - self.min_speed_kph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a reviewable track coaching model from a reference lap."
    )
    parser.add_argument("--reference-lap", type=Path, required=True)
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--layout-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--diagnostics-out", type=Path)
    parser.add_argument("--car-id", help="Override/reference car identity when metadata is absent.")
    # v2 (throttle_brake_v1) parameters
    parser.add_argument("--min-brake-fraction", type=float, default=0.15,
                        help="Minimum brake_norm to count as braking (default 0.15 = 15%%)")
    parser.add_argument("--max-throttle-fraction", type=float, default=0.90,
                        help="Throttle_norm below this = lift event (default 0.90 = 90%%)")
    parser.add_argument("--min-event-length-m", type=int, default=5,
                        help="Minimum zone length in metres to count as a corner (default 5)")
    parser.add_argument("--min-speed-drop-kph", type=float, default=10.0,
                        help="Minimum speed drop from entry to apex to count as a corner (default 10)")
    parser.add_argument("--max-throttle-significant", type=float, default=0.50,
                        help="For pure-lift zones: if min throttle within zone drops at or below this "
                             "fraction the corner qualifies even if speed drop < min-speed-drop-kph "
                             "(catches fast chicanes; default 0.50)")
    parser.add_argument("--min-speed-drop-lift-kph", type=float, default=3.0,
                        help="Minimum speed drop for a throttle-lift corner that qualifies via "
                             "max-throttle-significant (prevents near-zero speed kinks; default 3.0)")
    parser.add_argument("--min-separation-m", type=int, default=68,
                        help="Minimum apex-to-apex distance; closer ones are merged (default 68)")
    # v1 fallback parameters
    parser.add_argument("--smooth-window-m", type=int, default=5)
    parser.add_argument("--local-radius-m", type=int, default=8)
    parser.add_argument("--prominence-window-m", type=int, default=80)
    parser.add_argument("--min-prominence-kph", type=float, default=2.5)
    parser.add_argument("--zone-threshold-kph", type=float, default=1.0)
    parser.add_argument("--max-zone-half-width-m", type=int, default=120)
    parser.add_argument("--default-apex-side", choices=("left", "right"), default="right")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def finite_pairs(distances: list[Any], values: list[Any]) -> tuple[list[float], list[float]]:
    pairs = []
    for distance, value in zip(distances, values):
        if distance is None or value is None:
            continue
        d = float(distance)
        v = float(value)
        if d == d and v == v:
            pairs.append((d, v))
    pairs.sort(key=lambda item: item[0])
    return [p[0] for p in pairs], [p[1] for p in pairs]


def moving_average(values: list[float], window: int) -> list[float]:
    window = max(1, window)
    if window % 2 == 0:
        window += 1
    half = window // 2
    smoothed = []
    for index in range(len(values)):
        start = max(0, index - half)
        end = min(len(values), index + half + 1)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def merge_close_candidates(candidates: list[Candidate], min_separation_m: int) -> list[Candidate]:
    strongest_first = sorted(
        candidates,
        key=lambda c: (c.prominence_kph, -c.min_speed_kph),
        reverse=True,
    )
    accepted: list[Candidate] = []
    for candidate in strongest_first:
        nearby = [k for k in accepted if abs(candidate.apex_m - k.apex_m) < min_separation_m]
        if not nearby:
            accepted.append(candidate)
        else:
            # Dropped — but extend the winner's zone so the entry/exit aren't lost.
            for winner in nearby:
                winner.s_start_m = min(winner.s_start_m, candidate.s_start_m)
                winner.s_end_m = max(winner.s_end_m, candidate.s_end_m)
    return sorted(accepted, key=lambda c: c.apex_m)


def prevent_zone_overlap(candidates: list[Candidate]) -> None:
    for previous, current in zip(candidates, candidates[1:]):
        if previous.s_end_m <= current.s_start_m:
            continue
        midpoint = (previous.apex_m + current.apex_m) // 2
        previous.s_end_m = float(max(previous.apex_m + 1, midpoint))
        current.s_start_m = float(min(current.apex_m - 1, midpoint))


def _peak_around(speed: list[float], index: int, radius: int) -> float:
    left = speed[max(0, index - radius):index]
    right = speed[index + 1:min(len(speed), index + radius + 1)]
    combined = left + right
    return max(combined) if combined else speed[index]


# ---------------------------------------------------------------------------
# v2: throttle_brake_v1
# ---------------------------------------------------------------------------

def _find_brake_events(brakes: list[float], min_brake: float) -> list[tuple[int, int]]:
    """Segments where brake >= min_brake. Merges adjacent events if brake
    never returns to 0 between them (continuous corner / chicane)."""
    raw: list[tuple[int, int]] = []
    in_event = False
    start = 0
    for i, b in enumerate(brakes):
        if b >= min_brake and not in_event:
            start = i
            in_event = True
        elif b < min_brake and in_event:
            raw.append((start, i - 1))
            in_event = False
    if in_event:
        raw.append((start, len(brakes) - 1))

    if not raw:
        return []
    merged = [list(raw[0])]
    for s, e in raw[1:]:
        gap = brakes[merged[-1][1] + 1:s]
        if gap and min(gap) > 0.0:  # brake never fully released
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def _find_lift_events(
    throttles: list[float],
    brakes: list[float],
    max_throttle: float,
    min_brake: float,
) -> list[tuple[int, int]]:
    """Segments where throttle < max_throttle AND brake < min_brake (pure lift,
    no meaningful braking)."""
    events: list[tuple[int, int]] = []
    in_event = False
    start = 0
    for i, (t, b) in enumerate(zip(throttles, brakes)):
        is_lift = t < max_throttle and b < min_brake
        if is_lift and not in_event:
            start = i
            in_event = True
        elif not is_lift and in_event:
            events.append((start, i - 1))
            in_event = False
    if in_event:
        events.append((start, len(throttles) - 1))
    return events


def backfill_entries(
    candidates: list[Candidate],
    speed: list[float],
    throttle: list[float],
    brake: list[float],
    max_throttle_fraction: float,
    full_throttle_sentinel: float = 0.98,
) -> None:
    """Walk backward from s_start_m and forward from s_end_m to find true
    entry/exit — the last full-throttle sample before the driver started
    lifting/braking, and the first sample where throttle returns to the
    max_throttle_fraction threshold.

    Capped by neighbouring corners to avoid trespassing.  Mutates in place.
    """
    for i, c in enumerate(candidates):
        # --- entry: walk backward to last full-throttle sample ---
        floor = int(candidates[i - 1].s_end_m) + 1 if i > 0 else 0
        for m in range(int(c.s_start_m) - 1, floor - 1, -1):
            if throttle[m] >= full_throttle_sentinel:
                break
            c.s_start_m = float(m)

        # --- exit: walk forward to first sample where throttle returns ---
        ceiling = int(candidates[i + 1].s_start_m) - 1 if i < len(candidates) - 1 else len(throttle) - 1
        for m in range(int(c.s_end_m) + 1, ceiling + 1):
            if throttle[m] >= max_throttle_fraction:
                c.s_end_m = float(m)
                break


def detect_corners_from_signals(
    speed: list[float],
    throttle: list[float],
    brake: list[float],
    *,
    min_brake_fraction: float = 0.15,
    max_throttle_fraction: float = 0.90,
    min_separation_m: int = 60,
    min_event_length_m: int = 5,
    min_speed_drop_kph: float = 10.0,
    max_throttle_significant: float = 0.50,
    min_speed_drop_lift_kph: float = 3.0,
) -> list[Candidate]:
    """Detect corners using throttle and brake signals.

    Corner zones are brake events (merged across brief zero-brake gaps) plus
    pure throttle-lift events. Apex = speed minimum within each zone.
    """
    brake_events = _find_brake_events(brake, min_brake_fraction)
    lift_events = _find_lift_events(throttle, brake, max_throttle_fraction, min_brake_fraction)

    # Filter very short events (sensor noise / kerb touches)
    # Tag each zone as brake or lift so we can apply different qualifying rules
    tagged_zones: list[tuple[int, int, str]] = []
    for s, e in brake_events:
        if e - s >= min_event_length_m:
            tagged_zones.append((s, e, "brake"))
    for s, e in lift_events:
        if e - s >= min_event_length_m:
            tagged_zones.append((s, e, "lift"))

    if not tagged_zones:
        return []

    # Merge overlapping zones (brake wins over lift when merged)
    tagged_zones.sort(key=lambda z: z[0])
    merged: list[list] = [list(tagged_zones[0])]
    for s, e, kind in tagged_zones[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
            if kind == "brake":
                merged[-1][2] = "brake"
        else:
            merged.append([s, e, kind])

    # Build Candidate for each zone: apex = speed minimum inside the zone
    prominence_radius = 80
    candidates: list[Candidate] = []
    for s, e, kind in merged:
        zone_speeds = speed[s:e + 1]
        if not zone_speeds:
            continue
        local_idx = zone_speeds.index(min(zone_speeds))
        apex = s + local_idx
        min_spd = speed[apex]
        left_peak = max(speed[max(0, apex - prominence_radius):apex], default=min_spd)
        right_peak = max(speed[apex + 1:min(len(speed), apex + prominence_radius + 1)], default=min_spd)
        prominence = min(left_peak - min_spd, right_peak - min_spd)
        c = Candidate(
            apex_m=apex,
            min_speed_kph=min_spd,
            prominence_kph=prominence,
            left_peak_kph=left_peak,
            right_peak_kph=right_peak,
            s_start_m=float(s),
            s_end_m=float(e),
            entry_speed_kph=speed[s],
            exit_speed_kph=speed[e],
        )

        # Qualify: brake zones → speed drop >= threshold
        #          lift zones → speed drop >= threshold OR min throttle <= max_throttle_significant
        if kind == "brake":
            if c.speed_drop_kph < min_speed_drop_kph:
                continue
        else:  # pure lift
            zone_throttle = throttle[s:e + 1]
            min_throttle = min(zone_throttle) if zone_throttle else 1.0
            significant_lift = min_throttle <= max_throttle_significant
            if c.speed_drop_kph < min_speed_drop_kph:
                # Allow via significant lift, but still require a minimum speed drop
                if not significant_lift or c.speed_drop_kph < min_speed_drop_lift_kph:
                    continue

        candidates.append(c)

    # Merge candidates that are still too close (keep most prominent)
    candidates = merge_close_candidates(candidates, min_separation_m)
    prevent_zone_overlap(candidates)
    backfill_entries(candidates, speed, throttle, brake, max_throttle_fraction)
    return candidates


# ---------------------------------------------------------------------------
# v1 fallback: speed_local_minimum_v1
# ---------------------------------------------------------------------------

def candidate_prominence(values: list[float], index: int, window: int) -> tuple[float, float, float]:
    left = values[max(0, index - window):index]
    right = values[index + 1:min(len(values), index + window + 1)]
    if not left or not right:
        return 0.0, values[index], values[index]
    left_peak = max(left)
    right_peak = max(right)
    return min(left_peak - values[index], right_peak - values[index]), left_peak, right_peak


def raw_candidates(
    speed: list[float],
    local_radius_m: int,
    prominence_window_m: int,
    min_prominence_kph: float,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    radius = max(1, local_radius_m)
    for index in range(radius, len(speed) - radius):
        value = speed[index]
        window = speed[index - radius:index + radius + 1]
        if value > min(window):
            continue
        prominence, left_peak, right_peak = candidate_prominence(speed, index, prominence_window_m)
        if prominence < min_prominence_kph:
            continue
        candidates.append(Candidate(index, value, prominence, left_peak, right_peak))
    return candidates


def estimate_zone(
    candidate: Candidate,
    speed: list[float],
    zone_threshold_kph: float,
    max_half_width_m: int,
) -> None:
    apex = candidate.apex_m
    start_floor = max(0, apex - max_half_width_m)
    end_ceiling = min(len(speed) - 1, apex + max_half_width_m)

    start = start_floor
    for index in range(apex - 1, start_floor, -1):
        if speed[index] >= speed[index - 1] - zone_threshold_kph:
            start = index
        elif apex - index > 12:
            break

    end = end_ceiling
    for index in range(apex + 1, end_ceiling):
        if speed[index] <= speed[index + 1] + zone_threshold_kph:
            end = index
        elif index - apex > 12:
            break

    candidate.s_start_m = float(min(start, apex - 1))
    candidate.s_end_m = float(max(end, apex + 1))
    candidate.entry_speed_kph = speed[int(candidate.s_start_m)]
    candidate.exit_speed_kph = speed[int(candidate.s_end_m)]


def detect_apex_candidates(
    speed: list[float],
    *,
    smooth_window_m: int = 5,
    local_radius_m: int = 8,
    prominence_window_m: int = 80,
    min_prominence_kph: float = 2.5,
    min_separation_m: int = 60,
    zone_threshold_kph: float = 1.0,
    max_zone_half_width_m: int = 120,
) -> tuple[list[Candidate], list[float]]:
    smoothed = moving_average(speed, smooth_window_m)
    candidates = raw_candidates(smoothed, local_radius_m, prominence_window_m, min_prominence_kph)
    accepted = merge_close_candidates(candidates, min_separation_m)
    for candidate in accepted:
        estimate_zone(candidate, smoothed, zone_threshold_kph, max_zone_half_width_m)
    prevent_zone_overlap(accepted)
    return accepted, smoothed


# ---------------------------------------------------------------------------
# Car identity helpers
# ---------------------------------------------------------------------------

def first_distinct_value(table: Any, column_name: str) -> str | None:
    if column_name not in table.column_names:
        return None
    for value in table.column(column_name).to_pylist():
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def car_id_from_sidecar(reference_lap: Path) -> str | None:
    sidecars = [
        reference_lap.with_suffix(".json"),
        reference_lap.with_name(reference_lap.name + ".json"),
        reference_lap.with_name(reference_lap.stem + ".metadata.json"),
    ]
    for sidecar in sidecars:
        if not sidecar.exists():
            continue
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key in CAR_COLUMNS:
            value = data.get(key)
            if value:
                return str(value)
    return None


def car_id_from_filename(reference_lap: Path, track_id: str) -> str | None:
    stem = reference_lap.stem
    match = re.match(rf"^{re.escape(track_id)}_(.+?)_time_", stem)
    if not match:
        return None
    return match.group(1)


def resolve_car_id(table: Any, reference_lap: Path, track_id: str, override: str | None) -> str:
    if override:
        return override
    for column in CAR_COLUMNS:
        value = first_distinct_value(table, column)
        if value:
            return value
    sidecar_value = car_id_from_sidecar(reference_lap)
    if sidecar_value:
        return sidecar_value
    filename_value = car_id_from_filename(reference_lap, track_id)
    if filename_value:
        return filename_value
    raise ValueError("Unable to determine reference car identity; pass --car-id.")


def lap_time_s(table: Any) -> float:
    values = [float(v) for v in table.column("lap_time_s").to_pylist() if v is not None and float(v) > 0]
    return max(values) if values else 0.0


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

def build_model(
    reference_lap: Path,
    track_id: str,
    layout_id: str,
    car_id: str,
    lap_time: float,
    lap_length_m: float,
    candidates: list[Candidate],
    default_apex_side: str,
    detection_method: str,
) -> dict[str, Any]:
    corners = []
    for index, candidate in enumerate(candidates, start=1):
        corners.append({
            "id": f"t{index}",
            "name": f"turn {index}",
            "s_start_m": round(candidate.s_start_m, 1),
            "apex_s_m": round(float(candidate.apex_m), 1),
            "s_end_m": round(candidate.s_end_m, 1),
            "apex_side": default_apex_side,
            "apex_side_source": "default_cli_option",
        })

    return {
        "schema_version": "1",
        "track_id": track_id,
        "layout_id": layout_id,
        "reference_lap": {
            "path": str(reference_lap),
            "car_id": car_id,
            "lap_time_s": round(lap_time, 3),
            "detection_method": detection_method,
        },
        "lap_length_m": round(lap_length_m, 1),
        "corners": corners,
        "straight_zones": [],
    }


def diagnostics_text(candidates: list[Candidate], detection_method: str) -> str:
    lines = [f"detection_method={detection_method}"]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(
            f"t{index} apex={candidate.apex_m}m "
            f"start={candidate.s_start_m:.0f}m end={candidate.s_end_m:.0f}m "
            f"min={candidate.min_speed_kph:.1f}kph "
            f"entry={candidate.entry_speed_kph:.1f}kph exit={candidate.exit_speed_kph:.1f}kph "
            f"drop={candidate.speed_drop_kph:.1f}kph "
            f"recovery={candidate.recovery_kph:.1f}kph "
            f"prominence={candidate.prominence_kph:.1f}kph accepted"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(args.reference_lap)
        required = ["lap_distance_m", "speed_kph", "lap_time_s", "lap_number"]
        missing = [column for column in required if column not in table.column_names]
        if missing:
            raise ValueError(f"Reference lap missing required columns: {missing}")

        car_id = resolve_car_id(table, args.reference_lap, args.track_id, args.car_id)
        distances, speeds = finite_pairs(
            table.column("lap_distance_m").to_pylist(),
            table.column("speed_kph").to_pylist(),
        )
        if not distances:
            raise ValueError("Reference lap has no usable distance/speed samples.")

        lap_length = int(max(distances))
        resampled_speed = resample_column(distances, speeds, lap_length)

        has_signals = (
            "throttle_norm" in table.column_names
            and "brake_norm" in table.column_names
        )

        if has_signals:
            _, throttles = finite_pairs(
                table.column("lap_distance_m").to_pylist(),
                table.column("throttle_norm").to_pylist(),
            )
            _, brakes = finite_pairs(
                table.column("lap_distance_m").to_pylist(),
                table.column("brake_norm").to_pylist(),
            )
            resampled_throttle = resample_column(distances, throttles, lap_length)
            resampled_brake = resample_column(distances, brakes, lap_length)

            candidates = detect_corners_from_signals(
                resampled_speed,
                resampled_throttle,
                resampled_brake,
                min_brake_fraction=args.min_brake_fraction,
                max_throttle_fraction=args.max_throttle_fraction,
                min_separation_m=args.min_separation_m,
                min_event_length_m=args.min_event_length_m,
                min_speed_drop_kph=args.min_speed_drop_kph,
                max_throttle_significant=args.max_throttle_significant,
                min_speed_drop_lift_kph=args.min_speed_drop_lift_kph,
            )
            detection_method = DETECTION_METHOD_V2
        else:
            print("Warning: throttle_norm/brake_norm absent, falling back to speed_local_minimum_v1",
                  file=sys.stderr)
            candidates, _ = detect_apex_candidates(
                resampled_speed,
                smooth_window_m=args.smooth_window_m,
                local_radius_m=args.local_radius_m,
                prominence_window_m=args.prominence_window_m,
                min_prominence_kph=args.min_prominence_kph,
                min_separation_m=args.min_separation_m,
                zone_threshold_kph=args.zone_threshold_kph,
                max_zone_half_width_m=args.max_zone_half_width_m,
            )
            detection_method = DETECTION_METHOD_V1

        model = build_model(
            args.reference_lap,
            args.track_id,
            args.layout_id,
            car_id,
            lap_time_s(table),
            float(max(distances)),
            candidates,
            args.default_apex_side,
            detection_method,
        )

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

        diagnostics_out = args.diagnostics_out or args.out.with_suffix(".diagnostics.txt")
        diagnostics_out.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_out.write_text(diagnostics_text(candidates, detection_method), encoding="utf-8")

        print(f"Wrote {args.out}")
        print(f"Wrote {diagnostics_out}")
        print(f"Detected {len(candidates)} corners via {detection_method} for car {car_id}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
