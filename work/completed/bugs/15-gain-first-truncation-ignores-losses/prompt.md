# Bug 15: Gain-first ordering + word-limit truncation silences losses

## Observed symptom

From `sessions/recorder_with_coach.txt` (session `20260529T143959Z`).
Utterances are produced by `TemplateAdapter`, not an LLM.

**Lap 10 — driver is +2.054 s slower than reference:**
> "You gained five tenths going into turn 1. You braked 20 metres later.
>  You gained seven hundredths exiting turn 5. You got back on throttle five
>  metres earlier."

The driver hears only gains. The actual top facts contain losses of **+1.641 s
at turn 1 apex** and **+1.507 s at turn 1 exit** — the driver braked 20 m too
late, missed the apex by 7 kph, and lost all the entry gain in the corner.

**Lap 14 — driver is +0.321 s slower:**
> "You gained just over a tenth at the apex of turn 4. You carried seven
>  kilometres per hour more, hitting the apex four metres earlier, and got
>  back on throttle two metres earlier."

Turn 5 has losses of +0.456 s (min speed) and +0.417 s (exit) — bigger than
any gain in the lap. Neither is mentioned.

**Lap 15 — driver is +0.362 s slower:**
> "You gained two tenths going into turn 1. You braked ten metres later.
>  You gained a hundredth exiting turn 3. You carried more speed through."

The turn 3 exit gain is −0.009 s (sub-threshold noise). The turn 2 losses
(+0.162 s apex, +0.162 s exit) and turn 1 apex loss (+0.146 s) are all
absent. Additionally, "You carried more speed through" is factually wrong:
the driver's turn 3 exit speed is **186.5 kph vs reference 189.8 kph** —
the driver carried *less* speed.

## Root cause

`TemplateAdapter.generate()` in `template_adapter.py`:

```python
# Build phrases: gains first, then losses
for corner_id in _corner_order(gain_by_corner, is_gain=True):
    phrases.append(_dedup_corner(gain_by_corner[corner_id], is_gain=True))

for corner_id in _corner_order(loss_by_corner, is_gain=False):
    phrases.append(_dedup_corner(loss_by_corner[corner_id], is_gain=False))

result = " ".join(p for p in phrases if p)
max_words = facts.constraints.get("max_words", 35)
return _truncate_to_word_limit(result, max_words)
```

`_truncate_to_word_limit` drops whole sentences from the **end** of the
string. Gains are always first. When the gain phrases alone fill the 35-word
budget, loss phrases never appear.

Lap 10 example — gain phrases alone:

| Phrase | ~words |
|--------|--------|
| "You gained five tenths going into turn 1. You braked 20 metres later." | 13 |
| "You gained seven hundredths exiting turn 5. You got back on throttle five metres earlier." | 14 |
| "You gained a hundredth at the apex of turn 4. You carried one kilometre per hour more." | 16 |
| **Total** | **43** |

Truncation to 35 words keeps sentences 1+2 (27 words) and drops sentence 3
and all loss phrases. The driver hears only positive feedback on a lap that
is 2 seconds off pace.

The **factually wrong exit-speed claim** (lap 15, turn 3) is a separate
sub-bug in `_gain_exit()`:

```python
def _gain_exit(cl: CornerLoss) -> str:
    ...
    return f"You gained {time} exiting {cl.corner_name}. You carried more speed through."
```

`loss_s` is negative (a gain in Δt) but `cl.driver_value` (exit speed) can
be *lower* than `cl.reference_value`. Δt gain at a corner exit does not
imply higher exit speed; it means less time was lost relative to the
reference from that point onward. The detail clause must not assert speed.

## Files to fix

### `template_adapter.py`

**Fix 1 — magnitude-first ordering when losses dominate.**

Replace the unconditional gain-first ordering with delta-aware ordering:
when `facts.lap_time_delta_s > 0` (driver slower), sort all corner groups
by `max(abs(loss_s))` regardless of sign, so the most impactful moment
comes first and gains are not systematically privileged:

```python
def _all_corners_by_magnitude(
    gain_by_corner: dict, loss_by_corner: dict, lap_delta_s: float
) -> list[tuple[str, list[CornerLoss], bool]]:
    """Return (corner_id, items, is_gain) sorted by dominant impact.

    When lap_delta_s <= 0 (driver on pace or faster): gains first.
    When lap_delta_s > 0 (driver slower): sort all by abs(dominant loss_s).
    """
    entries = []
    for cid, items in gain_by_corner.items():
        dom = max(abs(c.loss_s) for c in items)
        entries.append((cid, items, True, dom))
    for cid, items in loss_by_corner.items():
        dom = max(abs(c.loss_s) for c in items)
        entries.append((cid, items, False, dom))

    if lap_delta_s > 0:
        entries.sort(key=lambda x: x[3], reverse=True)
    else:
        # Gain-first: gains before losses, each group sorted by magnitude
        entries.sort(key=lambda x: (not x[2], -x[3]))

    return [(cid, items, is_gain) for cid, items, is_gain, _ in entries]
```

**Fix 2 — remove the false exit-speed claim.**

`_gain_exit()` fallback (no `exit_distance_delta_m`) currently says
"You carried more speed through." Replace with a neutral fallback that
does not assert speed direction:

```python
def _gain_exit(cl: CornerLoss) -> str:
    ...
    # no delta available — neutral fallback only
    return f"You gained {time} exiting {cl.corner_name}."
```

Same fix for `_loss_exit()` fallback "You carried less speed through."

## Evidence from session

Session: `session_20260529T143959Z_bahrain-outer-circuit_lmu.parquet`
Reference: `bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet`
Track model: `bahrain-outer-circuit_dkr-engineering-4-elms25.json`

| Lap | delta | Biggest loss ignored | Utterance |
|-----|-------|---------------------|-----------|
| 10 | +2.054 s | turn 1 min_speed +1.641 s | gains only |
| 14 | +0.321 s | turn 5 min_speed +0.456 s | gains only |
| 15 | +0.362 s | turn 2 min_speed +0.162 s | gains + wrong exit claim |

## Tests to add

### `test_loss_dominant_lap_mentions_biggest_loss`

Build a `LapComparisonFacts` with `lap_time_delta_s = +2.0`,
`top_losses = [turn_1_min_speed(+1.5 s)]`,
`top_gains = [turn_1_entry(−0.5 s), turn_5_exit(−0.07 s)]`.
Assert the utterance **contains "You lost"** (loss-first when lap is slower).

### `test_gain_dominant_lap_stays_gain_first`

Build facts with `lap_time_delta_s = −0.3`, gains > losses in magnitude.
Assert utterance starts with "You gained".

### `test_exit_gain_no_false_speed_claim`

Build a gain fact with `phase="exit"` and no `exit_distance_delta_m`.
Assert the phrase does NOT contain "more speed" or "less speed".

### `test_word_limit_does_not_drop_dominant_loss`

Build facts with gains that alone exceed max_words and a large loss.
Assert the utterance is truncated but still contains the loss phrase.
