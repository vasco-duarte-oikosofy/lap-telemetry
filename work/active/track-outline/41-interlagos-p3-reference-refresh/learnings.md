# Learnings — Slice 41 (Interlagos P3 reference + model refresh)

- **A faster lap can be a worse geometry source.** The new lap is 0.29 s quicker
  precisely because the driver braked less (Ferradura, Bico de Pato) and got
  Mergulho flat. The braking-event detector therefore yields 7 events instead of
  ~10, and two curated corners (Ferradura 1/2) would have ended up on the same
  apex. Refresh the reference eagerly; refresh geometry only where the new lap
  reproduces the curated corner, and say why per corner.
- **Run the geometry guard as a probe, not a formality.** `--max-geometry-delta-m 1`
  turns the tool into a read-only diff: it prints every matched corner's movement
  and writes nothing. That is how the Ferradura/Laranjinha collision was found
  before touching product data.
- **`--preserve-geometry` needs a signal receipt.** Brake/throttle/steer/speed
  within ±0.5 s of each curated apex (old vs new lap) is cheap to produce and
  turns "keep the old geometry" from a shrug into evidence — including the
  distinction between *flat* (throttle 1.00), *lift* (throttle 0.45) and
  *compound second apex*.
- **Windows default encoding silently corrupts curated names.** `read_text()`
  uses cp1252 on this machine, so one refresh rewrote `Junção` as
  `JunÃ§Ã£o`. The same code is harmless on macOS/Linux (UTF-8 default), which is
  why it survived this long. Text I/O on curated data must always pass
  `encoding="utf-8"`, and `json.dumps` should use `ensure_ascii=False` so the
  files stay readable.
- **PYTHONUTF8=1 hides exactly this bug.** Our wrappers force UTF-8 mode, so a
  round-trip test passes even with the bug present. Only a static rule ("no text
  I/O without an explicit encoding in the guarded pipeline") catches it; keep
  that guard alongside the behavioural ones.
- **The outline↔model contract is enforced, so a model refresh is never
  model-only.** `test_outline_turns.js` compares every outline `apex_s_m` with
  the coaching model, so refreshing corner geometry forces a `bake_outline_turns`
  run plus a static-module/dist rebuild. Budget for it in the slice.
- **`bake_outline_turns.py` derives display labels from speech aliases.** It
  wrote `Descida do Lago 1` / `Ferradura 1` into the outline where the curated
  map labels were `Lago 1` / `null`. The pinned `BAKED_SHORT_NAMES` map in the
  test caught it; restore the display labels after baking (speech and map labels
  are different namespaces).
- **A recorder that never finalizes is normal here.** The session had no
  canonical parquet, `in_progress: true`, and it kept appending idle frames
  during the slice (94 → 131 shards). Freeze the closed shards read-only, hash
  them, exclude the live sidecar from the frozen hash set, and let the
  provenance script add the frozen copy to the validator's session dirs.
- **`parents[N]` in an artifact script is easy to get wrong**: from
  `work/active/track-outline/<slice>/artifacts/` the repo root is `parents[5]`,
  and the validator needs a *directory* (`frozen.parent`), not the file.
