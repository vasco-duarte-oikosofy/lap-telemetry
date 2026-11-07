# Learnings — Slice 47 (fixing bug 29)

- **The bug was one `for` loop, but its blast radius was eight corners on five
  real tracks.** Running the old and new algorithms side by side on the
  committed reference laps (`matching_before_after.py`) found the same failure
  at Fuji, Interlagos and Long Beach — pairs where a curated marker is listed
  just before the corner that actually brakes. It was never a Fuji quirk; Fuji
  was just where it got noticed.

- **"Nearest first" must be global, not per-corner.** The old code did ask for
  distance — `nearest()` — but asked it *sequentially*, so a 94 m match could
  win simply by being requested before a 4 m match. Sorting `(distance, i, j)`
  makes distance authoritative and keeps tie-breaking deterministic, which is
  why no existing test changed meaning.

- **Correctness here is visible as a *better* warning, not as silence.** After
  the fix the Fuji dry run still aborts, but on `13th Corner, Netz` — the two
  corners that genuinely have no event — instead of `13th Corner, Netz Hairpin`
  (which hid a corrupted Netz). A guard that reports the right thing is the
  proof the internals changed for the better.

- **Fix the tool before re-deriving the data.** It was tempting to "repair" the
  affected models; checking first showed they were already hand-corrected
  (Ferradura 2089/2152, Long Beach 950/1045, Netz 3310/hairpin 3404). Re-running
  the updater would have been churn with a real risk of a new corruption.

- **The workaround outlives the fix — keep it documented.** Every prior slice
  hand-added `--preserve-geometry netz netz_hairpin`; those commands still work
  and still mean "do not claim", so nothing breaks. What changed is that the
  *reason* is no longer "bug 29" but "I reviewed this zone".

- **A doc line can become false because of a fix.** `--allow-unmatched` was
  documented as not preventing a listed-earlier corner from stealing; that is
  precisely what the fix removes. Updating the sentence in the same commit is
  part of the change, not a courtesy.

- **Live confirmation is part of the process, not a formality.** The bug folder
  stays in `work/active/bugs/` until the user runs a real refresh and sees the
  marker keep its geometry — that is the only evidence the fix behaves on their
  machine with their tracks.
