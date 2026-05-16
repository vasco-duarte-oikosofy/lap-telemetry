// @parallel true
'use strict';

/**
 * Protocol enforcement — ensures every test script emits [PASS]/[FAIL] output.
 * Static analysis: reads source files and checks for protocol patterns.
 * Catches the bug class where a test uses Node assert() or console.log()
 * without the [PASS]/[FAIL] protocol (slices 02 and 04).
 */

const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');

let pass = 0, fail = 0;
function assert(c, n) { if (c) { console.log(`  [PASS] ${n}`); pass++; } else { console.log(`  [FAIL] ${n}`); fail++; } }

// Read test script list from package.json
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const scripts = pkg.scripts.test.split(' && ').map(s => s.match(/node\s+(.+)/)?.[1]).filter(Boolean);

// Protocol patterns that produce runner-counted output
const PROTOCOL_RE = /\[PASS\]|\[FAIL\]|\[\$\{status\}\]|PASS \$\{|PASS `|FAIL `|\bPASS\b.*message|\bFAIL\b.*message|console\.log\(.*PASS|console\.log\(.*FAIL/;

for (const s of scripts) {
  const src = fs.readFileSync(path.resolve(ROOT, s), 'utf8');
  assert(PROTOCOL_RE.test(src), `${s} follows PASS/FAIL protocol`);
}

console.log(`\n  Protocol enforcement: ${pass} passed, ${fail} failed`);
if (fail > 0) process.exitCode = 1;