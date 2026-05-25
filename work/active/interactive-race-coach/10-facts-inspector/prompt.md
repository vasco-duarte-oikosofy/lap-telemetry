# Slice 10: Facts Inspector

## Context

You are working inside `C:\Users\duart\lap-telemetry`, a telemetry recorder and
lap-comparison tool for Le Mans Ultimate (LMU). The codebase lives under
`product/python/lap_telemetry/`. All Python source is under
`product/python/lap_telemetry/`; test scripts live in `dev/scripts/`.

This is slice 10 of the interactive-race-coach mission. Slices 01–09 are
complete or in progress.

The live coaching pipeline can generate facts (lap comparison, corner exits,
fuel) but there is no standalone way to inspect them without also calling the
LLM. `generate_utterance.py` leaks facts only to stderr under `--debug`, which
is awkward — you have to run LLM inference just to see what the fact generator
computed.

---

## Goal

Add `--print-facts` to `generate_utterance.py` so the developer can inspect
facts without touching the LLM. When this flag is set:

1. Load or generate facts as normal.
2. Print the full facts JSON to **stdout** (pretty-printed, indent=2).
3. Exit **without** calling the LLM.

This gives a clean one-liner facts inspector:

```powershell
# From a canned JSON fixture
python -m lap_telemetry.coach.generate_utterance `
    --facts dev/fixtures/coach/barcelona_lap15_facts.json `
    --print-facts

# From live parquet files
python -m lap_telemetry.coach.generate_utterance `
    --lap `
    --current-lap  dev/fixtures/coach/barcelona_lap15_current.parquet `
    --reference-lap product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet `
    --track-config  product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json `
    --print-facts
```

---

## Scope

### Modified files

1. **`product/python/lap_telemetry/coach/generate_utterance.py`**

   Add `--print-facts` flag to the argument parser:

   ```python
   parser.add_argument(
       "--print-facts",
       action="store_true",
       help="Print facts JSON to stdout and exit without calling the LLM.",
   )
   ```

   After facts are loaded/generated (before the LLM call), insert:

   ```python
   if args.print_facts:
       print(json.dumps(facts.to_dict(), indent=2))
       return 0
   ```

   Remove the existing `--debug` facts dump from stderr (or keep it
   alongside — see Non-goals). The `--print-facts` output goes to **stdout**
   so it can be piped (`| python -m json.tool`, `| jq`, etc.).

### New files

2. **`dev/scripts/test_facts_inspector.py`**

   Unit tests (no sim, no LLM, no parquet files):

   1. `main(["--facts", FIXTURE, "--print-facts"])` exits with code 0.
   2. Captured stdout is valid JSON.
   3. Parsed JSON contains `"top_losses"` key.
   4. Parsed JSON contains `"lap_number"` key.
   5. `main(["--facts", FIXTURE, "--print-facts"])` does **not** call the LLM
      (mock `generate_utterance` and assert it was never called).
   6. `main(["--facts", FIXTURE])` (no `--print-facts`) **does** call the LLM
      (mock returns a string, assert called once).
   7. Without `--print-facts`, stdout contains the utterance, not JSON.

   Use `FIXTURE = Path("dev/fixtures/coach/barcelona_lap15_facts.json")` — it
   already exists and is used by other tests.

   Use `unittest.mock.patch` to mock
   `lap_telemetry.coach.generate_utterance.generate_utterance` (the imported
   name in the module under test).

   Capture stdout with `contextlib.redirect_stdout` + `io.StringIO`.

3. **`dev/scripts/test_facts_inspector.js`**

   Node child-process wrapper — same pattern as `test_corner_exit_coaching.js`.
   Runs the Python test and forwards stdout/stderr with exit-code passthrough.

### Updated files

4. **`package.json`**

   Add `"test_facts_inspector.js"` to the `interactive-race-coach` feature
   tests array.

---

## Key files to read before starting

- `product/python/lap_telemetry/coach/generate_utterance.py` — the file to extend
- `dev/fixtures/coach/barcelona_lap15_facts.json` — fixture used by tests
- `dev/scripts/test_corner_exit_coaching.js` — JS wrapper pattern to copy
- `dev/scripts/test_corner_exit_coaching.py` — mock pattern to copy
- `package.json` — where to add the new JS test

---

## Acceptance criteria

- [ ] `--print-facts` flag exists in `generate_utterance.py`
- [ ] `--print-facts` prints valid JSON to stdout and exits 0
- [ ] `--print-facts` does not call the LLM
- [ ] Without `--print-facts`, behaviour is unchanged (utterance printed to stdout)
- [ ] Unit tests pass: `bash scripts/test-summary.sh --feature interactive-race-coach`
- [ ] `npm run build` succeeds

## Definition of Done

- [ ] `generate_utterance.py` updated with `--print-facts`
- [ ] `test_facts_inspector.py` with ≥ 7 assertions
- [ ] `test_facts_inspector.js` JS wrapper
- [ ] `package.json` updated
- [ ] All tests green
- [ ] `handoff.md` + `learnings.md` written in this folder

## Non-goals

- Do not remove `--debug` — it dumps to stderr and is orthogonal; keep both flags.
- No new facts types (fuel, corner-exit) need `--print-facts` support in this
  slice; they go through different entry points.
- No colour / pretty-print beyond `indent=2` — plain JSON is enough for piping.
- No changes to how facts are structured or serialised.
