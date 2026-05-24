"""Exit phase detection: brake release, full throttle, merged exit point.

The search window extends past ``s_end_m`` by
``PhaseDetectionThresholds.exit_search_past_end_m`` (default 50 m).
This is necessary because the actual brake release and full-throttle
point often occur on the early straight, beyond the corner boundary —
especially for short corners where the apex-to-end span is only a few
metres.  Limiting the search to ``s_end_m`` would fall back to the
boundary for both driver and reference, yielding a delta of 0 and
masking the real exit-distance difference.
"""
from __future__ import annotations

from .facts import PhaseDetectionThresholds
from .track_model import Corner


def find_exit_points(
    brake: list[float] | None,
    throttle: list[float] | None,
    corner: Corner,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
) -> list[tuple[str, int]]:
    """Find exit phase distances for a corner.

    Walks forward from apex, searching up to
    ``s_end_m + exit_search_past_end_m`` (default 50 m past the corner
    boundary) using brake and throttle channels to detect brake release
    (exit_brake) and full-throttle (exit_throttle) points.

    Returns list of (phase_name, distance_m).
    When both are detected and within merge tolerance, emits a single
    "exit" at the midpoint.  When only one channel is available, emits
    "exit" at that point.  Falls back to s_end_m when neither is found.
    """
    apex_idx = max(0, int(corner.apex_s_m))
    data_len = len(brake or throttle or [])
    # Extend search past corner boundary so short corners don't miss
    # real brake release / throttle transitions on the exit straight.
    past_end = int(thresholds.exit_search_past_end_m)
    search_end = min(int(corner.s_end_m) + past_end, data_len - 1) if data_len else int(corner.s_end_m)

    exit_brake_s: int | None = None
    exit_throttle_s: int | None = None

    # --- Brake release (exit-1) ---
    if brake is not None:
        end_idx_brake = min(search_end, len(brake) - 1)
        was_braking = False
        for i in range(apex_idx, end_idx_brake + 1):
            if brake[i] > thresholds.brake_apply:
                was_braking = True
            if was_braking and brake[i] < thresholds.brake_off:
                exit_brake_s = i
                break

    # --- Full throttle (exit-2) ---
    if throttle is not None:
        end_idx_throttle = min(search_end, len(throttle) - 1)
        was_partial = False
        for i in range(apex_idx, end_idx_throttle + 1):
            if throttle[i] < thresholds.throttle_full:
                was_partial = True
            if was_partial and throttle[i] >= thresholds.throttle_full:
                exit_throttle_s = i
                break

    # Merge logic
    if exit_brake_s is not None and exit_throttle_s is not None:
        if abs(exit_brake_s - exit_throttle_s) <= thresholds.exit_merge_tolerance_m:
            mid = round((exit_brake_s + exit_throttle_s) / 2)
            return [("exit", mid)]
        return [("exit_brake", exit_brake_s), ("exit_throttle", exit_throttle_s)]

    if exit_brake_s is not None:
        return [("exit", exit_brake_s)]
    if exit_throttle_s is not None:
        return [("exit", exit_throttle_s)]

    # Neither channel detected → fall back to zone boundary
    return [("exit", int(corner.s_end_m))]