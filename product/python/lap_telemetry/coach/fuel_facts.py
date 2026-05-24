"""Fuel fact recorder: compute deterministic fuel-to-end facts from telemetry.

This module provides:
  - FuelFacts dataclass: structured fuel/race-state facts
  - compute_fuel_facts(): deterministic analysis from Parquet or Frame list
  - CLI: ``python3 -m lap_telemetry.coach.fuel_facts <parquet_path>``
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Union

import pyarrow.parquet as pq

from lap_telemetry.recorder.connect import Frame

# ── Session type mapping ──────────────────────────────────────────────────

SESSION_TYPE_MAP: dict[int, str] = {
    0: "practice",
    1: "test",
    2: "qualifying",
    3: "race",
    4: "other",
    5: "other",
    6: "other",
    7: "other",
    8: "other",
}


def session_type_str(code: int | None) -> str:
    """Convert numeric session type code to human-readable string."""
    if code is None:
        return "unknown"
    return SESSION_TYPE_MAP.get(code, "unknown")


# ── FuelFacts dataclass ──────────────────────────────────────────────────


@dataclass
class FuelFacts:
    """Deterministic fuel and race-state facts computed from telemetry."""

    track_name: str
    session_type: str  # "practice" | "qualifying" | "race" | "test" | "other" | "unknown"
    race_laps_total: int | None
    race_laps_remaining: int | None
    fuel_at_start_l: float | None
    fuel_at_end_l: float | None
    fuel_used_l: float | None
    laps_completed: int
    fuel_per_lap_l: float | None
    laps_of_fuel_remaining: float | None
    fuel_status: str  # "OK" | "WARNING" | "CRITICAL" | "UNKNOWN"


def compute_fuel_facts(source: Union[Path, str, list[Frame]]) -> FuelFacts:
    """Compute deterministic fuel facts from a Parquet file or list of Frames.

    Args:
        source: Path to a Parquet file, or a list of Frame objects.

    Returns:
        FuelFacts dataclass with computed values.
    """
    if isinstance(source, (str, Path)):
        return _compute_from_parquet(Path(source))
    return _compute_from_frames(source)


def _read_sidecar(parquet_path: Path) -> dict | None:
    """Try to read the JSON sidecar next to the Parquet file."""
    sidecar = parquet_path.with_suffix(".json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _compute_from_parquet(path: Path) -> FuelFacts:
    """Compute FuelFacts from a Parquet file path."""
    table = pq.read_table(str(path))
    col_names = set(table.schema.names)

    # Track name from sidecar JSON, fall back to "unknown"
    track_name = "unknown"
    sidecar = _read_sidecar(path)
    if sidecar and sidecar.get("track"):
        track_name = sidecar["track"]

    # Extract fuel columns if they exist
    fuel_col = table.column("fuel_l").to_pylist() if "fuel_l" in col_names else []
    fuel_cap_col = table.column("fuel_capacity_l").to_pylist() if "fuel_capacity_l" in col_names else []
    session_type_col = table.column("session_type").to_pylist() if "session_type" in col_names else []
    race_laps_total_col = table.column("race_laps_total").to_pylist() if "race_laps_total" in col_names else []
    lap_number_col = table.column("lap_number").to_pylist() if "lap_number" in col_names else []

    # Determine session type (most common non-None value)
    session_type_code: int | None = None
    if session_type_col:
        stypes = [v for v in session_type_col if v is not None]
        if stypes:
            session_type_code = max(set(stypes), key=stypes.count)

    # Determine race_laps_total (most common non-None value)
    race_laps_total: int | None = None
    if race_laps_total_col:
        rlaps = [v for v in race_laps_total_col if v is not None]
        if rlaps:
            race_laps_total = max(set(rlaps), key=rlaps.count)

    # Filter valid fuel readings (> 0, <= capacity if available)
    valid_fuel: list[float] = []
    for i, f in enumerate(fuel_col):
        if f is not None and f > 0:
            cap = fuel_cap_col[i] if i < len(fuel_cap_col) else None
            if cap is not None and cap > 0 and f > cap:
                continue  # skip invalid: fuel > capacity
            valid_fuel.append(f)

    fuel_at_start_l: float | None = valid_fuel[0] if valid_fuel else None
    fuel_at_end_l: float | None = valid_fuel[-1] if valid_fuel else None

    # Laps completed from lap_number column
    lap_numbers = [v for v in lap_number_col if v is not None]
    unique_laps: set[int] = set(lap_numbers)
    laps_completed = len(unique_laps)

    # Fuel per lap
    fuel_per_lap_l: float | None = None
    fuel_used_l: float | None = None
    if fuel_at_start_l is not None and fuel_at_end_l is not None and laps_completed > 0:
        fuel_used_l = fuel_at_start_l - fuel_at_end_l
        if fuel_used_l > 0:
            fuel_per_lap_l = fuel_used_l / laps_completed

    # Laps of fuel remaining
    laps_of_fuel_remaining: float | None = None
    if fuel_at_end_l is not None and fuel_per_lap_l is not None and fuel_per_lap_l > 0:
        laps_of_fuel_remaining = fuel_at_end_l / fuel_per_lap_l

    # Race laps remaining
    current_lap = max(unique_laps) if unique_laps else 0
    race_laps_remaining: int | None = None
    session_type = session_type_str(session_type_code)
    if session_type == "race" and race_laps_total is not None:
        race_laps_remaining = max(0, race_laps_total - current_lap)

    # Fuel status
    fuel_status = _classify_status(laps_of_fuel_remaining)

    return FuelFacts(
        track_name=track_name,
        session_type=session_type,
        race_laps_total=race_laps_total,
        race_laps_remaining=race_laps_remaining,
        fuel_at_start_l=round(fuel_at_start_l, 1) if fuel_at_start_l is not None else None,
        fuel_at_end_l=round(fuel_at_end_l, 1) if fuel_at_end_l is not None else None,
        fuel_used_l=round(fuel_used_l, 1) if fuel_used_l is not None else None,
        laps_completed=laps_completed,
        fuel_per_lap_l=round(fuel_per_lap_l, 1) if fuel_per_lap_l is not None else None,
        laps_of_fuel_remaining=round(laps_of_fuel_remaining, 1) if laps_of_fuel_remaining is not None else None,
        fuel_status=fuel_status,
    )


def _compute_from_frames(frames: list[Frame]) -> FuelFacts:
    """Compute FuelFacts from a list of Frame objects."""
    if not frames:
        return FuelFacts(
            track_name="unknown",
            session_type="unknown",
            race_laps_total=None,
            race_laps_remaining=None,
            fuel_at_start_l=None,
            fuel_at_end_l=None,
            fuel_used_l=None,
            laps_completed=0,
            fuel_per_lap_l=None,
            laps_of_fuel_remaining=None,
            fuel_status="UNKNOWN",
        )

    # Track name from first frame with a non-empty track
    track_name = "unknown"
    for f in frames:
        if f.track_name:
            track_name = f.track_name
            break

    # Session type: most common non-None value
    session_types = [f.session_type for f in frames if f.session_type is not None]
    session_type_code: int | None = None
    if session_types:
        session_type_code = max(set(session_types), key=session_types.count)

    # Race laps total: most common non-None value
    race_laps_totals = [f.race_laps_total for f in frames if f.race_laps_total is not None]
    race_laps_total: int | None = None
    if race_laps_totals:
        race_laps_total = max(set(race_laps_totals), key=race_laps_totals.count)

    # Valid fuel frames: fuel_l > 0 and (fuel <= capacity or capacity unknown)
    valid_frames = [
        f for f in frames
        if f.fuel_l is not None and f.fuel_l > 0
        and (f.fuel_capacity_l is None or f.fuel_l <= f.fuel_capacity_l)
    ]

    fuel_at_start_l: float | None = valid_frames[0].fuel_l if valid_frames else None
    fuel_at_end_l: float | None = valid_frames[-1].fuel_l if valid_frames else None

    # Laps completed — count unique lap numbers in ALL frames
    unique_laps: set[int] = set(f.lap_number for f in frames)
    laps_completed = len(unique_laps)

    # Fuel per lap
    fuel_per_lap_l: float | None = None
    fuel_used_l: float | None = None
    if fuel_at_start_l is not None and fuel_at_end_l is not None and laps_completed > 0:
        fuel_used_l = fuel_at_start_l - fuel_at_end_l
        if fuel_used_l > 0:
            fuel_per_lap_l = fuel_used_l / laps_completed

    # Laps of fuel remaining
    laps_of_fuel_remaining: float | None = None
    if fuel_at_end_l is not None and fuel_per_lap_l is not None and fuel_per_lap_l > 0:
        laps_of_fuel_remaining = fuel_at_end_l / fuel_per_lap_l

    # Race laps remaining
    current_lap = max(unique_laps) if unique_laps else 0
    race_laps_remaining: int | None = None
    session_type = session_type_str(session_type_code)
    if session_type == "race" and race_laps_total is not None:
        race_laps_remaining = max(0, race_laps_total - current_lap)

    # Fuel status
    fuel_status = _classify_status(laps_of_fuel_remaining)

    return FuelFacts(
        track_name=track_name,
        session_type=session_type,
        race_laps_total=race_laps_total,
        race_laps_remaining=race_laps_remaining,
        fuel_at_start_l=round(fuel_at_start_l, 1) if fuel_at_start_l is not None else None,
        fuel_at_end_l=round(fuel_at_end_l, 1) if fuel_at_end_l is not None else None,
        fuel_used_l=round(fuel_used_l, 1) if fuel_used_l is not None else None,
        laps_completed=laps_completed,
        fuel_per_lap_l=round(fuel_per_lap_l, 1) if fuel_per_lap_l is not None else None,
        laps_of_fuel_remaining=round(laps_of_fuel_remaining, 1) if laps_of_fuel_remaining is not None else None,
        fuel_status=fuel_status,
    )


def _classify_status(laps_remaining: float | None) -> str:
    """Classify fuel status based on laps of fuel remaining."""
    if laps_remaining is None:
        return "UNKNOWN"
    if laps_remaining < 2:
        return "CRITICAL"
    if laps_remaining <= 5:
        return "WARNING"
    return "OK"


# ── CLI ─────────────────────────────────────────────────────────────────

def _format_facts(facts: FuelFacts) -> str:
    """Format FuelFacts as human-readable output."""
    lines = [
        f"Track: {facts.track_name}",
        f"Session type: {facts.session_type}",
    ]
    if facts.race_laps_total is not None:
        lines.append(f"Race laps total: {facts.race_laps_total}")
    if facts.race_laps_remaining is not None:
        lines.append(f"Race laps remaining: {facts.race_laps_remaining}")
    if facts.fuel_at_start_l is not None:
        lines.append(f"Fuel at start: {facts.fuel_at_start_l:.1f} L")
    if facts.fuel_at_end_l is not None:
        lines.append(f"Fuel at end: {facts.fuel_at_end_l:.1f} L")
    if facts.fuel_used_l is not None:
        lines.append(f"Total fuel used: {facts.fuel_used_l:.1f} L")
    lines.append(f"Laps completed: {facts.laps_completed}")
    if facts.fuel_per_lap_l is not None:
        lines.append(f"Fuel per lap: {facts.fuel_per_lap_l:.1f} L")
    if facts.laps_of_fuel_remaining is not None:
        lines.append(f"Estimated laps of fuel remaining: {facts.laps_of_fuel_remaining:.1f}")
    if facts.fuel_status == "CRITICAL":
        lines.append("Fuel status: CRITICAL — must pit now")
    elif facts.fuel_status == "WARNING":
        lines.append("Fuel status: WARNING — consider pitting soon")
    elif facts.fuel_status == "OK":
        lines.append("Fuel status: OK")
    else:
        lines.append("Fuel status: UNKNOWN — no fuel data available")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze fuel facts from a recorded session")
    parser.add_argument("parquet_path", help="Path to the Parquet session file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.parquet_path)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    facts = compute_fuel_facts(path)

    if args.json:
        print(json.dumps(asdict(facts), indent=2))
    else:
        print(_format_facts(facts))


if __name__ == "__main__":
    main()