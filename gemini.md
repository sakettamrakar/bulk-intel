# Gemini AI Assistant General Rules

## Always Use Graphify Knowledge Graph
This project has a **Graphify knowledge graph** configured to help you understand the codebase. **For every prompt and response where architecture, code understanding, or file navigation is required, you must refer to the graphify knowledge graph.**

### Required Workflow:
1. **Initial Orientation**: Before answering architecture or codebase questions, read `graphify-out/GRAPH_REPORT.md` (via `view_file`) for god nodes and community structure.
2. **Knowledge Graph Navigation**: If `graphify-out/wiki/index.md` exists, navigate it instead of reading raw files.
3. **Use the Graphify CLI**: Instead of falling back to standard `grep_search`, use graphify to understand the project map:
   - Run `graphify query "<question>"` to do a semantic search over the graph.
   - Run `graphify path "<A>" "<B>"` to find dependencies between modules.
   - Run `graphify explain "<concept>"` to summarize an entity and its connections.
4. **Maintain the Graph**: After you modify code files in this session, always run `graphify update .` in terminal to keep the AST graph current.
5. **Prefer High-Level Topology**: Never read 5+ source files sequentially when the Graphify graph can answer the question in fewer steps. Ensure all analyses are grounded in the project's knowledge graph topology.
