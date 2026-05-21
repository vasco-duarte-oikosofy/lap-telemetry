# Mission 01c: Determine Entry/Exit Phase Algorithm

## Goal

Replace fixed-offset entry/exit phase detection with algorithm-driven detection using throttle, brake, and speed traces. Extend delta-time measurement from gains to losses. Surface actionable facts for both gains and losses.

## Feature test command

```bash
bash scripts/test-summary.sh --feature interactive-race-coach
```

## Slice history

### ✅ 01c — Algorithm-driven entry/exit phase detection
Replaced `apex ± 30 m` offsets with throttle-lift entry, brake-off/throttle-full exit detection, configurable via `PhaseDetectionThresholds`.

### ✅ 01c.2 — Exit gains improvements (3 sub-slices)
1. **Fix delta-T calculation** — JS pipeline as single source of truth
2. **Apex/min-speed gain algorithm** — `delta_t[straight_end] - delta_t[apex]`, `apex_offset_m`
3. **Entry gain algorithm** — `delta_t[apex] - delta_t[entry]`

All gains use real delta-time. (Losses unified in 01c.4.)

### ✅ 01c.3 — Fix oversized modules
Split test and implementation files to respect 437-line ceiling.

### ✅ 01c.4 — Losses and gains algorithm review + entry/exit distance deltas
Unified losses to use delta-time for all three phases (same formula as gains).
`gain_end_distance_m` now populated for both losses and gains.
`speed_delta / 100.0` heuristic removed (fallback only for out-of-range indices).
Added `entry_distance_delta_m`, `exit_distance_delta_m`, and
`reference_phase_distance_m` — comparing driver vs reference phase-transition
distances ("you lifted 8 m later", "you got back to full throttle 12 m earlier").
JS pipeline extended to resample reference throttle/brake traces.
Spec: `delta_loss_gain_delta_break_throttle.md`.

**Current algorithm summary:**

| Phase | Loss & gain formula | `gain_end_distance_m` |
|-------|-------------------|----------------------|
| entry | `delta_t[apex] - delta_t[entry]` | apex |
| minimum_speed | `delta_t[straight_end] - delta_t[apex]` | straight_end |
| exit | `delta_t[straight_end] - delta_t[exit]` | straight_end |

## Open items

### Same-corner, same-direction phase deduplication

When a corner produces both a `minimum_speed` gain and an `exit` gain (e.g. turn 5: −0.118s min-speed + −0.105s exit), these measure **overlapping reality** — the driver carried more speed through the apex and that advantage compounded down the straight. Reporting both as separate top-gains is technically correct but creates a coaching problem: the LLM would say "You gained in turn 5 minimum speed and also in turn 5 exit" — which is essentially the same insight twice.

**Options:**
1. **Deduplicate by corner_id+direction** — keep only the largest gain/loss per corner, discard smaller same-corner phases. Simple, but loses the phase-level detail.
2. **Merge same-corner gains into a composite** — combine min-speed + exit into a single entry tagged with both phases and the dominant one. Preserves detail but adds schema complexity.
3. **Let the LLM handle it** — pass all phases to the LLM with guidance: "when the same corner appears with multiple gain phases, say it once and reference the dominant phase." This keeps the data honest and puts deduplication in the phrasing layer.

**Decision needed** before constructing the coaching prompt contract. Document in `docs/specs/interactive-race-coach-and-engineer.md`.

### Entry/exit distance deltas ✅ DONE

`entry_distance_delta_m` and `exit_distance_delta_m` — comparing where the *driver's* phase transition happened vs where the *reference's* did ("you lifted 8 m later than reference" / "you got back to full throttle 12 m earlier"). Spec: `delta_loss_gain_delta_break_throttle.md`.

### gain_end_distance_m naming

Field is slightly misleading for losses. `measurement_end_distance_m` would be clearer but requires web UI changes. Low priority.



## Future slices needed

1. **Same-corner deduplication** — decide how to present overlapping phases per corner