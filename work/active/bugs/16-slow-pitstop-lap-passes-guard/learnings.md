# Learnings — Bug 16

- The prompt's proposed `1.20` threshold did not catch the real repro: lap 13 is 84.42 s vs a 71.24 s reference, about 118.5% of reference. The implemented threshold is `1.15`, with `>` comparison, so exactly 115% still passes but the pitstop lap is rejected.
- The Python guard must use Bug 13's authoritative duration path. For lap 13, the next-segment scorer value is implausible versus raw lap time, so `authoritative_duration()` falls back to 84.42 s and the slow-lap guard catches it.
- Blocking arbitrary compares in `compare.html` broke existing UI tests because users compare uneven laps intentionally. The JS-side fix therefore marks implausibly slow full-distance segments as `partial` during segment annotation, so they cannot receive fastest-lap stars and are visibly flagged, while manual comparison still works.
