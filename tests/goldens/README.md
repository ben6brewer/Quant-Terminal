# Golden files

Canonical JSON snapshots written by `tests/golden_utils.py::assert_golden(name, data, area)`,
stored as `tests/goldens/<area>/<name>.json` (sorted keys, floats rounded to 8 significant
digits, NaN -> null, +/-inf -> "inf"/"-inf").

* Compare (default): `pytest ...` - a missing file or any difference fails the test.
* Rewrite: `pytest ... --update-goldens` (or `QT_UPDATE_GOLDENS=1`). Only do this in a
  `Behavior-Change: yes` commit whose body lists what changed (`Goldens: updated(<list>)`).

Helpers: `frame_digest(df)` (shape, index start/end/freq, per-column count/first/last/sum/min/max)
and `snapshot_chart(chart, hover=[...])` (pyqtgraph items, pens, view ranges, placeholder, tooltip).
Inputs come from the offline fakes in `tests/fixtures/` (`fake_fred`, `fake_yahoo` fixtures), so
goldens are deterministic and never touch the network.
