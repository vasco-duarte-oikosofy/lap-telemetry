# Learnings

- Live process_time includes all native ONNX workers, unlike thread_time, but
  also picks up concurrent recorder/analysis threads. Explicit process scope
  matters: do not call these numbers precisely attributed whole-lap coach CPU.
- The speech queue's two execution paths (initial and already-pending speech)
  both need instrumentation. Reporting only the first speak site misses chained
  fuel/corner utterances. A shared reporting path prevents this gap.
- Recording only around speak() folds audible playback into wall time. A tiny
  optional adapter snapshot isolates Kokoro load/synthesis without changing
  the existing speak() return contract or pretending other engines provide it.
- Reset stage timing before every attempt and snapshot in finally. A failed
  synthesis must not report the preceding successful utterance's timing.
- Default live logging is WARNING, so INFO timing logs would be invisible.
  Flushed stderr printing makes the requested data available without new flags.
- JSON-escaped actual text ties records to delivered utterances while keeping
  multiline text on one line. Unspoken stale pending items must not be counted.
- Hardware-safe real-model queue testing preserved the old waveform hash for
  cold and warm attempts. Its playback capture does not represent live race
  wall latency; retain that distinction in the next analysis.
