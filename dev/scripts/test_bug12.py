"""Tests for bug 12: partial-lap data produces bogus coaching.

Two scenarios:
  A. Tail-partial shard — the 30-second flush timer fires mid-lap so the shard
     seen by the coach only contains the second half of the lap.
  B. Head-partial lap — the session ended while the lap was in progress so
     only the first portion of the lap exists in the file.

Fixes required:
  1. lap_comparator.compare_laps() must raise PartialLapError for both cases.
  2. record.run() must call writer.flush_shard() at every lap boundary so the
     shard handed to the coach always contains a complete lap.
  3. live_fact_generator.generate_from_parquet() must catch PartialLapError
     and return None instead of propagating a bogus utterance.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from lap_telemetry.coach.facts import PartialLapError
from lap_telemetry.coach.lap_comparator import compare_laps
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import _SCHEMA

_ROOT = Path(__file__).parents[2]
_SESSIONS = _ROOT / "dev" / "sessions"
_SESSION_FILE = _SESSIONS / "session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet"
_REF_FILE = _SESSIONS / "reference_lap_session_20260529T092852Z_bahrain-outer-circuit_lmu_seg7.parquet"
_TRACK_MODEL_FILE = _ROOT / "product/data/track-coaching/bahrain-outer-circuit_dkr-engineering-4-elms25.json"

_NEEDS_SESSION = pytest.mark.skipif(
    not _SESSION_FILE.exists() or not _REF_FILE.exists() or not _TRACK_MODEL_FILE.exists(),
    reason="Bahrain session/reference/model fixtures not present",
)


def _load_track_model():
    return load_track_coaching_model(_TRACK_MODEL_FILE)


def _make_frame(**overrides) -> Frame:
    """Minimal recordable frame for synthetic tests."""
    defaults = dict(
        sim="lmu",
        session_time_s=0.0,
        lap_number=1,
        lap_distance_m=100.0,
        lap_time_s=10.0,
        speed_kph=150.0,
        throttle_norm=0.8,
        brake_norm=0.0,
        steering_norm=0.0,
        gear=4,
        engine_rpm=8000.0,
        lap_valid=True,
        pos_x_m=0.0,
        pos_y_m=0.0,
        pos_z_m=0.0,
        last_sector_1_s=math.nan,
        last_sector_2_s=math.nan,
        slip_angle_fl_deg=0.0,
        slip_angle_fr_deg=0.0,
        slip_angle_rl_deg=0.0,
        slip_angle_rr_deg=0.0,
        abs_active=None,
        tc_active=None,
        in_realtime=True,
        paused=False,
        track_name="bahrain-outer-circuit",
        vehicle_name="dkr-engineering-4",
        player_scor_index=0,
        scoring_lap_start_et_s=0.0,
        scoring_last_lap_time_s=None,
        scoring_time_into_lap_s=10.0,
        scoring_total_laps=1,
    )
    defaults.update(overrides)
    return Frame(**defaults)


# ---------------------------------------------------------------------------
# Scenario A — tail-partial shard
# ---------------------------------------------------------------------------

@_NEEDS_SESSION
def test_tail_partial_raises_partial_lap_error(tmp_path):
    """compare_laps must raise PartialLapError when given only the tail of a lap.

    This reproduces the shard-cut scenario: the 30-second flush timer fires
    while lap 4 is in progress, so the shard written at the next lap boundary
    only contains frames from ~30s onward (dist≈1500m..3510m). The bug caused
    a phantom 14-second gain at turn 1 because bins 0–1499m were clamped to the
    start-of-shard speed.
    """
    session = pq.read_table(_SESSION_FILE)

    # Isolate lap 4 (a full ~79s lap)
    lap_numbers = session.column("lap_number").to_pylist()
    lap_times = session.column("lap_time_s").to_pylist()
    mask_lap4 = [ln == 4 for ln in lap_numbers]
    lap4 = session.filter(mask_lap4)

    # Simulate the shard cut: keep only frames from lap_time_s >= 30s
    lt = lap4.column("lap_time_s").to_pylist()
    tail_mask = [t >= 30.0 for t in lt]
    tail_shard = lap4.filter(tail_mask)

    # Write the tail-only shard to a temp parquet
    shard_path = tmp_path / "tail_shard.parquet"
    pq.write_table(tail_shard, shard_path)

    model = _load_track_model()
    with pytest.raises(PartialLapError, match="tail-partial|starts"):
        compare_laps(shard_path, _REF_FILE, model)


# ---------------------------------------------------------------------------
# Scenario B — head-partial lap
# ---------------------------------------------------------------------------

@_NEEDS_SESSION
def test_head_partial_raises_partial_lap_error():
    """compare_laps must raise PartialLapError when the lap ends mid-track.

    Lap 8 of the bahrain session was aborted at ~1059m (turn 4 is at 2038m).
    One stale cross-lap frame carries dist=3510m, lap_time=-0.16s from the end
    of lap 7. After stripping that frame the real coverage is 0..1059m, well
    below the 80% threshold (2808m). The bug caused a phantom 15-second gain
    at turn 4 because bins 1060–3510 were filled with the frozen speed.
    """
    model = _load_track_model()
    with pytest.raises(PartialLapError, match="head-partial|ends"):
        compare_laps(_SESSION_FILE, _REF_FILE, model, lap_number=8)


# ---------------------------------------------------------------------------
# Sanity — a full lap must not be affected
# ---------------------------------------------------------------------------

@_NEEDS_SESSION
def test_full_lap_unaffected():
    """A complete lap must produce valid coaching with no bogus 14-second gains.

    Lap 5 is a full ~72s clean lap. All per-corner |loss_s| must be < 3s.
    """
    model = _load_track_model()
    facts = compare_laps(_SESSION_FILE, _REF_FILE, model, lap_number=5)
    all_corners = facts.top_losses + facts.top_gains
    assert all_corners, "compare_laps returned no corner facts for a full lap"
    worst = max(abs(c.loss_s) for c in all_corners)
    assert worst < 3.0, (
        f"Implausible corner delta {worst:.2f}s on a full lap — "
        "partial-lap guard may have over-fired or introduced a regression."
    )


# ---------------------------------------------------------------------------
# Record.py — flush at lap boundary
# ---------------------------------------------------------------------------

def test_lap_boundary_flush(tmp_path, monkeypatch):
    """record.run() must call writer.flush_shard() at every lap boundary.

    Without the fix the writer only flushes on the 30-second timer, so a shard
    that spans a lap boundary contains frames from two laps. With the fix the
    writer is flushed before the lap counter advances, so the shard written at
    the boundary contains only the completed lap's frames.
    """
    import lap_telemetry.recorder.record as record_mod
    from lap_telemetry.recorder.writer import SessionWriter

    # ---- spy on flush_shard: record which lap_numbers were in the buffer ----
    flush_snapshots: list[set[int]] = []
    original_flush = SessionWriter.flush_shard

    def spy_flush(self: SessionWriter) -> None:
        if self._buf["lap_number"]:
            flush_snapshots.append(set(self._buf["lap_number"]))
        original_flush(self)

    monkeypatch.setattr(SessionWriter, "flush_shard", spy_flush)

    # ---- build synthetic frames: 50 on lap 1, then 10 on lap 2 ----
    lap1_frames = [
        _make_frame(lap_number=1, session_time_s=float(i), lap_distance_m=float(i * 60))
        for i in range(50)
    ]
    lap2_frames = [
        _make_frame(lap_number=2, session_time_s=float(50 + i), lap_distance_m=float(i * 60))
        for i in range(10)
    ]
    all_frames = lap1_frames + lap2_frames
    idx = [0]

    # ---- mock connection that yields frames then raises SystemExit ----
    mock_conn = MagicMock()
    mock_conn.sim = "lmu"
    mock_conn.update.return_value = None
    mock_conn.stop.return_value = None

    def read_frame():
        if idx[0] < len(all_frames):
            f = all_frames[idx[0]]
            idx[0] += 1
            return f
        raise SystemExit(0)

    mock_conn.read_frame.side_effect = read_frame

    monkeypatch.setattr(
        record_mod, "probe_and_connect", lambda **kwargs: mock_conn
    )

    # Freeze monotonic so the 30-second timer never fires during the test
    monkeypatch.setattr(record_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(record_mod.time, "monotonic", lambda: 1_000.0)

    with pytest.raises(SystemExit):
        record_mod.run(out_dir=tmp_path, probe_timeout_s=3.0)

    # The flush triggered at the lap-1 → lap-2 boundary must be a lap-1-only shard.
    # Without the fix only the final close() flush fires, which contains both laps.
    boundary_flush_lap1_only = any(s == {1} for s in flush_snapshots)
    assert boundary_flush_lap1_only, (
        "Expected a flush containing only lap-1 frames at the lap boundary, "
        f"but flush_snapshots={flush_snapshots}. "
        "Add writer.flush_shard() in record.py at the lap-number change."
    )
