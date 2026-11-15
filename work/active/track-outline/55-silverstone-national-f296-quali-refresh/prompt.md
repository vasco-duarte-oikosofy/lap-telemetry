# Slice 55 — Silverstone National / Ferrari 296 qualifying refresh

## Status

✅ Complete — 0:54.295 → 0:54.106, qualifying lap 10; see the mission PLAN
for the implementation commit. User explicitly prioritised this reference/model
refresh before rear-slip work. No rear-slip behavior was implemented.

## Goal

Use the latest finalised Ferrari 296 qualifying session at Silverstone National
to update this combo's reference, if faster, and refresh its existing curated
coaching model through Pipeline B. Preserve all six official turn names, stable
IDs, manual apex sides, and both complete flat-corner definitions.

## Input and protected assets

- Session: `sessions/session_20261115T095239Z_silverstone-national-circuit_lmu_quali.parquet`
  and its `.json` sidecar; `Vista AF Corse 2026 #21:LM` / `ferrari-296-gt3`.
- Current reference: `silverstone-national-circuit_vista-af-corse-2026-21-lm_time_00.54.295.parquet`.
- Model: `product/data/track-coaching/silverstone-national-circuit_vista-af-corse-2026-21-lm.json`.
- Official names: Copse, Maggots, Becketts, Brooklands, Luffield, Woodcote.
- Preserve the complete Maggots and Woodcote objects, including geometry and
  `target_throttle_pct: 100`; exclude them from braking-event matching.
- Do not change the P3 reference/model, outline, web/static map assets,
  TinyPedal labels/rotation or any other combo. The shared outline deliberately
  follows the P3 model, not the F296 model (slice 52).

## Execution order

1. Read `docs/HOW_TO_CREATE_A_COACHING_MODEL.md` Pipeline B, the guarded-export
   docs, slice 52 handoff and `docs/TESTING_LESSONS.md`.
2. Scan the latest quali with `lap-telemetry summary` and the segment-aware
   exporter helpers. Verify fastest candidate validity, full-lap coverage,
   authoritative duration, wall-clock span and row count. Never filter a session
   by `lap_number` to extract a lap. Record the source and asset hashes.
3. Write failing expectations in the existing
   `dev/scripts/test_silverstone_national_f296.py` for the new fastest reference
   and complete preserved flat zones. Retain all curation/resolver/map tests;
   use its existing Node wrapper and feature registration.
4. Review detected entry/apex/exit deltas against the curated geometry and the
   candidate's actual controls. Use only
   `dev/scripts/update_reference_and_coaching_model.py --session <input>
   --track-id silverstone-national-circuit --min-lap-time-s 30
   --preserve-geometry maggots woodcote --max-geometry-delta-m <reviewed-bound>`.
   If a geometry guard flags a corner, review its controls before deciding to
   preserve it; do not blindly relax bounds or use `--allow-unmatched`.
   The delegated export must report the mandatory single-combo audit.
5. Validate the full reference folder. Prove names/IDs/sides/flat zones and
   unrelated assets unchanged. Compare the updated reference against itself
   and/or a known slower lap with the coaching facts tool; verify resolution by
   track and car. Re-run updater to prove idempotence.
6. Run `bash scripts/test-summary.sh --feature track-outline` and
   `--feature session-debrief`, then the full `--pw` suite. Build with
   `npm run build` and verify `product/dist/compare.html` current. Existing
   feature lists already include the affected combo test, updater/reference
   guards, resolver tests and the two infrastructure guards.
7. Write handoff/learnings and real-input artifacts. Commit only this slice on
   `main`, update its `PLAN.md` row with the commit hash, then stop. Leave the
   previously prepared rear-slip planning files and runtime log untouched.

## Acceptance

- [x] Faster valid qualifying lap replaces only this combo's reference, with
      authoritative timing and the guarded export audit; otherwise no downgrade.
- [x] Model reference path/time agree with the exported lap; geometry changes
      are reviewed and documented, keeping the same simulator-distance axis.
- [x] All six official names, IDs and manual sides survive; Maggots and Woodcote
      retain their full objects and actual full-throttle/no-brake evidence.
- [x] Other curated data, outline, static map and TinyPedal assets unchanged.
- [x] Reference validator, feature suites, full suite and build pass.
- [x] Handoff, learnings, artifacts and completed plan row with commit exist.

## Non-goals

No production algorithm/schema changes, rear-slip work, new coaching behavior,
model regeneration, outline re-bake, turn-label placement or rotation changes.
