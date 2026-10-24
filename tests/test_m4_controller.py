import time
import threading

import c2g.crdt.document as document_module
from c2g.ui.controller import ApplicationController


class MemoryPersistence:
    def __init__(self, *args, **kwargs): pass
    def clear(self): pass
    def load_state(self): return None
    def save_state(self, *args, **kwargs): pass
    def stop(self): pass


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError("timed out")


def tx(identifier, version, offset, length, text):
    return {"transaction_id": identifier, "base_version": version,
            "changes": [{"rangeOffset": offset, "rangeLength": length, "text": text}]}


def test_controller_transactions_unicode_and_duplicate(monkeypatch):
    monkeypatch.setattr(document_module, "PersistenceManager", MemoryPersistence)
    controller = ApplicationController("alice")
    try:
        result = controller.apply_local_transaction(tx("a", 1, 0, 0, "A😀\nB"))
        assert result["accepted"] and controller.document.get_text() == "A😀\nB"
        result = controller.apply_local_transaction(tx("b", 2, 1, 2, "X"))
        assert result["accepted"] and controller.document.get_text() == "AX\nB"
        assert controller.apply_local_transaction(tx("b", 2, 1, 2, "X"))["duplicate"]
        assert not controller.apply_local_transaction(tx("stale", 1, 0, 0, "!"))["accepted"]
    finally: controller.shutdown()


def test_two_peer_real_network_controller_pipeline(monkeypatch):
    monkeypatch.setattr(document_module, "PersistenceManager", MemoryPersistence)
    alice = ApplicationController("alice", 0, start_network=True, start_discovery=False)
    bob = ApplicationController("bob", 0, start_network=True, start_discovery=False)
    try:
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == len(bob.network.peers) == 1)
        assert alice.apply_local_transaction(tx("a", 1, 0, 0, "hello"))["accepted"]
        wait_for(lambda: bob.document.get_text() == "hello")
        assert bob.apply_local_transaction(tx("b", bob.version, 1, 3, "i"))["accepted"]
        wait_for(lambda: alice.document.get_text() == bob.document.get_text() == "hio")
    finally:
        alice.shutdown(); bob.shutdown()


def test_disconnect_reconnect_preserves_offline_edits_and_tombstones(monkeypatch):
    monkeypatch.setattr(document_module, "PersistenceManager", MemoryPersistence)
    alice = ApplicationController("alice", 0, start_network=True, start_discovery=False)
    bob = ApplicationController("bob", 0, start_network=True, start_discovery=False)
    try:
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == len(bob.network.peers) == 1)
        assert alice.apply_local_transaction(tx("seed", 1, 0, 0, "abcd"))["accepted"]
        wait_for(lambda: bob.document.get_text() == "abcd")
        bob_id = next(iter(alice.network.peers))
        assert alice.disconnect_peer(bob_id)["accepted"]
        assert not alice.disconnect_peer(bob_id)["accepted"]  # repeated click is harmless
        wait_for(lambda: not alice.network.peers and not bob.network.peers)
        # Offline deletion leaves a tombstone; Bob independently inserts text.
        assert alice.apply_local_transaction(tx("delete", alice.version, 1, 1, ""))["accepted"]
        assert bob.apply_local_transaction(tx("insert", bob.version, 4, 0, "!"))["accepted"]
        assert alice.document.get_text() == "acd" and bob.document.get_text() == "abcd!"
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: alice.document.get_text() == bob.document.get_text())
        assert "b" not in alice.document.get_text() and alice.document.get_text().endswith("!")
        assert alice.document_id == bob.document_id
    finally:
        alice.shutdown(); bob.shutdown()


def test_simultaneous_disconnect_requests_are_idempotent(monkeypatch):
    monkeypatch.setattr(document_module, "PersistenceManager", MemoryPersistence)
    alice = ApplicationController("alice", 0, start_network=True, start_discovery=False)
    bob = ApplicationController("bob", 0, start_network=True, start_discovery=False)
    try:
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == len(bob.network.peers) == 1)
        alice_id, bob_id = next(iter(alice.network.peers)), next(iter(bob.network.peers))
        barrier, results = threading.Barrier(3), []
        def disconnect(controller, peer_id):
            barrier.wait(); results.append(controller.disconnect_peer(peer_id)["accepted"])
        left = threading.Thread(target=disconnect, args=(alice, alice_id))
        right = threading.Thread(target=disconnect, args=(bob, bob_id))
        left.start(); right.start(); barrier.wait(); left.join(2); right.join(2)
        assert not left.is_alive() and not right.is_alive() and any(results)
        wait_for(lambda: not alice.network.peers and not bob.network.peers)
    finally:
        alice.shutdown(); bob.shutdown()
