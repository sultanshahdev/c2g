"""Characterization tests for existing, expected CRDT behavior."""

from c2g.crdt.types import CRDTElement


def test_basic_01_empty_document(document_factory):
    assert document_factory().get_text() == ""


def test_basic_02_sequential_append(document_factory):
    document = document_factory()
    document.insert_local("A", 0)
    document.insert_local("B", 1)
    assert document.get_text() == "AB"


def test_basic_03_remote_insert(document_factory):
    source = document_factory("source")
    target = document_factory("target")
    element = source.insert_local("A", 0)

    assert target.insert_remote(CRDTElement.from_dict(element.to_dict())) is True
    assert target.get_text() == "A"


def test_basic_04_duplicate_remote_insert(document_factory):
    source = document_factory("source")
    target = document_factory("target")
    element = source.insert_local("A", 0)
    payload = CRDTElement.from_dict(element.to_dict())

    assert target.insert_remote(payload) is True
    assert target.insert_remote(CRDTElement.from_dict(element.to_dict())) is False
    assert target.get_text() == "A"


def test_basic_05_local_deletion(document_factory):
    document = document_factory()
    document.insert_local("A", 0)

    assert document.delete_local(0) is not None
    assert document.get_text() == ""


def test_basic_06_element_serialization_round_trip():
    original = CRDTElement.from_dict({
        "char_id": {"client_id": "peer", "lamport_clock": 2},
        "char": "A",
        "after_id": {"client_id": "peer", "lamport_clock": 1},
        "visible": True,
    })

    restored = CRDTElement.from_dict(original.to_dict())
    assert restored == original
