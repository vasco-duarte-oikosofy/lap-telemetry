# Learnings — Slice 07: Corner-Exit Coaching

## What surprised me

1. **CoachTap needed a full rewrite.** The original `CoachTap` was simple (bus → LapDetector → LiveFactGenerator → SpeechQueue). With three modes (LAP/TURN/ALL), the tap now has to:
   - Subscribe its own `_on_frame` callback to the bus (instead of subscribing LapDetector directly)
   - Conditionally feed `CornerExitDetector` only in TURN/ALL modes
   - Manage a pending corner utterance held until a speech window opens
   - Clear pending corner utterances when a LapCompleted event arrives (priority)

2. **CornerExitDetector needs `notify_lap_completed()` separately from `feed()`.** The detector tracks whether at least one lap has been completed (to skip first-lap corner exits). This is called by CoachTap when `_on_lap_completed` fires.

3. **Anti-chatter uses `session_time_s`, not frame count.** The cooldown is measured in wall-clock sessions seconds, which is independent of frame rate. After a corner exit event, 8 seconds must pass before another fires.

4. **SpeechWindowChecker needs two modes**: explicit `straight_zones` from the track model, and inferred zones from gaps between corners. The inferred mode works for tracks that don't define `straight_zones`.

5. **The `_on_frame` callback pattern in CoachTap** is cleaner than subscribing LapDetector and CornerExitDetector separately to the bus, because it lets us conditionally feed the corner detector based on mode.

6. **LiveCornerFactGenerator uses `LapDetector.current_lap_frames`** — the rolling buffer of frames for the current lap. This is passed from CoachTap to the generator, which filters frames to only those up to `EXIT_WINDOW_M` (150m) past the corner exit.

7. **Loss thresholds for corner-exit coaching are stricter than lap summaries.** `MIN_LOSS_S_MINIMUM_SPEED = 0.1` and `MIN_LOSS_S_ENTRY_EXIT = 0.05` prevent coaching noise on corners where the driver was close to the reference.

8. **Exit detection search window was too narrow.** `find_exit_points()` searched only from `apex_s_m` to `s_end_m`. For short corners (T3 at Barcelona: apex-to-end = 2m), both driver and reference real exit transitions (brake release, full throttle) occur **past the corner boundary** on the early straight. Both fallbacks produced the same boundary value, yielding `exit_distance_delta_m = 0.0` — a meaningless result. Fix: added `exit_search_past_end_m` (default 50m) to `PhaseDetectionThresholds`, extending the search past `s_end_m`.

9. **`test_losses_delta_time` T3 exit assertion (`delta < 0`) was revealing a real algorithm bug, not a test bug.** The test correctly asserted that for a known loss, `exit_distance_delta_m` should be negative (driver exited later). The `0.0` result was the algorithm giving up too early, not wrong test expectations. See L14 in TESTING_LESSONS.md.