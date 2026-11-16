# Handoff — Slice 02: rear-slip-aware debrief advice

## State: ✅ implemented (`c4a1fe3`), verified on two real sessions

The coach no longer recommends more brake or more speed at a corner where the
rear was measured sliding, and it never turns a missing or dead channel into
"the car is stable". Three states, everywhere:

| state | what the driver is told | what the advice does |
|---|---|---|
| `measured_instability` | value, corner, segment/lap, baseline, whether the brake was still on | braking and speed clauses are **removed** and replaced by "get the car settled first, then re-measure"; the plan target becomes a rear-slip number |
| `no_detected_instability` | "valid measurements, nothing above the envelope — not a claim that the car is stable everywhere" | ordinary reference advice, unchanged |
| `unknown` | "rear stability not measurable: <reason>" | advice unchanged, but framed as a **controlled test**, not a confirmed fix |

## Where the policy lives (one place, five consumers)

| file | role |
|---|---|
| `rear_stability.py` | the classifier (from slice 01) — thresholds, states, `describe()` |
| `session_priorities.py` | `suggest_change(..., rear=…)` replaces braking/speed clauses; `Priority.evidence["rear_stability"]` carries the structured state |
| `session_brief.py` | `REAR STABILITY` block **before** the LAPS table; measured slides listed wherever they rank; unknown listed for coached corners |
| `session_report.py` | `## Rear stability` section + a per-priority caveat |
| `session_conversation.py` | stability targets with a `caveat`, and an `Also measured:` plan line for a slide outside the top three |
| `coach/debrief_coach.py` | system contract + the no-LLM template answer in the same three states |

Ranking, recurring loss, spread, share-of-gap and pace are **untouched** — the
tests assert rank/score/loss are identical with and without rear evidence.

## The two real sessions

Both artifact sets are in `artifacts/` (see its `README.md` for the commands).

**Silverstone National P3 race, 2026-11-14 19:04 — the session that triggered the
mission.** Becketts is priority #1 at 0.257 s/lap and the old debrief said "hold
the brake 20 m longer". Measured: rear slip **13.78°** at the apex on segment 14
(lap 14), **5.61°** with the brake still on, against a **1.71°** clean-lap
baseline. New advice:

> the rear was measured sliding under braking (segment 14, lap 14): 13.78 deg at
> the apex, 5.61 deg with the brake still on, against a 1.71 deg clean-lap
> baseline — release the brake a little earlier and get the car settled before
> asking for more brake or speed, then re-measure

Plan target: "peak rear slip under 3.0 deg at the apex with the brake applied,
against 13.8 deg today, while matching the reference brake point".

**Barcelona / Ginetta P3 race, 2026-11-15 18:44 — the slide the driver described.**
Repsol ranks #4 (0.226 s/lap), so it is *not* one of the three plan targets. The
plan therefore carries a separate line — the case a top-3-only implementation
would have dropped:

> Also measured: **Repsol** — rear slip 6.51 deg at the apex with the brake
> applied against a 1.74 deg clean-lap baseline. Get the car settled there before
> chasing the loss.

## Artifacts on disk

`artifacts/silverstone-p3/` and `artifacts/barcelona-race/`, each with
`*_debrief.md` (report), `grounding.txt` (exactly what the model may read),
`opening-no-llm.txt`, `plan.md`, `rear-stability.json`; Silverstone also has
`becketts-answer.txt`. The saved debriefs in `var/debrief/` were **not**
overwritten.

## Verified

- `bash scripts/test-summary.sh --feature rear-grip-signal`: **582 assertions /
  14 scripts — ALL PASS** (the five shared debrief suites are now in the feature
  list, as this slice's prompt requires).
- `bash scripts/test-summary.sh --feature session-debrief`: **854 / 25 — ALL PASS**.
- `bash scripts/test-summary.sh --pw`: **3165 assertions / 103 scripts — ALL PASS**.
- `npm run build` succeeds; `product/dist/compare.html` rebuilt byte-identical
  (Python only).
- Grounding budget: Silverstone 3727 B, Barcelona 3137 B of 4096; a long
  UTF-8-name fixture keeps the caveat inside the budget and a stub model receives
  it (pinned in `test_session_brief.py`).

## One infrastructure commit outside the slice

`7ebc52b` adds `.agents` to the root-cleanup guard's allowlist. Remote commit
`15dc971` (the `/update_coach` skill) added a tracked `.agents/` tree without
touching the guard, so `--pw` had been red for everyone since. One allowlist
entry; no behaviour change. Flagged here because it is not slice scope.

## Deferred / open

- No live visual/provider QA of the coach voice on the real sessions: the LLM
  prompt change is covered by the contract test and the deterministic path, but a
  provider-backed opening was not run (credentials + network were not available
  and must never be a regression test).
- The instability threshold (`max(3.0°, 1.5 × clean-lap baseline)`) is calibrated
  on the Ginetta P3 only. A car with more rear slip everywhere would need its own
  baseline sanity check before trusting it — the baseline term is what makes this
  safe, but nobody has driven another car through it yet.
- The plan's `Caveat:` line is prose, not a structured field in the transcript's
  `targets[]`… it *is* structured (`Target.caveat` and `caveat` in
  `to_dict()`), so a future UI can render it without parsing.
- `grip_fraction_*` stays recorded and refused. If LMU ever populates
  `mGripFract`, `column_reasons` stops refusing it automatically — but nothing
  reads it until a validation gate proves it, and no such gate exists yet.
