# Learnings — Slice 05 (Paul Ricard ELMS at 400 px)

- **A preview that measures with the wrong font is worse than no preview.** The
  widget draws in Consolas Bold with a 0.085 em halo reserve; the preview used the
  page font. Labels came out ~30 % narrower, so a layout that looked clear at
  400 px overlapped by up to 25 px in the widget. Anyone tuning against a
  misleading preview will "fix" the wrong thing — copy the consumer's font, weight
  and stroke exactly.

- **"Honour the placement" needs a third option between honour and replace.**
  Rejecting a colliding placement threw away the driver's side and distance; the
  fan then placed it wherever the rule liked. Stretching the offset along its own
  direction (×1.0 → ×2.4) keeps the intent and resolves the collision: median
  stretch stayed 1.00 with only 2–3 labels moving more than 15 %.

- **A test harness that skips one widget argument lies quietly.** `support.plan_for`
  did not pass `units_per_metre`, which the widget does, so the sibling tests were
  validating a placement conversion 1.3 % off — invisible at 600 px, enough to
  change which labels collide at 400 px. Mirror the production call path exactly,
  or the "same code" claim is only nearly true.

- **Beware throwaway probes that re-implement the path**: mine reported 15/16
  labels at 400 px while the real harness reported 16/16, because it never ran a
  draw pass that sets the label font's pixel size. When a probe and the test
  disagree, trust the one that calls the production functions.
