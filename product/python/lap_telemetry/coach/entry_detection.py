"""Entry phase detection: throttle lift, speed peak, brake application point."""
from __future__ import annotations

from .facts import PhaseDetectionThresholds
from .track_model import Corner


def find_entry_point(
    speed: list[float],
    throttle: list[float] | None,
    brake: list[float] | None,
    corner: Corner,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
    look_back_m: float = 200.0,
) -> tuple[int, str]:
    """Find the entry phase distance for a corner.

    Scans from (s_start_m - look_back_m) toward apex using throttle
    (preferred) or speed local maximum (fallback) to find where corner
    entry begins. The look-back extends the search into the preceding
    straight, because throttle lift and braking often start well before
    the formal corner zone.

    Returns (distance_m, detection_method) where detection_method is
    'throttle_lift', 'speed_peak', or 'zone_start'.
    """
    search_start = max(0, int(corner.s_start_m - look_back_m))
    apex_idx = min(int(corner.apex_s_m), len(speed) - 1)

    if apex_idx <= search_start:
        return max(0, int(corner.s_start_m)), "zone_start"

    # --- Throttle lift (preferred) ---
    if throttle is not None:
        was_full_throttle = False
        for i in range(search_start, apex_idx + 1):
            if i >= len(throttle):
                break
            if throttle[i] >= thresholds.throttle_lift:
                was_full_throttle = True
            elif was_full_throttle:
                return i, "throttle_lift"

    # --- Speed local maximum (fallback) ---
    zone_speeds = speed[search_start:apex_idx + 1]
    if zone_speeds:
        max_val = max(zone_speeds)
        max_offset = zone_speeds.index(max_val)
        return search_start + max_offset, "speed_peak"

    return max(0, int(corner.s_start_m)), "zone_start"


def find_brake_point(
    brake: list[float] | None,
    corner: Corner,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
    look_back_m: float = 200.0,
) -> int | None:
    """Find the brake application point (secondary entry fact).

    Scans from (s_start_m - look_back_m) toward apex; returns the first
    index where brake rises above the threshold after being at or below
    it, or None.
    """
    if brake is None:
        return None

    search_start = max(0, int(corner.s_start_m - look_back_m))
    apex_idx = min(int(corner.apex_s_m), len(brake) - 1)

    was_no_brake = False
    for i in range(search_start, apex_idx + 1):
        if brake[i] <= thresholds.brake_apply:
            was_no_brake = True
        elif was_no_brake:
            return i

    return None