 We're starting M3 of the lap-telemetry project. Everything you need is in the
  repo — read these in order before writing any code:

  1. CLAUDE.md  — current state and command surface
  2. DESIGN.md  — architecture, file format (M2 just shipped, M3 scope is in §7)
  3. m3-plan.md — the implementation plan; this is your source of truth for scope,
                  steps, and acceptance criteria. The sidecar metadata recovery
                  piece is REQUIRED — that's the whole point of the milestone.

  Project background you won't get from the files:
  - M2's live acceptance test passed but exposed the metadata-loss bug:
    hard-killed sessions are recovered from .partN.parquet shards, but the
    rebuilt sidecar shows track as the slug, vehicle_name as "unknown", and no
    ended_utc. M3 closes that hole by persisting the sidecar throughout the
    session, not just at close.
  - Sector capture (the user-visible feature) is the second piece, and is much
    smaller — three Parquet columns and a summary-table column.

  How I want you to work:
  - Implement piece A (recoverable metadata) first, end-to-end, before touching
    piece B (sectors). They are independent.
  - The acceptance test in m3-plan.md requires a live LMU session. I'll run the
    recorder myself (LMU is on this machine); ask me when you're ready and I'll
    drive a couple of laps + do the hard-kill recovery test.
  - Important environment quirks (also in .claude/projects/.../memory):
    - Don't try to script Ctrl+C to background tasks via AttachConsole +
      GenerateConsoleCtrlEvent — it kills the Claude Code session itself.
      Use TaskStop and rely on the orphan-recovery path, or ask me to Ctrl+C
      from my own terminal.
    - This is Windows + PowerShell, but Bash is available too.
  - Before commit: run `lap-telemetry record --once` as a smoke test to confirm
    the recorder still starts and reads a frame.

  Start by reading m3-plan.md and confirming the plan back to me in 3-4 bullets,
  then begin step 1 (sector capture in connect.py — even though piece A lands
  first, the Frame/schema additions for sectors share the same files so it's
  fine to do them in the order the plan lists). Stop and check in with me before
  the live acceptance test.