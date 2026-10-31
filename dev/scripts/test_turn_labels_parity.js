#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * The turn label layout exists twice: `product/web/js/turnLabels.js` for the
 * compare app and `../tinypedal/tinypedal/turn_labels.py` for the Qt overlay.
 * Two copies of a layout rule drift silently, so this test feeds the SAME
 * anchors and the SAME text metrics to both implementations and compares every
 * planned label to the pixel.
 *
 * The Python side needs the TinyPedal venv; when it is missing the test says so
 * and skips instead of failing (the port lives in another repository).
 *
 * Run: node dev/scripts/test_turn_labels_parity.js
 */

const path = require('path');
const { spawnSync } = require('child_process');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..', '..');
const TINYPedal = path.resolve(ROOT, '..', 'tinypedal');

// Screen-space anchors: the Python planner takes them already transformed.
const ANCHORS = [
  { number: 1, name: 'Abbey', short_name: null, x: 120, y: 90, nx: -0.26, ny: -0.97, tx: 0.97, ty: -0.26 },
  { number: 2, name: 'Farm Curve', short_name: null, x: 200, y: 70, nx: 0.10, ny: 0.99, tx: 0.99, ty: -0.10 },
  { number: 3, name: 'Village', short_name: 'Village', x: 250, y: 130, nx: 0.71, ny: 0.71, tx: 0.71, ty: -0.71 },
  { number: 4, name: 'The Link', short_name: null, x: 250, y: 190, nx: 0.99, ny: -0.10, tx: -0.10, ty: -0.99 },
  { number: 5, name: null, short_name: null, x: 190, y: 220, nx: -0.50, ny: 0.86, tx: 0.86, ty: 0.50 },
  { number: 6, name: 'Becketts', short_name: null, x: 130, y: 200, nx: -0.97, ny: -0.26, tx: -0.26, ty: 0.97 },
  { number: 7, name: 'Stowe', short_name: null, x: 110, y: 150, nx: -0.71, ny: 0.71, tx: -0.71, ty: -0.71 },
];

// Deliberately tight so the search has to degrade text and change sides.
const CASES = [
  // `scale` fits the same anchor layout onto each map, so the tight cases really
  // exercise degradation, side swaps and drops in both implementations.
  { name: 'roomy map', mapSize: 260, width: 260, height: 260, scale: 1 },
  { name: 'dense map', mapSize: 120, width: 120, height: 120, scale: 0.46 },
  { name: 'tiny map', mapSize: 100, width: 100, height: 100, scale: 0.38 },
  { name: 'rectangular map', mapSize: 200, width: 320, height: 200, scale: 1 },
];

let failures = 0;
function check(name, ok, detail = '') {
  console.log(`  ${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) failures += 1;
}

function pythonBinary() {
  const candidates = [
    path.join(TINYPedal, '.venv', 'Scripts', 'python.exe'),
    path.join(TINYPedal, '.venv', 'bin', 'python'),
  ];
  const fs = require('fs');
  return candidates.find(p => fs.existsSync(p)) || null;
}

async function planInJs(caseSpec) {
  const { planTurnLabels } = await import(
    pathToFileURL(path.join(ROOT, 'product', 'web', 'js', 'turnLabels.js')).href);
  // Same fake metrics as the Python test helper.
  const measure = (text, size) => ({ w: text.length * size * 0.56, h: size * 1.15 });
  const plan = planTurnLabels({
    turns: ANCHORS.map(a => ({
      number: a.number,
      name: a.name,
      short_name: a.short_name,
      x: a.x * caseSpec.scale,
      // The JS planner flips the world Y axis; feed it screen space instead.
      y: a.y * caseSpec.scale,
      outward: [a.nx, -a.ny],
      tangent: [a.tx, -a.ty],
    })),
    toMapX: x => x,
    toMapZ: y => y,
    mapSize: caseSpec.mapSize,
    mapWidth: caseSpec.width,
    mapHeight: caseSpec.height,
    measure,
  });
  return plan.labels.map(l => ({
    text: l.text, x: l.x, y: l.y, w: l.w, h: l.h, side: l.side,
  }));
}

function planInPython(binary, caseSpec) {
  const script = `
import json, sys
sys.path.insert(0, ${JSON.stringify(TINYPedal)})
from tinypedal.turn_labels import TurnAnchor, plan_turn_labels

anchors = [TurnAnchor(number=a["number"], name=a["name"], short_name=a["short_name"],
                      x=a["x"], y=a["y"], normal_x=a["nx"], normal_y=a["ny"],
                      tangent_x=a["tx"], tangent_y=a["ty"])
           for a in json.loads(r'''${JSON.stringify(ANCHORS)}''')]
scale = ${caseSpec.scale}
anchors = [TurnAnchor(number=a.number, name=a.name, short_name=a.short_name,
                      x=a.x * scale, y=a.y * scale, normal_x=a.normal_x,
                      normal_y=a.normal_y, tangent_x=a.tangent_x, tangent_y=a.tangent_y)
           for a in anchors]

def measure(text, size):
    return len(text) * size * 0.56, size * 1.15

placed, _dropped = plan_turn_labels(anchors, ${caseSpec.mapSize}, measure,
                                    map_width=${caseSpec.width},
                                    map_height=${caseSpec.height})
print(json.dumps([{"text": l.text, "x": l.x, "y": l.y,
                   "w": l.width, "h": l.height, "side": l.side} for l in placed]))
`;
  const res = spawnSync(binary, ['-c', script], {
    encoding: 'utf8',
    timeout: 60000,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  if (res.status !== 0) {
    throw new Error(`python planner failed: ${res.stderr.trim() || res.stdout.trim()}`);
  }
  return JSON.parse(res.stdout);
}

(async () => {
  const binary = pythonBinary();
  check('TinyPedal checkout is present', binary !== null, binary || 'no ../tinypedal/.venv');
  if (!binary) {
    console.log('\nRESULT: SKIP — TinyPedal venv not found');
    process.exit(0);
  }

  for (const caseSpec of CASES) {
    const js = await planInJs(caseSpec);
    const py = planInPython(binary, caseSpec);
    const sameCount = js.length === py.length;
    check(`${caseSpec.name}: same number of labels`, sameCount, `js ${js.length} vs py ${py.length}`);
    if (!sameCount) continue;

    let worst = 0;
    let mismatch = null;
    for (let i = 0; i < js.length; i++) {
      const a = js[i], b = py[i];
      if (a.text !== b.text || a.side !== b.side) {
        mismatch = `#${i}: js "${a.text}"/${a.side} vs py "${b.text}"/${b.side}`;
        break;
      }
      worst = Math.max(worst, Math.abs(a.x - b.x), Math.abs(a.y - b.y),
        Math.abs(a.w - b.w), Math.abs(a.h - b.h));
    }
    check(`${caseSpec.name}: identical text, side and geometry`, mismatch === null,
      mismatch || `max delta ${worst.toFixed(9)} px`);
    check(`${caseSpec.name}: labels are actually produced`, js.length > 0, `${js.length} labels`);
  }

  console.log(`\n${failures === 0 ? 'RESULT: PASS' : 'RESULT: FAIL'}`);
  process.exit(failures === 0 ? 0 : 1);
})().catch(err => {
  console.error('FAIL unexpected error —', err.message);
  console.log('RESULT: FAIL');
  process.exit(1);
});
