# c2g — Code 2gether Context

## Project identity and architecture

Code 2gether (c2g) is a Python/Monaco/pywebview peer-to-peer collaborative
text editor derived from the MIT-licensed P2PDocs project. The production UI
uses `CRDTDocument`, protocol-v2 `NetworkManager`, and JSON-backed `PersistedCrdt`
with autosave beneath `~/.c2g`. Legacy Tk/pickle modules remain for historical
compatibility; the production New/Resume path does not load them.

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
M5 — Safe Persistence and Recovery: **PARTIAL (M5-C implemented)**. A separate,
strictly validated versioned JSON store with atomic replace and backup recovery
now exists. M5-B adds opt-in `PersistedCrdt` creation/recovery preserving CRDT,
document, and replica identity state. M5-C wires this into Monaco with
New/Resume selection, coalesced autosave, per-replica process locks, persisted
post-join document IDs, and final shutdown flush. See
`docs/M5_PERSISTENCE_RECOVERY_REPORT.md`.

M5-D makes `pyproject.toml` canonical for Python 3.12+, PEP 639 MIT metadata,
and optional desktop/test/build dependencies. Wheel/sdist and clean-wheel
headless/CLI verification pass. Persisted two-peer restart/reconnect,
one-peer tombstone reconciliation, writer failure recovery, and abrupt
lock-owner release have regression coverage. G5 remains PARTIAL because native
M5 desktop persistence smoke checks were not executable; M6 owns frontend and
native artifact bundling.

M6 — Release Tooling and Headless Peer Simulation: **PARTIAL.** A PyInstaller
onedir recipe bundles Vite/Monaco assets through source/frozen resolution; the
Linux artifact contains the worker and passes a foreign-CWD CLI smoke. A real
persisted three-peer chain/cycle/reconnect simulation, Docker test definition,
and Linux/Windows CI build configuration are present. Native frozen GUI,
Windows CI execution, Docker execution, and physical-LAN discovery remain
unverified or blocked. DOMPurify 3.4.17 is explicitly substituted for Monaco's
embedded 3.4.15 sanitizer in the Vite bundle; see
`docs/M6_RELEASE_TOOLING_REPORT.md`.

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
- Supported Python baseline is 3.12+; package metadata is canonical in
  `pyproject.toml` and `setup.py` is a compatibility shim.

## Test baseline

Run `./.venv/bin/python -m pytest -q` (or
`python -m pytest -q` with the virtual environment activated). M6 verification
result: **61 passed**. Fixtures replace `PersistenceManager` in the document module
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
still needs Windows/WebView2 and automated native selection evidence. **M7 is now explicitly authorized; current gate and acceptance gaps are recorded below.**

## Startup picker correction (2026-10-24; scoped maintenance, no M7)

Confirmed the startup overlay bug: `#picker { display:grid }` overrides the
browser's default hidden styling. Added an important `[hidden]` display rule.
Also moved remote-patch callback installation outside the startup ready handler,
so the picker branch's early return cannot leave incoming peer patches without
an installed handler after New/Resume. No Python runtime/packaging changes.

Added `tests/test_picker_visibility.py`, using existing pytest plus an installed
Chrome/Chromium (skips when unavailable), to check computed display for initial
hidden, selection-visible, and selection-completed states against actual HTML
and CSS. It fails before the CSS correction and passes afterward.
`npm run build` passes (large-chunk warning). Full pytest: **61 passed, 1 failed**;
`test_picker_lists_documents_and_rejects_bad_key` uses default port 5000, already
occupied by another Python process (PID 11029); isolated rerun confirms failure.
The existing process was left untouched. Graphify was refreshed.

Automated source-run native GTK/pywebview smoke with isolated temporary storage
passed normal empty startup + New, existing-document Resume, and forced-new
startup. Checked computed picker display, editor/sidebar hit-testing, Monaco
focus and DOM text insertion reaching the real Python controller, and remote
patch callback availability. Physical keyboard/mouse interaction and live
multi-peer GUI verification remain pending; automated persistence/network
coverage passed in the suite. Native smoke emitted pywebview introspection
warnings for GTK native widget properties but completed all assertions.
The existing frozen executable still needs rebuilding to include these frontend
changes; no PyInstaller rebuild, commit, push, or M7 work was performed.

## Picker test isolation (2026-10-24)

The port-dependent failure was in
`tests/test_m5_application_persistence.py::test_picker_lists_documents_and_rejects_bad_key`,
not the CSS regression in `tests/test_picker_visibility.py`. The failing test now
uses `listen_port=0` for both application instances and `try/finally` shutdown;
its document-listing and invalid-key assertions are unchanged. Production code
was not modified. Focused picker tests: **2 passed**. Full pytest: **62 passed**,
superseding the occupied-port failure above. Graphify refreshed; no PyInstaller
rebuild or M7 work.


## M7 final validation (2026-10-24)

**Available implementation/validation DONE; G6 PARTIAL.** Final planned milestone
was explicitly authorized. See `docs/M7_FINAL_VALIDATION_REPORT.md` for all
results, exact acceptance steps, support matrix, and limitations. No known
unresolved demonstrated P0/P1 remains from executed checks; final release still
requires explicit owner approval.

Baseline reverified: 62 passed; the old port-dependent picker test already uses
port 0. Two recovery tests leaked non-daemon writers after printing results;
context-managed cleanup now allows pytest to exit. M7 final full suite: **68 passed
in 12.22 s**, with normal exit. Existing 100 seeds (0–99), three replicas × 30 edits, passed in
2.83 s. Frontend build passed; production npm audit has zero vulnerabilities.

Verified and fixed with failing-before/passing-after regressions:
- P0: save after corrupt-primary backup recovery could destroy the valid backup
  if final replace failed. Validate the primary before rotating it over backup.
- P1: three-peer rejoin snapshots/tombstones were not relayed to the connected
  neighbor. Forward nonempty snapshots through the existing deduplicated OP path.
- P1: cyclic resume rejected after starting a writer/acquiring ownership. Validate
  ancestry before acquiring those resources.

Changed in M7: `c2g/network/manager.py`, `c2g/storage/json_store.py`,
`c2g/storage/recovered_document.py`, `tests/test_crdt_recovery_m5.py`,
`tests/test_json_store_m5.py`, new `tests/test_m7_release_validation.py`, new
`scripts/validate_desktop.py`, new `docs/M7_FINAL_VALIDATION_REPORT.md`, README,
this context, and implementation plan. All earlier dirty work was preserved.

Native GTK/X11 source picker/New/Resume/forced-new, synthetic keyboard typing,
selection/delete/undo/redo, Unicode DOM insertion, real Saved locally/error DOM
status, UTF-8 controller export, and sidebar checks pass. Frozen native Xvfb
pointer/keyboard New+Resume, final-flush text and clean exit pass from `/tmp`.
The owner separately reports manual application success. Neither automated
input nor that general report proves the full physical acceptance checklist.

Exactly one final Linux onedir rebuild includes the M7 Python fixes. Executable
SHA-256: dc4c1f1e6c4c24507586f6ae8ea70132a0379d92572255bdcb1121bec73d36fb.
Checksum and foreign-CWD help pass; picker CSS fix, editor worker, and DOMPurify
3.4.17 are bundled. Correction to earlier reports: pywebview starts a loopback
asset server even with http_server=False. Runtime verifies 127.0.0.1 binding,
web/dist root, and rejected parent traversal; no document root is served.

Windows desktop build: NOT VERIFIED (inspected remote successful run contains
only pytest). Docker: NOT EXECUTED (daemon permission denied). Physical LAN:
NOT VERIFIED. Remaining human work: final artifact's full native dialog/clipboard
and multi-window checks, two-machine discovery, actual Windows build/WebView2,
Docker run, owner acceptance. Trusted-LAN-only, unauthenticated/unencrypted P2P;
no public-Internet safety claim. No commit, push, release publication, or PyPI
publication. Graphify refreshed once at completion.
