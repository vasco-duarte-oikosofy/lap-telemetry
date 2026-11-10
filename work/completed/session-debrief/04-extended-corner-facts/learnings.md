# Learnings — Slice 04: extended corner facts

- **The slip channels are not slip angles.** `slip_angle_rl_deg` /
  `slip_angle_rr_deg` span ±180° with a median near ±140°, small
  sample-to-sample changes and occasional 360° wraps. Their magnitude
  correlates 0.04 with turn rate, and is *lower* under hard braking (0.03) than
  at constant throttle (0.11) — the opposite of a slip ratio too. Whatever the
  recorder is storing under that name, a slip angle is bounded to a few
  degrees, so the honest answer is `null` with the reason. The module refuses
  any "slip" channel whose maximum exceeds 60°.
- **A flag channel can be silently dead.** `abs_active` is null on every row of
  both fixtures; `tc_active` is null on 97% of the reference's rows (only the
  `true` samples were written, an older recorder version) and dense in the
  session. Duty over null-as-false would have said "ABS 0%" and "TC 0%" with
  total confidence. The gate is now: fewer than half the samples recorded, or
  never true in the session, means unmeasurable — never 0%.
- **Braking for a corner starts before the corner.** Measuring `brake_peak`
  over the model's `[s_start_m, s_end_m]` gave 0.23 for a hairpin whose real
  peak is 0.9, because the pedal is already mostly released by the corner zone.
  The window has to be the detected entry → apex.
- **Trail-braking depth needs "first release", not "last braking sample".**
  With a far bound, Village reported 220 m of trail braking: the driver had
  released at the apex and was braking for la Tour, the *next* corner. The rule
  is the first release after the apex, bounded by exit, corner end and the next
  corner's start. A corner with no pressure before the apex has no trail to
  measure (`null`, not 0).
- **Gear is 0 mid-shift.** One lap lost `gear_at_apex` because the downshift
  landed exactly on the apex. The nearest *engaged* gear within 20 m is both
  more useful and more honest than refusing the fact.
- **Chained corners share a braking zone.** Beausset 1 and 2 are one braking
  event split by the model: the entry floor (the previous corner's end) means
  Beausset 2's `brake_peak` only sees residual pressure. The number is not wrong
  for the window it claims, but slice 05 must not read "0.23 at the hairpin" as
  "you barely braked".
- **The reference never needs its own comparison.** Every driver comparison
  already reports the reference's entry, apex and exit distances, so the
  reference windows are the medians of those — no second run, no extra Node
  process.
- **The payload grows fast.** 9 corners × 18 laps of channel facts took the JSON
  from 151 KB to 338 KB. That is still fine for a file, and it is why the
  conversation must never receive the whole thing (slice 07's 2–4 KB report).
