# Learnings — Slice 43 (new car on a track that already has a curated model)

- **Same situation as slice 37, different track: "is there a faster lap" was
  really "this combo does not exist".** Imola had a Ginetta LMP3 and a 499P
  pair; the 296 GT3 resolved to nothing, so the correct first question is not
  "is 1:46.173 faster than 1:33.546" but "which car is 1:33.546". The 499P is a
  Hypercar — comparing them would be meaningless, and bug 27 already prevents
  it. Check the *canonical* car before comparing times.

- **"Keep the flat turns" is easier to honour when you can prove there are
  none.** Imola's curated models have never carried a `target_throttle_pct`
  marker (verified with `git log` over every revision of the Ginetta model), and
  every one of the 11 corners either brakes or is a compound's second half. The
  instruction still mattered: it forced the `--allow-unmatched` decision to be
  explicit and backed by signals rather than a hopeful re-run.

- **The three corners a GT3 "loses" are not losses.** Villeneuve 2, Acque
  Minerali 2 and Variante Alta 2 are the second halves of chicanes/complexes.
  The detector yields one event per complex, so nearest-apex matching gives the
  event to the first half and the second half is unmatched. Keeping the old
  geometry is right: the zones are the same circuit, only the speed differs.
  `signal-review.txt` shows the F296 already at 100 % throttle at the Acque 2 /
  Alta 2 apexes — proof they ride on the same braking event.

- **Seeding beats regenerating, and the seed source should be the model the
  outline is baked from.** The two curated Imola models disagree only on
  geometry; the Ginetta one is the alphabetically-first tie-breaker in
  `bake_outline_turns.choose_model` and the only one with Rivazza short names.
  Seeding from it keeps the per-car model and the per-layout outline anchored to
  the same curation.

- **`bake_outline_turns.py --check` says `STALE` for a healthy outline.** A raw
  bake derives map labels from the model's short names, but `BAKED_SHORT_NAMES`
  in `test_outline_turns.js` pins Imola's Rivazza pair to numbers on purpose.
  So the check reports a difference that must NOT be "fixed". Trust the test
  contract, not the check's exit word: `test_outline_turns.js` passes.

- **`lap_length_m` stays at the older value on purpose.** The updater copies
  `lap_length_m` from the existing model (4904.3 m), while both references stop
  at 4899.2 m. That mismatch predates this slice and affects only percentage
  normalisation by ~0.1 %. Changing it would silently shift every existing
  corner's percentage; leave it to a deliberate slice.

- **`--print-facts` remains the cheapest end-to-end proof.** Lap 4 is 0.379 s
  slower than the reference and the summary reports exactly 0.379, with
  official corner names — model + reference + resolver all agree in one command.
