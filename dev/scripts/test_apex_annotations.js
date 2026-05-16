/**
 * Track outline/apex Phase 03 annotation validator tests.
 *
 * Run: node scripts/test_apex_annotations.js
 */

'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');

const ROOT = path.resolve(__dirname, '..', '..');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function validAnnotation(overrides = {}) {
  return {
    track_id: 'circuit-de-spa-francorchamps',
    layout_id: 'default',
    corners: [
      {
        id: 't1',
        name: 'La Source',
        s_start_m: 200,
        s_end_m: 360,
        apex_s_m: 285,
        apex_side: 'right',
      },
    ],
    ...overrides,
  };
}

function invalidMessage(result) {
  return (result.errors || []).join(' | ');
}

async function runTests() {
  const mod = await import(path.join(ROOT, 'web/js/apexAnnotations.js'));

  const valid = mod.validateApexAnnotations(validAnnotation());
  assert(valid.ok === true, 'valid one-corner annotation validates successfully', invalidMessage(valid));
  assert(valid.annotations.corners[0].id === 't1', 'valid annotation returns normalized annotation data');

  const badStart = mod.validateApexAnnotations(validAnnotation({
    corners: [{ ...validAnnotation().corners[0], s_start_m: 285 }],
  }));
  assert(badStart.ok === false && invalidMessage(badStart).includes('s_start_m') && invalidMessage(badStart).includes('apex_s_m'),
    's_start_m >= apex_s_m fails with useful message', invalidMessage(badStart));

  const badEnd = mod.validateApexAnnotations(validAnnotation({
    corners: [{ ...validAnnotation().corners[0], s_end_m: 285 }],
  }));
  assert(badEnd.ok === false && invalidMessage(badEnd).includes('apex_s_m') && invalidMessage(badEnd).includes('s_end_m'),
    'apex_s_m >= s_end_m fails with useful message', invalidMessage(badEnd));

  const duplicate = mod.validateApexAnnotations(validAnnotation({
    corners: [validAnnotation().corners[0], { ...validAnnotation().corners[0], name: 'Duplicate Source' }],
  }));
  assert(duplicate.ok === false && invalidMessage(duplicate).includes('duplicate') && invalidMessage(duplicate).includes('t1'),
    'duplicate corner IDs fail with useful message', invalidMessage(duplicate));

  const badSide = mod.validateApexAnnotations(validAnnotation({
    corners: [{ ...validAnnotation().corners[0], apex_side: 'inside' }],
  }));
  assert(badSide.ok === false && invalidMessage(badSide).includes('apex_side') && invalidMessage(badSide).includes('left') && invalidMessage(badSide).includes('right'),
    'bad apex_side fails with useful message', invalidMessage(badSide));

  const missingRequired = mod.validateApexAnnotations(validAnnotation({ track_id: '' }));
  assert(missingRequired.ok === false && invalidMessage(missingRequired).includes('track_id'),
    'missing required root fields fail with useful message', invalidMessage(missingRequired));

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'apex-annotations-'));
  const annotationPath = path.join(tmp, 'spa-default.json');
  fs.writeFileSync(annotationPath, JSON.stringify(validAnnotation()), 'utf8');
  const loaded = await mod.loadApexAnnotationsFile(annotationPath);
  assert(loaded.status === 'ok' && loaded.annotations.corners[0].name === 'La Source',
    'valid one-corner annotation file loads successfully', loaded.status);

  const missing = await mod.loadApexAnnotationsFile(path.join(tmp, 'missing.json'));
  assert(missing.status === 'not_configured' && !missing.annotations,
    'missing annotation file returns not_configured without throwing', JSON.stringify(missing));
}

async function main() {
  console.log('═══ Track Outline Phase 03 Apex Annotation Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
