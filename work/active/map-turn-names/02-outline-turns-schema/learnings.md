# Learnings — Slice 02 (`turns` block + preservation guard)

- **The guard has to be behavioural *and* static.** A behavioural test (write an
  outline, regenerate, assert `turns` survived) needs a real writer invocation
  with fixtures per script, which is expensive. The static half is cheap and
  catches the real failure mode — a writer that forgets the helper — so the test
   asserts each writer `require`s `lib/outlineTurns` **and** that no writer still
  contains a bare `JSON.stringify(outline, null, 2)`.

- **`average_trajectory_outline.py` had to be patched twice.** The first attempt
  replaced a write block that looked identical but was not (the file indents the
  `with open(...)` block differently), so the call silently never landed. The
  static test caught it immediately — that is exactly the class of bug the guard
  exists for.

- **Most coaching models cannot be trusted as a turn list.** Of 22 outlines,
  only 14 have a model with at least one curated name; the rest are placeholder
  models, and several are over-segmented far beyond the real turn count
  (Spa 69 corners, Lusail 16, COTA 14, Bahrain 13, full Monza 6 when Monza has
  11). Baking those would have produced confidently wrong numbers on the map,
  so the bake refuses them and reports why.

- **One track can have several models with different corner counts** (Daytona
  12 vs 6, Barcelona 16/12/14, Bahrain Outer 6/11). Ranking by "most curated
  names, then most corners, then filename" gave the right answer on all of them
  and stays deterministic; a genuine name disagreement between the two best
  models is printed so a human can decide rather than being silently averaged.

- **`turn N` is not always a placeholder.** Road Atlanta's curated model names
  turns "Turn 1", "Turn 4 (The Esses)" — the official naming convention there.
  The bake treats a bare `turn N` as unnamed (labels render `T<n>`), which reads
  the same on the map and avoids "T1 Turn 1".
