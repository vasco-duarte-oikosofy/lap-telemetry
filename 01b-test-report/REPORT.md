# Phase 01b Test Report

Passed: 13
Failed: 0

| Status | Assertion | Detail |
|--------|-----------|--------|
| PASS | sLookup at start returns exact sample | {"s":0,"x":0,"z":0,"speed":0} |
| PASS | sLookup at exact middle sample returns exact sample | {"s":25,"x":2,"z":20,"speed":40} |
| PASS | sLookup at end returns exact sample | {"s":200,"x":9,"z":90,"speed":200} |
| PASS | sLookup interpolates mid-point correctly | {"s":50,"x":3.5,"z":35,"speed":70} |
| PASS | sLookup interpolates another mid-point correctly | {"s":32.5,"x":2.5,"z":25,"speed":50} |
| PASS | sLookup is monotonic (ascending s → ascending x) |  |
| PASS | monotonicity check covers 41 positions | 41 |
| PASS | sLookup random property: interpolated s within epsilon | worst diff 0 |
| PASS | monotonicity assertion throws on non-monotonic data | [sAlignment] test_s is NOT strictly monotonic at index 3: 20 → 15 |
| PASS | assertion message contains violation index | [sAlignment] test_s is NOT strictly monotonic at index 3: 20 → 15 |
| PASS | monotonicity assertion passes on strictly monotonic data |  |
| PASS | debug ticks render white pixels on canvas | whiteCount=156 |
| PASS | sAlignment debug screenshot artifact written | 2644 bytes |