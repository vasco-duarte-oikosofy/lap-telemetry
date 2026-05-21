"""Python wrapper that calls the Node.js telemetry pipeline.

Ensures ALL resampled channels match the web UI exactly by using the
same JavaScript code (computeKeepIndices, smoothLapTime, resample,
computeDeltaT, smoothDt) from product/web/js/pipeline.js.

The Node.js script (dev/scripts/compute_delta_t.mjs) takes JSON on
stdin and returns JSON on stdout with every resampled grid and the
delta-t trace.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Resolve project root: product/python/lap_telemetry/coach/ → repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_JS_SCRIPT = _REPO_ROOT / "dev" / "scripts" / "compute_delta_t.mjs"


def run_js_pipeline(
    driver_lap_time_s: list[float],
    driver_lap_distance_m: list[float],
    driver_speed_kph: list[float],
    ref_lap_time_s: list[float],
    ref_lap_distance_m: list[float],
    ref_speed_kph: list[float],
    track_length: int,
    driver_throttle_norm: list[float] | None = None,
    driver_brake_norm: list[float] | None = None,
    ref_throttle_norm: list[float] | None = None,
    ref_brake_norm: list[float] | None = None,
) -> dict:
    """Run the full JS telemetry pipeline and return all resampled grids.

    Calls the Node.js script which implements the identical 6-step
    pipeline as the web UI. Returns a dict with keys:
      delta_t_ms, driver_speed_kph, ref_speed_kph,
      driver_throttle_norm, driver_brake_norm,
      ref_throttle_norm, ref_brake_norm, track_length.

    Args:
        driver_lap_time_s: Raw lap_time_s column from driver parquet.
        driver_lap_distance_m: Raw lap_distance_m from driver parquet.
        driver_speed_kph: Raw speed_kph from driver parquet.
        ref_lap_time_s: Raw lap_time_s column from reference parquet.
        ref_lap_distance_m: Raw lap_distance_m from reference parquet.
        ref_speed_kph: Raw speed_kph from reference parquet.
        track_length: Track length for computeKeepIndices.
        driver_throttle_norm: Optional raw throttle_norm from driver.
        driver_brake_norm: Optional raw brake_norm from driver.
        ref_throttle_norm: Optional raw throttle_norm from reference.
        ref_brake_norm: Optional raw brake_norm from reference.

    Returns:
        Dict with all resampled grids and delta-t.

    Raises:
        RuntimeError: If Node.js subprocess fails.
        FileNotFoundError: If the JS script is missing.
    """
    if not _JS_SCRIPT.exists():
        raise FileNotFoundError(
            f"JS pipeline script not found: {_JS_SCRIPT}\n"
            "Run from the repo root or check that dev/scripts/compute_delta_t.mjs exists."
        )

    input_data = {
        "driver": {
            "lap_time_s": driver_lap_time_s,
            "lap_distance_m": driver_lap_distance_m,
            "speed_kph": driver_speed_kph,
            "throttle_norm": driver_throttle_norm,
            "brake_norm": driver_brake_norm,
        },
        "reference": {
            "lap_time_s": ref_lap_time_s,
            "lap_distance_m": ref_lap_distance_m,
            "speed_kph": ref_speed_kph,
            "throttle_norm": ref_throttle_norm,
            "brake_norm": ref_brake_norm,
        },
        "trackLength": track_length,
    }

    result = subprocess.run(
        ["node", str(_JS_SCRIPT)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Node.js telemetry pipeline failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    return json.loads(result.stdout)


def delta_t_ms_to_seconds(delta_t_ms: list[float]) -> list[float]:
    """Convert delta-t from milliseconds to seconds."""
    return [v / 1000.0 for v in delta_t_ms]