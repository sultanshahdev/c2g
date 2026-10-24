"""Headless M6 multi-peer simulation using real controllers and protocol v2."""
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


def test_persisted_three_peer_chain_cycle_and_reconnect(tmp_path):
    saved = {name: PersistedCrdt.create(tmp_path, name) for name in ("alice", "bob", "charlie")}
    peers = {name: ApplicationController(name, 0, persisted=item, start_network=True, start_discovery=False)
             for name, item in saved.items()}
    alice, bob, charlie = peers["alice"], peers["bob"], peers["charlie"]
    try:
        # Empty joiners deliberately adopt Alice's logical document identity.
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: bob.document_id == alice.document_id and len(alice.network.peers) == 1)
        assert charlie.connect(f"127.0.0.1:{bob.network.port}")["accepted"]
        wait_for(lambda: charlie.document_id == alice.document_id and len(bob.network.peers) == 2)
        assert alice.apply_local_transaction(tx("chain-a", alice.version, 0, 0, "abc"))["accepted"]
        wait_for(lambda: charlie.document.get_text() == "abc")
        # Close the triangle; duplicate operation delivery must remain harmless.
        assert charlie.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len(alice.network.peers) == 2 and len(charlie.network.peers) == 2)
        assert charlie.apply_local_transaction(tx("cycle-c", charlie.version, 1, 1, "Z"))["accepted"]
        wait_for(lambda: all(peer.document.get_text() == "aZc" for peer in peers.values()))
        # An offline tombstone and independent insertion survive reconnect.
        for peer_id in list(charlie.network.peers):
            assert charlie.disconnect_peer(peer_id)["accepted"]
        wait_for(lambda: not charlie.network.peers)
        assert alice.apply_local_transaction(tx("offline-delete", alice.version, 1, 1, ""))["accepted"]
        assert charlie.apply_local_transaction(tx("offline-insert", charlie.version, 3, 0, "!"))["accepted"]
        assert charlie.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: alice.document.get_text() == charlie.document.get_text() == "ac!")
        # Bob remained connected while Alice reconciled with Charlie; reconnecting
        # it triggers protocol-v2's targeted full-state exchange.
        assert bob.disconnect_peer(next(iter(bob.network.peers)))["accepted"]
        wait_for(lambda: not bob.network.peers)
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: len({peer.document.get_text() for peer in peers.values()}) == 1)
        assert "Z" not in alice.document.get_text() and alice.document.get_text().endswith("!")
    finally:
        for peer in peers.values():
            peer.shutdown()
