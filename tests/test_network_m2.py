import socket
import threading
import time

import pytest

from c2g.crdt import CRDTDocument, CRDTElement, CRDTId, CRDTMessage
from c2g.network.manager import FrameDecoder, NetworkManager, PROTOCOL_VERSION, ProtocolError, encode_frame
from c2g.network.discovery import PeerDiscovery


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError("timed out waiting for condition")

def port_is_closed(port):
    probe = socket.socket()
    try: return probe.connect_ex(("127.0.0.1", port)) != 0
    finally: probe.close()


class Replica:
    def __init__(self, name, doc_id=None):
        self.doc = CRDTDocument(name, doc_name="test_" + name, start_fresh=True)
        self.net = NetworkManager(name, 0, document_id=doc_id, state_provider=self.doc.get_full_state,
                                  is_document_empty=lambda: not self.doc.elements)
        self.net.on_message = self.receive
        assert self.net.start_listening()
    def receive(self, msg, _peer=None):
        if msg.msg_type == "FULL_SYNC": self.doc.apply_full_state(msg.elements)
        elif msg.msg_type == "INSERT":
            for raw in msg.elements: self.doc.insert_remote(CRDTElement.from_dict(raw))
        elif msg.msg_type == "DELETE": self.doc.delete_remote(CRDTId(**msg.char_id))
        elif msg.msg_type == "BATCH_DELETE":
            for raw in msg.char_ids: self.doc.delete_remote(CRDTId(**raw))
    def insert(self, text):
        for char in text:
            element = self.doc.insert_local(char, len(self.doc.get_text()))
            self.net.broadcast_message(CRDTMessage("INSERT", elements=[element.to_dict()]))
    def close(self): self.net.close(); self.doc.persistence.stop()


def test_frames_fragment_coalesce_and_reject_bad_input():
    one, two = encode_frame({"type":"x"}), encode_frame({"type":"y"})
    decoder = FrameDecoder()
    assert decoder.feed(one[:2]) == []
    assert decoder.feed(one[2:] + two) == [{"type":"x"}, {"type":"y"}]
    with pytest.raises(ProtocolError): FrameDecoder().feed((13 * 1024 * 1024).to_bytes(4, "big"))
    with pytest.raises(ProtocolError): FrameDecoder().feed((1).to_bytes(4, "big") + b"\xff")


def test_initial_join_bidirectional_and_chain_relay():
    a = Replica("alice"); b = Replica("bob"); c = Replica("charlie")
    try:
        a.insert("Hello c2g")
        assert b.net.connect_to_peer("127.0.0.1", a.net.port)
        wait_for(lambda: b.doc.get_text() == "Hello c2g" and len(a.net.peers) == len(b.net.peers) == 1)
        # Charlie explicitly joins Bob's already adopted document; forwarding crosses the chain.
        assert c.net.connect_to_peer("127.0.0.1", b.net.port)
        wait_for(lambda: c.doc.get_text() == "Hello c2g")
        a.insert("!")
        wait_for(lambda: c.doc.get_text() == "Hello c2g!")
        cid = c.doc.delete_local(0)
        c.net.broadcast_message(CRDTMessage("DELETE", char_id={"client_id":cid.client_id, "lamport_clock":cid.lamport_clock}))
        wait_for(lambda: a.doc.get_text() == b.doc.get_text() == c.doc.get_text() == "ello c2g!")
    finally:
        a.close(); b.close(); c.close()


def test_reconnect_merges_offline_state_and_rejects_unrelated_documents():
    doc_id = "shared-document"; a = Replica("a", doc_id); b = Replica("b", doc_id); other = Replica("other", "other-document")
    try:
        assert a.net.connect_to_peer("127.0.0.1", b.net.port)
        wait_for(lambda: len(a.net.peers) == 1)
        # Simulate loss then independent local work; snapshot exchange commutatively reconciles on reconnect.
        a.net.close(); b.net.close()
        a.insert("A"); b.insert("B")
        # create replacement managers preserving identity/document and callbacks
        for r in (a,b):
            r.net = NetworkManager(r.doc.client_id, 0, document_id=doc_id, state_provider=r.doc.get_full_state,
                                   is_document_empty=lambda r=r: not r.doc.elements); r.net.on_message = r.receive; assert r.net.start_listening()
        assert a.net.connect_to_peer("127.0.0.1", b.net.port)
        wait_for(lambda: a.doc.get_text() == b.doc.get_text() and set(a.doc.get_text()) == {"A","B"})
        other.insert("unrelated")
        assert not other.net.connect_to_peer("127.0.0.1", a.net.port)
        assert other.doc.get_text() == "unrelated"
    finally:
        a.close(); b.close(); other.close()


def test_three_peer_cycle_deduplicates_repeated_operation():
    doc_id = "cycle"; a = Replica("cycle-a", doc_id); b = Replica("cycle-b", doc_id); c = Replica("cycle-c", doc_id)
    try:
        assert a.net.connect_to_peer("127.0.0.1", b.net.port)
        assert b.net.connect_to_peer("127.0.0.1", c.net.port)
        assert c.net.connect_to_peer("127.0.0.1", a.net.port)
        wait_for(lambda: len(a.net.peers) == len(b.net.peers) == len(c.net.peers) == 2)
        element = a.doc.insert_local("X", 0)
        msg = CRDTMessage("INSERT", elements=[element.to_dict()], message_id="cycle-op")
        a.net.broadcast_message(msg); a.net.broadcast_message(msg)  # multiple paths / duplicate delivery
        wait_for(lambda: a.doc.get_text() == b.doc.get_text() == c.doc.get_text() == "X")
        wait_for(lambda: all(len(r.net._seen) == 1 for r in (a,b,c)))
        c.insert("Y")
        wait_for(lambda: a.doc.get_text() == b.doc.get_text() == c.doc.get_text() == "XY")
    finally: a.close(); b.close(); c.close()


def test_simultaneous_cross_connect_keeps_one_working_session():
    doc_id = "cross"; a = Replica("cross-a", doc_id); b = Replica("cross-b", doc_id)
    try:
        barrier = threading.Barrier(3); outcomes = []
        def connect(left, port):
            barrier.wait(); outcomes.append(left.net.connect_to_peer("127.0.0.1", port))
        ta = threading.Thread(target=connect, args=(a,b.net.port)); tb = threading.Thread(target=connect, args=(b,a.net.port))
        ta.start(); tb.start(); barrier.wait(); ta.join(3); tb.join(3)
        assert not ta.is_alive() and not tb.is_alive()
        wait_for(lambda: len(a.net.peers) == len(b.net.peers) == 1)
        a.insert("Q"); wait_for(lambda: b.doc.get_text() == "Q")
        assert any(outcomes)
    finally: a.close(); b.close()


def test_edit_during_snapshot_is_replayed_after_sync_boundary():
    a = Replica("live-a"); b = Replica("live-b")
    entered, release = threading.Event(), threading.Event()
    original = a.doc.get_full_state
    def paused_snapshot():
        state = original(); entered.set(); assert release.wait(2); return state
    a.net.state_provider = paused_snapshot
    try:
        a.insert("old")
        result = []
        worker = threading.Thread(target=lambda: result.append(b.net.connect_to_peer("127.0.0.1", a.net.port)))
        worker.start(); assert entered.wait(2)
        a.insert("!")  # occurs after snapshot boundary and before READY
        release.set(); worker.join(3); assert result == [True]
        wait_for(lambda: a.doc.get_text() == b.doc.get_text() == "old!")
        b.insert("?"); wait_for(lambda: a.doc.get_text() == b.doc.get_text() == "old!?")
    finally: release.set(); a.close(); b.close()


def test_partial_disconnect_repeated_shutdown_and_discovery_validation():
    manager = NetworkManager("cleanup", 0); assert manager.start_listening()
    raw = socket.create_connection(("127.0.0.1", manager.port), timeout=1)
    try:
        raw.sendall(b"\x00\x00")  # partial header then abrupt loss must not leave a session
        raw.close(); wait_for(lambda: not manager.peers)
    finally: manager.close()
    # Listener ports are released repeatedly and no active peer blocks close.
    for index in range(3):
        item = NetworkManager(f"cleanup-{index}", 0); assert item.start_listening(); port = item.port; item.close()
        wait_for(lambda: port_is_closed(port))
    discovery = PeerDiscovery("alice", peer_id="self")
    valid = {"protocol":"c2g", "protocol_version":2, "peer_id":"bob", "username":"Bob", "port":5002}
    assert discovery.process_announcement(valid, "127.0.0.1")
    assert discovery.process_announcement({**valid, "username":"Bobby"}, "127.0.0.1")
    assert len(discovery.get_peers()) == 1 and discovery.get_peers()["bob"][1] == 5002
    assert not discovery.process_announcement({"protocol":"old"}, "127.0.0.1")
    discovery.process_announcement({**valid, "peer_id":"stale"}, "127.0.0.1", time.monotonic() - 21)
    assert "stale" not in discovery.get_peers()


def test_legacy_hello_is_rejected_without_listener_failure():
    manager = NetworkManager("modern", 0); assert manager.start_listening()
    raw = socket.create_connection(("127.0.0.1", manager.port), timeout=1)
    try:
        raw.sendall(encode_frame({"type":"HELLO", "protocol_version":1, "peer_id":"legacy", "username":"old",
                                  "document_id":"old-doc", "listen_port":5000, "capabilities":[]}))
        raw.settimeout(1)
        decoder = FrameDecoder(); replies = []
        while not any(reply.get("type") == "REJECT" for reply in replies):
            replies.extend(decoder.feed(raw.recv(4096)))
        assert any(reply["type"] == "REJECT" for reply in replies)
        assert not manager.peers
    finally:
        raw.close(); manager.close()
