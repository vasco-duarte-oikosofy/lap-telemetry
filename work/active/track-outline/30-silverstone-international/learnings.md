# Learnings — Slice 30 (Silverstone International outline)

- **The short Silverstone layouts are subsets of the GP tarmac, so the GP
  TUMFTM outline is a free regression check.** Every point of the International
  centreline sits within ~7.5 m (p90) of the GP centreline — except one
  contiguous ~170 m stretch at up to 91 m, which is the International-only link
  road. Worth remembering: for any layout variant of a track we already have in
  TUMFTM, "nearest distance to the TUMFTM centreline" is a strong, cheap QA
  signal, and the *exceptions* are exactly where the layouts differ.

- **`register_outline.py` still cannot run the bundle build on Windows** — same
  `FileNotFoundError: [WinError 2]` as slice 13. Everything else (validation,
  ES module, manifest import + map entry, backup) completes first, so just run
  `npm run build` afterwards. Do not re-run the registrar to "finish" it.

- **Outline keys are per LMU track name, and Silverstone has several.**
  `silverstone-international-circuit`, `silverstone-grand-prix-circuit---elms`
  and (future) `silverstone-national` / `silverstone-gp-wec` are separate
  manifest entries pointing at different outlines. Lookup is exact-match
  (bug 25), so a missing entry means no outline — never a wrong one.

- **The outline JSON is generated from the reference lap, so keep the reference
  fresh first.** This outline was built after the 1:02.950 → 1:02.909 reference
  refresh; if the reference changes materially (different line through a
  corner), the outline should be regenerated — the trajectory outline *is* the
  racing line, and it will drift with it.
