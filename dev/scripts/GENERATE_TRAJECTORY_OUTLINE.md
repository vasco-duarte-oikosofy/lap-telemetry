# Generating a Trajectory-Based Track Outline

A **trajectory outline** is a track map built from the sim's position data when no external track-boundary source exists. The centerline follows the racing line; boundaries are a constant ±5 m shell. See [`docs/TRACK_OUTLINE_COVERAGE.md`](../../docs/TRACK_OUTLINE_COVERAGE.md) for outline types and quality caveats.

Use this procedure when a circuit has no TUMFTM or bacinger data (Tier 3 tracks: Lusail, Fuji, Le Mans, etc.). For TUMFTM-aligned outlines, follow [`docs/specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md`](../../docs/specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md) instead.

## Prerequisites

- A **reference lap** parquet for the target circuit under `product/data/reference-laps/`. Follow [`EXTRACT_AND_STORE_REFERENCE_LAP.md`](EXTRACT_AND_STORE_REFERENCE_LAP.md) first.
- The parquet must have `pos_x_m` and `pos_z_m` columns (all LMU sessions from M6+ recorder do).

## Procedure

### 1. Generate the outline JSON

Run this Python snippet from the project root:

```python
import pyarrow.parquet as pq, json, math

TRACK_SLUG   = "lusail-international-circuit"
TRACK_NAME   = "Lusail International Circuit"
REF_LAP      = f"product/data/reference-laps/{TRACK_SLUG}_dkr-engineering-4-elms25_time_01.52.200.parquet"
OUT_JSON     = f"product/data/track-outlines/{TRACK_SLUG}.json"

def dist(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])

def resample(pts, n=500):
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + dist(pts[i-1], pts[i]))
    total = cum[-1]
    result = []
    for i in range(n):
        tgt = (i / (n-1)) * total
        seg = 1
        while seg < len(cum)-1 and cum[seg] < tgt:
            seg += 1
        seg_len = cum[seg] - cum[seg-1]
        t = (tgt - cum[seg-1]) / seg_len if seg_len > 0 else 0
        result.append({'x': pts[seg-1]['x'] + t*(pts[seg]['x']-pts[seg-1]['x']),
                       'y': pts[seg-1]['y'] + t*(pts[seg]['y']-pts[seg-1]['y'])})
    return result

def boundaries(cl, w=5.0):
    left, right = [], []
    n = len(cl)
    for i in range(n):
        prev = cl[(i-1+n)%n]; nxt = cl[(i+1)%n]
        dx = nxt['x']-prev['x']; dy = nxt['y']-prev['y']
        ln = math.hypot(dx, dy)
        if ln == 0:
            left.append({'x': cl[i]['x'], 'y': cl[i]['y']-w})
            right.append({'x': cl[i]['x'], 'y': cl[i]['y']+w})
            continue
        tx, ty = dx/ln, dy/ln; nx, ny = -ty, tx
        left.append({'x': cl[i]['x']-nx*w, 'y': cl[i]['y']-ny*w})
        right.append({'x': cl[i]['x']+nx*w, 'y': cl[i]['y']+ny*w})
    return left, right

t = pq.read_table(REF_LAP)
# LMU: pos_x_m = longitudinal, pos_z_m = lateral
raw = [{'x': float(x), 'y': float(z)}
       for x, z in zip(t.column('pos_x_m').to_pylist(), t.column('pos_z_m').to_pylist())
       if x is not None and z is not None]

cl = resample(raw, 500)
left, right = boundaries(cl, 5.0)

outline = {
    "schema_version": 1,
    "source": "Single lap trajectory (±5m width)",
    "track_name": TRACK_NAME,
    "sim_track_name": TRACK_NAME,
    "layout_name": "default",
    "coordinate_system": "sim_xy",
    "units": "sim_units",
    "track_name_mapping": {
        "canonical_sim_track_name": TRACK_SLUG,
        "canonical_lmu_track_name": TRACK_NAME,
        "accepted_sim_track_names": [TRACK_SLUG],
        "accepted_lmu_track_names": [TRACK_NAME],
        "notes": "Generated from LMU simulator trajectory."
    },
    "alignment": {
        "method": "trajectory_trace",
        "width_per_side": 5.0,
        "notes": "Centerline = fastest reference lap; boundaries ±5m constant."
    },
    "visual_qa": {"status": "pending", "notes": "Needs visual verification."},
    "caveats": [
        "Width is constant ±5m — not measured from real track data.",
        "Centerline follows racing line — not track geometric center.",
        "No TUMFTM/bacinger data available. Upgrade requires OSM extraction.",
        "This outline is visual context only."
    ],
    "centerline": cl,
    "left_boundary": left,
    "right_boundary": right
}

with open(OUT_JSON, 'w') as f:
    json.dump(outline, f, indent=2)
    f.write('\n')
print(f"Wrote {OUT_JSON}: {len(cl)} pts")
```

### 2. Register the outline

```bash
# On Linux/Mac:
python3 dev/scripts/register_outline.py product/data/track-outlines/<track-slug>.json

# On Windows (PowerShell) — set encoding first:
$env:PYTHONIOENCODING = "utf-8"
python dev/scripts/register_outline.py product/data/track-outlines/<track-slug>.json
```

This validates the JSON, generates a JS ES module, updates `trackOutlineManifest.js`, and rebuilds the bundle. If the build step fails on Windows (subprocess lookup error), run `npm run build` manually afterwards.

### 3. Update coverage table

Add a row to [`docs/TRACK_OUTLINE_COVERAGE.md`](../../docs/TRACK_OUTLINE_COVERAGE.md):

```markdown
| Lusail International Circuit | `lusail-international-circuit` | Trajectory | Single lap (lap 12, 1:52.200) | Constant 5m each side | ❌ No |
```

### 4. Commit

```
feat(outline): add trajectory outline for <track-name>
```

## Limitations of trajectory outlines

- The driver always appears centered — apex proximity to the real edge is meaningless.
- The boundary width is arbitrary (5 m is a visual estimate, not measured).
- Upgrade path: obtain OSM `highway=raceway` data or satellite-derived centerline + width.
