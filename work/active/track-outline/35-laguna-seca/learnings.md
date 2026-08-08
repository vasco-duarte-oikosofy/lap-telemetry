# Learnings — Slice 35 (Laguna Seca)

- **Steering sign convention is unreliable even WITHIN a lap.** The steering
  column and the position-trace heading change disagreed at Turn 6 (steering
  said right, the car's actual path was left-down). Spent far too long on this.
  Lesson: for apex sides, trust the track guide, not the raw steering sign.
  This matches the Daytona finding (slice 34).

- **Laguna Seca is 11 turns but the detector found 10.** Turn 10 is a fast
  (~150 kph) corner whose braking runs straight into Turn 11, so the
  throttle-brake detector merged them. Added Turn 10 manually at ~3200 m from
  the speed/steering trace.

- **The Andretti Hairpin (Turn 2) min speed is ~104 kph for this WEC prototype**
  — much faster than a street car (45 mph). Don't judge corner type by the
  guide's car-specific speeds.

- **Turn 8 "Corkscrew" apex is on the right-hand part.** The detector's apex
  (2767 m) is the 8B right section, not the 8A left crest. Named it "Corkscrew
  (Turn 8)" with apex_side left per the guide's entry direction.

- **Reference came from the practice session** (fastest valid lap 4 @ 1:27.905).
  The summary showed lap 5 @ 1:27.943 and lap 4 @ 1:27.905; the export correctly
  picked lap 4 (faster). No cut-lap rejection issue here.
