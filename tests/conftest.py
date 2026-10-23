"""Isolated CRDT fixtures; no real persistence, threads, sockets, or GUI."""

import itertools

import pytest

import c2g.crdt.document as document_module


class MemoryPersistence:
    """Minimal persistence double matching the CRDT's currently used interface."""

    def __init__(self, doc_name):
        self.doc_name = doc_name

    def clear(self):
        pass

    def load_state(self):
        return None

    def save_state(self, elements_data, applied_ops, lamport_clock):
        pass


@pytest.fixture
def document_factory(monkeypatch):
    """Return independently initialized replicas without touching ~/.p2p_crdt."""
    monkeypatch.setattr(document_module, "PersistenceManager", MemoryPersistence)
    counter = itertools.count()

    def make(client_id=None):
        identity = client_id or f"test-peer-{next(counter)}"
        return document_module.CRDTDocument(identity, doc_name=identity, start_fresh=True)

    return make
