"""Speech window checker — determines safe-speech zones on track.

Decides whether it is currently safe to speak based on the car's position
relative to corner zones and straight zones. A speech window is:

1. Inside a defined ``StraightZone``, OR
2. Outside all corners AND at least ``MIN_STRAIGHT_AHEAD_M`` (default 50 m)
   before the next corner's entry.

If the track model has ``straight_zones``, those are used directly.
Otherwise, zones are inferred from gaps between corners.
"""
from __future__ import annotations

from lap_telemetry.coach.track_model import TrackCoachingModel

# Minimum distance to next corner entry for speech to be safe.
MIN_STRAIGHT_AHEAD_M = 50.0


def is_speech_window(
    distance_m: float,
    model: TrackCoachingModel,
    min_straight_ahead_m: float = MIN_STRAIGHT_AHEAD_M,
) -> bool:
    """Check if the car is in a safe speech window at the given distance.

    Args:
        distance_m: Current lap distance in metres.
        model: Track coaching model with corners and straight zones.
        min_straight_ahead_m: Minimum metres to next corner entry for safety.

    Returns:
        True if speech is safe (not in a corner, enough distance to next).
    """
    # Must not be inside a corner
    if model.get_corner_at(distance_m) is not None:
        return False

    # If the model defines straight_zones, use them directly
    if model.straight_zones:
        if model.get_straight_at(distance_m) is not None:
            # Also check distance to next corner
            next_corner_dist = _next_corner_distance(distance_m, model)
            if next_corner_dist is not None and next_corner_dist < min_straight_ahead_m:
                return False
            return True
        # In a gap that's not a defined straight zone
        return False

    # No straight_zones defined — infer from gaps between corners
    return _is_inferred_speech_window(distance_m, model, min_straight_ahead_m)


def _next_corner_distance(distance_m: float, model: TrackCoachingModel) -> float | None:
    """Find the distance from current position to the next corner's s_start_m.

    Returns None if no corner is ahead within the lap length.
    """
    candidates = [
        c.s_start_m - distance_m
        for c in model.corners
        if c.s_start_m > distance_m
    ]
    if candidates:
        return min(candidates)
    return None


def _is_inferred_speech_window(
    distance_m: float,
    model: TrackCoachingModel,
    min_straight_ahead_m: float,
) -> bool:
    """Infer speech windows from gaps between corners.

    A distance is in an inferred speech window if:
    - It's not inside any corner
    - The next corner's entry is at least min_straight_ahead_m ahead
    """
    # Already checked: not inside a corner
    next_dist = _next_corner_distance(distance_m, model)
    if next_dist is not None and next_dist < min_straight_ahead_m:
        return False
    if next_dist is None:
        # No corners ahead (end of lap) — safe to speak
        return True
    return True