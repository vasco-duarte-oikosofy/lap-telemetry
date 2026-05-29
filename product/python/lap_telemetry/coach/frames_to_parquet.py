"""Convert a list of Frame objects to a temporary Parquet file.

This is a bridge so that ``compare_laps()`` (which reads Parquet) can be
used on live Frame data.  The temp file is written once per completed lap
(~2500 rows, ~50 KB) and should be cleaned up by the caller after
comparison.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import _SCHEMA


def frames_to_parquet(frames: list[Frame], suffix: str = ".parquet") -> Path:
    """Write a list of Frames to a temporary Parquet file.

    The file uses the same schema as ``SessionWriter`` so that
    ``compare_laps()`` can read it directly.

    Args:
        frames: List of Frame objects to write.
        suffix: File suffix for the temp file (default ``.parquet``).

    Returns:
        Path to the temporary Parquet file.  The caller is responsible
        for deleting this file when done (e.g. after ``compare_laps()``
        completes).
    """
    # Derive columns from _SCHEMA so this function never drifts when new fields
    # are added. distance_to_track_edge_m is computed rather than read directly.
    columns = {
        field.name: (
            [_distance_to_track_edge(f) for f in frames]
            if field.name == "distance_to_track_edge_m"
            else [getattr(f, field.name) for f in frames]
        )
        for field in _SCHEMA
    }

    table = pa.table(columns, schema=_SCHEMA)

    # Write to a temp file.
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix, prefix="coach_lap_", delete=False,
    )
    tmp_path = Path(tmp.name)
    tmp.close()
    pq.write_table(table, tmp_path, compression="snappy")
    return tmp_path


def _distance_to_track_edge(frame: Frame) -> float | None:
    if frame.track_edge_m is None or frame.path_lateral_m is None:
        return None
    return frame.track_edge_m - abs(frame.path_lateral_m)