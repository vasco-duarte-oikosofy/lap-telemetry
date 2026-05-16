// ── Map interaction: zoom / pan / reset ───────────────────────────────────────
// One file, one job: handles Pointer Events, Wheel, and dblclick on the canvas
// and maintains user transform state { scale, tx, ty }.

const MIN_SCALE = 1;
const MAX_SCALE = 40;
const WHEEL_SENSITIVITY = 1.0015;

let baseTransformRef = { offsetX: 0, offsetY: 0 };

export function setBaseTransform(transform) {
  baseTransformRef = transform || { offsetX: 0, offsetY: 0 };
}

export function getBaseTransform() {
  return baseTransformRef;
}

export function createMapInteraction(canvas, onChange, { onReset, getMinScale } = {}) {
  const state = { scale: 1, tx: 0, ty: 0 };
  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let panStartX = 0;
  let panStartY = 0;

  function trigger() {
    if (onChange) onChange();
  }

  function onWheel(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const oldScale = state.scale;
    const minScale = getMinScale ? getMinScale() : MIN_SCALE;
    const newScale = Math.min(MAX_SCALE, Math.max(minScale, oldScale * (WHEEL_SENSITIVITY ** -e.deltaY)));
    if (newScale === oldScale) return;

    const zoomRatio = newScale / oldScale;
    const ox = baseTransformRef.offsetX || 0;
    const oy = baseTransformRef.offsetY || 0;

    state.tx = state.tx * zoomRatio + (mx - ox) * (1 - zoomRatio);
    state.ty = state.ty * zoomRatio + (my - oy) * (1 - zoomRatio);
    state.scale = newScale;

    updateZoomIndicator(canvas, state.scale);
    trigger();
  }

  function onPointerDown(e) {
    if (!e.isPrimary) return;
    dragging = true;
    canvas.setPointerCapture(e.pointerId);
    canvas.style.cursor = 'grabbing';
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    panStartX = state.tx;
    panStartY = state.ty;
  }

  function onPointerMove(e) {
    if (!dragging) return;
    state.tx = panStartX + (e.clientX - dragStartX);
    state.ty = panStartY + (e.clientY - dragStartY);
    trigger();
  }

  function onPointerUp(e) {
    if (!dragging) return;
    dragging = false;
    canvas.style.cursor = 'grab';
    try { canvas.releasePointerCapture(e.pointerId); } catch {}
  }

  function onDblClick(e) {
    state.scale = 1;
    state.tx = 0;
    state.ty = 0;
    updateZoomIndicator(canvas, state.scale);
    if (onReset) onReset();
    trigger();
  }

  function onTestEvent(e) {
    if (e.type === 'mapZoomPanChange') trigger();
  }

  canvas.style.cursor = 'grab';
  canvas.style.touchAction = 'none';
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('pointercancel', onPointerUp);
  canvas.addEventListener('dblclick', onDblClick);
  canvas.addEventListener('mapZoomPanChange', onTestEvent);

  window.__mapZoomPanState = state;

  return {
    getState: () => state,
    setState: (next) => {
      state.scale = next.scale ?? state.scale;
      state.tx = next.tx ?? state.tx;
      state.ty = next.ty ?? state.ty;
      updateZoomIndicator(canvas, state.scale);
      trigger();
    },
    destroy: () => {
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('dblclick', onDblClick);
      canvas.removeEventListener('mapZoomPanChange', onTestEvent);
      delete window.__mapZoomPanState;
    },
  };
}

function updateZoomIndicator(canvas, scale) {
  const indicator = document.getElementById('map-zoom-indicator');
  if (!indicator) return;
  indicator.textContent = `${scale.toFixed(1)}×`;
}
