"""Reproduce slice 01's calibration gates on the committed recordings.

Run from the project root:  python work/active/rear-grip-signal/01-true-slip-angle/artifacts/validate_channels.py

Read-only. Prints the numbers quoted in ``handoff.md`` / ``learnings.md`` and
copied into ``channel-validation.txt``.
"""
from __future__ import annotations

import glob
import os
import statistics
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.rear_slip import column_reasons, slip_series  # noqa: E402

NEW_COLUMNS = ("grip_fraction_rl", "grip_fraction_rr",
               "wheel_ground_vel_lat_rl", "wheel_ground_vel_lon_rl",
               "wheel_ground_vel_lat_rr", "wheel_ground_vel_lon_rr",
               "yaw_rate_radps")


def sessions_with_channels() -> list[str]:
    out = []
    for path in sorted(glob.glob(str(ROOT / "sessions" / "*.parquet"))):
        names = pq.ParquetFile(path).schema_arrow.names
        if all(column in names for column in NEW_COLUMNS):
            out.append(path)
    return out


def main() -> int:
    paths = sessions_with_channels()
    print(f"recordings carrying all seven new columns: {len(paths)}")
    dead_grip = 0
    for path in paths:
        table = pq.read_table(path, columns=["grip_fraction_rl"])
        values = {v for v in table.column("grip_fraction_rl").to_pylist() if v is not None}
        if values == {0.0}:
            dead_grip += 1
    print(f"  of those, grip_fraction_rl is a constant 0.0 in {dead_grip}")
    print(f"  verdict: mGripFract is a dead channel in LMU, not a sliding metric\n")

    for path in (ROOT / "sessions/session_20261115T124448Z_circuit-de-barcelona_lmu_race.parquet",
                 ROOT / "sessions/session_20261114T190410Z_silverstone-national-circuit_lmu_race.parquet"):
        table = pq.read_table(path)
        series = slip_series(table)
        speed = table.column("speed_kph").to_pylist()
        steering = table.column("steering_norm").to_pylist()
        yaw = table.column("yaw_rate_radps").to_pylist()
        surface = table.column("surface_type_rl").to_pylist()
        print(os.path.basename(path))

        def pick(predicate):
            return [i for i, value in enumerate(series)
                    if value is not None and speed[i] and speed[i] >= 30
                    and surface[i] in (0, None) and predicate(i)]

        straight = pick(lambda i: abs(steering[i] or 0.0) < 0.05
                        and abs(yaw[i] or 0.0) < 0.05 and speed[i] > 80)
        print(f"  straight (|steer|<0.05, |yaw|<0.05, >80 kph): n={len(straight)} "
              f"median |slip| {statistics.median([abs(series[i]) for i in straight]):.2f} deg")
        rotating = pick(lambda i: abs(yaw[i] or 0.0) > 0.15)
        agree = sum(1 for i in rotating if (series[i] > 0) == (yaw[i] > 0))
        print(f"  rotating (|yaw|>0.15 rad/s): n={len(rotating)} "
              f"sign(slip)==sign(yaw) {100 * agree / len(rotating):.1f}%")
        for label, low, high in (("ay<0.3 g", 0.0, 0.3), ("0.8-1.3 g", 0.8, 1.3),
                                 ("ay>1.3 g", 1.3, 3.0)):
            band = pick(lambda i: low <= abs((yaw[i] or 0.0) * speed[i] / 3.6 / 9.81) < high)
            print(f"  {label:10s}: n={len(band)} "
                  f"median |slip| {statistics.median([abs(series[i]) for i in band]):.2f} deg")
        print(f"  channels refused: {sorted(column_reasons(table))}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
