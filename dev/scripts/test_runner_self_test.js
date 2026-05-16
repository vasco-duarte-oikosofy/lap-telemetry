// @parallel true
'use strict';

const { spawnSync } = require('child_process');
const path = require('path');
const { countPasses, extractFailures, printSummary } = require('./run-tests-parallel');

const F = path.resolve(__dirname, 'lib/__runner-fixtures__');
const ROOT = path.resolve(__dirname, '..', '..');
const RUNNER = path.resolve(__dirname, 'run-tests-parallel.js');
let pass = 0, fail = 0;
function assert(c, n) { if (c) { console.log(`  [PASS] ${n}`); pass++; } else { console.log(`  [FAIL] ${n}`); fail++; } }

// ── Unit: countPasses and extractFailures
assert(countPasses('  [PASS] ok') === 1, 'countPasses: single PASS');
assert(countPasses('[PASS] a\n  [PASS] b\n  [FAIL] c') === 2, 'countPasses: multiple PASS');
assert(countPasses('[PASS] with detail — info') === 1, 'countPasses: PASS with detail');
assert(countPasses('no match here') === 0, 'countPasses: no match');
assert(extractFailures('  [FAIL] broken\n  [PASS] ok').length === 1, 'extractFailures: detects FAIL');
assert(extractFailures('all good').length === 0, 'extractFailures: no match');

// ── Unit: printSummary (capture console.log)
const orig = console.log;
const cap = fn => { const l = []; console.log = (...a) => l.push(a.join(' ')); const r = fn(); console.log = orig; return { l, r }; };
const R = (s, e, o) => ({ script: s, exitCode: e, output: o });

const ok = cap(() => printSummary([R('pass.js', 0, '  [PASS] ok')], '1.0'));
assert(ok.r === 0, 'printSummary: passing returns 0');
assert(ok.l[0].includes('ALL PASS — 1 assertions across 1'), 'printSummary: ALL PASS format');
const bad = cap(() => printSummary([R('fail.js', 1, '  [FAIL] broken')], '1.0'));
assert(bad.r === 1, 'printSummary: failing returns 1');
assert(bad.l[0].includes('FAILED'), 'printSummary: FAILED format');
assert(bad.l.some(l => l.includes('1 failure')), 'printSummary: shows failure count');
const zero = cap(() => printSummary([R('zero.js', 0, '')], '1.0'));
assert(zero.r === 1, 'printSummary: zero-assertion returns 1');
assert(zero.l.some(l => l.includes('protocol violation')), 'printSummary: shows protocol violation reason');
const crash = cap(() => printSummary([R('crash.js', 1, 'opaque')], '1.0'));
assert(crash.r === 1, 'printSummary: crash returns 1');
assert(crash.l.some(l => l.includes('exit 1')), 'printSummary: shows exit code reason');

// ── Integration: single-test mode via subprocess
const run = s => spawnSync('node', [RUNNER, s], { encoding: 'utf8', cwd: ROOT });
const ps = run(path.join(F, 'fixture-pass.js'));
assert(ps.status === 0, 'single-test: passing exits 0');
assert(ps.stdout.includes('PASS — 1 assertions'), 'single-test: passing output');
const fRes = run(path.join(F, 'fixture-fail.js'));
assert(fRes.status === 1, 'single-test: failing exits 1');
assert(fRes.stdout.includes('1 failure'), 'single-test: failing shows failure count');
const zRes = run(path.join(F, 'fixture-zero.js'));
assert(zRes.status === 1, 'single-test: zero-assertion exits 1');
assert(zRes.stdout.includes('protocol violation'), 'single-test: zero-assertion shows protocol violation');

console.log(`\n  Runner self-test: ${pass} passed, ${fail} failed`);
if (fail > 0) process.exitCode = 1;