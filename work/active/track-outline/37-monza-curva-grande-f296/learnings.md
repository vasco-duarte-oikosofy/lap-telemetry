# Learnings — Slice 37 (new car on a track that already has a curated model)

- **"Check for a faster lap" turned out to be "this combo does not exist yet".**
  The newest sessions were Ferrari 296 GT3, but every Monza Curva Grande file on
  disk was Ginetta LMP3. Worth checking before comparing times: a 1:39.4 GT3 lap
  is not "slower" than the 1:35.2 reference, it is a different race car. The coach
  resolves by (track, canonical car) since bug 27, so it correctly refused to
  compare them — and returned nothing at all for the F296.

- **The reference filename's car id is the *vehicle name* slug, not the catalog
  slug.** `Vista AF Corse 2026 #54:WEC` → `vista-af-corse-2026-54-wec`, while the
  catalog maps that car to `ferrari-296-gt3`. The resolver bridges the two: it
  slugifies the filename and canonicalises through the catalog, so one F296
  livery's files serve all F296 liveries. That is why the pair is named after the
  session's livery and still resolves for `2025 #21:LM`.

- **The updater is the right tool even for a brand-new car.** It refuses to run
  without an existing model file, so the sequence is: seed a copy of the curated
  model for the new car id, then `--ref <new ref> --allow-unmatched`. The updater
  then does the part that matters — it re-checks every curated corner against the
  new lap before writing anything — and keeps old geometry for corners the new lap
  cannot reproduce.

- **A GT3 lap reproduces fewer corners than an LMP3 lap: 5 of 10 here.** Both flat
  corners (expected, the detector can never see them) plus Roggia 2, Ascari 2 and
  Ascari 3, because the slower car brakes once for each complex instead of
  splitting it. `--allow-unmatched` keeps those zones intact rather than deleting
  half the chicanes; the names and flat markers all survive.

- **The geometry deltas are small and in one direction.** −16 … +10 m on the five
  reproduced corners (the GT3 turns in slightly earlier at Lesmo, later at the
  Parabolica). That is the sanity signal that the anchor is the same circuit: a
  wrong track or a bad lap would move apexes by hundreds of metres.

- **`--print-facts` is the cheapest end-to-end proof.** A 1:41.007 lap against the
  new 1:39.398 reference reported `lap_time_delta_s 1.609` exactly, and resolved
  every corner id to its official name — no KeyError, no car-blind fallback.
