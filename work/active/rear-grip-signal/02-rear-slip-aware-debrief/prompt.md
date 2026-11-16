# Slice 02 — Rear-slip-aware debrief advice

## Status: ✅ implemented (commit `c4a1fe3`)

The gate is satisfied: slice 01 closed with validated facts (rear slip from the
wheels' ground velocities, `mGripFract` refused as a dead channel) and a
validity contract (`rear_stability.assess_corner`). This slice consumes them —
it does not recompute any sensor physics.

The trigger session turned out to be the clearest case in the data: Silverstone
National P3, Becketts, **13.78°** rear slip at the apex (5.61° with the brake
still on) against a 1.71° clean-lap baseline, where the old debrief said "hold
the brake 20 m longer". The advice now qualifies or replaces that demand, and the
plan target is a rear-slip number. Evidence:
`artifacts/silverstone-p3/`, `artifacts/barcelona-race/` (see
`artifacts/README.md`), `handoff.md`, `learnings.md`.

## Goal — one vertical outcome

The post-session coach considers validated rear-slip evidence before recommending
more braking or corner speed. Opening debrief, named-corner answers, Markdown
report and next-stint plan all distinguish **measured rear instability**, **valid
measurements without detected instability**, and **unknown/unmeasurable**.

No surface should confidently prescribe "hold the brake 20 m longer" while
ignoring rear-instability evidence or silently equating missing data with grip.

## Trigger and real input

- Session: `sessions/session_20261114T190410Z_silverstone-national-circuit_lmu_race.parquet`
- Sidecar: same stem, `.json`; Silverstone National Circuit,
  `DKR Engineering #4:ELMS25` / `ginetta-lmp3`.
- Existing outputs: `var/debrief/<session-stem>_debrief.{json,md}` and `_plan.md`.
- Existing headline advice: Becketts, 0.257 s/lap recurring loss, "hold the brake
  20 m longer"; 104.6 vs 109.0 km/h at brake release.
- See `artifacts/input-audit.md`: seven new channels exist, but both
  `grip_fraction_*` columns are identically zero. Ground-velocity/yaw columns
  vary; that alone does not validate their physical interpretation.

The legacy `slip_angle_rl_deg` / `slip_angle_rr_deg` refusal must remain. New
validated ground-velocity facts must have their own provenance/availability;
never relabel the legacy channels as usable.

## Execution order (test first)

1. **Verify the dependency.** Record slice 01's closing commit and the fact
   fields, units, corner windows, sample coverage and validity rules it provides.
   Identify which facts can support a brake-phase statement. Stop and ask if
   the prerequisite is unfinished; do not bypass its calibration gate.
2. **Read nearby implementation and tests.** Start with
   `session_corner_extras.py`, `session_facts.py`, `session_priorities.py`,
   `session_brief.py`, `session_report.py`, `session_conversation.py` and
   `coach/debrief_coach.py`. Read `docs/TESTING_LESSONS.md` before new tests.
3. **Re-evaluate `testFeatures.rear-grip-signal` in `package.json`.** Retain all
   existing scripts and both infrastructure guards. Add the shared debrief
   tests for consistency, priorities, report, brief and conversation. If a new
   Python test is needed, add a Node wrapper using `runPython`, the
   `[PASS]`/`[FAIL]` protocol, and register it in the main test command too.
4. **Write failing tests for the advice contract below.** Use deterministic
   fixtures and stubbed model calls; synthetic data tests plumbing, not physical
   validation. Include a small validated real fixture from slice 01 when it
   exists. Baseline the existing rank/loss/pace values before changing advice.
5. **Implement the smallest shared advice policy.** Consume slice 01's facts;
   do not introduce another slip formula or ranking term. Keep uncertainty and
   provenance in structured facts/evidence, not just LLM prose. Apply the same
   policy to the deterministic suggestion and its targets, then propagate it
   to reports, grounding, model instructions and the no-LLM answer.
6. **Verify on the real session.** Generate fresh facts, report, no-LLM opening,
   a Becketts answer and a plan into a new artifact directory. Do not overwrite
   the original debrief. Capture availability and the exact evidence used; do
   not claim that the recorded Becketts event was a slide unless validated.
   A provider-backed opening and Becketts question are a manual smoke check
   when credentials are available, never a network-dependent regression test.
7. **Finish implementation only when green.** Run the feature suite, full suite
   with `--pw`, and build; inspect changes, update handoff/learnings and the
   mission status with the implementation commit. Stop after this slice.

## Advice contract

- **Instability measured:** cite the corner, supporting lap/segment, metric,
  units and measurement window. If evidence overlaps braking, suppress or
  qualify recommendations to brake later/hold longer. Prefer a controlled
  brake-release comparison, not a demand to push further into instability.
  Observed slip is not proof that braking caused it. Without phase evidence,
  report that limitation rather than claiming brake-induced oversteer.
- **Valid data, no detected instability:** the ordinary reference comparison
  may remain, with bounded language about the measured window. Do not claim
  the car is universally stable, or treat normal nonzero tyre slip as a slide.
- **Unknown:** explicitly state that rear stability could not be assessed and
  why. Any brake-extension/later-braking recommendation is a conditional test,
  not a confirmed fix: check the driver's experience of rear movement first.
  Never turn nulls, invalid samples, insufficient coverage or a constant-zero
  unvalidated `mGripFract` signal into "no rear slip".
- An unavailable reference rear-slip channel does not invalidate valid driver
  measurements. Report the driver value without inventing a reference delta.
- Preserve per-lap evidence of instability: do not median it away, and do not
  interpret traffic/mistake-filtered clean laps as evidence that no slide
  happened elsewhere. Label non-clean lap observations separately; keep the
  existing clean-lap pace/ranking rules unchanged.
- Plan actions and numeric targets must agree. An instability-qualified action
  must not retain an unconditional higher-speed target from the old suggestion.
- Grounding and named-corner detail must retain relevant rear-slip evidence or
  its explicit unknown state within their existing byte budgets. Put essential
  constraints before long lap tables; a truncated warning is not awareness.
- The no-LLM path must implement this behavior too. Prompt wording alone is
  insufficient. Existing number validation must use all facts actually sent.

## Acceptance tests

- [x] Valid braking-window instability changes the advice without changing
      corner rank, recurring loss, phase timing or pace calculations.
      — `test_session_priorities.py` asserts identical rank/score/loss.
- [x] Apex/exit-only slip cannot produce a claim of brake-induced instability.
      — the suggestion says "not evidence of brake-induced oversteer".
- [x] Valid low-slip/control data preserves normal reference-based advice
      without claiming universal stability.
- [x] Legacy missing columns, partial/non-finite data, insufficient coverage and
      dead constant-zero grip channels yield explicit unknown, never zero grip
      loss or "not sliding". — slice 01's validation, `describe()` + report.
- [x] A driver-only validated metric is usable when the older reference lacks
      it; no fabricated comparison is presented. — reference corners carry no
      rear-slip value and no delta is shown.
- [x] An isolated lap with instability remains visible with its segment ID,
      including separately labelled non-clean observations where available.
- [x] Report, opening grounding, named-corner block, no-LLM answers and plan
      carry consistent evidence/availability and do not contradict each other.
      — one `RearStability` object, one `describe()`.
- [x] A long-session/long-corner-name UTF-8 fixture keeps the rear-slip caveat
      inside the grounding/detail byte budgets; a stub model receives it.
- [x] The Silverstone P3 session gets evidence-backed advice or a prominent
      uncertainty qualification. Legacy slip columns still refuse honestly.
      — `artifacts/silverstone-p3/`.
- [x] `bash scripts/test-summary.sh --feature rear-grip-signal` exits 0.
      — 582 assertions / 14 scripts.
- [x] `bash scripts/test-summary.sh --pw` exits 0; `npm run build` succeeds and
      `product/dist/compare.html` is current (check the build's actual output).
      — 3165 assertions / 103 scripts; bundle unchanged.
- [x] `handoff.md`, `learnings.md`, real-input artifacts and `PLAN.md` status
      reflect implementation, not merely this preparation.

## Non-goals

No recorder/schema changes, calibration heuristics, front slip, tyre model,
setup prescriptions, live-coach/TTS work, UI changes, reference/model/data
curation, new loss ranking, or unrelated bug fixes. Do not depend on the
bug-36 `trail_brake_depth_m` path to establish braking/sliding overlap.

## Likely implementation surface

- `product/python/lap_telemetry/session_priorities.py`: evidence-aware advice.
- `product/python/lap_telemetry/session_brief.py`: compact rear-slip grounding.
- `product/python/lap_telemetry/coach/debrief_coach.py`: model contract/template.
- `product/python/lap_telemetry/session_report.py`: visible evidence/caveats.
- `product/python/lap_telemetry/session_conversation.py`: consistent plan targets.
- `session_facts.py` / a focused helper only if needed to carry existing
  validated observations without recomputing sensor physics.
- Relevant `dev/scripts/test_session_*.{py,js}` and `package.json`.

Keep files coherent: default 200 lines, hard ceiling 437. Existing oversized
files are not permission to grow them; extract only what this slice requires,
with separate green `refactor:` commits if necessary.
