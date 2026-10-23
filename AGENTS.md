## c2g workflow

At session start, read this file and `CONTEXT.md`, identify the approved
milestone, read the relevant implementation plan when present, use Graphify,
and inspect the relevant source before editing. Do not begin a later milestone
without explicit authorization.

Keep changes scoped to the approved milestone. Prefer targeted changes and
regression tests; preserve P2P and offline behavior; avoid broad refactors and
unnecessary dependencies. At completion, run relevant tests, update
`CONTEXT.md`, refresh Graphify after code changes, report changed files and
unresolved failures, then stop before the next milestone.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
