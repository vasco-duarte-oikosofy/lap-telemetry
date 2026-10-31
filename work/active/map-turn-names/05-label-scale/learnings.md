# Learnings — Slice 05 (type size)

- **A ceiling tuned on a small map silently froze the type on a big one.**
  `fontMax: 8` was correct for the 250 px spike; on the compare app's 650–910 px
  panel it made the type 8 px at every window size. The measurement that proved
  it: map panel 500 → 650 → 910 px wide, label height 9.2 px and width 32.5 px
  in all three cases — identical, i.e. the clamp was binding everywhere.

- **Check scale behaviour by measuring, not by looking.** `labelH`, `labelW` and
  `ctx.measureText` on the live canvas made the bug obvious in one probe;
  eyeballing a screenshot had not.

- **"The font is too small" can be two bugs.** Here it was the ceiling; on a
  DPR-2 display a missing `ctx.scale(dpr, dpr)` looks the same. The canvas path
  already sets `setTransform(dpr, 0, 0, dpr, 0, 0)` and the planner works in CSS
  px, so only the ceiling needed fixing.

- **A threshold that counts "labels with a name" is not a coverage test.** 37 of
  the 173 packaged turns are unnamed in their coaching model, so 136/173 is
  *complete*, not 79 %. The test now reads how many turns have a name in the
  data and asserts every one of those keeps it.

- **Adjacency is scale-invariant by construction** (caps are in font sizes), so
  growing the type 65 % moved the mean apex→box gap from 6 px to 10 px while the
  rule stayed identical — that is the property that made the port cheap.

- **The halo has to scale too.** A fixed 1.6 px stroke was right for 6 px type
  and became a hairline at 13 px; it is now `max(1.4, fontSize * 0.16)`.
