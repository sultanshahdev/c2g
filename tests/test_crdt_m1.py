"""M1 invariants: ordering, causal buffering, merge safety, and convergence."""

import copy
import random

import pytest

import c2g.crdt.document as document_module
from c2g.crdt.types import CRDTElement, CRDTId


def normalized(document):
    return {
        char_id: (element.char, element.after_id, element.before_id, element.visible)
        for char_id, element in document.elements.items()
    }, frozenset(document.pending_deletes), document.get_text()


def test_insert_before_parent_is_not_rendered_then_resolves(document_factory):
    document = document_factory()
    parent = CRDTElement(CRDTId("alice", 1), "A")
    child = CRDTElement(CRDTId("alice", 2), "B", parent.char_id)
    assert document.insert_remote(child) is True
    assert document.get_text() == ""
    assert child.char_id in document.pending_by_predecessor[parent.char_id]
    assert document.insert_remote(parent) is True
    assert document.get_text() == "AB"
    assert not document.pending_by_predecessor


def test_concurrent_siblings_are_delivery_order_independent(document_factory):
    parent = CRDTElement(CRDTId("root", 1), "A")
    left = CRDTElement(CRDTId("alice", 2), "L", parent.char_id)
    right = CRDTElement(CRDTId("bob", 2), "R", parent.char_id)
    one, two = document_factory("one"), document_factory("two")
    for element in (parent, left, right):
        one.insert_remote(CRDTElement.from_dict(element.to_dict()))
    for element in (right, left, parent):
        two.insert_remote(CRDTElement.from_dict(element.to_dict()))
    assert normalized(one) == normalized(two)
    assert one.get_text() == "ALR"


def test_snapshot_order_and_tombstone_merge_are_deterministic(document_factory):
    source = document_factory("source")
    source.insert_local("A", 0)
    source.insert_local("B", 1)
    source.insert_local("X", 1)
    source.delete_local(1)
    snapshot = source.get_full_state()
    left, right = document_factory("left"), document_factory("right")
    left.apply_full_state(snapshot)
    right.apply_full_state(list(reversed(snapshot)))
    stale = [dict(item, visible=True) for item in snapshot]
    left.apply_full_state(stale)
    assert normalized(left) == normalized(right)
    assert left.get_text() == "AB"


def test_conflicting_identity_and_cycles_are_rejected(document_factory):
    document = document_factory()
    original = CRDTElement(CRDTId("alice", 1), "A")
    assert document.insert_remote(original)
    with pytest.raises(ValueError, match="conflicting"):
        document.insert_remote(CRDTElement(CRDTId("alice", 1), "Z"))
    assert document.insert_remote(CRDTElement(CRDTId("bob", 2), "B", CRDTId("carol", 3)))
    # Completing B <- C would make C -> B -> C and is rejected.
    assert document.insert_remote(CRDTElement(CRDTId("carol", 3), "C", CRDTId("bob", 2))) is False
    assert document.get_text() == "A"
    with pytest.raises(ValueError, match="cyclic"):
        document.apply_full_state([
            CRDTElement(CRDTId("eve", 1), "E", CRDTId("mallory", 2)).to_dict(),
            CRDTElement(CRDTId("mallory", 2), "M", CRDTId("eve", 1)).to_dict(),
        ])


def test_invalid_payloads_and_unknown_delete_are_safe(document_factory):
    document = document_factory()
    with pytest.raises(ValueError):
        CRDTElement(CRDTId("alice", 1), "")
    with pytest.raises(ValueError):
        CRDTElement.from_dict({"char_id": {"client_id": "alice", "lamport_clock": -1}, "char": "A", "visible": True})
    unknown = CRDTId("remote", 4)
    assert document.delete_remote(unknown) is False
    assert unknown in document.pending_deletes
    assert document.insert_remote(CRDTElement(unknown, "A")) is True
    assert document.get_text() == ""


def test_pending_delete_survives_full_state(document_factory):
    source, target = document_factory("source"), document_factory("target")
    target_id = CRDTId("remote", 9)
    source.delete_remote(target_id)
    target.apply_full_state(source.get_full_state())
    assert target_id in target.pending_deletes
    target.insert_remote(CRDTElement(target_id, "A"))
    assert target.get_text() == ""


def test_deep_chain_is_iterative(document_factory):
    document = document_factory()
    parent = None
    for clock in range(1, 2001):
        element = CRDTElement(CRDTId("deep", clock), "x", parent)
        assert document.insert_remote(element)
        parent = element.char_id
    assert len(document.get_text()) == 2000


def test_unicode_code_point_indexing(document_factory):
    document = document_factory()
    for char in "A😀e\u0301\n":
        document.insert_local(char, len(document.get_text()))
    assert document.get_text() == "A😀e\u0301\n"
    document.insert_local("é", 2)
    assert document.get_text() == "A😀ée\u0301\n"


def test_local_batch_preserves_sequential_gap_anchors(document_factory):
    sequential, batched = document_factory("sequential"), document_factory("batched")
    for document in (sequential, batched):
        document.insert_local("A", 0)
        document.insert_local("B", 1)
    for offset, char in enumerate("😀X\n"):
        sequential.insert_local(char, 1 + offset)
    batched.insert_local_batch("😀X\n", 1)

    def shape(document):
        return [
            (element.char, element.after_id.lamport_clock if element.after_id else None,
             element.before_id.lamport_clock if element.before_id else None)
            for element in document._get_sorted_visible_elements()
        ]

    assert sequential.get_text() == batched.get_text() == "A😀X\nB"
    assert shape(sequential) == shape(batched)


def test_restore_clock_and_pending_delete(monkeypatch):
    states = {}

    class MemoryPersistence:
        def __init__(self, doc_name):
            self.doc_name = doc_name

        def clear(self):
            states.pop(self.doc_name, None)

        def load_state(self):
            return copy.deepcopy(states.get(self.doc_name))

        def save_state(self, elements, applied_ops, clock, pending_deletes=None):
            states[self.doc_name] = {
                "elements": copy.deepcopy(elements), "applied_ops": set(applied_ops),
                "lamport_clock": clock, "pending_deletes": copy.deepcopy(pending_deletes or []),
            }

    monkeypatch.setattr(document_module, "PersistenceManager", MemoryPersistence)
    first = document_module.CRDTDocument("alice", "resume", start_fresh=True)
    first.insert_local("A", 0)
    first.delete_remote(CRDTId("bob", 8))
    restored = document_module.CRDTDocument("alice", "resume", start_fresh=False)
    next_element = restored.insert_local("B", 1)
    assert next_element.char_id.lamport_clock > 1
    assert CRDTId("bob", 8) in restored.pending_deletes


def test_three_replica_randomized_convergence_100_seeds(document_factory):
    """Operation permutations, duplicate delivery, delayed parents, and stale snapshots."""
    for seed in range(100):
        rng = random.Random(seed)
        replicas = {name: document_factory(name) for name in ("alice", "bob", "charlie")}
        events, snapshots = [], []
        alphabet = "ab😀\né"
        for step in range(30):
            author = replicas[rng.choice(tuple(replicas))]
            if author.get_text() and rng.random() < 0.30:
                position = rng.randrange(len(author.get_text()))
                char_id = author.delete_local(position)
                events.append(("delete", char_id, author.client_id))
            else:
                position = rng.randrange(len(author.get_text()) + 1)
                element = author.insert_local(rng.choice(alphabet), position)
                events.append(("insert", element.to_dict(), author.client_id))
            if step % 6 == 0:
                snapshots.append((author.client_id, copy.deepcopy(author.get_full_state())))
            # Exercise a deliberately partial, shuffled schedule before final delivery.
            for kind, payload, origin in rng.sample(events, k=min(len(events), rng.randrange(0, 4))):
                target = replicas[rng.choice(tuple(replicas))]
                if target.client_id == origin:
                    continue
                if kind == "insert":
                    target.insert_remote(CRDTElement.from_dict(copy.deepcopy(payload)))
                else:
                    target.delete_remote(payload)
        delivery = list(events)
        rng.shuffle(delivery)
        for target in replicas.values():
            for kind, payload, origin in delivery:
                if target.client_id == origin:
                    continue
                if kind == "insert":
                    target.insert_remote(CRDTElement.from_dict(copy.deepcopy(payload)))
                    if rng.random() < 0.4:  # duplicate delivery
                        target.insert_remote(CRDTElement.from_dict(copy.deepcopy(payload)))
                else:
                    target.delete_remote(payload)
                    if rng.random() < 0.4:
                        target.delete_remote(payload)
        for _, snapshot in snapshots:
            for target in replicas.values():
                target.apply_full_state(list(reversed(snapshot)) if rng.random() < 0.5 else snapshot)
        # Final all-to-all state exchange makes every valid causal dependency available.
        for source in replicas.values():
            snapshot = source.get_full_state()
            for target in replicas.values():
                target.apply_full_state(list(reversed(snapshot)))
        states = [normalized(document) for document in replicas.values()]
        assert states[1:] == [states[0], states[0]], f"seed={seed}, states={states}"
        assert all(not document.pending_by_predecessor for document in replicas.values()), f"seed={seed}"
