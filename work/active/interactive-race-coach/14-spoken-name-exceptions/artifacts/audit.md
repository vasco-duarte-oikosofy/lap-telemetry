# Exception correction audit

Compared all 33 models against pre-slice `e624f7a`. Exactly four short-name
values changed in three files:

| Model | Official name | Before | After |
|---|---|---|---|
| Interlagos DKR | Descida do Lago 1 | Lago 1 | Descida do Lago 1 |
| Interlagos DKR | Descida do Lago 2 | Lago 2 | Descida do Lago 2 |
| Monza Curva Grande DKR | Curva Grande | Grande | Curva Grande |
| Monza Curva Grande Vista AF Corse | Curva Grande | Grande | Curva Grande |

Parsed JSON with short_name removed is identical in every file: all geometry,
IDs, official names, corner order, throttle targets, references and speech zones
are unchanged. No map data changed. All other spoken aliases are unchanged.

Test-first: six failing assertions before the correction. After the correction:

- Feature suite: 702 assertions, 14 scripts, pass.
- Full --pw: 1659 assertions, 69 scripts, pass using the same temporary Windows
  import adapter documented in slice 13 (stock bug-20 issue remains unrelated).
- Build and diff whitespace checks pass. Curation --check has zero proposals.
