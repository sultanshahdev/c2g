"""Executable evidence for M1 CRDT defects; do not remove xfails before fixing M1."""

import pytest

from c2g.crdt.types import CRDTElement, CRDTId


@pytest.mark.xfail(strict=True, reason="Known CRDT defect — scheduled for M1 (document.py:_get_sorted_visible_elements)")
def test_reg_01_insertion_in_the_middle(document_factory):
    """A->B then X at visual index 1 should be AXB, but is currently ABX."""
    document = document_factory()
    document.insert_local("A", 0)
    document.insert_local("B", 1)
    document.insert_local("X", 1)
    assert document.get_text() == "AXB"


@pytest.mark.xfail(strict=True, reason="Known CRDT defect — scheduled for M1 (document.py:_get_sorted_visible_elements)")
def test_reg_02_insertion_at_the_beginning(document_factory):
    """A->B then X at index 0 should be XAB, but CRDT ID ordering yields ABX."""
    document = document_factory()
    document.insert_local("A", 0)
    document.insert_local("B", 1)
    document.insert_local("X", 0)
    assert document.get_text() == "XAB"


@pytest.mark.xfail(strict=True, reason="Known CRDT defect — scheduled for M1 (document.py:apply_full_state/delete_remote)")
def test_reg_03_full_state_then_remote_delete(document_factory):
    """Full-state insertion IDs are incorrectly deduplicated as later delete IDs."""
    source = document_factory("source")
    target = document_factory("target")
    element = source.insert_local("A", 0)
    target.apply_full_state(source.get_full_state())
    source.delete_local(0)

    assert target.delete_remote(element.char_id) is True
    assert source.get_text() == target.get_text() == ""


@pytest.mark.xfail(strict=True, reason="Known CRDT defect — scheduled for M1 (document.py:delete_remote/insert_remote)")
def test_reg_04_delete_before_insert_is_retained(document_factory):
    """A delete buffered before a separately delivered insert must still hide it."""
    source = document_factory("source")
    target = document_factory("target")
    element = source.insert_local("A", 0)
    wire_insert = CRDTElement.from_dict(element.to_dict())
    source.delete_local(0)

    assert target.delete_remote(element.char_id) is False
    assert target.insert_remote(wire_insert) is True
    assert target.get_text() == ""


@pytest.mark.xfail(strict=True, reason="Known CRDT defect — scheduled for M1 (document.py:_get_sorted_visible_elements)")
def test_reg_05_tombstone_preserves_descendant_order(document_factory):
    """Traversal must retain invisible predecessors, not promote descendants to heads."""
    document = document_factory()
    predecessor = CRDTId("peer", 2)
    descendant = CRDTElement(CRDTId("peer", 4), "B", predecessor)
    later_head = CRDTElement(CRDTId("peer", 3), "H", None)

    document.insert_remote(CRDTElement(predecessor, "A"))
    document.insert_remote(descendant)
    document.insert_remote(later_head)
    assert document.delete_remote(predecessor) is True

    # Correct RGA traversal walks A (tombstone) -> B before the later head H.
    assert document.get_text() == "BH"


@pytest.mark.xfail(strict=True, reason="Known CRDT defect — scheduled for M1 (document.py:apply_full_state)")
def test_reg_06_full_state_merge_does_not_resurrect_tombstone(document_factory):
    """A newer tombstone must win when merged into a replica with an old visible copy."""
    source = document_factory("source")
    target = document_factory("target")
    source.insert_local("A", 0)
    target.apply_full_state(source.get_full_state())
    source.delete_local(0)

    target.apply_full_state(source.get_full_state())
    assert target.get_text() == ""
