# Template Phrase Specification

Reference document for the deterministic template adapter. Read this before
implementing `template_adapter.py` — it maps every code path from facts to
spoken phrases, so the implementer doesn't need to re-derive the logic from
the LLM prompt or the data structures.

---

## 1. Three Coaching Contexts

The template adapter must handle three distinct coaching calls, each with its
own fact structure and word constraints:

### 1a. After-lap summary (`LapComparisonFacts` — `type: lap_coaching_summary`)
- **Word limit:** 35 words (`top=3`) or 20 words (`top=1`)
- **Facts:** `top_losses` + `top_gains`, each a list of `CornerLoss` items
- **Same-corner dedup:** Multiple phases for the same corner are combined into one sentence
- **Called from:** `LiveFactGenerator` → `utterance_fn(facts)`

### 1b. Corner-exit note (`LapComparisonFacts` — filtered to one corner)
- **Word limit:** 20 words (`top=1`) or 30 words (`top=3`)
- **Facts:** `top_losses` only (gains are saved for the lap summary)
- **Same-corner dedup:** Multiple exit phases for the same corner are combined
- **Called from:** `LiveCornerFactGenerator` → `corner_utterance_fn(facts, corner_name, top)`

### 1c. Fuel engineer call (`FuelFacts` — completely different structure)
- **Word limit:** 20 words
- **Facts:** `fuel_status` (`OK | WARNING | CRITICAL | UNKNOWN`), `laps_of_fuel_remaining`, `race_laps_remaining`, `fuel_per_lap_l`
- **Called from:** `LiveFuelFactGenerator` → `fuel_utterance_fn(facts)`

---

## 2. Data Available Per Phase

Each `CornerLoss` has a `phase` field with **5 possible values**. The available
delta fields vary by phase — the template must check which fields are present
and `None`:

| Phase | `driver_value` | `reference_value` | `apex_offset_m` | `entry_distance_delta_m` | `exit_distance_delta_m` |
|---|---|---|---|---|---|
| `minimum_speed` | speed at apex | ref speed at apex | ✅ where apex was hit | ❌ | ❌ |
| `entry` | speed at entry | ref speed at entry | ❌ | ✅ lift/brake offset | ❌ |
| `exit` | speed at exit | ref speed at exit | ❌ | ❌ | ✅ throttle/exit offset |
| `exit_brake` | speed at brake release | ref speed at release | ❌ | ❌ | ✅ brake release offset |
| `exit_throttle` | speed at throttle | ref speed at throttle | ❌ | ❌ | ✅ throttle re-app offset |

### Delta interpretation rules (from prompt rule #6 of `prompt_templates.py`)

- **`entry_distance_delta_m`**: Positive = driver lifted/braked **earlier**. Negative = driver carried more speed into the corner (lifted/braked later).
- **`exit_distance_delta_m`**: Negative = driver released brakes/got to throttle **later**. Positive = driver got back to full throttle **earlier**.
- **`apex_offset_m`**: Positive = driver hit apex **earlier** (before reference). Negative = driver hit apex **later**.
- **`driver_value` vs `reference_value`**: These are raw speeds (km/h). For `minimum_speed`, if `driver_value > reference_value`, the driver was **faster** at the apex — do NOT say "slow down". The time loss comes from a different cause (late braking, running wide, poor exit).

### Speed difference computation

```python
speed_diff = abs(driver_value - reference_value)
speed_diff_rounded = round(speed_diff)  # integer km/h
```

Always use the **absolute** difference, then describe direction in words
("less", "more", "earlier", "later").

---

## 3. Time Formatting

The `loss_s` field is the most actionable number a driver needs — it tells them
**how much** time they lost or gained. Real race engineers speak in tenths, not
raw decimals. The template must format `loss_s` into natural spoken English:

| `loss_s` (absolute) | Spoken as |
|---|---|
| 0.01–0.04 | "X hundredths" → "two hundredths", "four hundredths" |
| 0.05 | "five hundredths" |
| 0.06–0.09 | "X hundredths" → "six hundredths", "eight hundredths" |
| 0.10 | "a tenth" |
| 0.11–0.19 | "just over a tenth", "a tenth and a half" (nearest natural fraction) |
| 0.20 | "two tenths" |
| 0.30 | "three tenths" |
| 0.40 | "four tenths" |
| 0.50 | "half a second" |
| 0.51–0.74 | "just over half a second", "six tenths", "seven tenths" |
| 0.75 | "three quarters of a second" |
| 0.80–0.99 | "eight tenths", "nine tenths" |
| 1.00 | "one second" |
| 1.01–1.99 | "one point X seconds" (e.g. "one point two seconds") |
| 2.00+ | "{n} seconds" (e.g. "two seconds", "three seconds") |

### Time formatting helper

```python
def format_time(loss_s: float) -> str:
    """Format a loss_s value into natural spoken English for TTS.

    Returns phrases like 'a tenth', 'two tenths', 'half a second',
    'one point two seconds'.
    """
    t = abs(loss_s)
    # Round to hundredths for comparison
    t = round(t, 2)

    if t < 0.1:
        hundredths = round(t * 100)
        if hundredths <= 1:
            return "a hundredth"
        return f"{spell_number(hundredths)} hundredths"
    if t == 0.10:
        return "a tenth"
    if t < 0.20:
        return "just over a tenth"
    if t < 0.50 and t % 0.10 == 0:
        tenths = round(t * 10)
        return f"{spell_number(tenths)} tenths"
    if t < 0.50:
        # e.g. 0.25 → "two and a half tenths" — too awkward
        # Just round to nearest tenth
        tenths = round(t * 10)
        return f"{spell_number(tenths)} tenths"
    if t == 0.50:
        return "half a second"
    if t < 0.75:
        tenths = round(t * 10)
        return f"{spell_number(tenths)} tenths"
    if t == 0.75:
        return "three quarters of a second"
    if t < 1.00:
        tenths = round(t * 10)
        return f"{spell_number(tenths)} tenths"
    if t == 1.00:
        return "one second"
    if t < 2.00:
        decimal = round(t, 1)
        return f"one point {spell_number(int(round(t * 10) % 10))} seconds"
    # 2.0+ → spell out the integer part if ≤ 10, else digits
    n = int(t)
    return f"{spell_number(n)} seconds"
```

---

## 4. Loss Phrases (per phase)

For `CornerLoss` items where `loss_s > 0` (the driver lost time).

### 4a. `minimum_speed` loss

**Primary** (always):
```
"You lost {time} at the apex of {corner_name}."
```

**With speed delta**:
```
"You lost {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour less."
```

**With speed delta + apex offset** (when `apex_offset_m` is not None and `!= 0`):
- `apex_offset_m > 0`:
  ```
  "You lost {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour less, and hit the apex {apex_offset} metres earlier."
  ```
- `apex_offset_m < 0`:
  ```
  "You lost {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour less, and hit the apex {abs(apex_offset)} metres later."
  ```

### 4b. `entry` loss

**Primary** (always):
```
"You lost {time} braking for {corner_name}."
```

**With entry delta** (when `entry_distance_delta_m` is not None and `!= 0`):
- `entry_distance_delta_m > 0` (lifted/braked earlier):
  ```
  "You lost {time} braking for {corner_name}. You lifted {delta} metres earlier."
  ```
- `entry_distance_delta_m < 0` (carried more speed in, braked later):
  ```
  "You lost {time} braking for {corner_name}. You braked {abs(delta)} metres later."
  ```

**No delta**:
```
"You lost {time} going into {corner_name}."
```

### 4c. `exit_brake` loss

**Primary** (always):
```
"You lost {time} exiting {corner_name}."
```

**With exit delta** (when `exit_distance_delta_m` is not None and `!= 0`):
- `exit_distance_delta_m < 0` (released brakes later):
  ```
  "You lost {time} exiting {corner_name}. You released the brakes {abs(delta)} metres later."
  ```
- `exit_distance_delta_m > 0` (released brakes earlier — unusual loss):
  ```
  "You lost {time} exiting {corner_name}. You released the brakes {delta} metres earlier."
  ```

### 4d. `exit_throttle` loss

**Primary** (always):
```
"You lost {time} getting on the power at {corner_name}."
```

**With exit delta** (when `exit_distance_delta_m` is not None and `!= 0`):
- `exit_distance_delta_m < 0` (got on throttle later):
  ```
  "You lost {time} getting on the power at {corner_name}. You got back on throttle {abs(delta)} metres later."
  ```
- `exit_distance_delta_m > 0` (got on throttle earlier — unusual loss):
  ```
  "You lost {time} getting on the power at {corner_name}. You got back on throttle {delta} metres earlier."
  ```

### 4e. `exit` loss (generic — no specific brake/throttle data)

```
"You lost {time} exiting {corner_name}. You carried less speed through."
```

---

## 5. Gain Phrases (per phase)

For `CornerLoss` items where `loss_s < 0` (the driver gained time).

### 5a. `minimum_speed` gain

**Primary** (always):
```
"You gained {time} at the apex of {corner_name}."
```

**With speed delta**:
```
"You gained {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour more."
```

**With speed delta + apex offset** (when `apex_offset_m` is not None and `!= 0`):
- `apex_offset_m > 0` (hit apex earlier):
  ```
  "You gained {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour more, hitting the apex {apex_offset} metres earlier."
  ```
- `apex_offset_m < 0` (hit apex later):
  ```
  "You gained {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour more, hitting the apex {abs(apex_offset)} metres later."
  ```

### 5b. `entry` gain

**Primary** (always):
```
"You gained {time} going into {corner_name}."
```

**With entry delta** (when `entry_distance_delta_m` is not None and `!= 0`):
- `entry_distance_delta_m < 0` (braked later, carried more speed in):
  ```
  "You gained {time} going into {corner_name}. You braked {abs(delta)} metres later."
  ```
- `entry_distance_delta_m > 0` (lifted earlier, more controlled entry):
  ```
  "You gained {time} going into {corner_name}. You lifted {delta} metres earlier."
  ```

**No delta**:
```
"You gained {time} going into {corner_name}. You carried more speed into the corner."
```

### 5c. `exit_brake` gain

**Primary** (always):
```
"You gained {time} exiting {corner_name}."
```

**With exit delta** (when `exit_distance_delta_m` is not None and `!= 0`):
- `exit_distance_delta_m > 0` (released brakes earlier):
  ```
  "You gained {time} exiting {corner_name}. You released the brakes {delta} metres earlier."
  ```
- `exit_distance_delta_m < 0` (released brakes later — unusual gain):
  ```
  "You gained {time} exiting {corner_name}. You released the brakes {abs(delta)} metres later."
  ```

### 5d. `exit_throttle` gain

**Primary** (always):
```
"You gained {time} getting on the power at {corner_name}."
```

**With exit delta** (when `exit_distance_delta_m` is not None and `!= 0`):
- `exit_distance_delta_m > 0` (got on throttle earlier):
  ```
  "You gained {time} getting on the power at {corner_name}. You got back on throttle {delta} metres earlier."
  ```
- `exit_distance_delta_m < 0` (got on throttle later — unusual gain):
  ```
  "You gained {time} getting on the power at {corner_name}. You got back on throttle {abs(delta)} metres later."
  ```

### 5e. `exit` gain (generic)

```
"You gained {time} exiting {corner_name}. You carried more speed through."
```

---

## 6. Same-corner Deduplication

When multiple `CornerLoss` items share the same `corner_id`, combine them
into a single coaching point. This applies to both losses and gains.

### Rules

1. **Dominant phase leads.** The phase with the highest `abs(loss_s)` becomes
   the primary clause. For losses, highest `loss_s` leads. For gains, most
   negative `loss_s` (biggest gain) leads.
2. **The lead sentence uses the time + phase template.** Supporting phases
   are appended as comma-separated detail clauses.
3. **Don't repeat the corner name** for supporting phases.
4. **Connect supporting details with ", and"** before the last one.

### Loss dedup example (from fixture data — turn 3, three phases)

Input: three `CornerLoss` items all with `corner_id = "t3"`:
- `exit_brake`, `loss_s = 0.194`, `exit_distance_delta_m = -4`
- `minimum_speed`, `loss_s = 0.190`, `speed_diff = 10.6 → ~11`, `apex_offset_m = -9`
- `exit_throttle`, `loss_s = 0.179`, `exit_distance_delta_m = -9`

Dominant: `exit_brake` (highest `loss_s = 0.194`).
Time: "two tenths" (round(0.194 * 10) / 10 ≈ 0.2).

> "You lost two tenths exiting turn three. You released the brakes four metres later, carried eleven kilometres per hour less through the apex, and got back on throttle nine metres later."

### Gain dedup example (from fixture data — turn 5, two phases)

Input: two `CornerLoss` items with `corner_id = "t5"`:
- `minimum_speed`, `loss_s = -0.118`, `speed_diff ≈ 3`
- `exit`, `loss_s = -0.105`, `exit_distance_delta_m = 10`

Dominant: `minimum_speed` (most negative `loss_s = -0.118`).
Time: "a tenth" (round(round(0.118, 1), 2) → 0.1).

> "You gained a tenth at the apex of turn five. You carried three kilometres per hour more, and got back on throttle ten metres earlier."

### Combined gain-first example (full utterance)

> "You gained a tenth at the apex of turn five. You carried three kilometres per hour more, and got back on throttle ten metres earlier. You lost two tenths exiting turn three. You released the brakes four metres later, carried eleven kilometres per hour less through the apex, and got back on throttle nine metres later."

---

## 7. Gain-first Ordering

When both gains and losses exist in the same utterance (only applies to
after-lap summaries — corner-exit notes only have losses):

1. **All gains first**, then **all losses**.
2. The two groups are separated by a full stop.
3. Each group may contain multiple corners, each with deduped phrases.

---

## 8. Fuel Phrases

Fuel facts use a completely different structure (`FuelFacts`), so they need
their own mini-phrases. These are simple — no dedup, no phase logic.

| `fuel_status` | Phrase |
|---|---|
| `CRITICAL` | "Fuel critical. Pit this lap." |
| `WARNING` | "Warning: {laps_remaining} laps of fuel remaining, {race_remaining} laps to go." |
| `OK` | "Fuel OK. {laps_remaining} laps remaining, {race_remaining} laps to go." |
| `UNKNOWN` | *(empty string — no data, no utterance)* |

Where:
- `laps_remaining` = `fuel_facts.laps_of_fuel_remaining` (rounded to nearest integer, if None → skip)
- `race_remaining` = `fuel_facts.race_laps_remaining` (integer, if None → skip)

TTS rules apply: spell out numbers 1–10, use "laps" not "L".

### Fuel edge cases

- If `fuel_status` is `UNKNOWN` → return empty string (don't speak).
- If `fuel_status` is `WARNING` or `OK` but `laps_of_fuel_remaining` is None → "Fuel status {status.lower()}. No fuel data available."
- If `fuel_status` is `OK` and margin > 5 laps → just "Fuel OK." (skip the numbers for brevity).
- If `session_type` is not `"race"` → always say "Fuel OK." regardless of status (no race laps remaining to compare).

---

## 9. TTS Output Rules (applied to all phrases)

These rules are baked into the template output, matching the LLM prompt rules
from `prompt_templates.py` rules 9–12:

1. **Numbers 1–10** → spelled out as words: "one", "two", "three", "four",
   "five", "six", "seven", "eight", "nine", "ten". Numbers ≥ 11 stay as
   digits: "155", "11".
2. **Units in full**: "kilometres per hour" (not "km/h"), "metres" (not "m"),
   "seconds" (not "s"), "litres" (not "L").
3. **No abbreviations** — no "vs", "ref", "appx", etc.
4. **No slashes** — no "km/h", "L/lap", etc.
5. **No parentheses or brackets**.
6. **No em-dashes** — use commas instead. Replace "—" with ",".
7. **Gain-first ordering**: when both gains and losses exist, gains come first.
8. **Same-corner dedup**: dominant phase leads, supporting phases are comma-separated clauses, connected with ", and" before the last.
9. **Lead with time**: every coaching point starts with "You lost {time}" or "You gained {time}" — the time value is always first, it's the most actionable number.
10. **Conversational phrasing**: use natural race engineer language: "at the apex of turn three", "braking for turn five", "going into turn one", "exiting turn seven", "getting on the power at turn two".

### Number-spelling helper

```python
_SPELL_OUT = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}

def spell_number(n: int) -> str:
    """Spell out 1-10, keep digits for 11+."""
    return _SPELL_OUT.get(n, str(n))
```

---

## 10. Word-limit Truncation

When the combined utterance exceeds the word limit (`constraints.max_words`,
default 35):

1. Keep the dominant phase of the dominant corner (always the first item after
   dedup and ordering).
2. Drop supporting phases from weakest corners first.
3. Drop entire corners from the end of the utterance if still over limit.
4. Never split a coaching point mid-sentence — drop whole sentences.
5. If even one dominant phase exceeds the word limit, truncate the detail clause
   (e.g., drop the delta measurement, keep just "You lost {time} at the apex of {corner_name}.").

---

## 11. Empty Facts Handling

- **If both `top_losses` and `top_gains` are empty** → return empty string.
- **If all `fuel_status` is `UNKNOWN`** → return empty string.
- Empty string means "don't speak" — the speech queue will skip it.

---

## 12. Complete Phrase Summary

| # | Phrase set | Source data | Phases | Context |
|---|---|---|---|---|
| A | Loss phrases | `CornerLoss`, `loss_s > 0` | 5 phases × 2–3 delta variants | After-lap & corner-exit |
| B | Gain phrases | `CornerLoss`, `loss_s < 0` | 5 phases × 2–3 delta variants | After-lap only |
| C | Same-corner dedup | Multiple items sharing `corner_id` | Combine into one sentence | Both contexts |
| D | Gain-first ordering | Combined gains + losses | Gains group, then losses group | After-lap only |
| E | Fuel statuses | `FuelFacts` | 4 statuses (CRITICAL/WARNING/OK/UNKNOWN) | Fuel calls |
| F | Word-limit truncation | `constraints.max_words` | Drop weakest items first | All contexts |
| G | TTS rules | Applied to all output | Numbers, units, no abbreviations | All contexts |
| H | Time formatting | `loss_s` | Natural spoken tenths/hundredths/seconds | All gain/loss phrases |

Total distinct phrase templates: **10 base phrases** (5 loss + 5 gain), each
with **2–3 delta-detail variants**, plus **time formatting**, **3 fuel phrases**,
dedup/ordering logic, and word-limit truncation.