"""M7 release gates using persisted controllers and real protocol-v2 sockets."""
import socket
import time
from contextlib import contextmanager


from c2g.network.manager import NetworkManager, MAX_HANDSHAKES
from c2g.storage.recovered_document import PersistedCrdt
from c2g.ui.controller import ApplicationController, codepoint_to_utf16


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('bounded wait expired')


def state(peer):
    with peer.document.lock:
        return (peer.document.get_text(),
                {key: value.to_dict() for key, value in peer.document.elements.items()},
                frozenset(peer.document.pending_deletes))


def converged(*peers):
    states = [state(peer) for peer in peers]
    return all(value == states[0] for value in states[1:])


def edit(peer, identifier, offset, length, text):
    before = peer.document.get_text()
    assert peer.apply_local_transaction({
        'transaction_id': identifier, 'base_version': peer.version,
        'changes': [{'rangeOffset': codepoint_to_utf16(before, offset),
                     'rangeLength': codepoint_to_utf16(before, offset + length) - codepoint_to_utf16(before, offset),
                     'text': text}],
    })['accepted']


@contextmanager
def peers_at(root, names, resume=False):
    peers = []
    try:
        for name in names:
            saved = (PersistedCrdt.open if resume else PersistedCrdt.create)(root, name)
            peer = ApplicationController(name, 0, persisted=saved)
            peers.append(peer)
            assert peer.start(start_discovery=False)
        yield peers
    finally:
        for peer in peers:
            peer.shutdown()


def join(source, target):
    assert source.network.connect_to_peer('127.0.0.1', target.network.port)
    wait_for(lambda: source.document_id == target.document_id and converged(source, target))


def concurrent_edits(monkeypatch, peers, operation):
    # Hold broadcasts until every replica has edited the same causal frontier.
    # Release the original CRDT messages through the actual protocol-v2 sockets.
    messages = []
    with monkeypatch.context() as patch:
        for peer in peers:
            original = peer.network.broadcast_message
            patch.setattr(peer.network, 'broadcast_message',
                          lambda message, original=original, **kwargs: messages.append((original, message, kwargs)))
        for peer in peers:
            operation(peer)
    for broadcast, message, kwargs in reversed(messages):
        broadcast(message, **kwargs)
    wait_for(lambda: converged(*peers))


def test_two_peer_edit_disconnect_unicode_and_restart(tmp_path, monkeypatch):
    with peers_at(tmp_path, ('alice', 'bob')) as (alice, bob):
        join(bob, alice)
        edit(alice, 'initial', 0, 0, 'abcd')
        wait_for(lambda: bob.document.get_text() == 'abcd')
        edit(bob, 'middle', 1, 2, 'XY')
        wait_for(lambda: converged(alice, bob))
        concurrent_edits(monkeypatch, (alice, bob),
                         lambda peer: edit(peer, 'concurrent', 1, 0, peer.username[0]))
        concurrent_edits(monkeypatch, (alice, bob),
                         lambda peer: edit(peer, 'delete', 0 if peer is alice else 2, 1, ''))
        for peer in (alice, bob):
            edit(peer, 'paste', len(peer.document.get_text()), 0, '\nمرحبا 😀\ne\u0301\n')
            wait_for(lambda: converged(alice, bob))
        assert bob.disconnect_peer(alice.network.peer_id)['accepted']
        wait_for(lambda: not alice.network.peers and not bob.network.peers)
        edit(alice, 'offline-delete', 0, 1, '')
        edit(bob, 'offline-insert', 0, 0, '>')
        join(bob, alice)
        expected = state(alice)
        identities = [(p.document_id, p.document.client_id, p.document.lamport_clock) for p in (alice, bob)]
        assert any(not e.visible for e in alice.document.elements.values())
        exported = tmp_path / 'export.txt'
        assert alice.export(str(exported))['accepted']
        assert exported.read_text(encoding='utf-8') == expected[0]
        assert not alice.export(str(tmp_path))['accepted']
    with peers_at(tmp_path, ('alice', 'bob'), resume=True) as (alice, bob):
        for peer, (document_id, replica_id, clock) in zip((alice, bob), identities):
            assert state(peer) == expected
            assert (peer.document_id, peer.document.client_id) == (document_id, replica_id)
            assert peer.document.lamport_clock >= clock
        join(bob, alice)
        old_ids = set(alice.document.elements)
        edit(alice, 'resumed', len(alice.document.get_text()), 0, '!')
        wait_for(lambda: converged(alice, bob))
        assert old_ids < set(alice.document.elements)


def test_three_peer_reconciliation_reaches_connected_neighbor(tmp_path, monkeypatch):
    with peers_at(tmp_path, ('alice', 'bob', 'charlie')) as (alice, bob, charlie):
        join(bob, alice)
        join(charlie, bob)
        edit(alice, 'chain', 0, 0, 'abc')
        wait_for(lambda: converged(alice, bob, charlie))
        join(charlie, alice)  # cycle
        concurrent_edits(monkeypatch, (alice, bob, charlie),
                         lambda peer: edit(peer, 'cycle', 1, 0, peer.username[0].upper()))
        for peer_id in list(charlie.network.peers):
            assert charlie.disconnect_peer(peer_id)['accepted']
        wait_for(lambda: not charlie.network.peers and len(alice.network.peers) == len(bob.network.peers) == 1)
        edit(charlie, 'offline-delete', 0, 1, '')
        edit(alice, 'online-insert', len(alice.document.get_text()), 0, '!')
        join(charlie, alice)
        # Bob stays connected: full-state reconciliation must reach it too.
        wait_for(lambda: converged(alice, bob, charlie))
        assert any(not element.visible for element in bob.document.elements.values())


def test_port_conflict_and_connection_refused_are_isolated():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0)); occupied.listen()
        manager = NetworkManager('conflict', occupied.getsockname()[1])
        try:
            assert not manager.start_listening()
        finally:
            manager.close()
    # A bound socket without listen reserves a port but refuses TCP connections.
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        manager = NetworkManager('refused', 0)
        try:
            assert not manager.connect_to_peer('127.0.0.1', reserved.getsockname()[1])
            assert not manager.peers
        finally:
            manager.close()


def test_inbound_handshake_cap_releases_slots():
    manager = NetworkManager('cap', 0)
    clients = []
    assert manager.start_listening()
    try:
        for _ in range(MAX_HANDSHAKES):
            client = socket.create_connection(('127.0.0.1', manager.port), timeout=2)
            client.recv(4096)  # server HELLO; keep handshake incomplete
            clients.append(client)
        wait_for(lambda: manager._handshakes == MAX_HANDSHAKES)
        with socket.create_connection(('127.0.0.1', manager.port), timeout=2) as overflow:
            assert overflow.recv(1) == b''
        assert manager._handshakes == MAX_HANDSHAKES
        for client in clients:
            client.close()
        wait_for(lambda: manager._handshakes == 0)
    finally:
        for client in clients:
            client.close()
        manager.close()
