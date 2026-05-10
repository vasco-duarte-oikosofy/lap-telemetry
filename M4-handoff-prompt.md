We're starting M4 of the lap-telemetry project. Everything you need is in the
repo — read these in order before writing any code:

1. CLAUDE.md  — current state, command surface, key facts
2. DESIGN.md  — architecture, file format, phasing. M4 scope is in §7
                (single HTML/JS/CSS comparison app, two uploads, single
                speed-vs-distance plot). §4.2 describes the analyzer
                vision: distance-aligned, 1 m bins, Δt by integrating
                1/speed. §10 has two reader-side oddities (O1, O2) from
                M3 that you should consider folding into M4.
3. m3-plan.md — the previous milestone's plan and live-test report. Read
                §E1, §E2 (chronological segments) and §10/O1, O2 (sector
                lookup timing) — those are the reader concepts you'll
                inherit.

There is no m4-plan.md yet. **Your first job is to write one** — same shape as
m3-plan.md, no implementation until I've ack'd it.

Project background you won't get from the files:
- M3 shipped 2026-05-10 with a live test at Circuit de Barcelona, LMP3
  (DKR Engineering #4:ELMS25, default_LMP3_1wing.svm). The recorder is now
  long-running: started before the sim, retries the probe forever, captures
  one session file per (track, vehicle), survives hard kills with a fully
  identifying sidecar via in-progress + atomic-replace writes.
- The two SHM-timing oddities (O1, O2 in DESIGN §10) showed up on the live
  test. They're reader bugs: first-frame `mLastSector*` lookups catch the
  SHM mid-update, so some laps show `-` and consecutive laps can display
  identical S1/S2 to the millisecond. Proposed fix is "sample inside the
  next segment, not the literal first frame." Worth folding into M4 since
  M4 is also reader-side — the comparison app will want correct per-lap
  sector data to label laps in the picker, and a debug pass on the parquet
  data costs almost nothing once you're already in the analyzer code.
- Existing recordings are in `./sessions/`. The cleanest one for M4
  development is `session_20260510T093245Z_circuit-de-barcelona_lmu.parquet`
  — 6-lap LMP3 run with laps 2–5 timed clean, 28,493 rows. Use it as the
  "session" upload fixture. There's also a 7-lap recovered session
  `session_20260510T091432Z_circuit-de-barcelona_lmu.parquet` that
  contains a Restart Session mid-recording (lap_number sequence
  …6,7,0,1) — use it for testing that the app handles the
  chronological-segment model from M3.
- Naming convention: a "lap" in the user's mental model is a chronological
  segment, not a unique `lap_number`. Two segments with the same
  `lap_number` (post-restart) are two distinct laps to compare. The
  app's lap picker should display them unambiguously — likely a
  1-indexed chronological position with the lap_number shown alongside,
  since `lap_number` alone isn't a key.

**The M4 requirement (from the user, verbatim):**

> M4 is "the app". For now, a single HTML/JS/CSS file that will handle the
> whole UI. I can upload a session file, and a reference lap. Then I can
> compare each lap in the session file to the loaded reference lap.
>
> For now, those would be 2 separate loads: 1 for session, 1 for reference
> lap. Later, we will need to improve this. So document this for M5.

What M4 should produce (per the requirement + DESIGN §7):
- A single self-contained HTML/JS/CSS file (no server, no build step) that
  the user opens in a browser. Two file inputs: one for the session
  parquet, one for the reference-lap parquet. After both load, the user
  picks any lap from the session and the app overlays the chosen session
  lap against the reference lap on a single speed-vs-distance plot.
- Distance-aligned resampling onto a common 1 m bin grid so the two
  laps share an x-axis. Don't trust raw `lap_distance_m` deltas —
  interpolate.
- Full plot stack (throttle/brake, RPM/gear, steering, slip, Δt panel)
  is M5; M4 is just speed-vs-distance to validate the upload + parse +
  resample + render path end-to-end.

How I want you to work:
- Start by drafting `m4-plan.md` in the same shape as `m3-plan.md`: scope
  pieces (e.g. A. resampler, B. plot window, C. fold in O1/O2), steps,
  acceptance test. Confirm it back to me in 3-4 bullets — but I'll be
  **AFK for a few hours** when you start, so once you've drafted the
  plan, **proceed straight to implementation and self-test**; don't
  block waiting for me. (See the AFK testing section below for what
  "self-test" looks like.) When I get back I'll review the plan and
  the results together. If the plan needs to change after my review,
  the implementation rewinds; that's fine.
- Important environment quirks (also in
  .claude/projects/.../memory/MEMORY.md):
  - Don't try to script Ctrl+C to background tasks via AttachConsole +
    GenerateConsoleCtrlEvent — it kills the Claude Code session itself.
    Use TaskStop and rely on the orphan-recovery path, or ask me to
    Ctrl+C from my own terminal.
  - This is Windows + PowerShell, but Bash is available too.
  - The `lap-telemetry` console script on the user's PATH is the
    *system Python 3.10* install (not the .venv — that one's missing
    pyarrow). Run commands as `lap-telemetry ...` and they'll resolve
    to the right interpreter.
- Before commit: run `lap-telemetry summary sessions/<latest>.parquet`
  as a smoke test to confirm the existing reader still works after
  any changes you make to summary.py. If you also tweak the recorder
  (likely not in M4), `lap-telemetry record --once` is the smoke test
  for that.
- The app is interactive in a browser, but I won't be around to drive
  it — see the AFK testing section below.

## Testing while I'm AFK

I'll be away from the keyboard for a few hours. **The app must be
self-tested end-to-end before I get back.** "Looks plausible in code"
is not enough — you need evidence the upload + parse + resample +
render path actually works in a browser. Concretely:

1. **Build a reference-lap fixture.** The user-facing two-upload flow
   needs a single-lap parquet for the "reference lap" input. Write a
   tiny throwaway Python helper (don't ship it as a CLI; a script or
   one-liner is fine) that filters one of the existing session
   parquets in `./sessions/` down to a single chosen lap and writes
   it as e.g. `./sessions/reference_lap_<track>_<lap>.parquet`. Use
   the fastest lap from the 09:32:45 session as the reference (lap 5
   at 1:37.834 was the best clean lap — the chronological-segment
   model from M3 will tell you which row indices). Save the helper
   under `scripts/` or similar so it's reproducible.

2. **Drive the app headlessly.** Use Playwright (or Puppeteer; pick
   what installs cleanly on Windows + Node). Open the HTML file via
   `file://`, programmatically attach the session parquet to the
   first file input and the reference-lap parquet to the second,
   wait for both to load, exercise the lap picker, and verify
   rendering. Capture:
   - Screenshots at each state: initial empty page, after session
     load (picker populated), after reference load, after picking
     the target lap (plot rendered).
   - The full browser console log to a file. Any error or warning
     is a failure to investigate, not ignore.
   - DOM/canvas assertions where they make the test crisper:
     "picker has 7 options" for the restart-session file,
     "two `<path>` elements present in the SVG plot," etc.

3. **Cross-check the resampler.** The browser-side resampler should
   produce the same 1 m-binned speed array as a Python equivalent
   you write alongside (a few lines of pyarrow + numpy interp). Run
   both on the same lap, assert max|diff| is below some small
   threshold (e.g. 0.1 km/h) and write the comparison to a report
   file. This is the single test that catches "I shipped a working
   plot of wrong data."

4. **Run the test against both fixtures:** the clean 6-lap
   `session_20260510T093245Z_*` AND the restart-session
   `session_20260510T091432Z_*`. The second one is the reason the
   chronological-segment model exists — if the lap picker shows
   `…6, 7, 0, 1` in driving order and the speed traces line up with
   their `lap_distance_m`, the model survived contact with the UI.

5. **Leave evidence I can read when I return.** Drop everything into
   `m4-test-report/` (or similar — pick a name and stick with it):
   the screenshots, the console log, the resampler diff numbers,
   any Playwright traces, and a `REPORT.md` summarising what you
   ran, what passed, what didn't, and what you fixed in response.
   Don't commit this directory — add it to `.gitignore` if needed.
   I'll read it cold; write it so I can.

6. **If a test fails, diagnose and fix, then re-run.** Don't stop
   and wait — that's the whole point of the AFK setup. Only stop
   if you hit something that genuinely needs a decision from me
   (architectural fork, the spec is ambiguous, you can't make the
   resampler match within tolerance and you've ruled out the
   obvious causes). In that case, leave a clearly-marked
   `BLOCKED.md` in the test report directory with the question and
   what you tried.

7. **Smoke the recorder too.** `lap-telemetry record --once`
   against live LMU is a 3-second sanity check that you didn't
   break anything outside M4 scope. LMU was running when I left
   (Circuit de Barcelona, LMP3) — if it's still up when you smoke
   test, that's free.

Don't background-task a browser window. Playwright launches the
browser and tears it down inside the test process; that's the
correct path.

Start by reading the three files above plus this prompt, then draft
m4-plan.md, confirm the plan back to the conversation in 3-4 bullets
for my later review, and proceed straight into implementation and
self-test per the AFK section above.
