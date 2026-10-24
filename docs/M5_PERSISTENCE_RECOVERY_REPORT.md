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
