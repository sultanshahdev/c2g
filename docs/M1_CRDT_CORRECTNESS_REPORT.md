# c2g M1 CRDT Correctness Report

## A. Executive summary

M1 repairs the character-level replicated document without changing the Tk,
network, or packaging architecture. The engine now keeps immutable insertion
records, tombstone ancestry, causal pending inserts/deletes, deterministic
iterative linearization, and monotonic state merging. Gate G1 is **PASS**.

## B. Original defects corrected

| Regression | Previous behavior and root cause | Corrected behavior |
|---|---|---|
| REG-01 | `AB` plus `X@1` became `ABX`; sibling ID sorting lost the visual gap. | The local record captures `before_id=B`; linearization produces `AXB`. |
| REG-02 | A new head was sorted after old heads. | The right anchor constrains the new head before the old head: `XAB`. |
| REG-03 | Snapshot insertion IDs were reused as delete deduplication IDs. | Inserts and tombstones are independent; a later delete changes visibility. |
| REG-04 | Unknown deletes were forgotten when their insert arrived. | Pending tombstones hide the subsequently received insertion. |
| REG-05 | Rendering discarded invisible predecessors and promoted descendants. | Full structural traversal includes tombstones, preserving `BH`. |
| REG-06 | A visible snapshot could overwrite a tombstone. | Visibility is false-dominant during every merge. |

## C. Algorithm design

Each `CRDTElement` has an immutable `(client_id, lamport_clock)` identity,
character, `after_id`, and optional `before_id`. `after_id` forms RGA ancestry;
`before_id` is the element immediately right of a locally requested visual gap.
The latter is optional for legacy records. Rendering uses an iterative preorder
of resolved ancestry as a stable priority, followed by iterative topological
linearization of ancestry and right-anchor constraints. If independently
created right anchors would form a cycle, constraints are considered by stable
ID and only the cycle-closing right-anchor edge is discarded. Ancestry is never
discarded.

Unknown-parent inserts are retained but excluded from rendering in
`pending_by_predecessor`; resolution cascades iteratively when a parent arrives.
Unknown deletes are retained in `pending_deletes`. Tombstones are monotonic:
`False` dominates `True`. Same-ID records must have equal immutable fields or
are rejected. Snapshot merges union compatible records and take the visibility
join; they never replace the local document wholesale.

## D. Correctness invariants and evidence

- IDs are validated `(non-empty client ID, non-negative integer clock)` and the
  local clock is restored at least to its own maximum observed ID.
- Ordering is independent of dictionary/snapshot/delivery order after all
  dependencies arrive; deterministic ordering and shuffled snapshots are tested.
- Tombstone ancestry remains structural; traversal is iterative and deep-chain
  tested.
- Unknown parents and deletes are buffered; duplicates are idempotent.
- Conflicting IDs and predecessor cycles are rejected; malformed fields are
  rejected at type boundaries.
- Merge is idempotent and commutative for compatible records, with false-wins
  visibility. This is tested evidence, not a formal proof.

Limits: 100,000 elements/snapshot records and 20,000 pending dependencies or
pending deletes. Python Unicode code points are the indexing unit in M1.

## E. Test evidence

```text
./.venv/bin/python -m pytest -q
# 22 passed in 7.56s

./.venv/bin/python -m pytest -v tests/test_crdt_regressions.py \
  tests/test_crdt_m1.py::test_three_replica_randomized_convergence_100_seeds
# 7 passed in 2.57s

./.venv/bin/python -m pytest -q tests/test_crdt_m1.py::test_deep_chain_is_iterative
# 1 passed in 5.13s (real 5.49s measured with /usr/bin/time -p)
```

The first command includes baseline, historical regression, causal, merge,
validation, Unicode, persistence-seam, deep-chain, and convergence tests.

## F. Randomized coverage

`test_three_replica_randomized_convergence_100_seeds` runs 100 reproducible
`random.Random(seed)` histories over `alice`, `bob`, and `charlie`. Each has 30
bounded inserts/deletes, partial reordered deliveries, duplicate deliveries,
captured stale snapshots in both orders, and a final all-to-all reconciliation.
It compares visible text, immutable records, tombstones, and pending deletes;
any failure reports its seed and normalized states.

## G. Compatibility

The UI-facing boolean methods (`insert_remote`, `delete_remote`) and local
editing APIs retain their meanings: `True` means a new visible/record change;
duplicate deletes return `False`. Existing element JSON remains readable.
`before_id` is optional. Full-state payloads may carry optional
`_crdt_pending_delete` records so same-version M1 peers preserve unknown delete
intent. Existing unversioned peers cannot negotiate this extension; M2 must add
protocol versioning before cross-version claims. Persistence gained an optional
`pending_deletes` field; legacy files still load but retain their legacy
ambiguity in `applied_ops`. Pickle safety migration remains M5.

## H. Performance

Traversal is iterative (no recursion overflow). The 2,000-element deep-chain
test passed in 5.13 seconds of pytest time on this host. The main remaining
cost is full-state serialization on every persistence call and whole-document
linearization for position edits; both are intentionally deferred rather than
optimizing before a correctness-preserving index is designed.

## I. Changed files

- `c2g/crdt/document.py`, `c2g/crdt/types.py`
- `c2g/storage/persistence.py` (optional pending tombstone argument only)
- `tests/conftest.py`, `tests/test_crdt_regressions.py`, `tests/test_crdt_m1.py`
- `CONTEXT.md`, `docs/IMPLEMENTATION_PLAN.md`, this report

## J. Remaining risks

The current wire protocol has no document ID or negotiated version and does not
relay/reconcile peers reliably; M2 owns that work. Right-anchor conflict
resolution is deterministic but may choose a different concurrent ordering than
one participant's transient view. Pickle remains unsafe for untrusted files,
and character-level full traversal/persistence is not optimized for large docs.

## K. Gate G1 decision

**PASS.** All six historical regressions are normal passing tests, 22 CRDT
tests pass, 100 deterministic three-replica histories converge, and M1 stayed
within the CRDT/persistence-seam boundary. M2 has not started.
