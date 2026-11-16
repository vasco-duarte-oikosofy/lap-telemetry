"""Session discovery for the `/update_coach` skill.

Given a loose description of a recording (track text, car text, a time window),
find the `session_*.parquet` files it refers to, collapse them to ONE
(track, car) combo, and compare that combo's fastest complete lap with the
reference lap already on disk.

Nothing here writes anything. It answers a question; the caller decides.

Lap selection reuses the guarded exporter's `find_complete_laps`
(segment-based, authoritative timing, abandoned-lap and wall-clock guards) so
this check can never disagree with the exporter about "the fastest lap".
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHARD_RE = re.compile(r"\.part\d+$")
SNAP_RE = re.compile(r"\.snap\d+$")
STAMP_RE = re.compile(r"^session_(\d{8}T\d{6}Z)_")


# ── Environment ──────────────────────────────────────────────────────────────

def repo_root() -> Path:
    """Climb from this file to the checkout that owns the curated data."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "product/data/reference-laps").is_dir() and (parent / "dev/scripts").is_dir():
            return parent
    raise SystemExit("ERROR: cannot locate the lap-telemetry repo root from this script")


def load_guarded_export(root: Path):
    """Import dev/scripts/export_fastest_reference_laps.py without running it."""
    for extra in (root / "product/python", root / "dev/scripts"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    spec = importlib.util.spec_from_file_location(
        "_guarded_export", root / "dev/scripts/export_fastest_reference_laps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_car_slug(vehicle_name: str) -> str | None:
    """Catalog slug for a vehicle (bug 27 Step 0), or None when not catalogued."""
    try:
        from lap_telemetry.coach.car_catalog import canonical_car_slug as lookup
        return lookup(vehicle_name)
    except Exception:
        return None


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in ascii_text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


# ── Discovery ────────────────────────────────────────────────────────────────

def read_sidecar(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def started_at(stem: str, files: list[Path], sidecar: dict) -> datetime:
    """Sidecar start time, else the filename stamp, else the oldest mtime."""
    iso = sidecar.get("started_utc")
    if isinstance(iso, str):
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            pass
    match = STAMP_RE.match(stem)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.fromtimestamp(min(f.stat().st_mtime for f in files), tz=timezone.utc)


def recording(stem: str, files: list[Path], sidecar: dict | None = None) -> dict:
    """One recording: its shard files plus the identity read from the sidecar.

    The sidecar is named after the recording, never after a shard, so the stem
    (not the first file) is what locates it.
    """
    if sidecar is None:
        sidecar = read_sidecar(files[0].parent / f"{stem}.json")
    return {
        "stem": stem,
        "files": files,
        "started": started_at(stem, files, sidecar),
        "track_text": str(sidecar.get("track") or ""),
        "vehicle_name": str(sidecar.get("vehicle_name") or ""),
    }


def explicit_recording(files: list[Path]) -> dict:
    """A recording named directly on the command line (shards grouped by stem)."""
    return recording(SHARD_RE.sub("", files[0].stem), files)


def collect_sessions(sessions_dir: Path) -> list[dict]:
    """Every recording in the directory; `.partN` shards of one stay together."""
    groups: dict[str, list[Path]] = {}
    for path in sorted(sessions_dir.glob("session_*.parquet")):
        if SNAP_RE.search(path.stem):
            continue  # per-lap snapshots are not sessions
        groups.setdefault(SHARD_RE.sub("", path.stem), []).append(path)
    return [recording(stem, files) for stem, files in groups.items()]


def matches_query(session: dict, track_query: str | None, car_query: str | None) -> bool:
    """Fuzzy, order-independent match on the track and/or car description."""
    if track_query:
        needle = slugify(track_query)
        if not any(needle in slugify(text) for text in (session["track_text"], session["stem"])):
            return False
    if car_query:
        needle = slugify(car_query)
        vehicle = slugify(session["vehicle_name"])
        catalog = slugify(canonical_car_slug(session["vehicle_name"]) or "")
        if not (needle in vehicle or needle in catalog):
            return False
    return True


def within_window(sessions: list[dict], window: timedelta | None,
                  now: datetime | None = None) -> list[dict]:
    if window is None:
        return sessions
    now = now or datetime.now(timezone.utc)
    return [s for s in sessions if now - s["started"] <= window]


# ── Verdict inputs ───────────────────────────────────────────────────────────

def fastest_lap(sessions: list[dict], guarded, min_lap_time_s: float):
    """(lap_number, time_s, recording_name) for the fastest complete lap, or None.

    Shards of one recording are read together so a lap straddling a shard
    boundary is still one contiguous segment.
    """
    import pyarrow.parquet as pq

    best = None
    for session in sessions:
        try:
            table = pq.read_table([str(f) for f in session["files"]])
        except Exception as exc:  # corrupt / half-written shard
            print(f"  SKIP unreadable {session['stem']}: {exc}", file=sys.stderr)
            continue
        for lap_num, lap_time, _start, _end in guarded.find_complete_laps(table, min_lap_time_s):
            if best is None or lap_time < best[1]:
                best = (lap_num, lap_time, f"{session['stem']}.parquet")
    return best


def current_reference(refs_dir: Path, track_slug: str, vehicle_slug: str, guarded):
    """Fastest existing reference for this exact (track, vehicle) slug, or None."""
    refs = []
    for path in sorted(refs_dir.glob(f"{track_slug}_{vehicle_slug}_time_*.parquet")):
        lap_time = guarded.parse_lap_time_from_name(path)
        if lap_time is not None:
            refs.append((path, lap_time))
    return min(refs, key=lambda item: item[1]) if refs else None
