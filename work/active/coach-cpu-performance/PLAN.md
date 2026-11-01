# Coach CPU performance

Spec: [coach-cpu-performance](../../../docs/specs/coach-cpu-performance.md).

Goal: halve measured lap-end local CPU work first; then plan the path toward 10%.
Feature tests: `bash scripts/test-summary.sh --feature coach-cpu-performance`.

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-halve-lap-end-cpu` | 🔧 In progress | Measured original baseline, output-equivalent change using <=50% CPU work, real replay evidence and regression tests |

Further slices will be planned from measured remaining bottlenecks after slice 01.
