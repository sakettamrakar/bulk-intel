# CLAUDE.md — project conventions

## Documentation

**Always update documentation when changing code.** Whenever a code change alters
behavior, configuration, public API, output format, or how the system is run, update
the relevant docs in the same commit.

Specifically:

- **`README.md`** — keep the system overview, folder structure, data-flow diagram,
  config table, and "How to run" section in sync with the code. New canonical
  columns, new pipeline stages, new CLI flags, new config knobs, and new output
  fields all belong here.
- **Module docstrings** — when you add or remove columns produced by a stage,
  update the docstring at the top of the module that describes its outputs
  (e.g. `intelligence/profit.py`, `output/reporter.py`).
- **Function docstrings** — keep type hints, ``Args``, and ``Returns`` accurate.
  If you add a new column to a returned DataFrame, mention it.
- **`config/settings.py`** — every new tunable needs a one-line comment
  explaining what it does, and an entry in the README config table.
- **Tests as documentation** — when adding new behavior, also add a regression
  test that demonstrates it. The test name itself is documentation.

Do not defer documentation updates to "a later pass". Code and docs ship together
in the same commit so reviewers and future readers always see a consistent picture.

## Architecture

The pipeline is structured as: **ingestion → cleaning → enrichment → pricing →
scoring → profit → decision → reporting**. Each stage is a small module with a
typed entry point and a functional wrapper. Keep stages pure: only `ingestion`
and `output` perform I/O. Pluggable strategies (e.g. `PriceProvider`) use the
`typing.Protocol` pattern, not inheritance.

Configuration lives in `config/settings.py` as an immutable `Settings`
dataclass. Domain experts should be able to tune the engine by editing this
file without touching business logic.

## Tests

`pytest` runs the full suite. Add a regression test for any externally visible
behavior change. End-to-end smoke tests live in `tests/test_pipeline.py`;
schema-level coverage in `tests/test_real_manifest_schema.py`. New stages need
their own `tests/test_<stage>.py`.
