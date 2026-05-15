#!/usr/bin/env bash
# test-summary.sh — Run npm test, show only failures or a concise pass summary.
#
# Usage:
#   bash scripts/test-summary.sh          # run full suite
#   bash scripts/test-summary.sh <file>   # re-run a single failing test script
set -euo pipefail

now_ms() { python3 -c "import time; print(int(time.time()*1000))"; }

# Patterns that match a passing assertion in any of our test formats:
#   [PASS] ...    (bracketed, used by m5/m6/f1f2/apex/etc.)
#     PASS ...    (indented, used by static-outline tests)
PASS_RE='\[PASS\]|^\s+PASS '

# Patterns that match a failing assertion:
#   [FAIL] ...    (bracketed)
#     FAIL ...    (indented)
#   Error: ...    (thrown errors)
#   AssertionError ...
FAIL_RE='\[FAIL\]|^\s+FAIL |^Error:|^AssertionError'

if [ $# -gt 0 ]; then
  target="$1"
  if [ ! -f "$target" ]; then echo "FAIL: file not found: $target"; exit 1; fi
  echo "Re-running: $target"
  start=$(now_ms)
  output=$(node "$target" 2>&1) || true
  end=$(now_ms)
  secs=$(python3 -c "print(f'{($end-$start)/1000:.1f}')")
  failures=$(echo "$output" | grep -E "$FAIL_RE" || true)
  if [ -z "$failures" ]; then
    total=$(echo "$output" | grep -cE "$PASS_RE" || true)
    echo "PASS — $total assertions in ${secs}s ($target)"
  else
    echo "FAIL — $target"
    echo "$failures"
  fi
  exit 0
fi

# Full suite — run each script individually to attribute failures
start=$(now_ms)
temp=$(mktemp)
trap 'rm -f "$temp"' EXIT

scripts=($(node -e "
  const pkg = require('./package.json');
  const parts = pkg.scripts.test.split(' && ');
  parts.forEach(p => { const m = p.match(/node\s+(.+)/); if (m) console.log(m[1]); });
"))

total_passed=0
failed_scripts=()
for s in "${scripts[@]}"; do
  out=$(node "$s" 2>&1) || true
  p=$(echo "$out" | grep -cE "$PASS_RE" || true)
  total_passed=$((total_passed + p))
  f=$(echo "$out" | grep -E "$FAIL_RE" || true)
  if [ -n "$f" ]; then
    echo "=== FAIL: $s ===" >> "$temp"
    echo "$f" >> "$temp"
    echo "" >> "$temp"
    failed_scripts+=("$s")
  fi
done

end=$(now_ms)
secs=$(python3 -c "print(f'{($end-$start)/1000:.1f}')")
total_scripts=${#scripts[@]}

if [ ${#failed_scripts[@]} -eq 0 ]; then
  echo "ALL PASS — $total_passed assertions across $total_scripts test scripts in ${secs}s"
else
  echo "FAILED — $total_passed passed, ${#failed_scripts[@]} of $total_scripts scripts failed in ${secs}s"
  echo ""
  cat "$temp"
  echo "To re-run a failing test:"
  for s in "${failed_scripts[@]}"; do
    echo "  bash scripts/test-summary.sh $s"
  done
fi