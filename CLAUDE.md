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

## Knowledge Graph (Graphify)

This project has a Graphify knowledge graph at `graphify-out/`. **Always use
it before reaching for `grep` or reading raw files.**

Rules (enforced on every prompt):

1. **Before answering any architecture or codebase question**, read
   `graphify-out/GRAPH_REPORT.md` to orient using god nodes and community
   structure. Do this _before_ opening individual source files.
2. **Cross-module questions** (e.g. "what calls X", "how does Y relate to Z")
   must use the Graphify CLI instead of grep:
   - `graphify query "<question>"` — semantic search over the graph
   - `graphify path "<A>" "<B>"` — shortest dependency path between two nodes
   - `graphify explain "<concept>"` — summarise a node and its neighbours
3. **If the Graphify MCP server is active**, prefer `query_graph`, `get_node`,
   and `shortest_path` tools over CLI equivalents.
4. **After modifying any source file** in the session, run
   `graphify update .` to keep the graph current (AST-only, zero API cost).
5. The god nodes (highest connectivity) are: `Settings` (39 edges),
   `ScoringEngine` (21), `ManifestLoader` (17), `DecisionEngine` (17),
   `Pipeline` (17), `ManifestCleaner` (17), `ProfitEngine` (16), `Enricher`
   (15). Start navigation from these when exploring unfamiliar areas.

Never read 5+ source files sequentially when the graph can answer the question
in one step.

## Tests

`pytest` runs the full suite. Add a regression test for any externally visible
behavior change. End-to-end smoke tests live in `tests/test_pipeline.py`;
schema-level coverage in `tests/test_real_manifest_schema.py`. New stages need
their own `tests/test_<stage>.py`.
