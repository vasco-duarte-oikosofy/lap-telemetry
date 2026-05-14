"""SessionWriter: buffer frames, flush Parquet shards, finalise session file + JSON sidecar."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry import __version__
from .connect import Frame

_SCHEMA = pa.schema([
    pa.field("session_time_s",   pa.float64()),
    pa.field("lap_number",       pa.int32()),
    pa.field("lap_distance_m",   pa.float32()),
    pa.field("lap_time_s",       pa.float32()),
    pa.field("speed_kph",        pa.float32()),
    pa.field("throttle_norm",    pa.float32()),
    pa.field("brake_norm",       pa.float32()),
    pa.field("steering_norm",    pa.float32()),
    pa.field("gear",             pa.int8()),
    pa.field("engine_rpm",       pa.float32()),
    pa.field("lap_valid",        pa.bool_()),
    pa.field("pos_x_m",          pa.float32()),
    pa.field("pos_y_m",          pa.float32()),
    pa.field("pos_z_m",          pa.float32()),
    pa.field("last_sector_1_s",  pa.float32()),
    pa.field("last_sector_2_s",  pa.float32()),
    pa.field("slip_angle_fl_deg", pa.float32()),
    pa.field("slip_angle_fr_deg", pa.float32()),
    pa.field("slip_angle_rl_deg", pa.float32()),
    pa.field("slip_angle_rr_deg", pa.float32()),
    pa.field("abs_active", pa.bool_(), nullable=True),
    pa.field("tc_active",  pa.bool_(), nullable=True),
    pa.field("raw_lap_distance_m", pa.float32(), nullable=True),
    pa.field("path_lateral_m", pa.float32(), nullable=True),
    pa.field("track_edge_m", pa.float32(), nullable=True),
    pa.field("distance_to_track_edge_m", pa.float32(), nullable=True),
    pa.field("surface_type_fl", pa.int8(), nullable=True),
    pa.field("surface_type_fr", pa.int8(), nullable=True),
    pa.field("surface_type_rl", pa.int8(), nullable=True),
    pa.field("surface_type_rr", pa.int8(), nullable=True),
    pa.field("terrain_name_fl", pa.string(), nullable=True),
    pa.field("terrain_name_fr", pa.string(), nullable=True),
    pa.field("terrain_name_rl", pa.string(), nullable=True),
    pa.field("terrain_name_rr", pa.string(), nullable=True),
])


def _distance_to_track_edge(frame: Frame) -> float | None:
    if frame.track_edge_m is None or frame.path_lateral_m is None:
        return None
    return frame.track_edge_m - abs(frame.path_lateral_m)


def _track_slug(track: str) -> str:
    slug = track.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or "unknown"


def _utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_SHARD_RE = re.compile(r"^(session_.+)\.part(\d+)\.parquet$")


_SIM_DEFAULT_INSTALL: dict[str, Path] = {
    "lmu": Path(r"C:\Program Files (x86)\Steam\steamapps\common\Le Mans Ultimate"),
    "rf2": Path(r"C:\Program Files (x86)\Steam\steamapps\common\rFactor 2"),
}
_SIM_HOME_ENV: dict[str, str] = {"lmu": "LMU_HOME", "rf2": "RF2_HOME"}


def _sim_install_root(sim: str) -> Path | None:
    env_var = _SIM_HOME_ENV.get(sim)
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path:
            cand = Path(env_path)
            if cand.is_dir():
                return cand
    default = _SIM_DEFAULT_INSTALL.get(sim)
    return default if default and default.is_dir() else None


def _guess_setup_file(sim: str, track_name: str) -> str | None:
    """Best-effort: name of the most-recently-modified .svm in the sim's
    per-track settings folder. The setup filename is *not* exposed via SHM, so
    this is a guess — could be wrong if the driver loaded an older setup
    without saving."""
    if not track_name:
        return None
    root = _sim_install_root(sim)
    if root is None:
        return None
    settings_dir = root / "UserData" / "player" / "Settings" / track_name
    if not settings_dir.is_dir():
        return None
    svms = [p for p in settings_dir.glob("*.svm") if p.is_file()]
    if not svms:
        return None
    newest = max(svms, key=lambda p: p.stat().st_mtime)
    return newest.name


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

        laps = sorted(set(merged.column("lap_number").to_pylist()))
        json_path = out_dir / f"{stem}.json"
        new_sidecar: dict | None = None

        if json_path.exists():
            existing = json.loads(json_path.read_text(encoding="utf-8"))
            # Only stamp recovery onto sidecars from killed-mid-session writers.
            # An old/clean sidecar (no in_progress flag) is left untouched.
            if existing.get("in_progress"):
                existing["recovered"] = True
                existing["in_progress"] = False
                existing["row_count"] = merged.num_rows
                existing["lap_count"] = len(laps)
                if not existing.get("ended_utc"):
                    existing["ended_utc"] = "unknown"
                new_sidecar = existing
        else:
            # No sidecar from the killed session — best-effort from the
            # filename stem: session_<YYYYMMDDTHHMMSSZ>_<track-slug>_<sim>
            parts = stem.split("_", 3)
            started = parts[1] if len(parts) > 1 else "unknown"
            try:
                started_iso = datetime.strptime(started, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                started_iso = started
            sim_name   = parts[3] if len(parts) > 3 else "unknown"
            track_slug = parts[2] if len(parts) > 2 else "unknown"
            new_sidecar = {
                "schema_version": "2",
                "recorder_version": __version__,
                "started_utc": started_iso,
                "ended_utc": "unknown",
                "sim": sim_name,
                "track": track_slug,
                "vehicle_name": "unknown",
                "setup_file_guess": None,
                "sample_rate_hz": 50.0,
                "row_count": merged.num_rows,
                "lap_count": len(laps),
                "in_progress": False,
                "recovered": True,
            }

        if new_sidecar is not None:
            tmp = json_path.with_name(json_path.name + ".tmp")
            tmp.write_text(json.dumps(new_sidecar, indent=2), encoding="utf-8")
            os.replace(tmp, json_path)

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
        self._sidecar_path = out_dir / f"{stem}.json"
        self._shard_index = 0
        self._shard_paths: list[Path] = []
        self._buf: dict[str, list] = {f.name: [] for f in _SCHEMA}
        self._last_vehicle: str = ""
        self._lap_numbers: set[int] = set()
        self._row_count: int = 0  # cumulative across closed shards
        self._setup_file_guess: str | None = _guess_setup_file(sim, track)

        # Persist sidecar from session start so a hard kill still leaves
        # identifying metadata (track, sim, started_utc) on disk.
        self._write_sidecar(in_progress=True, ended_utc=None)

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
        b["last_sector_1_s"].append(frame.last_sector_1_s)
        b["last_sector_2_s"].append(frame.last_sector_2_s)
        b["slip_angle_fl_deg"].append(frame.slip_angle_fl_deg)
        b["slip_angle_fr_deg"].append(frame.slip_angle_fr_deg)
        b["slip_angle_rl_deg"].append(frame.slip_angle_rl_deg)
        b["slip_angle_rr_deg"].append(frame.slip_angle_rr_deg)
        b["abs_active"].append(frame.abs_active)
        b["tc_active"].append(frame.tc_active)
        b["raw_lap_distance_m"].append(frame.raw_lap_distance_m)
        b["path_lateral_m"].append(frame.path_lateral_m)
        b["track_edge_m"].append(frame.track_edge_m)
        b["distance_to_track_edge_m"].append(_distance_to_track_edge(frame))
        b["surface_type_fl"].append(frame.surface_type_fl)
        b["surface_type_fr"].append(frame.surface_type_fr)
        b["surface_type_rl"].append(frame.surface_type_rl)
        b["surface_type_rr"].append(frame.surface_type_rr)
        b["terrain_name_fl"].append(frame.terrain_name_fl)
        b["terrain_name_fr"].append(frame.terrain_name_fr)
        b["terrain_name_rl"].append(frame.terrain_name_rl)
        b["terrain_name_rr"].append(frame.terrain_name_rr)
        self._lap_numbers.add(frame.lap_number)
        self._last_vehicle = frame.vehicle_name

    def flush_shard(self) -> None:
        if not self._buf["session_time_s"]:
            return
        n_rows = len(self._buf["session_time_s"])
        path = self._out_dir / f"{self._stem}.part{self._shard_index}.parquet"
        table = pa.table(self._buf, schema=_SCHEMA)
        pq.write_table(table, path, compression="snappy")
        self._shard_paths.append(path)
        self._shard_index += 1
        self._row_count += n_rows
        self._buf = {f.name: [] for f in _SCHEMA}
        self._write_sidecar(in_progress=True, ended_utc=None)

    def close(self) -> tuple[Path, Path]:
        self.flush_shard()

        parquet_path = self._out_dir / f"{self._stem}.parquet"

        if self._shard_paths:
            tables = [pq.read_table(p) for p in self._shard_paths]
            final = pa.concat_tables(tables)
            pq.write_table(final, parquet_path, compression="snappy")
            for p in self._shard_paths:
                p.unlink(missing_ok=True)
            self._row_count = final.num_rows
        else:
            pq.write_table(pa.table(self._buf, schema=_SCHEMA), parquet_path, compression="snappy")
            self._row_count = 0

        self._write_sidecar(in_progress=False, ended_utc=_utc_iso())
        return parquet_path, self._sidecar_path

    def _write_sidecar(
        self,
        in_progress: bool,
        ended_utc: str | None,
        recovered: bool = False,
    ) -> None:
        sidecar: dict = {
            "schema_version": "2",
            "recorder_version": __version__,
            "started_utc": self._started_utc,
            "ended_utc": ended_utc,
            "sim": self._sim,
            "track": self._track,
            "vehicle_name": self._last_vehicle,
            "setup_file_guess": self._setup_file_guess,
            "sample_rate_hz": self._rate_hz,
            "row_count": self._row_count,
            "lap_count": len(self._lap_numbers),
            "in_progress": in_progress,
        }
        if recovered:
            sidecar["recovered"] = True
        tmp = self._sidecar_path.with_name(self._sidecar_path.name + ".tmp")
        tmp.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        os.replace(tmp, self._sidecar_path)
