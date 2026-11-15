# Barcelona numerical regression inputs

`barcelona_reference_time_01.36.456.parquet` and
`barcelona_reference_model.json` are byte-for-byte snapshots of the committed
Barcelona/Ginetta P3 reference and model at `f951d2a` (before the race/quali
refreshes). The lap is the historical 1:36.456 reference; this is test data,
not another active reference.

The JS-pipeline, delta-time-gain and speed-minimum generator tests assert exact
values measured on that lap (including the user-confirmed web-UI delta trace).
They must not silently switch to a future personal-best lap or model when the
live reference is superseded. Keep their original assertions and tolerances.

The live reference/model are separately checked by
`dev/scripts/test_barcelona_p3_reference.py` and its Node wrapper, including
car-aware resolution, authoritative duration, curation and source-row identity.

The model snapshot's historical `reference_lap.path` is provenance only; these
numerical tests pass the fixture parquet explicitly to the comparator.
