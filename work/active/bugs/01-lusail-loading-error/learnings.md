# Learnings — 01 Lusail Loading Error

- A synthetic-fixture test passing does not prove the real file loads. The fixture exercised the hyparquet RLE overflow path, but a second spread overflow in `rebuildPickers` (`Math.max(...sliceTimes)`) only fired on the real session, where per-lap slices are large enough to hit the V8 limit. Always verify with the actual failing file, not just a crafted fixture.

- The V8 spread argument limit (~120k–199k elements) can be hit by ordinary app code, not only by library internals. Any `Math.max(...largeArray)` or `Math.min(...largeArray)` in application JS is at risk when the array comes from per-session telemetry data. Replace with `reduce` for any array whose size scales with session length or lap count.

- The bug doc "status: partial fix shipped" was premature — the app-level isolation existed in the source but had never been run against the actual failing file. Mark a fix as done only after loading the real session and observing the badge.

- A single root-cause can have multiple independent crash sites at different call-stack depths. The first one (hyparquet read) masked the second (pickers). Treat "it crashed here" as "it crashed here first," and keep testing after each fix.

- Writing `None` instead of `False` for inactive nullable bools in the recorder is both a correctness and a safety fix: pyarrow stores nulls in a definition-level bitmap with no data run, so the overflow risk disappears regardless of session length or track character.
