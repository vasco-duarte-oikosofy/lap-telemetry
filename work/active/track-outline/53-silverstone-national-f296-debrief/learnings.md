# Learnings — Slice 53 (Silverstone National / F296 debrief)

## The debrief is the cheapest acceptance test for a new coaching model

A new (track, car) pair can pass every data-contract test and still be useless to
the driver. Two debrief runs answered in ten minutes what no assertion can:
the four corners the detector refreshed own the whole gap, and the two flat bends
the model *cannot* detect (Maggots, Woodcote) rank **last** in both sessions —
Maggots is 0.025 s/lap with no braking in the data and the same gear as the
reference. If the seed/preserve decision had been wrong (e.g. preserving all six
corners, or refreshing the flats onto a neighbour's event), the priorities would
have pointed at Maggots and the driver would have chased a corner that costs
nothing. **Run the debrief at the end of every new-combo slice.**

## Cross-session agreement is the real validation

One session can rank corners by noise. Two sessions with different characters
(9 erratic quali laps vs 31 consistent race laps) agreeing on Becketts +
Luffield at the top, with the same mechanism (early brake release / low minimum
speed), is what makes the model trustworthy. Worth recording both, not one.

## The REPL writes next to its *input*, not where you want it

`debrief <session>` with no `--out` puts `<stem>_plan.md` and
`<stem>_debrief.json` beside the session. For `sessions/*.parquet` that means
writing two untracked files into a curated directory — they were moved into the
slice artifacts straight after the run. `--report-only` honours `--out`; the
conversation path only uses it for `run_repl`'s `out_dir`, so pipe-driven runs
need the file move either way.

## A 4 m exit window is measurable but thin

Slice 52 deliberately refreshed Copse to `206/368/372` (exit = throttle onset,
4 m past the apex), which is the corpus norm. The debrief shows the practical
consequence: in quali, Copse became priority #1 on an `exit_brake` fact backed
by **3 laps**, because the exit phase has almost no distance to average over.
The number is real (161.8 vs 166.4 km/h onto the straight) and the advice is
sane, but this is exactly the "if Copse feels noisy, curate the exit by hand"
deferred item — and it is a *curation* job, not a reason to re-run the updater.

## `time_available_s` can clamp to 0.000 when the best lap is the reference

Quali reported `envelope_lap_s 54.676` — **slower** than the session's own best
(0:54.295) — so `time_available_s` clamps to 0.000 while the spread is 2.115 s.
The report then says "0.000 s is sitting in repeatability alone", which reads
oddly next to a 2.1 s spread. The race session was consistent (envelope 54.540 <
best 54.696). Left as a finding: a `min(envelope, best)` guard in
`session_facts` would make the quali case read honestly. Do not "fix" it by
lowering the reference — the reference lap legitimately came from this session.

## Mechanics

- LLM path works with the repo config (`provider = ollama`,
  `glm-5.3-flash:cloud`); `litellm` is **not** installed on this machine and is
  not needed for the ollama provider (`openai` is enough).
- Pipe the scripted turns in (`< inputs.txt > conversation.txt`); `input()`
  echoes `You:   ` into the transcript, which is why the conversation file reads
  `You:   Coach: …`.
- Both runs exit 0 with a stderr that is empty — check `conversation.err` size
  (0 bytes) rather than eyeballing the transcript for warnings.
