# M7 — Final Validation and Release Decision

Date: 2026-10-24. Scope: final validation and verified blocking fixes; no
publication, commit, push, or change to historical MIT attribution.

## 1. Executive summary

**G6 PARTIAL.** The available Linux, CRDT, protocol-v2, persistence, frontend,
and artifact checks pass. Three verified defects were fixed with regressions:
rejoin snapshots did not reach an already-connected neighbor; interrupted save
after backup recovery could destroy the last valid backup; cyclic-state resume
leaked a writer and ownership lock. No known P0/P1 remains from the executed
checks. Required Windows, Docker, physical-LAN, and complete human desktop
acceptance evidence is still missing. This is a candidate for owner acceptance,
not an approved public release.

## 2. Environment and dependencies

Ubuntu 24.04.4 LTS, Linux 7.0.0-38-generic, x86_64; Python 3.12.3;
pytest 8.4.2; pywebview 6.2.1; WebKitGTK 2.52.6; PyInstaller 6.22.3;
Node 24.12.0; npm 11.6.2; Vite 8.3.5; Monaco 0.57.0; DOMPurify 3.4.17.
The build uses the existing dirty working tree, not a newly committed revision.

## 3. Automated test results

Initial baseline: **62 passed in 14.59 s**. The port-dependent picker test is
already isolated with `listen_port=0`; no further change was needed there.
The initial full test process nevertheless remained alive: two older recovery
tests had left non-daemon autosave writers open. Those tests now close every
owned replica with `contextlib.closing`, preserving their assertions.

Final M7 run: **68 passed in 12.22 s**, with normal process exit.
An earlier full post-fix run also passed in 13.05 s.
Focused network/controller gates: **13 passed in 0.82 s**. Focused M7,
M5 persistence/restart, and M6 simulation checks: **20 passed in 2.52 s**.
`npm run build` passed in 5.57 s (large-chunk/performance warnings only).
`npm audit --omit=dev`: **0 vulnerabilities**. `git diff --check` passed.
All new network tests reserve their own sockets or use ephemeral ports, bounded
polling, and deterministic cleanup. No dependency or test framework was added.

## 4. Randomized convergence

Reused `test_three_replica_randomized_convergence_100_seeds`: **100 deterministic
seeds, 0–99**, three replicas, 30 generated edits per seed; **passed in 2.83 s**
(2.84 s including pytest overhead). The final full-suite run measured 2.43 s (earlier run: 2.80 s).
It covers arbitrary insertion positions, Unicode/newlines, partial delivery,
reordering, duplicate insertion/deletion delivery, delayed predecessors,
pending deletions, stale/reversed snapshots, and final all-to-all CRDT merges.
It compares element identities/anchors/visibility, pending deletions, and text;
failed convergence assertions include the seed. This is bounded randomized
evidence, not a formal proof or a large-document performance guarantee.

## 5. Two-peer verification

New `test_two_peer_edit_disconnect_unicode_and_restart` uses actual persisted
controllers and protocol-v2 TCP sockets. Alice creates; empty Bob joins; Alice
inserts; Bob replaces the middle; both insert concurrently and delete;
both paste multiline Arabic, emoji, and combining marks. Broadcasts are held
only to create a deterministic concurrent causal frontier, then original CRDT
messages are released through real sockets. Bob disconnects; both edit
offline; reconnect reconciles; both close, resume, reconnect, and continue.

Assertions compare full immutable element records, visibility/tombstones,
pending deletes, and rendered text, plus document/replica identity and safe
Lamport continuation. UTF-8 export and export-error handling pass. No plain-text
copy is used for reconciliation. Existing restart/tombstone tests also pass.

## 6. Three-peer verification

Existing M2/M6 tests verify chain forwarding, a cycle, duplicate suppression,
reconnect, and tombstones. The M7 regression adds deterministic concurrent
modifications and reconnecting Charlie while Bob remains connected to Alice.
It failed before the fix because Bob never received Charlie's tombstone.

`NetworkManager` now relays nonempty direct FULL_SYNC snapshots through the
existing message-ID-deduplicated OP envelope, excluding the sending neighbor.
Existing receivers already understand the FULL_SYNC message. This preserves
protocol v2 and its limits; repeated cycle delivery is deduplicated. Empty
snapshots have no records to forward. All three replicas converge in full CRDT
state without separately reconnecting Bob. Existing cycle/dedup/session tests
remain green.

## 7. Native Linux verification

The owner reports manually confirming the application works after the picker
fix; this is owner-provided evidence, not an agent-observed test checklist.

`scripts/validate_desktop.py` passed `picker`, `resume`, and `new` modes in
GTK/X11 using disposable profiles. These are real WebKit/Monaco windows and
Python bridge calls: initial picker visibility, New/Resume activation,
computed `display:none`, editor/sidebar hit-testing, synthetic X11 typing,
Ctrl+A/Backspace selection deletion, Ctrl+Z/Ctrl+Y undo/redo, DOM insertion of
multiline Arabic/emoji/combining text, real completed-save status, injected
writer-error DOM reporting and recovery, UTF-8 controller export, and invalid
sidebar endpoint submission. Undo grouping follows Monaco's current behavior;
one undo need not remove an entire multiline DOM insertion.

Reproduction (X11/XTest and desktop dependencies required):

```bash
profile=$(mktemp -d)
./.venv/bin/python scripts/validate_desktop.py picker "$profile/picker"
./.venv/bin/python scripts/validate_desktop.py resume "$profile/picker"
./.venv/bin/python scripts/validate_desktop.py new "$profile/new"
```

The final frozen binary also passed a separate Xvfb/XTest smoke from `/tmp`:
`--new`, native pointer click and keyboard edit `a`, WM_DELETE close with exit
0, `--resume KEY`, pointer/keyboard edit to `ab`, normal close/exit 0, and
persisted final text. Readiness used bounded worker-load/listener polling.
This caught and corrected an early-input timing error in the smoke harness;
the application was not changed for it. Temporary profile:
`/tmp/c2g-m7-frozen-lhg8zesj`. No real document profile was used.

Synthetic native events and DOM insertion are **not human physical testing**.
Native Save dialog interaction, real clipboard paste, multi-window peer GUI,
and the final artifact's complete human checklist remain pending. GTK native
property introspection warnings occurred without assertion failures.

## 8. Windows verification

Local workflow inspection confirms a Python 3.12/Node 24 `windows-latest`
PyInstaller job, bundled HTML/workers/checksum checks, and artifact upload.
No release publishing is configured. WebView2 remains a prerequisite.

Actual GitHub evidence: successful run
[40077214766](https://github.com/sultanshahdev/c2g/actions/runs/40077214766)
at `ec570ce1c7e018930559b66eaea7fa196f4ac533` contained only a `pytest` job.
Run [40079444172](https://github.com/sultanshahdev/c2g/actions/runs/40079444172)
at `d5599915bb3f0112d68cc3bcefcc61b9024e41a5` was in progress when inspected,
also with only a `pytest` job. Neither validates the local desktop-build matrix.
Artifact API checks timed out; no Windows artifact was obtained or tested.
**Windows build and WebView2 runtime: NOT VERIFIED.** Linux evidence does not
establish Windows compatibility.

## 9. Docker verification

One `docker info` attempt returned permission denied on `/var/run/docker.sock`.
Existing `Dockerfile.tests` was inspected; it runs M6, persisted restart, and M2
loopback suites. **Docker tests: NOT EXECUTED.** No repeated permission
troubleshooting or privilege changes were attempted.

## 10. Physical LAN verification

Only one test machine was available. UDP discovery across machines is
**NOT VERIFIED**; loopback TCP tests are not discovery evidence.

Two-machine procedure: use disposable profiles and the same candidate folder
on compatible Linux machines on one trusted LAN; allow the selected TCP peer
port and UDP discovery port 5001 through host firewalls. Start Alice with
`--new --listen-port 5000`, start Bob with a separate new profile; confirm
Alice appears under Discovered, click Connect, and confirm shared document ID.
Exchange beginning/middle edits, selection deletions, multiline Unicode and
emoji; disconnect Bob, edit both, reconnect and compare; close/resume both and
continue. Repeat with Charlie for chain/cycle. Also test explicit IP:port when
broadcast discovery is unavailable. Record OS, artifact hash, identities,
results, and failures. Never connect unrelated nonempty documents expecting an
automatic merge.

## 11. Persistence and recovery

Passing coverage includes atomic replace, valid backup recovery, rejecting
corrupt primary+backup without overwrite, final flush, coalesced writer status,
writer-error/retry, normal and terminated-owner cross-process locking,
document isolation, replica/document identity, pending deletes and tombstones.

**Fixed P0:** following corrupt-primary backup recovery, save previously rotated
the corrupt primary over the valid backup. Fault injection at final replace
then made both copies unrecoverable. Save now validates the primary before
backup rotation, retaining the valid backup on failed commit. The new regression
failed before the fix and passes afterward. This does not promise immunity to
hardware failure or filesystem corruption beyond atomic-replace semantics.

**Fixed P1:** cyclic ancestry was rejected after starting an autosave worker and
acquiring ownership. A subprocess regression demonstrated lock leakage and
failure to exit. Ancestry is now checked before acquiring either resource; the
subprocess exits normally and ownership can be reacquired.

## 12. Offline frontend and file isolation

Monaco, language modules, fonts, and editor worker are bundled. Native resource
logs show all tested requests on the application's loopback origin; no CDN is
needed. This is evidence of self-contained tested operation, not an air-gapped
network-namespace test.

**Correction to earlier M6 wording:** pywebview 6.2.1 starts a loopback Bottle
asset server for local URLs even with `http_server=False`. Runtime socket
inspection shows that server at **127.0.0.1**, plus the intentional P2P TCP
listener on 0.0.0.0. The server root equals `web/dist` (frozen:
`_internal/web/dist`), not the repository or document profile. A parent traversal
request for `../CONTEXT.md` was rejected (403/404). Saved documents remain under
the separate storage profile. Recovery works without network peers.

## 13. Security findings

Production npm audit: **0 vulnerabilities** at execution time. Built and frozen
main bundles contain **3.4.17**, not **3.4.15**; Monaco's embedded sanitizer is
replaced by the existing scoped Vite resolver. No unresolved critical runtime
finding was identified in these checks. This is not a comprehensive audit of
system WebKitGTK, Python dependencies, or future advisories.

Production New/Resume explicitly uses JSON-backed persistence; it does not
instantiate the legacy pickle loader. The legacy module remains for historical
compatibility and must not be used to load untrusted pickle files.

Protocol v2 is **trusted-LAN only**: no authentication, encryption, or protection
against malicious peers is claimed. Peers can receive and modify the selected
shared document. Do not expose peer/discovery ports to the public Internet.
Validated frame/buffer limits are 12 MiB; peer and inbound-handshake caps are
16; dedup cache 20,000; sync queue 1,000; CRDT records 100,000 and pending entries
20,000. Existing malformed/oversize/legacy-frame and duplicate-session tests
pass. New tests verify the handshake cap closes an overflow connection and
releases slots, isolated bind conflict, and connection refusal. These bounds do
not establish hostile-network or denial-of-service safety.

## 14. Artifact details

The initial onedir executable existed, its checksum matched, and its frontend
was byte-identical to the current picker-fixed build with patched DOMPurify.
A rebuild was nevertheless necessary after M7's Python fixes. Exactly one
`scripts/build_desktop.py` rebuild completed successfully (about 53.8 s).

Final executable: `dist/c2g/c2g` (Linux x86_64 onedir).
SHA-256: `dc4c1f1e6c4c24507586f6ae8ea70132a0379d92572255bdcb1121bec73d36fb`.
`sha256sum -c SHA256SUMS.txt`: `c2g: OK`; `--help` works from `/tmp`.
Logical file bytes: 398,584,774 (filesystem `du`: 363 MiB).
Bundled frontend: 14,268,718 bytes, 96 files, including
`editor.worker-CRz__AKW.js` and language workers. Bundled CSS has the important
hidden rule; JS has DOMPurify 3.4.17 and lacks its old 3.4.15 marker.
The checksum manifest covers the executable, not every resource or a signed
archive. Distribute the complete onedir folder; the executable alone is
insufficient. No installer, archive, GitHub Release, or PyPI release was made.

## 15. Known limitations

Linux system GTK/WebKitGTK dependencies are required; arbitrary distro and
Wayland compatibility are not established by this Ubuntu/X11 acceptance run.
No Windows/macOS support claim. Physical LAN and full human multi-window GUI
acceptance remain open. Native file-dialog and real clipboard flows remain
open. Large CRDT histories retain tombstones and have bounded size; no
compaction/performance guarantee is added. Vite warns about large chunks.
Autosave protects completed writes, not unsaved edits on abrupt termination.

## 16. Supported platform matrix

| Target | Evidence | Release support decision |
| --- | --- | --- |
| Ubuntu 24.04.4 x86_64, GTK/WebKitGTK 2.52.6, X11 | Source native and frozen synthetic smoke; full headless suite | Linux acceptance candidate; human signoff pending |
| Other Linux distributions / Wayland | Earlier owner launch confirmation; no complete platform checklist | Not qualified by this run |
| Windows / WebView2 | Local CI configuration only; no desktop job/artifact evidence | NOT VERIFIED; no supported-platform claim |
| macOS | No build/runtime validation | Not verified |
| Docker | Definition inspected; daemon denied | NOT EXECUTED |
| Two-machine physical LAN | Procedure supplied | NOT VERIFIED |

## 17. Defects and severity

| Finding | Severity | Disposition |
| --- | --- | --- |
| Last valid backup destroyed on failed post-recovery save | P0 | Fixed; fault-injection regression passes |
| Rejoin snapshot/tombstone fails to reach connected neighbor | P1 | Fixed; real three-peer regression passes |
| Cyclic resume leaks ownership and a non-daemon writer | P1 | Fixed; subprocess regression passes |
| Recovery tests leave autosave writers alive after passing | P1 validation blocker | Fixed test cleanup; full pytest now exits |
| Incomplete platform/physical-LAN/human acceptance | Verification gap | Open; prevents G6 PASS |
| Large build chunks and GTK introspection warnings | P2 | Documented; tested flows pass |

No unresolved demonstrated P0/P1 defect remains in the executed scope.
Unexecuted tests can still reveal defects; their absence is not a passing result.

## 18. Release recommendation

Retain this build as a Linux release-candidate **for acceptance testing**.
Do not publish or describe it as a fully qualified cross-platform release.
Preserve the original MIT license and P2PDocs attribution. Final release needs
explicit owner approval after the remaining acceptance evidence is reviewed.

## 19. Gate G6 decision

**G6 PARTIAL.** Implementation/stabilization and available local checks are
complete; mandatory acceptance evidence remains unexecuted. Neither the unit
suite nor the owner's general manual confirmation alone closes all gates.
G6 is not owner-signed and this report is not publication authorization.

## 20. Exact remaining human acceptance steps

1. On the final hashed Linux folder, physically exercise normal/New/Resume,
   typing, selection deletion, real multiline Unicode clipboard paste,
   undo/redo, native UTF-8 Export dialog, Saved locally, close/resume, and
   sidebar Connect/Disconnect. Confirm the picker never obstructs the editor.
2. Complete two-/three-window native collaboration and two-machine discovery
   using section 10, including offline edits, tombstones, resume/reconnect, and
   continued convergence. Record actual physical mouse/keyboard evidence.
3. Run the current desktop-build workflow when the owner authorizes committing
   and pushing; inspect the Windows job and download its artifact. Test on a
   Windows/WebView2 host before claiming Windows support.
4. With authorized Docker access, run `docker build -f Dockerfile.tests -t
   c2g-tests .` then `docker run --rm c2g-tests`; record results.
5. Review remaining platform/security limitations and approve or reject the
   release explicitly. No publication follows automatically.
