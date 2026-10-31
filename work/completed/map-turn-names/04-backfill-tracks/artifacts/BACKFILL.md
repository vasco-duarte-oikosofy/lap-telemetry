# Backfill — every outline we have

`python3 dev/scripts/bake_outline_turns.py --all` on 2026-10-31, then measured
with the slice-01 placement harness at the canonical **250 px** map.

## Baked (14 of 22 outlines)

| Track | Turns | Model used (curated names) | Labels at 250 px | Notes |
|---|---|---|---|---|
| Autodromo Enzo e Dino Ferrari (Imola) | 11 | dkr 11/11 | 11/11 | T3, T10 → numbers (chicane pairs) |
| Autódromo José Carlos Pace | 15 | dkr 15/15 | 15/15 | |
| Circuit de Barcelona-Catalunya | 14 | ferrari-50 7/14 | 14/14 | short names removed the one dropped label |
| Circuit de la Sarthe | 19 | dkr 19/19 | 18/19 | T13 dropped, T19 → number (Pont/Raccordement pairs) |
| Daytona Road Course | 12 | dkr 6/12 | 12/12 | 6 corners have no curated name yet |
| Fuji Speedway Classic | 9 | vista-54 9/9 | 9/9 | T1, T9 → numbers |
| Michelin Raceway Road Atlanta | 13 | dkr 3/13 | 13/13 | official naming is `Turn N`; T4 → "Esses" |
| Monza Curva Grande | 10 | dkr 10/10 | 10/10 | 7 short names curated |
| Paul Ricard 1A-V2-Short | 13 | ferrari-50 13/13 | 13/13 | T5 → number; 9 short names curated |
| Paul Ricard 3A | 9 | dkr 8/9 | 9/9 | T1 → number |
| Sebring International | 10 | lgc-9 5/10 | 10/10 | T10 → number |
| Silverstone GP (ELMS) | 18 | dkr 18/18 | 18/18 | |
| Silverstone International | 8 | vista-21 8/8 | 8/8 | |
| WeatherTech Raceway Laguna Seca | 12 | dkr 4/12 | 12/12 | 2 short names curated |

Zero string overlaps on all 14 tracks; every visible label is within
**2.5–5.1 px** (mean) of its apex.

## Skipped (8) and why

| Outline | Reason |
|---|---|
| `autodromo-nazionale-monza` | model not curated (6 placeholder corners; Monza has 11 turns) |
| `bahrain-international-circuit` | model not curated (13 placeholders) |
| `bahrain-outer-circuit` | model not curated (11 placeholders) |
| `circuit-of-the-americas` | model not curated (14 placeholders) |
| `lusail-international-circuit` | model not curated (16 placeholders) |
| `spa-francorchamps` | model not curated (69 placeholders — clearly over-segmented) |
| `bahrain_outline`, `fuji-speedway_outline`, `circuit-de-barcelona-median` | no coaching model for that slug (legacy/alternate outline files) |

Baking those would put a wrongly numbered `T1..Tn` on the map, so the tool
refuses them and says why. They need coaching-model curation first (a data task
in the coaching pipeline, not a rendering task).

## Short names curated in this slice

Added `short_name` to the coaching models (display-only; `name` unchanged so the
coach still speaks the official name):

| Track | Name → short name |
|---|---|
| Barcelona | `Turn 3 — Renault` → `Renault`, `Turn 4 — Repsol` → `Repsol`, `Turn 7 — Würth` → `Würth`, `Turn 9 — Campsa` → `Campsa`, `Turn 10 — La Caixa` → `La Caixa` |
| Daytona | `International Horseshoe` → `Horseshoe`, `Turn 5 (West Horseshoe)` → `West Horseshoe`, `Turn 9/10 (Bus Stop 1/2)` → `Bus Stop 1/2` |
| Road Atlanta | `Turn 4 (The Esses)` → `Esses` |
| Laguna Seca | `Corkscrew (Turn 8)` → `Corkscrew`, `Rainey Curve (Turn 9)` → `Rainey` |
| Monza Curva Grande | `Variante della Roggia 1/2` → `Roggia 1/2`, `Curva del Serraglio` → `Serraglio`, `Variante Ascari 1/2/3` → `Ascari 1/2/3`, `Curva Alboreto (Parabolica)` → `Parabolica` |
| Paul Ricard 1A-V2-Short | `S de la Verrerie 1/2` → `Verrerie 1/2`, `Virage de l'Hotel 1/2` → `l'Hotel 1/2`, `Virage du Camp` → `Camp`, `Virage de la Sainte-Beaume` → `Ste-Beaume`, `Virage de Bendor` → `Bendor`, `Virage de la Tour` → `la Tour`, `Virage du Pont` → `Pont` |
| Paul Ricard 3A | `L'Epingle de Bendor` → `Bendor`, `Virage de la Tour` → `la Tour`, `Virage du Pont` → `Pont` |
| Imola | `Variante Villeneuve 1/2` → `Villeneuve 1/2` |
| La Sarthe | `Mulsanne Corner` → `Mulsanne`, `Indianapolis Entry` → `Indianapolis`, `Virage du Pont Entry/Exit` → `Pont Entry/Exit` |

## Review images (`artifacts/`)

`labels-monza-curva-grande-circuit-250.png`,
`labels-silverstone-international-circuit-250.png`,
`labels-circuit-de-la-sarthe-250.png` (19 turns, the densest),
`labels-paul-ricard---1a-v2-short-250.png` (chicane pairs),
`labels-circuit-de-barcelona-250.png`,
`labels-silverstone-grand-prix-circuit---elms-250.png`.
