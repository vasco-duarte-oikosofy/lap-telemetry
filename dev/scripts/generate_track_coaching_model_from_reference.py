#!/usr/bin/env python3
"""Generate a reviewable track coaching model from a reference lap.

This script detects telemetry apex proxies from local minima in reference-lap
speed. It writes a production-loader-compatible JSON model plus diagnostics for
manual review before replacing any product track model.
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


DETECTION_METHOD = "speed_local_minimum_v1"
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
    parser.add_argument("--smooth-window-m", type=int, default=5)
    parser.add_argument("--local-radius-m", type=int, default=8)
    parser.add_argument("--prominence-window-m", type=int, default=80)
    parser.add_argument("--min-prominence-kph", type=float, default=2.5)
    parser.add_argument("--min-separation-m", type=int, default=60)
    parser.add_argument("--zone-threshold-kph", type=float, default=1.0)
    parser.add_argument("--max-zone-half-width-m", type=int, default=120)
    parser.add_argument("--default-apex-side", choices=("left", "right"), default="right")
    return parser.parse_args()


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


def merge_close_candidates(candidates: list[Candidate], min_separation_m: int) -> list[Candidate]:
    strongest_first = sorted(
        candidates,
        key=lambda c: (c.prominence_kph, -c.min_speed_kph),
        reverse=True,
    )
    accepted: list[Candidate] = []
    for candidate in strongest_first:
        if all(abs(candidate.apex_m - kept.apex_m) >= min_separation_m for kept in accepted):
            accepted.append(candidate)
    return sorted(accepted, key=lambda c: c.apex_m)


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


def prevent_zone_overlap(candidates: list[Candidate]) -> None:
    for previous, current in zip(candidates, candidates[1:]):
        if previous.s_end_m <= current.s_start_m:
            continue
        midpoint = (previous.apex_m + current.apex_m) // 2
        previous.s_end_m = float(max(previous.apex_m + 1, midpoint))
        current.s_start_m = float(min(current.apex_m - 1, midpoint))


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
    candidates = raw_candidates(
        smoothed,
        local_radius_m,
        prominence_window_m,
        min_prominence_kph,
    )
    accepted = merge_close_candidates(candidates, min_separation_m)
    for candidate in accepted:
        estimate_zone(candidate, smoothed, zone_threshold_kph, max_zone_half_width_m)
    prevent_zone_overlap(accepted)
    return accepted, smoothed


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
    prefix = f"{track_id}_"
    if not stem.startswith(prefix):
        return None
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


def build_model(
    reference_lap: Path,
    track_id: str,
    layout_id: str,
    car_id: str,
    lap_time: float,
    lap_length_m: float,
    candidates: list[Candidate],
    default_apex_side: str,
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
            "detection_method": DETECTION_METHOD,
        },
        "lap_length_m": round(lap_length_m, 1),
        "corners": corners,
        "straight_zones": [],
    }


def diagnostics_text(candidates: list[Candidate]) -> str:
    lines = [f"detection_method={DETECTION_METHOD}"]
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

        model = build_model(
            args.reference_lap,
            args.track_id,
            args.layout_id,
            car_id,
            lap_time_s(table),
            float(max(distances)),
            candidates,
            args.default_apex_side,
        )

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

        diagnostics_out = args.diagnostics_out or args.out.with_suffix(".diagnostics.txt")
        diagnostics_out.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_out.write_text(diagnostics_text(candidates), encoding="utf-8")

        print(f"Wrote {args.out}")
        print(f"Wrote {diagnostics_out}")
        print(f"Detected {len(candidates)} apex candidates for car {car_id}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should report clear failure
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
