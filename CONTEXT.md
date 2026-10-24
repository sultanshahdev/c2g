# c2g — Code 2gether Context

## Project identity and architecture

Code 2gether (c2g) is a Python/Tkinter peer-to-peer collaborative text editor
derived from the MIT-licensed P2PDocs project. The UI
uses `CRDTDocument` for RGA-like character operations, `NetworkManager` for
JSON-framed socket messages, and `PersistenceManager` for asynchronous pickle
state storage beneath `~/.p2p_crdt/`.

## Current milestone

M0 — Baseline and Agent-Ready Development Foundation: **COMPLETE (G0 PASS)**.
M1 — CRDT Convergence, Causal Handling, and State Correctness: **COMPLETE (G1
PASS)**. c2g was rebranded locally while retaining P2PDocs historical-source
references and attribution. Original history remains on `main` at `5bf7a3b`.
M2 — Reliable peer connectivity and state exchange: **PARTIAL (automated G2
evidence complete; manual GUI/LAN smoke outstanding)**. Protocol v2 now has
framed HELLO negotiation, process-local UUID peer identity, explicit document
UUID join semantics, target-session snapshots plus a bounded sync-window replay
buffer, bounded relay de-duplication, configurable/ephemeral ports, capped
inbound handshakes, and local-receipt LAN discovery records. Tk receives all
network/discovery events via a main-thread queue and lists discovered endpoints
with explicit Connect actions. `tests/test_network_m2.py` has eight loopback /
headless tests; the full suite reports **30 passed**. G2 remains PARTIAL solely
because manual two-instance Tk/LAN discovery verification was not executable
in this environment. M3 — Monaco + pywebview feasibility spike: **PARTIAL**.
pywebview 6.2.1 with GTK launches a native Linux Monaco window; its local
worker and JavaScript/Python bridge paths were smoke-tested. A narrow CRDT
insertion batch makes the 10,003-code-point paste pass. G3 remains partial
because Windows/WebView2 and automated native cursor/selection evidence are
unverified. See `docs/M3_MONACO_FEASIBILITY_REPORT.md`. M4 — Production Monaco
desktop integration: **PARTIAL**. The default CLI now starts the pywebview
Monaco host, with one serialized controller using the existing M1 CRDT and M2
network manager; focused real-loopback two-peer editing passes. Native
multi-window, three-peer UI, cursor assertions, and Windows evidence remain
outstanding. See `docs/M4_DESKTOP_INTEGRATION_REPORT.md`.
M4 also includes an explicit Disconnect Peer control backed by M2's guarded
session cleanup; automated loopback tests cover disconnect, independent offline
edits including tombstones, and explicit reconnect convergence.

## Development environment

- Ubuntu 24.04-derived Linux kernel 7.0.0-38-generic, x86_64.
- Python 3.12.3 in `.venv`; package `c2g 0.1.0` is installed editable from
  this repository after reinstallation.
- pytest 8.x is declared in the `test` extra (`pytest>=7,<9`).
- Graphify 0.9.59 is installed. An AST-only local index was generated at
  `graphify-out/` (ignored); Codex instructions were installed in `AGENTS.md`.
- Git root: `/home/sultan/Desktop/repos/c2g`, with one `.git` directory and
  historical baseline `5bf7a3b` from the original P2PDocs repository. The only
  configured c2g remote is
  `git@github.com:sultanshahdev/c2g.git`; migration changes remain local until
  reviewed and committed.
- Proposed future Python baseline: 3.12+, pending a future packaging decision;
  the current `>=3.7` declaration remains unchanged.

## Test baseline

Run `./.venv/bin/python -m pytest -q` (or
`python -m pytest -q` with the virtual environment activated). M3 verification
result: **40 passed**. Fixtures replace `PersistenceManager` in the document module
with an in-memory double, so tests create no persistence workers or user-state
files. The historical six regressions are now normal passing tests.

## Corrected CRDT behavior (M1)

- Insert records now retain immutable predecessor and optional right-anchor
  references. Iterative, deterministic linearization preserves tombstones and
  honors local start/middle/end gaps; contradictory concurrent right anchors
  are discarded deterministically only when they would create a cycle.
- Unknown-parent inserts are causally pending and unrendered until resolution.
  Unknown deletes become pending tombstones; deletion is false-dominant.
- Full-state merging is idempotent and order-independent for compatible
  records, rejects conflicting immutable identities, carries pending tombstone
  markers, and restores a collision-safe Lamport clock.
- The six M0 regressions (REG-01 through REG-06) pass without xfail markers.

## M1 decisions and compatibility

M1 retained the character-level APIs and existing JSON element payloads.
`before_id` is an optional field, so old element records remain readable.
Full-state lists can now include `_crdt_pending_delete` markers; same-version
peers preserve unknown deletes during snapshots. M2 must add a negotiated
protocol version before relying on that extension with older peers. Persistence
stores pending tombstones in an optional field; the M5 pickle/format migration
remains deferred.

## Files changed in M0

`AGENTS.md`, `CONTEXT.md`, `.gitignore`, `pyproject.toml`, `setup.py`,
`MANIFEST.in`, `README.md`,
`.github/workflows/tests.yml`, `tests/conftest.py`, `tests/test_crdt_basics.py`,
`tests/test_crdt_regressions.py`, `docs/M0_BASELINE_REPORT.md`, and the Git
rename from `p2pdocs/` to `c2g/`. The restored planning records
(`docs/IMPLEMENTATION_PLAN.md`, `docs/CHANGE_REQUEST.md`, and
`docs/MODERNIZATION_RESEARCH.md`) are also included. The former publishing
workflow is retained as disabled `.github/workflows/publish.yml.disabled`.
M1 additionally changes `c2g/crdt/document.py`, `c2g/crdt/types.py`, the
minimal `PersistenceManager.save_state` interface, `tests/conftest.py`, and
adds `tests/test_crdt_m1.py` plus `docs/M1_CRDT_CORRECTNESS_REPORT.md`.
Graphify also generated ignored local artifacts in `graphify-out/` and `.codex/`.

## Known limitations and next action

The historical `~/.p2p_crdt/` path and message names are deliberately
unchanged; path/data migration is deferred to M5 and negotiated protocol
versioning to M2. The new M1 snapshot tombstone marker is documented but not
yet negotiated with legacy peers. G2 still needs its manual Tk/LAN smoke; G3
still needs Windows/WebView2 and automated native selection evidence. **M4
remains unstarted and requires explicit authorization.**
