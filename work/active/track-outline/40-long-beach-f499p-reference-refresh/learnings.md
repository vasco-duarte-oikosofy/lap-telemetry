# Learnings

- A source can recover while being inspected: the initial partN listing changed
  to a finalized canonical parquet. The contiguous-shard check failed safely;
  switching to the stable recovered file avoided mixing snapshots/partial merges.
- in_progress=true in an abandoned sidecar is not proof of active writing.
  Record provenance and verify immutable source hashes instead of editing it.
- Nearest-event matching plus --allow-unmatched does NOT protect flat/compound
  geometry. T3 stole T4, and T10 stole T11 in the read-only default preview.
  Explicit preservation must skip claiming events, not restore geometry afterward.
- For this refresh, preserving t3/t7/t10/t11 lets the other seven official turns
  match cleanly. Signal inspection confirms retained flat zones are still full
  throttle/no brake, so preservation is evidence-backed, not blind retention.
- Committed model ref paths need as_posix() on Windows. Also normalize audit path
  keys before excluding the intended changed files; mixed slash styles otherwise
  falsely report the deliberately removed/replaced target as collateral damage.
- General Long Beach tests originally pinned lap 10's filename/time. Resolving
  through the current model and asserting authoritative consistency lets them
  survive legitimate faster-reference updates without losing geometry guards.
- A retained outline's old reference is historical provenance, not its new turn
  anchor source. Pin the old source's Git revision and record the current anchor
  ref separately rather than claim unchanged coordinates came from a new lap.
- The folder validator can exceed a combined 180 s tool budget. Running it
  separately/unbuffered completes successfully; don't skip it or change timing
  definitions to make a faster but less rigorous validation.
- Live coach reference/model caches require restart after replacing the ref file.
  Updating data on disk alone can leave a running process pointing at the deleted
  superseded filename. TinyPedal likewise needs map reload for changed fractions.
