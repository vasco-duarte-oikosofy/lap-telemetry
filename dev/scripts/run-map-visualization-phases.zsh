#!/usr/bin/env zsh
# run-phases.zsh — orchestrate the track-heatmap spec via the pi.dev harness.
#
# Pi (https://pi.dev) is the agent harness. It is intentionally minimal:
# four core tools (read, write, edit, bash) and disk-based markdown files for
# state. That matches our spec's phase-folder approach perfectly.
#
# Each subphase = one fresh pi invocation in print/JSON mode with:
#   - prompt.md piped on stdin (avoiding the --- frontmatter no-op bug #4163)
#   - --no-session to keep phases isolated (we manage handoff via files, not pi sessions)
#   - --mode json so the loop can verify the agent actually ran a turn
#   - --offline + PI_SKIP_VERSION_CHECK=1 for hermetic, network-free runs
#
# Standing rules (the XP working agreements) live in AGENTS.md at the repo root.
# Pi auto-loads AGENTS.md, so we do not re-inject the rules into every prompt.
#
# Loop's job (NOT the agent's):
#   - Run the test suite. Exit code is the gate.
#   - Check no file exceeds 437 lines.
#   - Check the agent produced learnings.md and handoff.md.
#   - Check pi actually emitted an agent_end event (defends against silent no-ops).
#   - Compose the next phase's prompt from the spec excerpt + previous handoff.
#   - Halt on failure. Resume on re-run.

set -euo pipefail

# ---------- Config ----------------------------------------------------------

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel)}"
PHASES_DIR="$REPO_ROOT/phases"
SPEC_FILE="$REPO_ROOT/docs/track-heatmap-spec.md"
AGENTS_FILE="$REPO_ROOT/AGENTS.md"
PLAN_FILE="$PHASES_DIR/PLAN"
CURRENT_FILE="$PHASES_DIR/CURRENT"
MAX_FILE_LINES=437
TEST_CMD="${TEST_CMD:-npm test}"

# Pi configuration. Tweak these per project.
PI_BIN="${PI_BIN:-pi}"
PI_MODEL="${PI_MODEL:-qwen3.5:cloud}"
PI_EXTRA_ARGS=("${(@s/ /)PI_EXTRA_ARGS:-}")
export PI_SKIP_VERSION_CHECK=1
export PI_OFFLINE="${PI_OFFLINE:-0}"

# ---------- Plumbing -------------------------------------------------------

log()  { print -P "%F{cyan}[orchestrator]%f $*"; }
warn() { print -P "%F{yellow}[orchestrator]%f $*" >&2; }
fail() { print -P "%F{red}[orchestrator]%f $*" >&2; exit 1; }

require_bin() {
  command -v "$1" >/dev/null 2>&1 || fail "Required binary not found: $1"
}

bootstrap() {
  require_bin "$PI_BIN"
  require_bin git
  require_bin jq
  [[ -f "$SPEC_FILE" ]] || fail "Spec not found at $SPEC_FILE"
  mkdir -p "$PHASES_DIR"

  if [[ ! -f "$AGENTS_FILE" ]]; then
    log "Writing standing rules to $AGENTS_FILE (pi auto-loads this at startup)."
    write_agents_file
  fi

  if [[ ! -f "$PLAN_FILE" ]]; then
    log "Initializing $PLAN_FILE with the spec's subphase order."
    cat > "$PLAN_FILE" <<'EOF'
00-layout
00.1-renderer-responsive
00.5-walking-skeleton
01a-heatmap-single-lap
01b-s-alignment
01c-dual-ribbon
02-zoom-pan
03-legend
04-hover
05a-linked-highlight
05b-click-to-scrub
06.1-dpr-aware
06.2-perf-pass
06.3-cbsafe-ramp
06.4-keyboard
06.5-zoom-buttons
06.6-minimap
06.7-auto-pan
06.8-sector-jump
EOF
  fi

  [[ -f "$CURRENT_FILE" ]] || head -n1 "$PLAN_FILE" > "$CURRENT_FILE"
}

write_agents_file() {
  cat > "$AGENTS_FILE" <<'EOF'
# AGENTS.md — standing rules for every phase of this project

These rules apply to every commit you make, on every phase. They override
convenience. Pi loads this file automatically at startup; you do not need
to be reminded of these rules in each prompt.

## XP working agreements

1. **One subphase at a time.** Never bundle two subphases into one delivery.
2. **Test-first.** Write the failing test before the code that makes it pass.
3. **Commit cadence: small and green.** Many small commits per subphase, each
   one passing the existing test suite. No "WIP" commits.
4. **Refactor commits are separate from behavior commits.** Refactor commits
   start with `refactor:` and must not change rendered output.
5. **YAGNI is an active veto.** No abstractions or "while I'm here" cleanups
   beyond what this subphase needs.
6. **The simplest thing that could possibly work.** Optimize only when a
   later subphase reveals a real problem.
7. **Spike, then stabilize.** For unknowns, write a throwaway spike, learn,
   throw it away, then implement properly with tests. Do not ship the spike.
8. **Stop at green.** When this subphase's acceptance passes, commit, write
   your handoff, exit. Do not start the next subphase.
9. **When in doubt, ask.** If anything is ambiguous, STOP and write the
   question to `phases/<this-phase>/QUESTION.md` instead of guessing.
10. **Narrate decisions in commit messages.** Explain *why*, not just *what*.

## File architecture

- Follow the existing file architecture. Read three nearby files before
  adding a new one.
- Files should be small and coherent. Default ceiling: 200 lines per file.
- **Hard ceiling: 437 lines per file. No file may exceed this, ever.**
- One file, one job.

## Required artifacts at end of every phase

You are not done until all of these exist:

1. `npm test` (or whatever `TEST_CMD` is configured) exits 0.
2. `phases/<this-phase>/learnings.md` — what surprised you, anything the
   next agent needs to know that is not in the spec.
3. `phases/<this-phase>/handoff.md` — concrete state: what is on disk now,
   what feature flags are live, new helpers worth knowing about, deferred
   TODOs.
4. Commits on branch `phase/<this-phase>`, with `refactor:` prefixes where
   appropriate.

## What you should NOT do

- Do not start a subphase other than the one named in your current prompt.
- Do not modify `AGENTS.md` or `docs/track-heatmap-spec.md` without being asked.
- Do not run `pi update`, `pi install`, or any pi self-modification commands.
- Do not exceed 437 lines in any file. Not even temporarily.
- Do not write a generic abstraction when a specific implementation suffices.
EOF
}

# ---------- Per-phase steps ------------------------------------------------

prepare_prompt() {
  local phase_id="$1"
  local phase_dir="$PHASES_DIR/$phase_id"
  mkdir -p "$phase_dir"

  local prev_id prev_handoff=""
  prev_id=$(awk -v cur="$phase_id" '$0==cur{print prev; exit} {prev=$0}' "$PLAN_FILE")
  if [[ -n "$prev_id" && -f "$PHASES_DIR/$prev_id/handoff.md" ]]; then
    prev_handoff="$PHASES_DIR/$prev_id/handoff.md"
  fi

  # IMPORTANT: prompt must not start with `---` due to pi issue #4163
  # (silent no-op). We start with a `#` header to guarantee safety.
  {
    print "# Phase $phase_id — your task"
    print
    print "You are working on subphase **$phase_id** of the track-heatmap spec."
    print "Open \`$SPEC_FILE\` and locate the section for phase $phase_id."
    print "Implement ONLY that section."
    print
    print "Standing rules (XP working agreements, file architecture, required"
    print "artifacts, things you must not do) are in \`AGENTS.md\` at the repo"
    print "root. Pi has already loaded them. Follow them."
    print
    if [[ -n "$prev_handoff" ]]; then
      print "## Handoff from previous phase ($prev_id)"
      print
      cat "$prev_handoff"
      print
    fi
    print "## Branch"
    print
    print "You are on branch \`phase/$phase_id\` (the orchestrator created it)."
    print "Make small commits on this branch. Do not push, do not merge."
    print
    print "## When you are done"
    print
    print "Write \`phases/$phase_id/learnings.md\` and \`phases/$phase_id/handoff.md\`,"
    print "verify \`$TEST_CMD\` is green, then exit. The orchestrator will run"
    print "the test suite and the file-size check itself — your exit + the"
    print "artifacts on disk are the signal of completion."
    print
    print "If anything is ambiguous, write the question to"
    print "\`phases/$phase_id/QUESTION.md\` and exit. The orchestrator will halt"
    print "and surface it to a human."
  } > "$phase_dir/prompt.md"

  log "Prompt prepared at $phase_dir/prompt.md"
}

run_agent() {
  local phase_id="$1"
  local phase_dir="$PHASES_DIR/$phase_id"
  local events_file="$phase_dir/pi-events.jsonl"
  local stderr_file="$phase_dir/pi-stderr.log"

  git checkout -B "phase/$phase_id" >/dev/null 2>&1 \
    || fail "Could not create branch phase/$phase_id"

  log "Spawning pi for $phase_id (model=$PI_MODEL, mode=json, no-session)"

  # Pipe the prompt via stdin instead of -p "..." to dodge issue #4163
  # (prompts starting with --- silently no-op). Stdin path is robust.
  local pi_args=(
    --mode json
    --no-session
    --model "$PI_MODEL"
    -p ""
  )
  if [[ "$PI_OFFLINE" == "1" ]]; then
    pi_args+=(--offline)
  fi
  if (( ${#PI_EXTRA_ARGS[@]} > 0 )) && [[ -n "${PI_EXTRA_ARGS[1]:-}" ]]; then
    pi_args+=("${PI_EXTRA_ARGS[@]}")
  fi

  if ! cat "$phase_dir/prompt.md" \
       | "$PI_BIN" "${pi_args[@]}" \
       > "$events_file" 2> "$stderr_file"; then
    warn "pi exited non-zero for $phase_id. stderr:"
    cat "$stderr_file" >&2
    fail "Halting. Inspect $phase_dir and the working tree."
  fi

  log "pi exited cleanly. Events captured at $events_file"
}

# ---------- Gates (the loop runs these, NOT the agent) ----------------------

gate_agent_actually_ran() {
  # Defends against pi issue #4163 (silent no-op exit 0 when prompt starts
  # with `---`) and similar future failures. We require pi's JSON event
  # stream to contain at least one agent_end / turn_end / response event.
  local phase_id="$1"
  local events_file="$PHASES_DIR/$phase_id/pi-events.jsonl"

  [[ -s "$events_file" ]] || fail "Pi emitted no events for $phase_id (silent no-op?)"

  local turn_count
  turn_count=$(jq -rs '
    [.[] | select(.type=="agent_end" or .type=="turn_end" or .type=="response")]
    | length
  ' "$events_file" 2>/dev/null || print 0)

  if (( turn_count == 0 )); then
    warn "Pi event stream contains no agent_end/turn_end/response events."
    warn "This is the signature of issue #4163 or a similar silent failure."
    warn "Events file: $events_file"
    fail "Halting. Pi did not actually run."
  fi
  log "Pi ran $turn_count turn(s)."
}

gate_question_raised() {
  local phase_id="$1"
  if [[ -f "$PHASES_DIR/$phase_id/QUESTION.md" ]]; then
    warn "Agent raised a question for $phase_id:"
    print "" >&2
    cat "$PHASES_DIR/$phase_id/QUESTION.md" >&2
    print "" >&2
    warn "Answer it (edit the spec or the handoff), delete QUESTION.md, re-run."
    exit 2
  fi
}

gate_artifacts_present() {
  local phase_id="$1"
  local phase_dir="$PHASES_DIR/$phase_id"
  [[ -f "$phase_dir/learnings.md" ]] || fail "Missing $phase_dir/learnings.md"
  [[ -f "$phase_dir/handoff.md"  ]] || fail "Missing $phase_dir/handoff.md"
  [[ -s "$phase_dir/learnings.md" ]] || fail "Empty learnings.md — agent skipped reflection"
  [[ -s "$phase_dir/handoff.md"  ]] || fail "Empty handoff.md — next agent will be flying blind"
}

gate_tests_pass() {
  local phase_id="$1"
  local log_file="$PHASES_DIR/$phase_id/test-results.log"
  log "Running $TEST_CMD"
  if ! eval "$TEST_CMD" > "$log_file" 2>&1; then
    warn "Tests failed for $phase_id. Last 40 lines of $log_file:"
    tail -n 40 "$log_file" >&2
    fail "Halting. Fix tests, then re-run."
  fi
  log "Tests green."
}

gate_file_size() {
  local offenders
  offenders=$(git ls-files | while read -r f; do
    [[ -f "$f" ]] || continue
    local n
    n=$(wc -l < "$f")
    (( n > MAX_FILE_LINES )) && print "$n  $f"
  done)
  if [[ -n "$offenders" ]]; then
    warn "Files exceed the $MAX_FILE_LINES-line hard ceiling:"
    print "$offenders" >&2
    fail "Split these files before continuing."
  fi
}

gate_refactor_purity() {
  local phase_id="$1"
  local bad
  bad=$(git log --format='%H %s' "main..phase/$phase_id" 2>/dev/null \
        | awk '$2 ~ /^refactor:/ {print $1}' \
        | while read -r sha; do
            git diff-tree --no-commit-id --name-only -r "$sha" 2>/dev/null \
              | grep -E '(color|ramp|render|draw)' >/dev/null && print "$sha"
          done)
  if [[ -n "$bad" ]]; then
    warn "Refactor commits touched render-critical files (soft warning):"
    print "$bad" >&2
    warn "Verify these did not change visual output."
  fi
}

gate_commit_cadence() {
  local phase_id="$1"
  local n
  n=$(git rev-list --count "main..phase/$phase_id" 2>/dev/null || print 0)
  if (( n < 2 )); then
    warn "Only $n commit(s) on phase/$phase_id. Spec asks for many small commits."
  elif (( n > 30 )); then
    warn "$n commits on phase/$phase_id — possibly too granular, or subphase too big."
  fi
}

# ---------- The loop -------------------------------------------------------

bootstrap

while true; do
  current=$(<"$CURRENT_FILE")
  [[ -z "$current" ]] && { log "All phases complete. 🎉"; break; }

  log "=== Phase $current ==="
  phase_dir="$PHASES_DIR/$current"

  if [[ -f "$phase_dir/DONE" ]]; then
    log "$current already DONE, advancing."
  else
    prepare_prompt "$current"
    run_agent     "$current"

    gate_agent_actually_ran "$current"
    gate_question_raised    "$current"
    gate_artifacts_present  "$current"
    gate_tests_pass         "$current"
    gate_file_size
    gate_refactor_purity    "$current"
    gate_commit_cadence     "$current"

    touch "$phase_dir/DONE"
    log "Phase $current passed all gates."
  fi

  next=$(awk -v cur="$current" 'found{print; exit} $0==cur{found=1}' "$PLAN_FILE")
  if [[ -z "$next" ]]; then
    log "Reached end of plan."
    print -n "" > "$CURRENT_FILE"
    break
  fi
  print "$next" > "$CURRENT_FILE"
  log "Advancing to $next"
done
