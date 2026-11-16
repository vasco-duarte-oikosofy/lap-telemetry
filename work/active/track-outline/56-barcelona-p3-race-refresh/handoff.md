# Handoff — Slice 56: Barcelona / Ginetta P3 race refresh (superseded, no net data change)

## Result

**This slice leaves no net change in `product/data/`.** Its data outcome was
superseded before it could be committed, and this closure records the evidence
rather than re-applying anything.

| | |
|---|---|
| Race source | `sessions/session_20261115T124448Z_circuit-de-barcelona_lmu_race` (DKR Engineering #4:ELMS25 / ginetta-lmp3) |
| Fastest complete valid lap | **race lap 16 @ 96.319 s**, 4791 rows, sectors 28.956 / 38.607 / 28.756 |
| Reference before this slice | `…_time_01.36.456.parquet` |
| What this slice produced in the work tree | `…_time_01.36.319.parquet` + model with **Turn 3 — Renault** refreshed, 11 corners preserved |
| What is on disk now | `…_time_01.36.040.parquet` — **slice 57's faster qualifying lap 4** (`672a12c`), which deleted the 1.36.319 file and re-pointed the model |
| Net effect of slice 56 on data | **none** (superseded by a faster lap before commit) |

The race refresh itself was correct and defensible — 96.319 beat the 96.456
reference — but slice 57 then found a 96.040 qualifying lap on the same combo,
so the race reference never reached a commit. `git log -1 --
product/data/reference-laps/` confirms `672a12c` is the only recent commit for
this combo.

## What the frozen evidence still proves

- **Frozen source** — `var/tmp/barcelona-p3-race-refresh/session_20261115T124448Z_circuit-de-barcelona_lmu_race.parquet`
  (sha256 `5859407d…bf57`), assembled from `part0..part94` by
  `artifacts/freeze_source.py`; the sidecar is `in_progress: true` and the
  possibly-open `part95` was excluded. Shard hashes are in
  `artifacts/source-manifest.json`; the original recording was never modified.
- **Lap scan** — `artifacts/lap-scan.txt` (authoritative `summary`): 19 complete
  laps, lap 16 fastest at 1:36.319; lap 20 is a 0:37.850 partial tail and is
  excluded as incomplete. `artifacts/candidate-review.json` carries the
  per-lap (time, rows, validity) table and the pre-guard geometry proposal.
- **Geometry review** — the default 40 m guard **aborted** on the first attempt
  with 8 corners flagged (`artifacts/guarded-review-abort.txt`); the flags were
  checked against real controls in `artifacts/controls-review.json` (window row
  counts, min speed, min throttle, max brake, mean apex steering, curated vs
  detected geometry). The accepted run refreshed only **Turn 3 — Renault**
  (1068/1161/1163 → 1081/1163/1167, a 13 m entry move) and preserved the other
  11 corners (`artifacts/guarded-update.txt`).
- **Single-combo audit** — the delegated exporter printed
  `AUDIT: 1 reference lap changed … OK` for that run; no second combo moved.
- **Closure audit** — `artifacts/closure-audit.txt`: `git status --short
  product/ dist/ web/` is empty, only `01.36.040` exists for this car, the model
  points at it with `lap_time_s 96.04` and all 12 corner ids/names intact, and
  `(track, car)` resolution returns the right file for both Barcelona cars
  (bug 27 catalog path).
- **Validator** — `artifacts/reference-validation.txt`: **38 references,
  0 failures**.

## Tests, build

- `--feature track-outline`: **1598 assertions / 36 scripts — ALL PASS** (`artifacts/feature-track-outline.txt`).
- `--feature session-debrief`: **812 assertions / 25 scripts — ALL PASS** (`artifacts/feature-session-debrief.txt`).
  Both files were **re-recorded at closure**; the versions left by the previous
  agent captured a transient red state that no longer reproduces.
- Full `--pw` suite: 3075 passed, **1 pre-existing failure** —
  `dev/scripts/test_repo_reorg_root_cleanup.js` rejects the `.agents` root
  directory introduced by remote commit `15dc971` (the `/update_coach` skill).
  Unrelated to this slice and deliberately not touched.
- `npm run build` succeeded; `product/dist/compare.html` rebuilt byte-identical
  (no data, outline or web change in this slice).

## Docs touched

- `dev/tools/README-REFERENCE-LAPS.md` — the worked example now names
  `…_time_01.36.040.parquet`, the file that actually exists. (It said 1.36.456
  at HEAD, then 1.36.319 from this slice's transient export; both are stale.)
- `PLAN.md` — row 56 marked ✅ and "In progress" cleared.

## Deferred / open

- `test_repo_reorg_root_cleanup.js` allowlist needs `.agents` (or the skill
  should live under an allowed root). One-line fix, outside this slice's scope.
- `visual_qa.status` for the Barcelona map stays `pending`; this slice touched
  no map asset.
- The frozen race parquet lives under gitignored `var/tmp/` — re-run
  `artifacts/freeze_source.py` if you need it again.
