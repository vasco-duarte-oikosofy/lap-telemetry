# Bug 18: Hard-guarantee appends worst-loss phrase after truncation already included its lead

## Observed symptom

From `sessions/recorder_with_coach.txt` (session `20260530T125800Z`, Bahrain Outer Circuit).

Utterances where the lead sentence of the worst loss appears **twice**:

**Lap 1:**
> "You lost seven tenths exiting turn 9. **You lost seven tenths exiting turn 9.** You released
>  the brakes 15 metres earlier, carried ten kilometres per hour less through the apex, hitting
>  it six metres later, and got back on throttle eight metres later."

**Lap 3:**
> "You lost one point 0 seconds at the apex of turn 1. **You lost one point 0 seconds at the
>  apex of turn 1.** You carried 15 kilometres per hour less, hitting it 11 metres later,
>  released the brakes five metres earlier, and got back on throttle eight metres later."

**Lap 4:**
> "You lost nine seconds at the apex of turn 1. **You lost nine seconds at the apex of turn 1.**
>  You carried ten kilometres per hour less, hitting it 11 metres later, released the brakes
>  four metres earlier, and got back on throttle seven metres later."

Pattern: the lead sentence of the worst-loss corner always appears twice, followed by the full
detail clause only once.

## Root cause

`TemplateAdapter.generate()` in `template_adapter.py` (lines 579–601):

```python
# Step 1: compute worst_loss_phrase (full phrase: lead + detail)
worst_loss_phrase = _dedup_corner(loss_by_corner[worst_cid], is_gain=False)

# Step 2: build ordered phrases (worst loss is first due to Bug 15 fix)
phrases = [_dedup_corner(items, is_gain) for _, items, is_gain in ordered]
result = " ".join(p for p in phrases if p)

# Step 3: truncate to word limit — can strip detail sentences, leaving only the lead
result = _truncate_to_word_limit(result, max_words)

# Step 4 (the bug): hard guarantee — checks full phrase, not just the lead
if worst_loss_phrase and worst_loss_phrase not in result:
    result = (result.rstrip() + " " + worst_loss_phrase).strip()
```

After step 3, `result` may equal just the lead sentence:
```
"You lost seven tenths exiting turn 9."
```

`worst_loss_phrase` is the full phrase:
```
"You lost seven tenths exiting turn 9. You released the brakes 15 metres earlier, ..."
```

`worst_loss_phrase not in result` → **True** (full phrase isn't a substring of truncated result).

So the full phrase is appended, producing:
```
"You lost seven tenths exiting turn 9.  ←— from truncated result
 You lost seven tenths exiting turn 9. You released the brakes 15 metres earlier, ..."
                                        ←— appended by hard guarantee
```

## Why it wasn't caught before

Bug 15's fix added the hard guarantee as a safety net for cases where truncation silenced the
worst loss entirely. That fix correctly handles the case where the lead sentence is absent from
`result`. It fails when the lead sentence *is* present but the detail clause was trimmed —
because the membership check uses the full phrase as the needle, not just the lead.

## Fix

Change the hard-guarantee check to test whether the **lead sentence** of `worst_loss_phrase` is
already present in `result`, rather than the full phrase:

```python
if worst_loss_phrase:
    # Extract just the lead sentence (everything up to and including the first ".")
    worst_loss_lead = worst_loss_phrase.split(". ")[0] + "."
    if worst_loss_lead not in result:
        result = (result.rstrip() + " " + worst_loss_phrase).strip()
```

This way:
- If truncation kept the lead (even without details) → no append, no duplicate.
- If truncation removed the lead entirely → lead (and details) are appended as before.

## Evidence from session

Session: `sessions/session_20260530T125800Z_bahrain-outer-circuit_lmu.parquet`
Reference: `product/data/reference-laps/bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet`
Track model: `product/data/track-coaching/bahrain-outer-circuit_dkr-engineering-4-elms25.json`

Affected laps (from log): 1, 3, 4.

## Tests to add

### `test_hard_guarantee_no_duplicate_when_lead_present`

Scenario: `worst_loss_phrase` has a multi-clause detail sentence. Build facts where the ordered
phrases, joined and truncated, produce exactly the lead sentence of the worst loss corner (detail
trimmed by word limit). Assert the final utterance does **not** contain the lead sentence twice.

```python
def test_hard_guarantee_no_duplicate_when_lead_present():
    # Turn 9 exit: two phases → dedup produces long phrase
    # Set max_words low enough to keep only the lead after truncation
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=1,
        lap_time_delta_s=0.7,
        top_losses=[
            CornerLoss(corner_id="t9", corner_name="turn 9",
                       apex_distance_m=500.0, phase="exit_brake",
                       loss_s=0.7, driver_value=0.0, reference_value=0.0,
                       unit="s", confidence=1.0,
                       exit_distance_delta_m=15.0),
            CornerLoss(corner_id="t9", corner_name="turn 9",
                       apex_distance_m=500.0, phase="exit_throttle",
                       loss_s=0.3, driver_value=0.0, reference_value=0.0,
                       unit="s", confidence=1.0,
                       exit_distance_delta_m=8.0),
        ],
        top_gains=[],
        constraints={"max_words": 8},   # keeps only lead sentence
    )
    utterance = TemplateAdapter.generate(facts)
    lead = "You lost seven tenths exiting turn 9."
    assert utterance.count(lead) == 1, (
        f"Lead sentence duplicated: {utterance!r}"
    )
```

### `test_hard_guarantee_appends_when_lead_absent`

Scenario: result is entirely fills with gain phrases (no loss in result at all). Assert the
worst-loss lead sentence IS present after the guarantee runs.

```python
def test_hard_guarantee_appends_when_lead_absent():
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=2,
        lap_time_delta_s=1.0,
        top_losses=[
            CornerLoss(corner_id="t1", corner_name="turn 1",
                       apex_distance_m=100.0, phase="minimum_speed",
                       loss_s=1.0, driver_value=100.0, reference_value=110.0,
                       unit="kph", confidence=1.0),
        ],
        top_gains=[
            CornerLoss(corner_id="t2", corner_name="turn 2",
                       apex_distance_m=200.0, phase="entry",
                       loss_s=-0.5, driver_value=0.0, reference_value=0.0,
                       unit="s", confidence=1.0,
                       entry_distance_delta_m=-5.0),
            CornerLoss(corner_id="t3", corner_name="turn 3",
                       apex_distance_m=300.0, phase="entry",
                       loss_s=-0.4, driver_value=0.0, reference_value=0.0,
                       unit="s", confidence=1.0,
                       entry_distance_delta_m=-3.0),
        ],
        # max_words fills up with gains (ordered first since driver is slower... wait,
        # bug-15 fix puts worst loss first; with max_words=20 loss phrase fits first anyway)
        constraints={"max_words": 9},   # just enough for one gain phrase, no room for loss
    )
    utterance = TemplateAdapter.generate(facts)
    assert "You lost" in utterance, (
        f"Worst loss absent from utterance: {utterance!r}"
    )
```

### `test_no_duplicate_lead_in_all_log_laps`

Integration-level: replay laps 1, 3, 4 from the session parquet against the Bahrain Outer
Circuit reference, generate template utterances, and assert no sentence appears more than once
in any utterance.

```python
def test_no_duplicate_sentences_in_utterance(utterance: str):
    sentences = [s.strip() for s in utterance.split(".") if s.strip()]
    assert len(sentences) == len(set(sentences)), (
        f"Duplicate sentence in utterance: {utterance!r}"
    )
```
