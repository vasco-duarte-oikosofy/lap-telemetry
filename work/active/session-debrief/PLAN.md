# Mission: Session Debrief Coach

**Spec:** [`docs/specs/session-debrief-coach.md`](../../docs/specs/session-debrief-coach.md)

**Goal:** Analyse a whole recorded session (every eligible lap) and hold a
grounded, warm-but-demanding coaching conversation that ends in two or three
measurable targets for the next stint.

**Feature tests:** `bash scripts/test-summary.sh --feature session-debrief`

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-session-lap-inventory` | ✅ 8cecacb (fixes 744717a, this commit) | Auto-merge session shards into an in-memory view and classify every contiguous lap segment (eligible / out-lap / in-lap / pit-lap / incomplete / short / invalid); `debrief --list` prints the inventory with rejection reasons. Includes the `lap_comparator` refactor needed to analyse a segment instead of a lap number |
| `02-per-lap-debrief-facts` | ✅ 14f8cfe | Every eligible lap compared against the curated reference at segment granularity, uncapped, into a `SessionDebriefFacts` JSON that `debrief --json` prints. Gate: at least five eligible laps |
| `03-consistency-metrics` | ✅ e85a1c8 | Session-best baseline, optimal lap from a **speed envelope** (sectors are unusable, see the slice), lap spread, per-corner-phase spread, and separate "slow every lap" vs "inconsistent" rankings |
| `04-extended-corner-facts` | ✅ 94c8de3 | Gear, brake peak/area, trail-braking depth, steering corrections, TC/ABS duty and lateral line offset per corner; rear slip refused with evidence; graceful degradation with a reason per unusable channel |
| `05-improvement-priorities` | 🔲 Not started | Ranked, deduplicated opportunities combining recurring loss, consistency spread and corner weight, each with a computed suggested change ("brake 6 m later") |
| `06-markdown-report` | 🔲 Not started | `--report-only --no-llm` writes `<session>_debrief.md`: summary, clean-lap table, optimal lap, top priorities, per-corner appendix, excluded laps |
| `07-llm-debrief-summary` | 🔲 Not started | Coach voice contract + compact-report grounding: the opening debrief and one-shot `--ask` answers, with contract tests against a fake adapter |
| `08-interactive-debrief` | 🔲 Not started | Multi-turn REPL: history, automatic corner drill-down, `/corner`, `/laps`, `/plan`, `/save`; transcript in `_debrief.json`, targets in `_plan.md` |

---

## Per-slice template

### Slice N: `<slice-name>`

**Outcome.** `<brief outcome>`

**Steps:**
1. Write the failing test first
2. Write the minimal code to make it pass
3. Run `bash scripts/test-summary.sh --feature session-debrief` — must pass
4. Run `npm run build` — must succeed (only when the slice touches `web/` or `product/data/`)
5. Run the full suite at slice 3 and slice 6
6. Commit — small, green, on `main`

---

## Acceptance target

At the end of slice 06, a driver can run one command after a stint and read a
report that names the corner they lose the most time in, distinguishes a
recurring loss from an inconsistency, estimates the optimal lap, and lists
excluded laps. At the end of slice 08, they can talk it through with the coach
and leave with three numeric targets for the next stint.

## Notes carried in from planning

- `lap_number` is not unique across a session: sim restarts reset it, so all
  analysis is keyed on segment index. This was observed on
  `dev/sessions/session_20260524T141613Z_paul-ricard---3a_lmu.parquet`.
- 19 laps cost ~3.5 s of comparison time. No caching, parallelism or
  incremental design is needed.
- `lap_comparator.py` is at 422 of its 437-line hard ceiling: slice 01 must
  extract the slicing/duration helpers into their own module before adding
  segment support.
- `debrief` artifacts live in the gitignored `sessions/` directory.
- Two duration-guard tests (`test_lap_duration_telemetry.js`,
  `test_lap_duration_surfaces.js`) need real recordings under `sessions/` that
  are not committed. They are deliberately left out of the feature suite until
  those fixtures exist locally; add them to `testFeatures["session-debrief"]`
  in `package.json` on a machine that has them (slice 01 touches
  `parquet_utils`).
