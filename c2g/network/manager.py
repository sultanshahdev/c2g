"""Bounded, versioned TCP sessions for c2g peers (trusted LAN only)."""
import json
import socket
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from ..crdt.message import CRDTMessage

PROTOCOL_VERSION = 2
REQUIRED_CAPABILITIES = frozenset(("rga-before-anchor", "pending-tombstones", "state-sync"))
MAX_FRAME_SIZE = 12 * 1024 * 1024
MAX_BUFFER_SIZE = MAX_FRAME_SIZE + 4
MAX_PEERS, MAX_SEEN_MESSAGES, MAX_PENDING_OUTBOUND, MAX_HANDSHAKES = 16, 20_000, 1_000, 16

class ProtocolError(ValueError): pass

def encode_frame(payload):
    try: raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc: raise ProtocolError("message is not JSON serializable") from exc
    if not raw or len(raw) > MAX_FRAME_SIZE: raise ProtocolError("invalid frame size")
    return len(raw).to_bytes(4, "big") + raw

class FrameDecoder:
    def __init__(self): self.buffer = bytearray()
    def feed(self, chunk):
        self.buffer.extend(chunk)
        if len(self.buffer) > MAX_BUFFER_SIZE: raise ProtocolError("receive buffer limit exceeded")
        result = []
        while len(self.buffer) >= 4:
            size = int.from_bytes(self.buffer[:4], "big")
            if not 0 < size <= MAX_FRAME_SIZE: raise ProtocolError("invalid frame length")
            if len(self.buffer) < 4 + size: break
            raw = bytes(self.buffer[4:4 + size]); del self.buffer[:4 + size]
            try: value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ProtocolError("invalid JSON frame") from exc
            if not isinstance(value, dict): raise ProtocolError("frame must be object")
            result.append(value)
        return result

@dataclass
class PeerSession:
    conn: socket.socket; peer_id: str; username: str; endpoint: str; outgoing: bool
    state: str = "SYNCING"; lock: threading.Lock = field(default_factory=threading.Lock)
    pending: list = field(default_factory=list)

class NetworkManager:
    """Transport is Tk-free. READY means snapshot exchange was initiated both ways."""
    def __init__(self, username: str, port: int = 5000, *, peer_id=None, document_id=None,
                 state_provider: Optional[Callable[[], list]]=None, is_document_empty=None):
        if not isinstance(username, str) or not username or len(username) > 128: raise ValueError("invalid username")
        if not isinstance(port, int) or not 0 <= port <= 65535: raise ValueError("invalid port")
        self.username, self.port, self.peer_id = username, port, peer_id or str(uuid.uuid4())
        self.document_id = document_id or str(uuid.uuid4()); self.state_provider = state_provider
        self.is_document_empty = is_document_empty or (lambda: True)
        self.peers: Dict[str, PeerSession] = {}; self.peers_lock = threading.RLock(); self.server_socket = None
        self.running = True; self.on_message = None; self.on_event = None; self._seen = OrderedDict(); self._handshakes = 0
    def _event(self, kind, **data):
        if self.on_event:
            try: self.on_event(kind, data)
            except Exception: pass
    def start_listening(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.port)); sock.listen(MAX_PEERS); sock.settimeout(.5)
            self.server_socket = sock; self.port = sock.getsockname()[1]
            threading.Thread(target=self._accept_peers, daemon=True).start(); return True
        except OSError as exc: self._event("listen_error", error=str(exc)); return False
    def _hello(self, join):
        return {"type":"HELLO", "protocol_version":PROTOCOL_VERSION, "peer_id":self.peer_id, "username":self.username,
                "document_id":self.document_id, "listen_port":self.port, "capabilities":sorted(REQUIRED_CAPABILITIES), "join_request":bool(join)}
    def _validate_hello(self, msg):
        required = {"protocol_version","peer_id","username","document_id","listen_port","capabilities"}
        if msg.get("type") != "HELLO" or not required <= msg.keys(): raise ProtocolError("invalid HELLO")
        if msg["protocol_version"] != PROTOCOL_VERSION: raise ProtocolError("unsupported protocol version")
        if not all(isinstance(msg[x], str) and 0 < len(msg[x]) <= 128 for x in ("peer_id","username","document_id")): raise ProtocolError("invalid identity")
        if msg["peer_id"] == self.peer_id: raise ProtocolError("self connection")
        if not isinstance(msg["listen_port"], int) or not 0 <= msg["listen_port"] <= 65535: raise ProtocolError("invalid port")
        if not isinstance(msg["capabilities"], list) or not REQUIRED_CAPABILITIES <= set(msg["capabilities"]): raise ProtocolError("capability mismatch")
    def connect_to_peer(self, peer_ip, peer_port=5000):
        conn = None
        try:
            if not isinstance(peer_port, int) or not 1 <= peer_port <= 65535: return False
            conn = socket.create_connection((peer_ip, peer_port), timeout=5); conn.settimeout(5); conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._handshake(conn, True, peer_ip); return True
        except (OSError, ProtocolError) as exc:
            self._event("connection_error", endpoint=f"{peer_ip}:{peer_port}", error=str(exc))
            if conn: conn.close()
            return False
    def _accept_peers(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept(); conn.settimeout(5); conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self.peers_lock:
                    full = len(self.peers) >= MAX_PEERS or self._handshakes >= MAX_HANDSHAKES
                    if not full: self._handshakes += 1
                if full: conn.close(); continue
                threading.Thread(target=self._incoming_handshake, args=(conn, addr[0]), daemon=True).start()
            except socket.timeout: continue
            except OSError: pass
    def _incoming_handshake(self, conn, host):
        try: self._handshake(conn, False, host)
        finally:
            with self.peers_lock: self._handshakes -= 1
    def _recv_one(self, conn, decoder):
        while True:
            data = conn.recv(65536)
            if not data: raise ProtocolError("closed during frame")
            messages = decoder.feed(data)
            if messages: return messages[0], messages[1:]
    def _reject(self, conn, reason):
        try: conn.sendall(encode_frame({"type":"REJECT", "reason":reason}))
        except OSError: pass
    def _handshake(self, conn, outgoing, host):
        decoder = FrameDecoder()
        try:
            conn.sendall(encode_frame(self._hello(outgoing and self.is_document_empty()))); hello, pending = self._recv_one(conn, decoder)
            if hello.get("type") == "REJECT": raise ProtocolError(hello.get("reason", "rejected"))
            self._validate_hello(hello); mismatch = hello["document_id"] != self.document_id
            allowed_join = ((not outgoing and hello.get("join_request") is True) or
                            (outgoing and self.is_document_empty() and hello.get("join_request") is False))
            if mismatch and not allowed_join:
                self._reject(conn, "document mismatch; explicit empty-document join required"); raise ProtocolError("document mismatch")
            # The explicit join initiator adopts the existing peer's logical ID;
            # the receiving peer remains authoritative for this join.
            if mismatch and outgoing: self.document_id = hello["document_id"]
            session = PeerSession(conn, hello["peer_id"], hello["username"], f"{host}:{hello['listen_port']}", outgoing)
            with self.peers_lock:
                old = self.peers.get(session.peer_id); preferred_outgoing = self.peer_id < session.peer_id
                if old:
                    if old.outgoing == preferred_outgoing: self._reject(conn, "duplicate connection"); raise ProtocolError("duplicate")
                self.peers[session.peer_id] = session
            # Closing a replaced connection can block; never do it under the
            # peer registry lock. Its reader carries `expected`, so it cannot
            # remove this replacement session.
            if old: self._drop(session.peer_id, old)
            conn.settimeout(1); self._event("peer_connected", peer_id=session.peer_id, username=session.username, state="SYNCING")
            if self.state_provider: self._send(session, {"type":"FULL_SYNC", "document_id":self.document_id, "state":self.state_provider()})
            # The same lock serializes the snapshot boundary and all live
            # operations. Edits made while SYNCING are replayed after snapshot.
            with session.lock:
                session.state = "READY"
                for packet in session.pending: session.conn.sendall(packet)
                session.pending.clear()
            self._event("sync_complete", peer_id=session.peer_id)
            for frame in pending: self._handle(session, frame)
            # Outgoing setup is synchronous only through HELLO/snapshot so the
            # caller gets a meaningful result; receiving continues in a worker.
            if outgoing:
                threading.Thread(target=self._reader, args=(session, decoder), daemon=True).start()
            else:
                self._reader(session, decoder)
        except (OSError, ProtocolError, ValueError) as exc:
            if not outgoing and isinstance(exc, (ProtocolError, ValueError)):
                self._reject(conn, str(exc))
            self._event("peer_rejected", error=str(exc)); conn.close()
            if outgoing: raise
    def _send(self, session, payload):
        with session.lock: session.conn.sendall(encode_frame(payload))
    def _send_or_buffer(self, session, payload):
        packet = encode_frame(payload)
        with session.lock:
            if session.state == "SYNCING":
                if len(session.pending) >= MAX_PENDING_OUTBOUND: raise ProtocolError("sync operation buffer limit exceeded")
                session.pending.append(packet); return
            if session.state != "READY": raise OSError("session is not ready")
            session.conn.sendall(packet)
    def _reader(self, session, decoder):
        try:
            while self.running:
                try: data = session.conn.recv(65536)
                except socket.timeout: continue
                if not data: break
                for frame in decoder.feed(data): self._handle(session, frame)
        except (OSError, ProtocolError, ValueError) as exc: self._event("connection_error", peer_id=session.peer_id, error=str(exc))
        finally: self._drop(session.peer_id, session)
    def _remember(self, mid):
        if mid in self._seen: return False
        self._seen[mid] = None
        if len(self._seen) > MAX_SEEN_MESSAGES: self._seen.popitem(last=False)
        return True
    def _handle(self, session, frame):
        typ = frame.get("type")
        if typ == "FULL_SYNC":
            if frame.get("document_id") != self.document_id or not isinstance(frame.get("state"), list): raise ProtocolError("invalid sync")
            self._deliver(CRDTMessage(msg_type="FULL_SYNC", elements=frame["state"]), session.peer_id); return
        if typ != "OP" or frame.get("document_id") != self.document_id: raise ProtocolError("invalid application frame")
        mid, raw = frame.get("message_id"), frame.get("message")
        if not isinstance(mid, str) or not mid or len(mid) > 256 or not isinstance(raw, dict): raise ProtocolError("invalid operation")
        if not self._remember(mid): return
        msg = CRDTMessage.from_dict(raw); self._deliver(msg, session.peer_id); self.broadcast_message(msg, exclude_peer=session.peer_id, message_id=mid)
    def _deliver(self, msg, peer_id):
        if self.on_message:
            try: self.on_message(msg, peer_id)
            except TypeError: self.on_message(msg)
    def broadcast_message(self, msg, exclude_peer=None, message_id=None):
        mid = message_id or msg.message_id or f"{self.peer_id}:{uuid.uuid4()}"; self._remember(mid)
        payload = {"type":"OP", "document_id":self.document_id, "message_id":mid, "message":msg.to_dict()}
        with self.peers_lock: sessions = [s for p,s in self.peers.items() if p != exclude_peer]
        for session in sessions:
            try: self._send_or_buffer(session, payload)
            except (OSError, ProtocolError): self._drop(session.peer_id, session)
    def send_to_peer(self, peer_id, msg):
        with self.peers_lock: session = self.peers.get(peer_id)
        if not session or session.state != "READY": return False
        try: self._send(session, {"type":"OP", "document_id":self.document_id, "message_id":msg.message_id or f"{self.peer_id}:{uuid.uuid4()}", "message":msg.to_dict()}); return True
        except OSError: self._drop(peer_id, session); return False
    def _drop(self, peer_id, expected=None):
        with self.peers_lock:
            session = self.peers.get(peer_id)
            if not session or (expected and expected is not session): return
            self.peers.pop(peer_id, None)
        try: session.conn.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        try: session.conn.close()
        except OSError: pass
        self._event("peer_disconnected", peer_id=peer_id)
    def close(self):
        self.running = False
        if self.server_socket:
            try: self.server_socket.close()
            except OSError: pass
        with self.peers_lock: sessions = list(self.peers.items())
        for peer_id, session in sessions: self._drop(peer_id, session)
