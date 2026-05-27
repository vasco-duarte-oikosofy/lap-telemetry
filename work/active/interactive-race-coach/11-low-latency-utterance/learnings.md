# Slice 11 Learnings: Low-Latency Utterance Generation

## Template phrase design

1. **Same-corner dedup is the hardest part.** When multiple phases (exit_brake, minimum_speed, exit_throttle) share a corner_id, they must be combined into one sentence. The dominant phase (highest abs(loss_s)) leads, and supporting phases become detail clauses joined with ", and" before the last. The lead sentence only has time + location; details follow as "You {detail1}, {detail2}, and {detail3}." — a two-sentence structure.

2. **minimum_speed detail needs "through the apex" suffix when it's NOT the dominant phase.** In dedup context, if minimum_speed is a supporting phase (not dominant), the detail clause "carried X kilometres per hour less" needs "through the apex" appended to clarify which phase the detail refers to. When minimum_speed IS dominant, the lead sentence already says "at the apex of {corner_name}" so the suffix is redundant.

3. **Generic `exit` phase can have `exit_distance_delta_m`.** The data fixture shows `exit` phase items with `exit_distance_delta_m` values. The template-phrase-spec treats `exit` as a fallback for when no specific brake/throttle data is available, but if `exit_distance_delta_m` IS present, it should be interpreted as throttle timing — same logic as `exit_throttle`.

4. **Word-limit truncation can drop entire coaching points.** With `max_words=35`, the template adapter produces phrases that are typically 20–35 words per coaching point. When multiple corners are present, the combined utterance can easily exceed the word limit. The truncation drops whole sentences from the end (weakest corners first), which means the loss portion of a mixed gains/losses utterance may be dropped entirely. This is correct per spec.

5. **`format_time(3.50)` returns "four seconds"** because `int(round(3.50))` = 4. Time values ≥ 2.0 are rounded to the nearest integer for spoken English. This matches the spec's `{n} seconds` rule.

## Template adapter architecture

6. **Separate single-phrase builders from dedup detail extractors.** Single phases use full-sentence builders (`_loss_minimum_speed()`, etc.) that produce complete sentences with a lead "You lost/gained" clause. Dedup uses a separate set of detail extractors (`_loss_detail()`, `_gain_detail()`) that return verb phrases without "You" or period — then the `_dedup_corner()` function assembles them as "Lead sentence. You {detail1}, and {detail2}."

7. **Lead location depends on the dominant phase and delta availability.** For `entry` phase, the location phrase switches between "braking for {corner}" (when delta is present) and "going into {corner}" (when no delta). Similarly for other phases. The `_lead_location()` helper handles this.

8. **Fuel phrases have several edge cases.** "UNKNOWN" → empty string (don't speak). "CRITICAL" → always "Fuel critical. Pit this lap." Non-race sessions → always "Fuel OK." regardless of status. `laps_remaining is None` → fallback message. Margin >5 laps → just "Fuel OK." for brevity.

## CLI plumbing

9. **`--coach-mode off` needs an early return.** When mode is OFF, `live_coach.py` skips creating CoachTap, SpeechQueue, and TTS adapter entirely, and starts the recorder directly. This is the simplest possible change — no new process or entry point, just an early branch in the existing `main()`.

10. **`_dict_to_facts()` in `generate_utterance.py` is reused for LOCAL_LLM mode.** When `corner_utterance_fn` needs to override `max_words` for a different word limit, it needs to reconstruct a `LapComparisonFacts` from the dict. The existing `_dict_to_facts` function in `generate_utterance.py` is imported for this purpose. This import path (`from lap_telemetry.coach.generate_utterance import _dict_to_facts`) is used in `live_coach.py` for the LOCAL_LLM mode corner-utterance override.

## Pitfalls

11. **Pre-existing `test_facts_inspector.js` failure.** This test crashes with `ERR_INVALID_ARG_TYPE` — it's unrelated to this slice and was failing before these changes.

12. **Corner names with em-dashes.** The barcelona fixtures use corner names like "Turn 3 — Renault" which contain em-dashes. The template adapter doesn't strip these (they come from the track model). The spec says to replace em-dashes with commas in TTS output, but this should be handled at the track model level, not in the template adapter — the template adapter receives whatever `corner_name` the facts provide.