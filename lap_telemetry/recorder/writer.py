"""SessionWriter: buffer frames, flush Parquet shards, finalise session file + JSON sidecar."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry import __version__
from .connect import Frame

_SCHEMA = pa.schema([
    pa.field("session_time_s", pa.float64()),
    pa.field("lap_number",     pa.int32()),
    pa.field("lap_distance_m", pa.float32()),
    pa.field("lap_time_s",     pa.float32()),
    pa.field("speed_kph",      pa.float32()),
    pa.field("throttle_norm",  pa.float32()),
    pa.field("brake_norm",     pa.float32()),
    pa.field("steering_norm",  pa.float32()),
    pa.field("gear",           pa.int8()),
    pa.field("engine_rpm",     pa.float32()),
    pa.field("lap_valid",      pa.bool_()),
    pa.field("pos_x_m",        pa.float32()),
    pa.field("pos_y_m",        pa.float32()),
    pa.field("pos_z_m",        pa.float32()),
])


def _track_slug(track: str) -> str:
    slug = track.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or "unknown"


def _utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_SHARD_RE = re.compile(r"^(session_.+)\.part(\d+)\.parquet$")


def recover_orphaned_shards(out_dir: Path) -> None:
    """Merge any .partN.parquet shards left by a previous hard-kill."""
    shards = [p for p in out_dir.glob("*.part*.parquet") if _SHARD_RE.match(p.name)]
    if not shards:
        return

    groups: dict[str, list[Path]] = {}
    for p in shards:
        m = _SHARD_RE.match(p.name)
        if m:
            groups.setdefault(m.group(1), []).append(p)

    for stem, group in groups.items():
        final = out_dir / f"{stem}.parquet"
        group = sorted(group, key=lambda p: int(_SHARD_RE.match(p.name).group(2)))  # type: ignore[union-attr]

        print(f"lap-telemetry: recovering {len(group)} orphaned shards -> {final.name}", flush=True)
        tables = [pq.read_table(p) for p in group]
        merged = pa.concat_tables(tables)
        pq.write_table(merged, final, compression="snappy")

        # write a best-effort sidecar from what we can parse out of the stem
        # stem: session_<YYYYMMDDTHHMMSSZ>_<track-slug>_<sim>
        parts = stem.split("_", 3)
        started = parts[1] if len(parts) > 1 else "unknown"
        # reformat compact UTC to ISO
        try:
            started_iso = datetime.strptime(started, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            started_iso = started
        sim  = parts[3] if len(parts) > 3 else "unknown"
        track_slug = parts[2] if len(parts) > 2 else "unknown"

        laps = sorted(set(merged.column("lap_number").to_pylist()))
        json_path = out_dir / f"{stem}.json"
        if not json_path.exists():
            sidecar = {
                "schema_version": "1",
                "recorder_version": __version__,
                "started_utc": started_iso,
                "ended_utc": "unknown",
                "sim": sim,
                "track": track_slug,
                "vehicle_name": "unknown",
                "sample_rate_hz": 50.0,
                "row_count": merged.num_rows,
                "lap_count": len(laps),
                "recovered": True,
            }
            json_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

        for p in group:
            p.unlink(missing_ok=True)
        print(f"lap-telemetry: recovered  {merged.num_rows} rows, laps {laps}", flush=True)


class SessionWriter:
    def __init__(self, out_dir: Path, sim: str, track: str, rate_hz: float) -> None:
        self._out_dir = out_dir
        self._sim = sim
        self._track = track
        self._rate_hz = rate_hz
        self._started_utc = _utc_iso()
        stem = f"session_{_utc_compact()}_{_track_slug(track)}_{sim}"
        self._stem = stem
        self._shard_index = 0
        self._shard_paths: list[Path] = []
        self._buf: dict[str, list] = {f.name: [] for f in _SCHEMA}
        self._last_vehicle: str = ""
        self._lap_numbers: set[int] = set()

    def append(self, frame: Frame) -> None:
        b = self._buf
        b["session_time_s"].append(frame.session_time_s)
        b["lap_number"].append(frame.lap_number)
        b["lap_distance_m"].append(frame.lap_distance_m)
        b["lap_time_s"].append(frame.lap_time_s)
        b["speed_kph"].append(frame.speed_kph)
        b["throttle_norm"].append(frame.throttle_norm)
        b["brake_norm"].append(frame.brake_norm)
        b["steering_norm"].append(frame.steering_norm)
        b["gear"].append(frame.gear)
        b["engine_rpm"].append(frame.engine_rpm)
        b["lap_valid"].append(frame.lap_valid)
        b["pos_x_m"].append(frame.pos_x_m)
        b["pos_y_m"].append(frame.pos_y_m)
        b["pos_z_m"].append(frame.pos_z_m)
        self._lap_numbers.add(frame.lap_number)
        self._last_vehicle = frame.vehicle_name

    def flush_shard(self) -> None:
        if not self._buf["session_time_s"]:
            return
        path = self._out_dir / f"{self._stem}.part{self._shard_index}.parquet"
        table = pa.table(self._buf, schema=_SCHEMA)
        pq.write_table(table, path, compression="snappy")
        self._shard_paths.append(path)
        self._shard_index += 1
        self._buf = {f.name: [] for f in _SCHEMA}

    def close(self) -> tuple[Path, Path]:
        self.flush_shard()

        parquet_path = self._out_dir / f"{self._stem}.parquet"
        json_path = self._out_dir / f"{self._stem}.json"

        if self._shard_paths:
            tables = [pq.read_table(p) for p in self._shard_paths]
            final = pa.concat_tables(tables)
            pq.write_table(final, parquet_path, compression="snappy")
            for p in self._shard_paths:
                p.unlink(missing_ok=True)
            row_count = final.num_rows
        else:
            pq.write_table(pa.table(self._buf, schema=_SCHEMA), parquet_path, compression="snappy")
            row_count = 0

        sidecar = {
            "schema_version": "1",
            "recorder_version": __version__,
            "started_utc": self._started_utc,
            "ended_utc": _utc_iso(),
            "sim": self._sim,
            "track": self._track,
            "vehicle_name": self._last_vehicle,
            "sample_rate_hz": self._rate_hz,
            "row_count": row_count,
            "lap_count": len(self._lap_numbers),
        }
        json_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

        return parquet_path, json_path
