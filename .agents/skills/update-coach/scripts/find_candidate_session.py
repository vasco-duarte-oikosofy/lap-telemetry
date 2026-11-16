#!/usr/bin/env python3
"""Resolve "the session I just ran" to ONE (track, car) combo and answer one question:

    is its fastest complete lap faster than the reference already on disk?

This is the gate for the `/update_coach` skill: the reference lap and the
coaching model are refreshed **if and only if** the answer is yes. The gate is
decided here, by numbers, not by whoever is driving the shell.

Exit codes (the verdict is the exit code):
    0  PROCEED  — FASTER, or NO_REFERENCE (first reference for this combo)
    3  STOP     — NOT_FASTER: keep the current reference, change nothing
    2  ASK      — NO_SESSION / AMBIGUOUS / NO_LAPS: stop and ask the user

Usage:
    python find_candidate_session.py --sessions-dir sessions --car Ginetta --track Barcelona --within 2h
    python find_candidate_session.py --sessions-dir sessions --session sessions/session_20261114T064918Z_*.parquet
    python find_candidate_session.py --sessions-dir sessions --car DKR --within 90m --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_lookup as lookup  # noqa: E402

# Same 1 ms margin as the updater: an equal lap is NOT faster (idempotence).
FASTER_MARGIN_S = 0.001

PROCEED, ASK, STOP = 0, 2, 3


def parse_within(text: str):
    import re
    from datetime import timedelta

    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd])", text.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError(f"bad --within {text!r}: use e.g. 90m, 2h, 1d")
    value, unit = float(match.group(1)), match.group(2)
    return timedelta(seconds=value * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions-dir", type=Path, default=Path("sessions"),
                        help="directory holding session_*.parquet + .json sidecars")
    parser.add_argument("--track", help="circuit name or slug (any spelling)")
    parser.add_argument("--car", help="vehicle name, livery, brand or catalog slug")
    parser.add_argument("--within", type=parse_within, default=None,
                        help="only sessions started this recently, e.g. 90m, 2h, 1d")
    parser.add_argument("--since", type=datetime.fromisoformat, default=None,
                        help="only sessions started at/after this ISO 8601 instant")
    parser.add_argument("--session", type=Path, nargs="+", default=None,
                        help="explicit session file(s); skips discovery")
    parser.add_argument("--refs-dir", type=Path, default=None,
                        help="reference-lap directory (default: product/data/reference-laps)")
    parser.add_argument("--min-lap-time-s", type=float, default=None,
                        help="forwarded to the exporter's lap guard (short circuits)")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    return parser


def resolve_window(args, sessions_dir: Path) -> tuple[list[dict], object]:
    """Candidate recordings + the age window applied (None when unbounded)."""
    if args.session:
        return [lookup.explicit_recording(list(args.session))], None
    window = args.within
    if args.since is not None:
        since = args.since if args.since.tzinfo else args.since.replace(tzinfo=timezone.utc)
        relative = datetime.now(timezone.utc) - since
        window = max(filter(None, [window, relative]), key=lambda d: d.total_seconds())
    sessions = [s for s in lookup.collect_sessions(sessions_dir)
                if lookup.matches_query(s, args.track, args.car)]
    return lookup.within_window(sessions, window), window


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (args.session or args.track or args.car):
        print("ERROR: give --session, or --track and/or --car to find it.", file=sys.stderr)
        return ASK
    missing = [p for p in (args.session or []) if not p.exists()]
    if missing:
        print(f"ERROR: missing session file(s): {[p.name for p in missing]}", file=sys.stderr)
        return ASK
    if not args.session and not args.sessions_dir.is_dir():
        print(f"ERROR: no sessions directory at {args.sessions_dir}", file=sys.stderr)
        return ASK

    root = lookup.repo_root()
    guarded = lookup.load_guarded_export(root)
    refs_dir = args.refs_dir or (root / "product/data/reference-laps")
    min_lap = args.min_lap_time_s if args.min_lap_time_s is not None else guarded.MIN_LAP_TIME_S

    sessions, _window = resolve_window(args, args.sessions_dir)
    if not sessions:
        print("VERDICT: NO_SESSION — nothing recorded matches that description.", file=sys.stderr)
        return ASK
    for session in sorted(sessions, key=lambda s: s["started"]):
        print(f"  candidate {session['started']:%Y-%m-%d %H:%M:%SZ}  {session['stem']}"
              f"  [{session['track_text'] or '?'} / {session['vehicle_name'] or '?'}]")

    combos = {(guarded.track_slug_from_path(Path(f"{s['stem']}.parquet")),
               guarded.vehicle_slug(s["vehicle_name"])) for s in sessions}
    if len(combos) > 1:
        print(f"\nVERDICT: AMBIGUOUS — candidates span {len(combos)} combos: "
              f"{sorted(combos)}. Ask which one, then narrow with --car/--track.",
              file=sys.stderr)
        return ASK
    track_slug, vehicle_slug = combos.pop()
    if not vehicle_slug:
        print("VERDICT: AMBIGUOUS — no vehicle_name in the sidecar; cannot tell the car.",
              file=sys.stderr)
        return ASK

    best = lookup.fastest_lap(sessions, guarded, min_lap)
    reference = lookup.current_reference(refs_dir, track_slug, vehicle_slug, guarded)
    model_path = root / f"product/data/track-coaching/{track_slug}_{vehicle_slug}.json"
    vehicle_name = next(s["vehicle_name"] for s in sessions if s["vehicle_name"])
    catalog_slug = lookup.canonical_car_slug(vehicle_name)

    print(f"\nCombo:     {track_slug} / {vehicle_slug}"
          f"  (catalog: {catalog_slug or 'MISSING - add to product/data/vehicle_catalog.json'})")
    if best is None:
        print(f"VERDICT: NO_LAPS — no complete lap above {min_lap:g}s in these sessions.",
              file=sys.stderr)
        return ASK
    lap_num, lap_time, lap_name = best
    print(f"Fastest:   lap {lap_num} @ {lap_time:.3f}s  ({lap_name})")
    print("Reference: " + (f"{reference[0].name} @ {reference[1]:.3f}s" if reference
                          else "none on disk for this combo"))
    print(f"Model:     {model_path.name} "
          f"({'exists -> pipeline B' if model_path.exists() else 'absent -> pipeline A'})")

    if reference is None:
        verdict, code = "NO_REFERENCE", PROCEED
        print("VERDICT: NO_REFERENCE — first reference for this combo; export it.")
    elif lap_time < reference[1] - FASTER_MARGIN_S:
        verdict, code = "FASTER", PROCEED
        print(f"VERDICT: FASTER — {reference[1] - lap_time:.3f}s quicker "
              f"({reference[1]:.3f}s -> {lap_time:.3f}s). Update reference + model.")
    else:
        verdict, code = "NOT_FASTER", STOP
        print(f"VERDICT: NOT_FASTER — {lap_time - reference[1]:+.3f}s vs {reference[1]:.3f}s. "
              "Keep the current reference; change nothing.")

    if args.json:
        print(json.dumps({
            "verdict": verdict,
            "track": track_slug,
            "vehicle_slug": vehicle_slug,
            "vehicle_name": vehicle_name,
            "catalog_slug": catalog_slug,
            "sessions": [str(f) for s in sessions for f in s["files"]],
            "fastest": {"lap": lap_num, "time_s": round(lap_time, 3), "recording": lap_name},
            "reference": None if reference is None else {
                "path": str(reference[0]), "time_s": round(reference[1], 3)},
            "coaching_model": {"path": str(model_path), "exists": model_path.exists()},
            "pipeline": "B" if model_path.exists() else "A",
        }, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
