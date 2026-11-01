# Data audit

Baseline: `a39f21f` (before this slice).

- 33 models, 453 corners reviewed; 340 short names added.
- Parsed JSON with short_name removed is identical in every model.
- Every existing alias is unchanged. No official names, IDs, reference metadata,
  corner ordering, distances, apex sides, speech zones or throttle targets changed.
- Legacy Spa: formatting-only compaction in `bd32dbb` (636 → 84 lines).

| Model | Corners | Aliases added |
|---|---:|---:|
| `algarve-international-circuit_dkr-engineering-4-elms25.json` | 15 | 15 |
| `algarve-international-circuit_vista-af-corse-2025-21-lm.json` | 9 | 9 |
| `autodromo-enzo-e-dino-ferrari_dkr-engineering-4-elms25.json` | 11 | 2 |
| `autodromo-enzo-e-dino-ferrari_ferrari-af-corse-2026-50-lm.json` | 11 | 8 |
| `autodromo-jose-carlos-pace_dkr-engineering-4-elms25.json` | 15 | 2 |
| `autodromo-nazionale-monza_dkr-engineering-4-elms25.json` | 6 | 6 |
| `bahrain-international-circuit_dkr-engineering-4-elms25.json` | 13 | 13 |
| `bahrain-outer-circuit_dkr-engineering-4-elms25.json` | 6 | 6 |
| `bahrain-outer-circuit_richard-mille-af-corse-2026-50-elms.json` | 11 | 11 |
| `circuit-de-barcelona.json` | 16 | 16 |
| `circuit-de-barcelona_dkr-engineering-4-elms25.json` | 12 | 12 |
| `circuit-de-barcelona_ferrari-af-corse-2026-50-lm.json` | 14 | 9 |
| `circuit-de-la-sarthe_dkr-engineering-4-elms25.json` | 19 | 6 |
| `circuit-de-spa-francorchamps-endurance_dkr-engineering-4-elms25.json` | 11 | 11 |
| `circuit-de-spa-francorchamps_dkr-engineering-4-elms25.json` | 17 | 10 |
| `circuit-of-the-americas_dkr-engineering-4-elms25.json` | 14 | 14 |
| `daytona-international-speedway-road-course_dkr-engineering-4-elms25.json` | 12 | 8 |
| `daytona-international-speedway-road-course_vista-af-corse-2026-54-wec.json` | 6 | 6 |
| `fuji-speedway-classic_vista-af-corsa-2026-54-wec.json` | 9 | 5 |
| `fuji-speedway_dkr-engineering-4-elms25.json` | 11 | 7 |
| `lusail-international-circuit_dkr-engineering-4-elms25.json` | 15 | 15 |
| `lusail-international-circuit_vista-af-corse-2026-54-wec.json` | 16 | 16 |
| `michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json` | 13 | 12 |
| `monza-curva-grande-circuit_dkr-engineering-4-elms25.json` | 10 | 3 |
| `monza-curva-grande-circuit_vista-af-corse-2026-54-wec.json` | 10 | 3 |
| `paul-ricard---1a-v2-short_ferrari-af-corse-2026-50-lm.json` | 13 | 2 |
| `paul-ricard---3a_dkr-engineering-4-elms25.json` | 9 | 5 |
| `sebring-international-raceway_logitech-g-challenge-9-lgc.json` | 10 | 8 |
| `silverstone-grand-prix-circuit---elms_dkr-engineering-4-elms25.json` | 18 | 7 |
| `silverstone-international-circuit_vista-af-corse-2026-21-lm.json` | 8 | 2 |
| `spa-francorchamps_wtm-12-lmp3-duqueine-hdf-spa.json` | 69 | 69 |
| `weathertech-raceway-laguna-seca_dkr-engineering-4-elms25.json` | 12 | 10 |
| `weathertech-raceway-laguna-seca_vista-af-corse-2026-54-wec.json` | 12 | 12 |
