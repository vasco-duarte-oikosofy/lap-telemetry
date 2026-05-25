# Bug 04: LLM tells driver to "slow down" when driver apex speed is higher than reference

## Observed

```
Lost three seconds in turn 2, minimum speed 199 versus 111 kilometres per hour. Slow down much more for this corner.
```

## Root cause

The `CornerLoss` JSON gives raw `driver_value` and `reference_value` but the prompt doesn't explain the relationship. When `driver_value > reference_value` for `minimum_speed`, the driver was actually going *faster* through the apex — yet the LLM inverts the advice. The time loss likely comes from a different source (late braking, running wide) not from going too fast at minimum speed.

## Fix plan

Add a rule to `SYSTEM_PROMPT_TEMPLATE` explaining:

> "For minimum_speed: driver_value is the driver's apex speed, reference_value is the reference. If driver_value > reference_value, the driver is carrying MORE speed, not less — do NOT say slow down. Time loss from this entry likely comes from late braking or running wide."

Also add a rule for entry/exit phases:

> "Positive loss_s always means the driver was slower overall in this phase."

## Files

- `product/python/lap_telemetry/coach/prompt_templates.py`

## Status

📋 Open — needs fix in next slice
