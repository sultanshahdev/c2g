# M5 Persistence and Recovery Report

## M5-A safe storage foundation

M5-A adds `c2g.storage.json_store.JsonDocumentStore` alongside the existing
runtime persistence route. It is deliberately not wired into `CRDTDocument`,
`ApplicationController`, startup, or the Monaco UI yet; that integration is
reserved for M5-B and later work.

The schema is JSON `format: "c2g-document"`, `schema_version: 1`, with logical
document/replica metadata, Lamport clock, all CRDT element records (including
anchors and tombstones), pending deletions, and applied operations. Loading
strictly validates every field and CRDT element before returning a state.

Each document uses a caller-supplied safe storage key below
`<root>/documents/<key>/`. Saves serialize deterministic UTF-8 JSON to a
same-directory temporary file, flush and fsync it, retain the prior primary as
`state.backup.json`, then use `os.replace`. A corrupt/invalid primary recovers
only from a valid backup; both files are otherwise left untouched and loading
raises `StateValidationError`. Abandoned temporary files are ignored.

No legacy pickle path is read, migrated, modified, or deleted. The historical
runtime persistence manager remains unchanged during this foundation slice.

## Evidence

```text
./.venv/bin/python -m pytest -q tests/test_json_store_m5.py  # 4 passed
./.venv/bin/python -m pytest -q                              # 44 passed in 5.95s
```

Tests use pytest temporary directories and cover Unicode/tombstone/pending
delete round trip, isolated storage directories, schema/duplicate-ID/path
rejection, corrupt-primary backup recovery, abandoned temporary files, and
both-primary-and-backup failure without overwrite.

## M5-C production lifecycle

M5-C makes JSON-backed `PersistedCrdt` the Monaco runtime path. Normal startup
shows a Recent Documents picker; `--new` creates a UUID-keyed replica and
`--resume STORAGE_KEY` opens only that validated key. The picker creates no
CRDT, listener, or writer until a choice is made. Legacy pickle storage is not
opened or written by this path.

Each local replica holds an OS advisory lock (`flock` on Linux and
`msvcrt.locking` on Windows) plus one non-daemon, bounded latest-snapshot
writer. The writer uses the existing v1 atomic store, reports completed save or
failure to Monaco, and is flushed/joined on shutdown. CRDT local and remote
mutations, including tombstones/pending causal state and full syncs, flow
through this same persistence callback. A confirmed empty-peer join persists
the adopted logical document ID; replica IDs remain local.

Evidence: `tests/test_m5_application_persistence.py` covers restart, same- and
real cross-process Linux lock exclusion/release, picker validation, and joined-ID restart; full suite is 51
passed. Measured temporary-directory save/close and open/close: 1 character
0.0248/0.0091 s, 1,000 characters 0.0664/0.0594 s, 10,003 characters
0.5282/0.5321 s. Native GTK/pywebview recovery, two-window collaboration, and
write-failure UI checks were not executed. Windows lock behavior is documented
but not native-tested.

## Status

**M5-C implemented; M5 remains PARTIAL pending M5-D and native/manual G5 evidence.** `PersistedCrdt.create(root, key)` and
`PersistedCrdt.open(root, key)` create/open an explicitly selected JSON-backed
replica. They preserve logical document ID and replica ID, rebuild indexes from
validated immutable records, retain tombstones/pending deletes, and raise rather
than substituting an empty document on failure. Mutations persist through the
JSON backend synchronously; two independently restored replicas converged after
further full-state exchange. This path never invokes the legacy persistence
backend.

## M5-D packaging and lifecycle verification

`pyproject.toml` is canonical: c2g 0.1.0 requires Python 3.12+, uses PEP 639
MIT / `LICENSE` metadata, retains P2PDocs attribution, declares no core runtime
dependencies, and offers `desktop` (`pywebview>=6,<7`), `test`, and `build`
extras. `setup.py` is only a `setup()` compatibility shim; the unused
`setuptools_scm` requirement was removed. Isolated `python -m build` produced
both wheel and source distribution, and `twine check` passed for both. A clean
wheel environment passed headless imports, module and console-script help, and
reported `Requires-Python: >=3.12` / `License-Expression: MIT`. Monaco assets
are intentionally not in the wheel; desktop launch reports the missing-assets
diagnostic. M6 owns native/frontend artifact bundling.

Real M2 `NetworkManager` + `ApplicationController` tests now cover independent
persisted replicas joining, exchanging edits, closing, reopening, reconnecting,
and continuing edits; and a restarted Bob reconciling Alice's offline insertion
plus tombstone. They also cover writer failure status/recovery and graceful and
terminated-owner Linux lock release. A disposable-profile GTK/pywebview launch
was attempted with available X11/Wayland variables, but it timed out after GTK
native-property warnings and could not support interactive assertions. Native
M5 New/Resume, two-window restart, save-failure, and offline UI checks remain
NOT EXECUTED.

Verification at M5-D completion: `tests/test_m5_application_persistence.py` +
`tests/test_m5_persisted_network_restart.py` passed 9 tests; the full Python
suite passed 55 tests in 7.58 s.

Current frontend audit (`npm audit --omit=dev`) reports two production findings:
low-severity `monaco-editor` (the dependency path) and critical `dompurify
<=3.4.16`, with five DOM-XSS advisories. npm proposes a forced Monaco 0.57 to
0.56 downgrade; it was not applied because that is an unverified breaking
change to the tested editor/worker path. The application remains trusted-LAN
only and this dependency risk blocks a public-security claim.

## M5-D status

**PARTIAL.** Automated persistence and packaging evidence is complete, but G5
cannot be called PASS without the outstanding native M5 lifecycle smoke tests.
The app remains trusted-LAN only; the dependency audit and platform limitations
must be considered before a public release.

## M6 handoff

M6 now packages the Vite/Monaco output into a PyInstaller onedir distribution
while retaining JSON data outside application resources. See
`docs/M6_RELEASE_TOOLING_REPORT.md` for frozen-resource and artifact evidence;
native persistence UI verification remains a pre-G6/M7 requirement.
