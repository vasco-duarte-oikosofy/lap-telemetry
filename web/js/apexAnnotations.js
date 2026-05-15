// ── Apex annotation JSON validator/loader ───────────────────────────────────

const VALID_APEX_SIDES = new Set(['left', 'right']);

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function requireString(obj, field, errors, prefix) {
  if (!isNonEmptyString(obj?.[field])) {
    errors.push(`${prefix}${field} is required and must be a non-empty string`);
  }
}

function requireNumber(obj, field, errors, prefix) {
  if (!isFiniteNumber(obj?.[field])) {
    errors.push(`${prefix}${field} is required and must be a finite number`);
  }
}

export function validateApexAnnotations(input) {
  const errors = [];
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return { ok: false, errors: ['annotation root must be an object'] };
  }

  requireString(input, 'track_id', errors, '');
  requireString(input, 'layout_id', errors, '');
  if (!Array.isArray(input.corners)) {
    errors.push('corners is required and must be an array');
  }

  const seenIds = new Set();
  const corners = Array.isArray(input.corners) ? input.corners : [];
  corners.forEach((corner, index) => {
    const prefix = `corners[${index}].`;
    if (!corner || typeof corner !== 'object' || Array.isArray(corner)) {
      errors.push(`corners[${index}] must be an object`);
      return;
    }

    requireString(corner, 'id', errors, prefix);
    requireString(corner, 'name', errors, prefix);
    requireNumber(corner, 's_start_m', errors, prefix);
    requireNumber(corner, 'apex_s_m', errors, prefix);
    requireNumber(corner, 's_end_m', errors, prefix);

    if (isNonEmptyString(corner.id)) {
      if (seenIds.has(corner.id)) errors.push(`duplicate corner id: ${corner.id}`);
      seenIds.add(corner.id);
    }

    if (!VALID_APEX_SIDES.has(corner.apex_side)) {
      errors.push(`${prefix}apex_side must be "left" or "right"`);
    }

    if (isFiniteNumber(corner.s_start_m) && isFiniteNumber(corner.apex_s_m) &&
        corner.s_start_m >= corner.apex_s_m) {
      errors.push(`${prefix}s_start_m must be less than apex_s_m`);
    }
    if (isFiniteNumber(corner.apex_s_m) && isFiniteNumber(corner.s_end_m) &&
        corner.apex_s_m >= corner.s_end_m) {
      errors.push(`${prefix}apex_s_m must be less than s_end_m`);
    }
  });

  if (errors.length) return { ok: false, errors };
  return { ok: true, annotations: structuredClone(input), errors: [] };
}

export async function loadApexAnnotationsFile(filePath) {
  const fsModule = 'node:fs/promises';
  const fs = await import(fsModule);
  let text;
  try {
    text = await fs.readFile(filePath, 'utf8');
  } catch (err) {
    if (err && err.code === 'ENOENT') {
      return { status: 'not_configured', annotations: null, errors: [] };
    }
    throw err;
  }

  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    return { status: 'invalid', annotations: null, errors: [`invalid JSON: ${err.message}`] };
  }

  const validation = validateApexAnnotations(parsed);
  if (!validation.ok) {
    return { status: 'invalid', annotations: null, errors: validation.errors };
  }
  return { status: 'ok', annotations: validation.annotations, errors: [] };
}
