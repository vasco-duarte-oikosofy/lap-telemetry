# Bug 09 learnings

1. **Rule numbering is fragile.** Adding rules 11 and 12 meant renumbering the old Rule 11 to Rule 13. Any test that checks for specific rule text by number would break. Our tests search for content patterns, not numbers, so this was fine.

2. **JS wrapper needed for Python tests.** The test runner (`test-summary.sh`) executes `.js` files via Node. Python tests need a thin `.js` wrapper that uses `spawnSync` to call `python3`. Lesson L12 in TESTING_LESSONS.md documents this pattern.

3. **Package.json feature suites must reference `.js` wrappers**, not `.py` files directly. Putting `.py` paths in `testFeatures` causes Node to try parsing Python as JS, which fails with a SyntaxError on the docstring.

4. **`max_words=35` may be too tight** for the new "You gained time in … You lost time at …" pattern. The mixed fixture uses 45 to fit both gain and loss messages. If production utterances get truncated, bump `max_words` in the facts constraints.

5. **The LLM follows the new rules well.** E2E testing with all 5 corpus fixtures shows every utterance now leads with "You gained time" or "You lost time", and mixed cases report gains before losses with a natural sentence break.