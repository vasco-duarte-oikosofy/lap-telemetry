# Bug 29 Learnings — Greedy matching let a curated marker steal its neighbour's event

- **The failure was order-dependent, which is why it looked random.** The
  matcher did compute distances — it just asked each corner in turn for *its*
  nearest event, so a 94 m match won purely because it was requested before a
  4 m match. Two refreshes of the same Fuji corner produced two different
  corruptions; a third would have produced another. If a data bug changes result
  when you reorder the input list, suspect greedy ownership.

- **The audit was honest and useless.** Both corruptions printed
  `WARNING: … keeps old geometry (--allow-unmatched)` and a normal-looking
  geometry table. Nothing said "a corner 94 m from an event claimed it while the
  corner 4 m away got nothing". The signal was there in the numbers, but only if
  you compared the *deltas of both* corners. When a warning can describe either a
  benign or a corrupt outcome, it is not a guard.

- **One bug, four tracks.** Replaying old vs new matching over the five reference
  laps in the repo found the same shape at Fuji (`Netz`/`Netz Hairpin`),
  Interlagos (`Ferradura 1`/`2`) and Long Beach (`Turn 3`/`4`, `Turn 10`/`11`).
  A "track-specific" bug report is usually one instance of a pattern.

- **Fix the algorithm, not the data.** Every affected model had already been
  hand-corrected after its corruption, so re-running the updater would have been
  churn with a fresh corruption risk. Checking `apex_s_m` values for duplicates
  first is what told us no data repair was needed.

- **`--preserve-geometry` was a workaround that became a preference.** Before the
  fix, preserving the marker corners was the only way to avoid the steal. After
  the fix it is only needed when you want a zone to claim nothing at all. The
  live validation ran *without* it on purpose — that is what proves the matcher
  is now deciding correctly rather than being bypassed.

- **The live test is the only test that counts.** Unit fixtures passed at 31/31
  and the synthetic table looked perfect, but the confirmation came from a real
  refresh: `Netz` frozen at 3284/3310/3310 while `Netz Hairpin` moved onto its own
  event, then the user checking the car/map. Until that happened the bug stayed
  in `work/active/bugs/` — which is the right default for anything whose fix has
  only ever run against a fixture.
