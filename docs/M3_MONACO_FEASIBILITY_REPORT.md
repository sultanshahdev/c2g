# M3 Monaco + pywebview Feasibility Report

## Result

**G3: PARTIAL.** Linux GTK native launch, Monaco worker initialization, the
local JavaScript/Python bridge, simulated remote patch path, and the
10,003-code-point paste are now verified. Windows/WebView2 and an automated
native cursor/selection assertion remain unverified, so the cross-platform
gate cannot pass.

## Versions and architecture

- Node `v24.12.0`, npm `11.6.2`
- `monaco-editor` `0.57.0`, Vite `8.3.5` (pinned in `web/package-lock.json`)
- Python `3.12.3`; pywebview `6.2.1` with the GTK renderer

`web/src/main.js` hosts actual Monaco in `vs-dark`, with line numbers, Python
syntax highlighting, bracket matching, automatic indentation, minimap, word
wrap, Monaco find/replace/selection/multicursor/clipboard facilities, cursor
status, and a diagnostic footer. Vite produces entirely local assets, including
the `editor.worker` bundle. It has no CDN/runtime network dependency. The large
initial JavaScript bundle (~4 MB minified) is a known spike limitation.

`c2g.ui.bridge_spike` is an isolated launch target and does not alter the `c2g`
CLI or Tk editor. It checks for `web/dist/index.html`, imports pywebview only at
launch, and uses its local asset serving; no application HTTP server or external
navigation is introduced.

## Bridge contract

JavaScript calls `editor_ready`, `apply_local_transaction`, and `report_error`.
Python replies with accepted/rejected/version data and applies remote simulated
CRDT text as `{offset,length,text}` patches. `BridgeController` serializes
mutations under a lock, validates transaction IDs and base versions, rejects
stale transactions, and records duplicate IDs. Monaco's programmatic patch has
an explicit `applyingRemote` guard, so it is not echoed as a local transaction.

Transactions contain Monaco pre-change UTF-16 `rangeOffset`, `rangeLength`, and
text. Changes are validated and applied in descending offset order, avoiding
position shifts. The bridge uses only public `CRDTDocument` local insert/delete
methods. Remote patches use `executeEdits`, never `setValue`, except initial
document initialization.

## Unicode, selection, and undo

The Python boundary converts UTF-16 units to Python code points and rejects a
surrogate-splitting offset. Tests cover emoji, combining marks, mixed RTL text,
and multiline replacement. Newlines are carried as `\n`; CRLF/IME composition
were not renderer-tested. Monaco selection is restored after remote patches,
but an automated native assertion of exact cursor/selection coordinates remains
an M4 requirement. Full operational collaborative cursor transforms are
deferred to M4.

Monaco native undo/redo is not declared collaboration-safe: undo creates a
normal content event which becomes a new CRDT transaction. This spike does not
claim semantic collaborative undo.

## Tests and build evidence

```text
./.venv/bin/python -m pytest -q tests/test_bridge_spike.py  # 5 passed in 0.30s
./.venv/bin/python -m pytest -q                            # 36 passed in 5.00s
cd web && npm run build                                    # passed (1,249 modules)
```

The GTK native smoke opened the built page with `http_server=False`, reached
`Connected`, found a Monaco editor and loaded `editor.worker`, then completed a
JavaScript-to-Python local transaction (accepted text `L`) and accepted a
Python-generated simulated remote patch. Its Vite entrypoint has only relative
`./assets/...` references, so the tested Linux resource path has no CDN or
application HTTP dependency. A physically disconnected repeat remains release
validation work. Windows WebView2, native clipboard/shortcuts, and automated
native cursor/selection coordinates are unexecuted.

The original 1,000-code-point transaction took **10.184 s** with persistence
stubbed; `cProfile` attributed 8.638 s to repeated visible-order linearization
and 1.134 s to repeated serialization. `CRDTDocument.insert_local_batch` now
resolves one existing visual gap, performs one collision-safety clock scan, and
persists once while retaining one immutable CRDT element and Lamport tick per
code point. It creates the same predecessor chain and right anchor as
sequential `insert_local` calls (regression tested), and the bridge uses it only
for one Monaco change's inserted text. The formerly skipped
10,003-code-point Unicode paste passes: **0.179 s** transaction application
plus **0.059 s** subsequent text read with in-memory persistence.
Delete semantics, wire/state records, networking, and single-character APIs
are unchanged.

`npm audit --omit=dev` reports two production entries: direct `monaco-editor`
(low) and transitive `dompurify` (critical). npm's only offered fix is a
semver-major 0.x downgrade from Monaco `0.57.0` to `0.56.0`; it was not applied
without evidence that it resolves all advisories or preserves the verified
worker/runtime behavior. Re-evaluate a supported Monaco update path before
release.

## Decision and M4 input

The frontend build and bridge design are a **conditional GO for pywebview** on
the verified Linux GTK path. G3 remains **PARTIAL** because Windows WebView2
and automated native cursor/selection evidence are missing. M4 must retain the
serialized bridge, add those native tests, implement robust selection
transforms/transaction queue acknowledgements, and determine collaborative undo
semantics. M3 does not modify networking, persistence, or the production Tk UI.
