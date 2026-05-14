# Phase 01a Test Report

Passed: 10
Failed: 0

| Status | Assertion | Detail |
|--------|-----------|--------|
| PASS | colorForNet(-1) exact endpoint | #0a3d91 |
| PASS | colorForNet(0) exact endpoint | #2a3340 |
| PASS | colorForNet(1) exact endpoint | #0f7a2e |
| PASS | colorForNet(-0.5) closer to brake endpoint than neutral | #173c76 distances 0.0455 < 0.0939 |
| PASS | colorForNet(0.5) closer to throttle endpoint than neutral | #19674d distances 0.0833 < 0.1682 |
| PASS | net color LUT has 256 entries | 256 |
| PASS | LUT matches colorForNet at integer positions | [] |
| PASS | braking-zone pixel is brake-blue | {"r":23,"g":60,"b":118,"a":255} |
| PASS | throttle-zone pixel is throttle-green | {"r":15,"g":122,"b":46,"a":255} |
| PASS | synthetic ribbon screenshot artifact written | 1259 bytes |