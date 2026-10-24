# M4 Desktop Integration Report

## Executive summary

M4 replaces the default Tk launch path with a pywebview-hosted Monaco desktop
application. `c2g alice`, `python -m c2g alice`, and the existing peer/port
arguments now construct `DesktopApplication`. The legacy Tk editor remains an
explicit compatibility import only.

## Architecture

`ApplicationController` owns one `CRDTDocument`, one M2 `NetworkManager`, and
one `PeerDiscovery` instance behind a single re-entrant mutation lock. The
pywebview `DesktopBridge` exposes only initialization, transactions,
connections, UI state, export, and error reporting. Network worker callbacks
mutate the authoritative CRDT under that same lock and dispatch JSON-safe UI
events; Monaco is presentation only.

Local Monaco transactions carry application `base_version` (not Monaco's
`versionId`) and are serialized by a JavaScript queue. The controller validates
UTF-16 ranges, applies deletes right-to-left, uses `insert_local_batch`, and
broadcasts actual M2 `INSERT` and `BATCH_DELETE` CRDT messages. Duplicate and
stale transactions are acknowledged/rejected deterministically. Remote INSERT,
DELETE, BATCH_DELETE, and FULL_SYNC retain remote CRDT identities and produce a
contiguous incremental Monaco patch; ordinary remote changes never use
`setValue`.

## UI, lifecycle, and policy

The bundled local frontend now has a dark Monaco-first layout, connection and
discovery lists, manual IP connection, peer/sync status, cursor status, and a
native-dialog UTF-8 export action. No discovered peer auto-connects. The host
uses pywebview local assets with `http_server=False`; it starts/stops M2 and
discovery with the window lifecycle. The protocol remains trusted-LAN only
(unauthenticated and unencrypted).

Remote patches use Monaco `executeEdits` without raw selection restoration, so
Monaco transforms tracked selections. Native coordinate assertions, IME, and
full collaborative undo semantics are not yet proven. Undo/redo content events
are treated as ordinary new CRDT edits; this is not semantic collaborative undo.

## Evidence

```text
Initial baseline: ./.venv/bin/python -m pytest -q   # 36 passed
M4 final:       ./.venv/bin/python -m pytest -q    # 40 passed in 10.36s
Focused:         tests/test_m4_controller.py + tests/test_network_m2.py  # 12 passed
cd web && npm ci && npm run build                    # passed
```

The real-loopback controller integration test verifies initial join, Alice
insert propagation, Bob middle replacement, and final two-peer convergence.
The M4 Disconnect Peer extension adds an idempotent, identity-guarded public
network disconnect path, a controller/bridge API, and a sidebar Disconnect
button. It reuses M2 session cleanup outside the peer registry lock. Focused
tests verify repeated and simultaneous disconnect requests, offline edits on
both peers, tombstone preservation, explicit reconnect, document-ID retention,
and final CRDT convergence.
M3's 10,003-code-point in-memory transaction measurement remains 0.179 s;
M4 retains that batch insertion path. The npm audit remains two production
entries (direct Monaco low; transitive DOMPurify critical); npm only proposes
an unvalidated Monaco 0.57 to 0.56 downgrade, which was not applied.

## Gate G4

**PARTIAL.** Headless controller/network integration and the default production
launch path are implemented and tested. A manual Linux multi-window test,
three-peer/reconnect UI test, native cursor/selection assertions, offline
disconnected repetition, and Windows WebView2 verification were not executed
in this run. M5 must not start automatically.
