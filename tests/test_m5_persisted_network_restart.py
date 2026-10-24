"""M5-D real controller/network restart scenarios using JSON-backed replicas."""
import time

from c2g.storage.recovered_document import PersistedCrdt
from c2g.ui.controller import ApplicationController


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("timed out")


def tx(identifier, version, offset, length, text):
    return {"transaction_id": identifier, "base_version": version,
            "changes": [{"rangeOffset": offset, "rangeLength": length, "text": text}]}


def controller(root, key, username):
    return ApplicationController(username, 0, persisted=PersistedCrdt.open(root, key), start_network=True,
                                 start_discovery=False)


def test_persisted_two_peer_restart_reconnect_and_continue(tmp_path):
    alice_saved = PersistedCrdt.create(tmp_path, "alice")
    bob_saved = PersistedCrdt.create(tmp_path, "bob")
    alice_id, alice_replica, bob_replica = alice_saved.document_id, alice_saved.replica_id, bob_saved.replica_id
    alice = ApplicationController("alice", 0, persisted=alice_saved, start_network=True, start_discovery=False)
    bob = ApplicationController("bob", 0, persisted=bob_saved, start_network=True, start_discovery=False)
    try:
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == len(bob.network.peers) == 1 and bob.document_id == alice_id)
        assert alice.apply_local_transaction(tx("seed", 1, 0, 0, "abcd"))["accepted"]
        wait_for(lambda: bob.document.get_text() == "abcd")
        assert bob.apply_local_transaction(tx("bob-edit", bob.version, 1, 2, "XY"))["accepted"]
        wait_for(lambda: alice.document.get_text() == bob.document.get_text() == "aXYd")
    finally:
        alice.shutdown(); bob.shutdown()

    alice, bob = controller(tmp_path, "alice", "alice"), controller(tmp_path, "bob", "bob")
    try:
        assert alice.document_id == bob.document_id == alice_id
        assert alice.document.client_id == alice_replica and bob.document.client_id == bob_replica
        assert alice.document.get_text() == bob.document.get_text() == "aXYd"
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == len(bob.network.peers) == 1)
        assert alice.apply_local_transaction(tx("after-restart-a", alice.version, 4, 0, "!"))["accepted"]
        wait_for(lambda: bob.document.get_text() == "aXYd!")
        assert bob.apply_local_transaction(tx("after-restart-b", bob.version, 0, 0, ">"))["accepted"]
        wait_for(lambda: alice.document.get_text() == bob.document.get_text() == ">aXYd!")
    finally:
        alice.shutdown(); bob.shutdown()


def test_one_peer_restart_reconciles_offline_insert_and_tombstone(tmp_path):
    alice_saved, bob_saved = PersistedCrdt.create(tmp_path, "alice"), PersistedCrdt.create(tmp_path, "bob")
    alice = ApplicationController("alice", 0, persisted=alice_saved, start_network=True, start_discovery=False)
    bob = ApplicationController("bob", 0, persisted=bob_saved, start_network=True, start_discovery=False)
    try:
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == len(bob.network.peers) == 1)
        assert alice.apply_local_transaction(tx("shared", 1, 0, 0, "abcd"))["accepted"]
        wait_for(lambda: bob.document.get_text() == "abcd")
        peer_id = next(iter(alice.network.peers)); assert alice.disconnect_peer(peer_id)["accepted"]
        wait_for(lambda: not alice.network.peers and not bob.network.peers)
        bob.shutdown()
        # Alice's changes are persisted while Bob is down: one tombstone and one insertion.
        assert alice.apply_local_transaction(tx("delete", alice.version, 1, 1, ""))["accepted"]
        assert alice.apply_local_transaction(tx("insert", alice.version, 3, 0, "!"))["accepted"]
        assert alice.document.get_text() == "acd!"
        bob = controller(tmp_path, "bob", "bob")
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: alice.document.get_text() == bob.document.get_text() == "acd!")
        assert all(element.char != "b" or not element.visible for element in alice.document.elements.values())
    finally:
        alice.shutdown(); bob.shutdown()
