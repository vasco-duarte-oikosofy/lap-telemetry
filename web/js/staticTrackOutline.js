import { SPA_STATIC_OUTLINE } from './staticSpaOutlineData.js';

const REQUIRED_ARRAYS = ['left_boundary', 'right_boundary', 'centerline'];

export function getSpaStaticOutline() {
  validateStaticOutline(SPA_STATIC_OUTLINE);
  return SPA_STATIC_OUTLINE;
}

export function validateStaticOutline(outline) {
  if (!outline || outline.schema_version !== 1) {
    throw new Error('Static track outline must use schema_version 1');
  }
  for (const key of REQUIRED_ARRAYS) {
    const points = outline[key];
    if (!Array.isArray(points) || points.length === 0) {
      throw new Error(`Static track outline missing ${key}`);
    }
    for (const point of points) {
      if (!Number.isFinite(point?.x) || !Number.isFinite(point?.y)) {
        throw new Error(`Static track outline ${key} contains a non-finite point`);
      }
    }
  }
}

export function renderStaticTrackOutlineSvg(outline, trackTransform) {
  if (!outline || !trackTransform) return '';
  validateStaticOutline(outline);
  const left = renderBoundary(outline.left_boundary, trackTransform, 'left_boundary', 'static-track-boundary');
  const right = renderBoundary(outline.right_boundary, trackTransform, 'right_boundary', 'static-track-boundary');
  const center = renderBoundary(outline.centerline, trackTransform, 'centerline', 'static-track-centerline');
  return `<g data-static-track-outline="spa-francorchamps" class="static-track-outline">${left}${right}${center}</g>`;
}

function renderBoundary(points, trackTransform, part, className) {
  const pts = pointsToSvg(points, trackTransform);
  if (!pts) return '';
  return `<polyline data-static-outline-part="${part}" class="${className}" points="${pts}"/>`;
}

function pointsToSvg(points, trackTransform) {
  const pts = [];
  for (const point of points) {
    const x = trackTransform.toMapX(point.x);
    const y = trackTransform.toMapZ(point.y);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
  }
  return pts.join(' ');
}
