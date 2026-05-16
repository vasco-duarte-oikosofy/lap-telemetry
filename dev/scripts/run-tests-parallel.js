#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Parallel test runner — runs @parallel true tests concurrently, @parallel false
 * tests sequentially after.  Output matches the old bash runner's contract.
 *
 * Usage:
 *   node dev/scripts/run-tests-parallel.js                # full suite
 *   node dev/scripts/run-tests-parallel.js <script>        # single test
 *   node dev/scripts/run-tests-parallel.js --concurrency 4
 */

const { spawn } = require('child_process');
const { cpus } = require('os');
const fs = require('fs');
const path = require('path');

const PASS_RE = /\[PASS\]|^\s+PASS /m;
const FAIL_RE = /\[FAIL\]|^\s+FAIL |^Error:|^AssertionError/m;
const DEFAULT_CONCURRENCY = Math.min(cpus().length - 2, 6);
const ROOT = path.resolve(__dirname, '..', '..');

// ── Discovery ─────────────────────────────────────────────────────────────────

function getParallelMode(filePath) {
  try {
    const m = fs.readFileSync(filePath, 'utf8').match(/^\/\/ @parallel (true|false)\s*$/m);
    return m ? m[1] === 'true' : false;
  } catch { return false; }
}

function getTestScripts() {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  return pkg.scripts.test.split(' && ')
    .map(p => { const m = p.match(/node\s+(.+)/); return m ? m[1] : null; })
    .filter(Boolean);
}

// ── Running ──────────────────────────────────────────────────────────────────

function runTest(script) {
  return new Promise(resolve => {
    const child = spawn('node', [script], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '';
    child.stdout.on('data', d => { output += d; });
    child.stderr.on('data', d => { output += d; });
    child.on('close', code => resolve({ script, exitCode: code ?? 1, output }));
  });
}

async function runConcurrently(scripts, concurrency) {
  const results = new Array(scripts.length);
  let next = 0;
  async function worker() {
    while (next < scripts.length) { const i = next++; results[i] = await runTest(scripts[i]); }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, scripts.length) }, () => worker()));
  return results;
}

async function runSequentially(scripts) {
  const results = [];
  for (const s of scripts) results.push(await runTest(s));
  return results;
}

// ── Parsing ───────────────────────────────────────────────────────────────────

function countPasses(output) {
  return output.split('\n').filter(line => PASS_RE.test(line)).length;
}

function extractFailures(output) {
  return output.split('\n').filter(line => FAIL_RE.test(line));
}

// ── Reporting ─────────────────────────────────────────────────────────────────

function printSummary(results, elapsed) {
  let totalPassed = 0;
  const failedScripts = [];
  for (const r of results) {
    totalPassed += countPasses(r.output);
    const failures = extractFailures(r.output);
    if (failures.length > 0 || r.exitCode !== 0) {
      failedScripts.push({ script: r.script, output: r.output, failures });
    }
  }
  if (failedScripts.length === 0) {
    console.log(`ALL PASS — ${totalPassed} assertions across ${results.length} test scripts in ${elapsed}`);
    return 0;
  }
  console.log(`FAILED — ${totalPassed} passed, ${failedScripts.length} of ${results.length} scripts failed in ${elapsed}`);
  console.log('');
  for (const f of failedScripts) {
    console.log(`=== FAIL: ${f.script} ===`);
    (f.failures.length > 0 ? f.failures : f.output.split('\n').slice(0, 20)).forEach(l => console.log(l));
    console.log('');
  }
  console.log('To re-run a failing test:');
  failedScripts.forEach(f => console.log(`  bash scripts/test-summary.sh ${f.script}`));
  return 1;
}

// ── Single-test mode ──────────────────────────────────────────────────────────

async function runSingleTest(target) {
  let script = target;
  if (!fs.existsSync(script) && script.startsWith('scripts/')) {
    const mapped = path.join('dev', script);
    if (fs.existsSync(mapped)) script = mapped;
  }
  if (!fs.existsSync(script)) { console.log(`FAIL: file not found: ${target}`); return 1; }

  console.log(`Re-running: ${script}`);
  const start = Date.now();
  const r = await runTest(script);
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  const failures = extractFailures(r.output);

  if (failures.length === 0 && r.exitCode === 0) {
    console.log(`PASS — ${countPasses(r.output)} assertions in ${elapsed}s (${script})`);
    return 0;
  }
  console.log(`FAIL — ${script}`);
  (failures.length > 0 ? failures : r.output.split('\n').slice(0, 20)).forEach(l => console.log(l));
  return 1;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  let concurrency = DEFAULT_CONCURRENCY;
  const ci = args.indexOf('--concurrency');
  if (ci !== -1) { concurrency = parseInt(args[ci + 1], 10); args.splice(ci, 2); }

  if (args.length > 0) { process.exit(await runSingleTest(args[0])); }

  const scripts = getTestScripts();
  const parallel = [], serial = [];
  for (const s of scripts) (getParallelMode(path.resolve(ROOT, s)) ? parallel : serial).push(s);

  const start = Date.now();
  const pResults = parallel.length ? await runConcurrently(parallel, concurrency) : [];
  const sResults = serial.length ? await runSequentially(serial) : [];
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);

  process.exit(printSummary([...pResults, ...sResults], elapsed));
}

main().catch(err => { console.error('Runner error:', err); process.exit(1); });