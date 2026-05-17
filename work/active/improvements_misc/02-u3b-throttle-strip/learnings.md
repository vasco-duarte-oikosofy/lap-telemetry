# Learnings — U3b Throttle TC strip removal

- The Throttle panel's TC activity strip was redundant because TC has its own dedicated panel. The Brake panel's ABS activity strip should remain because there is no dedicated ABS panel.
- This is a pure removal — no downstream code depends on the presence of `activityStrip` in the panel definition. The renderer handles panels with or without activity strips.
- No test changes were required because existing tests do not assert the presence of activity strips. If visual regression tests are added later, they should verify that the Throttle panel no longer has the TC strip.
