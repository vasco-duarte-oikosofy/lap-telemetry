// ── Net pedal color ramp (Phase 01a) ─────────────────────────────────────────
// Maps throttle - brake in [-1, +1] to a brake-blue → neutral → throttle-green
// ramp. HSL interpolation keeps the signed halves on blue/green hues and avoids
// muddy brown between the endpoints.

const BRAKE = '#0a3d91';
const NEUTRAL = '#2a3340';
const THROTTLE = '#0f7a2e';

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function hexToRgb(hex) {
  const n = Number.parseInt(hex.slice(1), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function rgbToHex({ r, g, b }) {
  const toHex = (v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function rgbToHsl({ r, g, b }) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return { h: h * 60, s, l };
}

function hslToRgb({ h, s, l }) {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const hp = (((h % 360) + 360) % 360) / 60;
  const x = c * (1 - Math.abs((hp % 2) - 1));
  let r1 = 0, g1 = 0, b1 = 0;
  if (hp < 1) [r1, g1, b1] = [c, x, 0];
  else if (hp < 2) [r1, g1, b1] = [x, c, 0];
  else if (hp < 3) [r1, g1, b1] = [0, c, x];
  else if (hp < 4) [r1, g1, b1] = [0, x, c];
  else if (hp < 5) [r1, g1, b1] = [x, 0, c];
  else [r1, g1, b1] = [c, 0, x];
  const m = l - c / 2;
  return { r: (r1 + m) * 255, g: (g1 + m) * 255, b: (b1 + m) * 255 };
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerpHue(a, b, t) {
  let delta = ((b - a + 540) % 360) - 180;
  return a + delta * t;
}

function interpolateHsl(fromHex, toHex, t) {
  const from = rgbToHsl(hexToRgb(fromHex));
  const to = rgbToHsl(hexToRgb(toHex));
  return rgbToHex(hslToRgb({
    h: lerpHue(from.h, to.h, t),
    s: lerp(from.s, to.s, t),
    l: lerp(from.l, to.l, t),
  }));
}

export function colorForNet(net) {
  const n = clamp(Number.isFinite(net) ? net : 0, -1, 1);
  if (n === -1) return BRAKE;
  if (n === 0) return NEUTRAL;
  if (n === 1) return THROTTLE;
  const t = Math.sqrt(Math.abs(n));
  return n < 0 ? interpolateHsl(NEUTRAL, BRAKE, t) : interpolateHsl(NEUTRAL, THROTTLE, t);
}

export const NET_COLOR_LUT = Array.from({ length: 256 }, (_, i) => {
  const net = -1 + (2 * i) / 255;
  return colorForNet(net);
});
