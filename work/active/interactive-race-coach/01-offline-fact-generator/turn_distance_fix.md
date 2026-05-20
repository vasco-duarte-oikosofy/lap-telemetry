# Fix: Add Apex Distance to Coaching Output

## Problem

The coaching output JSON shows corner losses but doesn't indicate **where** on the track each corner is located. This makes it hard for the driver to quickly identify which corner is being referenced, especially on tracks with many similar turns.

**Current output:**
```json
{
  "corner_id": "t8",
  "corner_name": "turn 8",
  "phase": "entry",
  "loss_s": 0.12,
  ...
}
```

**Desired output:**
```json
{
  "corner_id": "t8",
  "corner_name": "turn 8",
  "apex_distance_m": 3430.0,
  "phase": "entry",
  "loss_s": 0.12,
  ...
}
```

## Acceptance Criteria

1. **`CornerLoss` dataclass** includes `apex_distance_m: float` field
2. **`compare_laps()`** populates `apex_distance_m` from the track model's `corner.apex_s_m`
3. **`LapComparisonFacts.to_dict()`** serializes `apex_distance_m` in the output JSON
4. **Output JSON** shows `apex_distance_m` immediately after `corner_name`
5. **All existing tests pass** — no breaking changes to test assertions
6. **Demo script output** shows apex distance for each corner loss

## Implementation Steps

### 1. Update `CornerLoss` dataclass

File: `product/python/lap_telemetry/coach/lap_comparator.py`

```python
@dataclass
class CornerLoss:
    """Loss/gain analysis for a single corner."""
    corner_id: str
    corner_name: str
    apex_distance_m: float  # NEW FIELD
    phase: str
    loss_s: float
    driver_value: float
    reference_value: float
    unit: str
    confidence: str
```

### 2. Update `compare_laps()` to populate apex distance

File: `product/python/lap_telemetry/coach/lap_comparator.py`

In the corner analysis loop, pass `corner.apex_s_m` to `CornerLoss`:

```python
corner_losses.append(CornerLoss(
    corner_id=corner.id,
    corner_name=corner.name,
    apex_distance_m=corner.apex_s_m,  # NEW
    phase="minimum_speed",
    loss_s=speed_delta / 100.0,
    driver_value=driver_min,
    reference_value=ref_min,
    unit="km/h",
    confidence="high" if speed_delta > 2.0 else "medium",
))
```

Do this for all three phases (minimum_speed, entry, exit).

### 3. Update `to_dict()` serialization

File: `product/python/lap_telemetry/coach/lap_comparator.py`

```python
"top_losses": [
    {
        "corner_id": c.corner_id,
        "corner_name": c.corner_name,
        "apex_distance_m": c.apex_distance_m,  # NEW
        "phase": c.phase,
        ...
    }
]
```

### 4. Run tests

```bash
bash scripts/test-summary.sh dev/scripts/test_coach_lap_comparison.js
bash scripts/test-summary.sh
```

### 5. Verify demo output

```bash
cd product/python
python3 demo_coach_slice01.py
```

Expected output includes `"apex_distance_m": 3430.0` for turn 8.

## Example Output After Fix

```json
{
  "type": "lap_coaching_summary",
  "track_id": "circuit-de-barcelona",
  "lap_number": 15,
  "lap_time_delta_s": 1.155,
  "top_losses": [
    {
      "corner_id": "t8",
      "corner_name": "turn 8",
      "apex_distance_m": 3430.0,
      "phase": "entry",
      "loss_s": 0.12,
      "driver_value": 176.7,
      "reference_value": 188.7,
      "unit": "km/h",
      "confidence": "medium"
    },
    {
      "corner_id": "t14",
      "corner_name": "turn 14",
      "apex_distance_m": 4280.0,
      "phase": "entry",
      "loss_s": 0.08,
      "driver_value": 194.8,
      "reference_value": 202.8,
      "unit": "km/h",
      "confidence": "medium"
    }
  ],
  "top_gains": [],
  "constraints": {
    "max_words": 35,
    "style": "calm_concise_engineer"
  }
}
```

## Why This Matters

1. **Driver clarity** — "Turn 8 at 3.4km" is more actionable than just "Turn 8"
2. **Map correlation** — Drivers can find the apex distance on their track map
3. **Future features** — Apex distance enables distance-based coaching zones (e.g., "300m before turn 8 apex")
4. **Debugging** — Easier to verify corner model accuracy when apex is visible in output

## Non-Goals

- Don't change the corner model schema
- Don't add start/end distances (only apex for now)
- Don't modify the LLM prompt contract (that's slice 03)

## Definition of Done

- [ ] `CornerLoss` has `apex_distance_m` field
- [ ] `compare_laps()` populates it from track model
- [ ] `to_dict()` serializes it
- [ ] Demo output shows apex distance
- [ ] All tests pass
- [ ] Commit message explains the change
