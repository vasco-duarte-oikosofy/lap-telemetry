# Learnings — Slice 08: interactive debrief

- **Targets must only point upward.** The first plan said "Target: 65.0 km/h at
  the apex, against 71.0 today" for Bretelle — the driver was already faster at
  the apex than the reference, so that is not a target. A speed target is only
  emitted when the driver's value is below the reference's; otherwise the target
  is the loss itself ("no more than 0.294 s lost here").
- **"3th" and "2th".** Ordinals were being built with a bare `f"{n}th"`. The
  helper already existed in `session_priorities`; it is now public (`ordinal`)
  and reused, so gear targets read "3rd, against 2nd".
- **The evidence place matters.** A target that says "69.0 km/h at the apex" for
  a brake-release loss is wrong about where the number comes from. The phase
  decides the wording: at the apex, at the braking point, at the brake release,
  onto the straight.
- **Recording what was shown is part of the audit.** The transcript keeps the
  corner facts block as a `facts` turn next to the driver's question and the
  coach's answer, so a future reading of the JSON can see exactly what the coach
  was looking at when it said something.
- **`/plan` and `/save` are driver turns too.** Without recording them the
  transcript reads as if targets appeared from nowhere.
- **The REPL's opening move is the debrief itself**, not a prompt waiting for the
  driver. `run()` asks "give me the debrief" before reading any input, which also
  means the piped-stdin path produces something useful with a single newline.
- **Saving on quit is not optional.** A driver will close the terminal; `/quit`,
  EOF and StopIteration all end the same way — transcript written, plan written if
  it does not exist yet.
