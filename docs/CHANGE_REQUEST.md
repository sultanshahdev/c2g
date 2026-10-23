# c2g Change Request — Code 2gether Modernization

**Title:** Reliable P2P collaboration with a VS Code-grade editing surface and reproducible desktop distribution
**Status:** Proposed — pending approval
**Requested by:** Project owner
**Prepared:** 2026-10-23
**Source of truth:** `docs/MODERNIZATION_RESEARCH.md`, backed by paths/line numbers in the original P2PDocs code archive. c2g retains P2PDocs attribution, history, and MIT licensing.

## 1. Executive summary

Retain c2g as a **local-first, serverless Python desktop editor**. It is derived
from P2PDocs; replace its Tkinter text surface with a real Monaco editor (subject
to pywebview spike), correct the existing CRDT's concurrency and state-merge
defects, make peer joining/rejoining dependable, repair local recovery, modernize
supported Python and package metadata, and produce easy-to-run Windows/Linux
desktop artifacts. Docker should support automated isolated peer/network tests only.

This change request **does not** authorize implementation, migration, installers, downloads, or dependency installation. Architectural choices are **proposed**, not approved. Start with regression tests for proven defects; cosmetic UI changes must not mask synchronization errors.

## 2. Problem statement / current evidence

- **User experience:** `c2g/ui/editor.py:246-255` uses `tk.Text`, not a VS Code-equivalent editor. Basic layout doesn't match requested UX.
- **CRDT:** `crdt/document.py:130-173` ascending sibling order misplaces prepend and middle inserts; tombstone descendants lose stable ancestry; `:210-249` drops delete-before-insert and treats incoming element identity as deletion dedup marker.
- **Networking:** `network/manager.py:25-35,40-116` hardcodes peer port/identity assumptions; no initial state sync is triggered on connection; received messages aren't relayed (`ui/editor.py:584-674`). UDP discovers without connecting (`network/discovery.py`, `editor.py:280-359`).
- **Persistence:** GUI always clears prior state (`editor.py:25`); queue-based pickle saves are not crash-atomic, and `pickle.load` is unsafe for untrusted files (`storage/persistence.py:45-82`).
- **Build discipline:** No tests or Docker definition in the archive; Python >=3.7; conflicting metadata in `pyproject.toml` and `setup.py`; `publish.yml` has no test gate.
- **Security:** TCP inbound on `0.0.0.0:5000`, no authentication or encryption; validation needs hardening. Do not promise open-internet security.

## 3. Outcomes / success metrics

| ID | Measurable intended outcome | Acceptance test |
|---|---|---|
| OUT-01 | Familiar VS Code-like editing surface | Actual Monaco mounted with dark theme, line numbers, find, syntax highlighting, minimap setting, paste and selections |
| OUT-02 | Correct CRDT text ordering | Deterministic local inserts at start/middle/end; concurrent/randomized convergence tests pass |
| OUT-03 | No lost/undone remote deletion | Delete-before-insert and stale full-state replay tests pass; tombstones monotonic |
| OUT-04 | Join, disconnect, and rejoin without losing edits | Two-peer + three-peer integration tests with reconnect and duplicates |
| OUT-05 | Offline, coherent editing with cursor preservation | Monaco/Python model equality, no CDN and remote edit doesn't corrupt selection/undo |
| OUT-06 | Durable, safe document recovery | Fresh/resume tests, atomic writes, corruption handling, no arbitrary pickle autoload |
| OUT-07 | End-user packaging | Windows app folder and Linux app bundle smoke-tested on documented supported targets, no Python developer install needed |
| OUT-08 | Automated quality controls | Headless CI tests run before release; UI/desktop smoke test evidence recorded |

**Non-goal:** arbitrary number of worldwide peers, internet relays, NAT traversal, account management, enterprise encryption/security, perfect VS Code extension compatibility, and full IDE functionality.

## 4. Functional requirements

| ID | Priority | Requirement | Proof / acceptance |
|---|---|---|---|
| UI-01 | Must | Use actual Microsoft Monaco ESM code editor with offline-bundled assets | Native window loads dark Monaco offline, workers and language highlighting verified |
| UI-02 | Must | Match core editing UX: line numbers, find/replace, selection, clipboard, cursor navigation, bracket matching, configurable minimap | Manual/automated UI checklist on both platforms |
| UI-03 | Must | Apply local Monaco content changes as atomic CRDT transactions, including paste, selection replacement, delete, IME/multicursor where supported | Transaction/batch tests compare Python text and Monaco model |
| UI-04 | Must | Apply remote edits incrementally, preserve cursor/selection, avoid event feedback | Rapid cross-peer edits, selection tests, zero echoed duplicate local ops |
| UI-05 | Must | Correct UTF-16 ↔ Python code-point offsets for emoji and Unicode; define CRLF behavior | Emoji/multiline test suite passes |
| UI-06 | Must | Collaborative undo/redo has explicit semantics or is disabled until correct, never falsely advertised | Interleaved remote/local edit undo cases documented and passing for shipped behavior |
| UI-07 | Must | Keep direct-connect, discovered-peer list, connection status, text export, minimal identity and status controls | End-user flow parity checklist |
| CRDT-01 | Must | Correct start/middle/end local insertion | `AB` + `X@1` → `AXB`; prepend test passes |
| CRDT-02 | Must | Deterministic convergence across concurrent inserts and shuffled/duplicate delivery | Hypothesis/randomized multi-replica tests with seed reproducibility |
| CRDT-03 | Must | Tombstones preserve structural links, false visibility cannot be resurrected | Delete+insert descendant, repeated stale state test |
| CRDT-04 | Must | Pending unknown delete and missing insert predecessor handled without losing operations | Delete-before-insert and child-before-parent tests |
| CRDT-05 | Must | Full-state merge idempotent/commutative and correct with interleaved deletes | A+B merge order, stale snapshot, rejoin tests |
| CRDT-06 | Must | Unique IDs and monotonically advanced logical clocks through restart | Resume / multi-peer clock tests |
| CRDT-07 | Must | Reject invalid CRDT data, cycles, oversized input, invalid Unicode boundaries | Property/negative tests; no crash or partial unsafe merge |
| NET-01 | Must | Versioned, bounded framed handshake declares peer ID/listen port/doc ID and rejects incompatible peers | Loopback handshake tests including bad/missing fields |
| NET-02 | Must | On connection/reconnection exchange and reconcile state including tombstones | Nonempty join, missed edits and reconnect tests |
| NET-03 | Must | Forward relevant operations to other connected peers exactly once per ID, excluding origin | A↔B↔C test with no loops |
| NET-04 | Must | Configurable ports for local multi-instance testing; manual join retains simple IP flow | Two/three instances same host on distinct ports |
| NET-05 | Should | List discovered LAN peers and allow one-click explicit connect; do not automatically trust/connect | Discovery UI shows correct IP + advertised port, click initiates handshake |
| NET-06 | Must | Bound message size, per-peer buffers and connection time; reject malformed inputs safely | Fragment/coalesce/slow/oversize tests |
| STATE-01 | Must | Resume documents rather than delete on every startup, with explicit New option | Restart restores exactly same text and tombstones |
| STATE-02 | Must | Versioned structured state with immutable snapshots and atomic writes | Fault/interrupted-write tests and safe fallback |
| STATE-03 | Must | No implicit `pickle.load` of arbitrary/untrusted files | Code path inspection and malicious-file non-execution test |
| STATE-04 | Should | Trusted opt-in legacy migration or documented clean-start/export path | Migration test if implemented, otherwise release notes |
| PKG-01 | Must | Consolidate package metadata and choose supported Python runtime baseline | Build metadata validation + CI Python matrix |
| PKG-02 | Must | Reproducible locally bundled Monaco/frontend build with lockfiles | Offline build/artifact manifest verification |
| PKG-03 | Must | Provide Windows and Linux native app artifacts; list webview prerequisites | Fresh-machine install/start/save/peer test on each OS |
| PKG-04 | Should | Add isolated Docker-based core/network tests (no Docker for end-user app) | Docker CI/headless jobs show multi-peer pass |
| PKG-05 | Must | No publishing without passing tests; retain legitimate PyPI release if useful | CI gating and release dry-run |
| TEST-01 | Must | Regression tests for every reproduced CRDT and network defect | Red before fix; green after fix evidence in milestone report |
| TEST-02 | Must | Deterministic fuzz/property tests for eventual convergence | Logged seeds and documented fault model |
| TEST-03 | Must | End-to-end GUI/bridge smoke checks against real platform renderer | Recorded OS/runtime versions, results, limitations |
| OPS-01 | Must | `AGENTS.md`, `CONTEXT.md` and milestone plan maintained for Codex | Each completed milestone links tests/modified files and updates next action |
| OPS-02 | Should | Query Graphify first when installed and graph available; never equate graph inference with source truth | `AGENTS.md` compliant process; no hidden auto-installs |

## 5. Nonfunctional requirements

- **NFR-01 — Correctness:** after delivery and reconciliation finish, participants in the same document render byte-equivalent normalized content, with no tombstone resurrection and deterministic order; reproducible randomized verification.
- **NFR-02 — Reliability:** one crashing or malformed peer cannot crash the editor; state recovery is crash-safe within documented limits.
- **NFR-03 — Offline:** no cloud, API key, CDN or central relay required to start, edit, save or connect over reachable local networks.
- **NFR-04 — Usability:** Monaco shortcuts/clipboard/focus/resize stable; responsive edit loop at a documented target size (proposed test: 10,000 characters and pasted 10,000 characters). These are **test targets**, not demonstrated benchmarks.
- **NFR-05 — Maintainability:** keep Python core testable without GUI; small stable bridge contract and explicit module ownership.
- **NFR-06 — Security:** clearly signal trusted-LAN-only assumptions, validate all network and bridge payloads, bind asset server to loopback only, redact logs and do not execute untrusted legacy pickle.
- **NFR-07 — Compatibility:** version on-wire and persisted structures; fail safely with unsupported versions; do not claim compatibility with legacy peers unless proven.
- **NFR-08 — Platform:** target Windows 10/11 and a documented Linux baseline (prefer Ubuntu 24.04 LTS or equivalent). Support depends on successful renderer + packaging spike.

## 6. In scope / out of scope

**In scope:** unit/property/integration tests; RGA correctness; transport session/handshake/anti-entropy; Monaco + pywebview spike and full editor if validated; safe and durable local state; Python/JS packaging; reproducible developer workflows; minimal UI/peer controls; Windows/Linux native distribution; Docker headless testing.

**Out of scope:** cloud backend; user accounts; collaboration across NAT via relay; chat/presence/video; syntax-server or IDE extensions; large multi-document workspace; rich-text formatting; database service; end-to-end encryption unless a separate change request; automatic migration of untrusted pickle; macOS release in initial scope; production-scale load/performance promises.

## 7. Proposed architecture (pending approval)

`Monaco editor (Vite-built local ESM)` ⇄ `JS/Python bridge` ⇄ `single ordered Python edit coordinator` ⇄ `repaired Python CRDT` ⇄ `TCP P2P session`, with independent `atomic local snapshot store`. UDP discovery feeds the peer-connect UX. The Python CRDT is authoritative; Monaco is a view and source of intent, not an independent state authority. See the three diagrams and detailed contract in `MODERNIZATION_RESEARCH.md` §10.

Decision gate: A (`pywebview`) preferred. Validate Windows WebView2 and a Linux webview renderer in M3. If not viable, adopt B (Qt WebEngine) without changing Python domain modules. Reject unnecessary Electron/Tauri rewrite.

## 8. Affected components / integration impact

| Component | Intended changes | Risk |
|---|---|---|
| `c2g/crdt/{document,types,message}.py` | Stable integration/tombstone/order, typed messages | High — convergence and compatibility |
| `c2g/network/{manager,discovery}.py` | Session identity, targeted sync, relay, timeouts, advertised ports | High — connection lifecycle and threading |
| `c2g/ui/editor.py` | Replace Tk view with webview shell / adapter; preserve controls | High — event mapping, selection/undo |
| `c2g/storage/persistence.py` | Safe versioned crash-atomic snapshots | High — migration / data loss |
| `c2g/cli.py`, `__init__.py` | Preserve positional interface, optional flags, lazy imports | Low–Medium |
| `pyproject.toml`, `setup.py`, release workflow | Consolidate metadata, CI/test/bundle per OS | Medium |
| New `web/`, `tests/`, `scripts/` | Monaco/Vite, unit/contract/desktop tests | Medium |
| `AGENTS.md`, `CONTEXT.md`, `docs/` | Persistent coding-agent context | Low |

## 9. Compatibility, data migrations and release policy

1. **Wire protocol versioning** is required when introducing peer/document identity, changed full-state merge semantics or message formats. Preserve existing INSERT/DELETE fields where feasible, but reject older peers with clear guidance if correctness can't be guaranteed.
2. **Saved-state version** is required. `~/.p2p_crdt/.collaborative_doc_state.pkl` is a legacy unsafe pickle, **never auto-unpickle** on new startup. New state should use a deterministic per-document path and versioned serialization; backup before migration. If opt-in trusted migration proves unsafe or too costly, provide clear export/migration instructions instead.
3. **CLI compatibility:** continue `c2g <username> [peer_ip]`; optionally allow `--port`, `--peer-port`, `--doc`. Do not break defaults silently.
4. **Release notes:** explain Python support baseline, unsupported old protocol versions, native runtime prerequisites, and state migration policy.
5. **Rollback:** hold prior release artifact and original document copy; avoid overwriting legacy saved state. Rollback does not imply new document schema reads on old client.

## 10. Verification plan and release gates

- **Gate G0:** test infrastructure installed and old failure cases reproduced using test fixtures (no actual app code changed before red-test evidence).
- **Gate G1:** every required CRDT invariant passes unit and randomized permutation tests across 2–3 replicas, including out-of-order deletes and state merges. If not: stop UI development, decide `pycrdt` fallback.
- **Gate G2:** join/rejoin and A↔B↔C tests pass with disconnects and duplicate messages, correct ports and bounded frames.
- **Gate G3:** Monaco pywebview (or chosen fallback) is proven offline on supported OS renderers with worker, Unicode, undo and selection tests. Fail = choose alternate shell.
- **Gate G4:** UI editing workflows end-to-end pass and remain consistent with Python CRDT state.
- **Gate G5:** saved state is recoverable and tamper/atomicity behavior tested; frozen app handles bundled assets.
- **Gate G6:** Windows/Linux artifacts, headless regression CI, and actual smoke checks complete; release gate green.

The supplied P2PDocs archive had no test suite. c2g M0 now has its separately
recorded baseline; this proposal makes no claim that later gates have passed.

## 11. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| RGA cannot be soundly repaired within scope | Critical | Timebox M1; property-based test gate; fallback `pycrdt` with explicit migration |
| Monaco editor event feedback loops or lost undo | High | Typed adapter, origin tokens, version tracking, incremental edits, UI contract tests |
| Linux native renderer incompatibility | High | Real platform spike before committing full UI; Qt WebEngine fallback |
| State-loss when moving from pickle | High | Never auto-unpickle; versioned backup/migration decision, atomic writes |
| Protocol divergence between old/new clients | High | HELLO version negotiation and fail-closed behavior |
| Multi-peer rebroadcast storms | High | Stable op identity, dedup, forward-once, origin exclusion |
| LAN message abuse or buffer exhaustion | High | Limit frames, rate, peers and pending state, validate schema; trusted-LAN disclaimer |
| Docker networking mistaken for real LAN | Medium | Manual Windows/Linux LAN smoke; Docker only loopback/headless topology tests |
| Feature creep | Medium | Only scoped text-edit + collaboration features and minimal controls |

## 12. Ordered milestones

| Milestone | Objective | Complexity | Gate |
|---|---|---|---|
| M0 | Foundation: context/agents, baseline tests, tooling compatibility, Graphify if available | Low–Medium | G0 |
| M1 | RGA correctness: ordering, tombstones, causal dependencies, state merge, convergence | **High** | G1 |
| M2 | Peer session: join/rejoin, framing, doc/version handshake, relay, 3-peer tests | High | G2 |
| M3 | Monaco + pywebview proof-of-concept, native renderer/offline/bridge | Medium–High | G3 |
| M4 | Replace GUI and connect editor transaction adapter; preserve peer controls | **High** | G4 |
| M5 | Durable state recovery, metadata/Python tooling modernization | Medium | G5 |
| M6 | Native packaging, Docker headless test harness, CI builds | Medium | partial G6 |
| M7 | End-to-end platform validation, release evidence, documentation | Medium | G6 |

Detailed task breakdown, exact expected files and acceptance tests are in `docs/IMPLEMENTATION_PLAN.md`.

## 13. Overall definition of done

- Every P0 defect from `MODERNIZATION_RESEARCH.md` has a regression test and a justified, verified resolution.
- Two/three peers converge after tested adverse delivery/reconnect scenarios, and all joins are document/version-safe.
- Monaco editor provides offline VS Code-style UX without compromising CRDT authority, selection and undo behavior.
- Persisted document survives restart/crash tests; no automatic unsafe pickle loading.
- Supported Windows/Linux native artifacts run, save, connect and edit on clean target environments; Docker remains optional developer tooling.
- Versioned release, user docs and truthful limitations published only with green CI and test evidence.

**Decision status:** This document is an implementation **proposal**, not an authorization. M0 is complete; proceed with M1 only after explicit approval.
