# c2g — Code 2gether Context

## Project identity and architecture

Code 2gether (c2g) is a Python/Tkinter peer-to-peer collaborative text editor
derived from the MIT-licensed P2PDocs project. The UI
uses `CRDTDocument` for RGA-like character operations, `NetworkManager` for
JSON-framed socket messages, and `PersistenceManager` for asynchronous pickle
state storage beneath `~/.p2p_crdt/`.

## Current milestone

M0 — Baseline and Agent-Ready Development Foundation: **COMPLETE (G0 PASS)**.
c2g was rebranded locally without changing CRDT behavior. The restored planning
documents were validated and aligned to the active c2g package while retaining
P2PDocs historical-source references and attribution. Original history remains
on `main` at `5bf7a3b`. M1 has not started and requires explicit authorization.

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
`python -m pytest -q` with the virtual environment activated). M0 final result:
**6 passed, 6 xfailed**. Fixtures replace `PersistenceManager` in the document
module with an in-memory double, so tests create no persistence workers or
user-state files.

## Verified CRDT defects (deferred to M1)

- REG-01: middle insertion expects `AXB`, actual `ABX`.
- REG-02: beginning insertion expects `XAB`, actual `ABX`.
- REG-03: a full-state insertion suppresses its later remote delete.
- REG-04: a delete received before its insert is lost; actual visible text `A`.
- REG-05: hiding a predecessor promotes its descendant to a head; expected
  `BH`, actual `HB` in the ordering probe.
- REG-06: applying a newer tombstone state over an old visible copy leaves it
  visible; actual `A`.

## M1 decisions to approve

Define ordering/traversal over the full element graph (including tombstones),
explicit pending-predecessor and pending-delete handling, distinct insert and
delete operation identities, monotonic full-state merge semantics, persisted
replica/document identities and Lamport clocks, plus versioned network and
persistence formats. None is implemented or approved by M0.

## Files changed in M0

`AGENTS.md`, `CONTEXT.md`, `.gitignore`, `pyproject.toml`, `setup.py`,
`MANIFEST.in`, `README.md`,
`.github/workflows/tests.yml`, `tests/conftest.py`, `tests/test_crdt_basics.py`,
`tests/test_crdt_regressions.py`, `docs/M0_BASELINE_REPORT.md`, and the Git
rename from `p2pdocs/` to `c2g/`. The restored planning records
(`docs/IMPLEMENTATION_PLAN.md`, `docs/CHANGE_REQUEST.md`, and
`docs/MODERNIZATION_RESEARCH.md`) are also included. The former publishing
workflow is retained as disabled `.github/workflows/publish.yml.disabled`.
Graphify also generated ignored local artifacts in `graphify-out/` and `.codex/`.

## Known limitations and next action

The six strict expected failures are intentionally unresolved. The historical
`~/.p2p_crdt/` path and wire message names are deliberately unchanged; path/data
migration is deferred to M5 and protocol versioning to M2. Searches across the
supplied home/archive paths and all reachable upstream Git history informed the
original baseline record; the planning documents have since been restored and
are now present. Next action: **M1 — CRDT Correctness, awaiting explicit
authorization.**
