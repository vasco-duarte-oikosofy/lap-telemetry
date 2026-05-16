import { colorForNet } from './colorRamp.js';

const RAMP_W = 160;
const RAMP_H = 16;

function createLapLegend(panel) {
  const el = document.createElement('div');
  el.id = 'map-lap-legend';
  el.className = 'map-legend-overlay map-lap-legend';
  el.innerHTML = `
    <div class="legend-row">
      <span class="legend-swatch" id="map-lap-swatch-a"></span>
      <span class="legend-label" id="map-lap-label-a">Session</span>
    </div>
    <div class="legend-row">
      <span class="legend-swatch" id="map-lap-swatch-b"></span>
      <span class="legend-label" id="map-lap-label-b">Reference</span>
    </div>
  `;
  panel.appendChild(el);
  return el;
}

function createRampLegend(panel) {
  const el = document.createElement('div');
  el.id = 'map-ramp-legend';
  el.className = 'map-legend-overlay map-ramp-legend';

  const rampCanvas = document.createElement('canvas');
  rampCanvas.width = RAMP_W;
  rampCanvas.height = RAMP_H;
  rampCanvas.className = 'ramp-bar';

  const ctx = rampCanvas.getContext('2d');
  for (let x = 0; x < RAMP_W; x++) {
    const net = -1 + (2 * x) / (RAMP_W - 1);
    ctx.fillStyle = colorForNet(net);
    ctx.fillRect(x, 0, 1, RAMP_H);
  }

  el.innerHTML = `
    <span class="ramp-label">Brake</span>
    <div class="ramp-wrap"></div>
    <span class="ramp-label">Throttle</span>
  `;
  el.querySelector('.ramp-wrap').appendChild(rampCanvas);
  panel.appendChild(el);
  return el;
}

export function updateMapLegend(panel, lapA, lapB, visible) {
  if (!panel) return;

  let lapLegend = document.getElementById('map-lap-legend');
  let rampLegend = document.getElementById('map-ramp-legend');

  if (!visible) {
    if (lapLegend) lapLegend.style.display = 'none';
    if (rampLegend) rampLegend.style.display = 'none';
    return;
  }

  if (!lapLegend) lapLegend = createLapLegend(panel);
  if (!rampLegend) rampLegend = createRampLegend(panel);

  lapLegend.style.display = '';
  rampLegend.style.display = '';

  document.getElementById('map-lap-swatch-a').style.background = lapA.color || '#4fc3f7';
  document.getElementById('map-lap-swatch-b').style.background = lapB.color || '#ff9800';
}
