"""Authoritative M4 document controller, independent of a GUI toolkit."""
from __future__ import annotations

import ipaddress
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..crdt import CRDTDocument, CRDTElement, CRDTId, CRDTMessage
from ..network import NetworkManager, PeerDiscovery
from ..storage.recovered_document import PersistedCrdt


def utf16_to_codepoint(text: str, offset: int) -> int:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("invalid UTF-16 offset")
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > offset:
            raise ValueError("offset splits a surrogate pair")
        units += width
    if units == offset:
        return len(text)
    raise ValueError("UTF-16 offset past text")


def codepoint_to_utf16(text: str, index: int) -> int:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= len(text):
        raise ValueError("invalid code-point index")
    return len(text[:index].encode("utf-16-le")) // 2


def incremental_patch(before: str, after: str) -> Dict[str, Any]:
    """Return the smallest contiguous Monaco patch for two CRDT renderings."""
    prefix = 0
    while prefix < min(len(before), len(after)) and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    while suffix < len(before) - prefix and suffix < len(after) - prefix and before[-1 - suffix] == after[-1 - suffix]:
        suffix += 1
    end = len(before) - suffix
    start16 = codepoint_to_utf16(before, prefix)
    return {"offset": start16, "length": codepoint_to_utf16(before, end) - start16,
            "text": after[prefix:len(after) - suffix if suffix else len(after)]}


class ApplicationController:
    """One serialized owner of the CRDT, M2 network, and UI notifications."""

    def __init__(self, username: str, listen_port: int = 5000, *, client_id: Optional[str] = None,
                 document_id: Optional[str] = None, start_network: bool = False,
                 start_discovery: bool = False, persisted: Optional[PersistedCrdt] = None):
        self.username = username
        self.lock = threading.RLock()
        self.running = True
        self.version = 1  # Authoritative text version, distinct from Monaco versionId.
        self.seen_transactions = set()
        self.ui_dispatch: Optional[Callable[[Dict[str, Any]], None]] = None
        self.persisted = persisted
        self.save_status, self.save_error = ("saved", None) if persisted else ("unsaved", None)
        if persisted:
            persisted.set_status_callback(self._on_save_status)
        self.document = persisted.document if persisted else CRDTDocument(client_id or str(uuid.uuid4()), doc_name="collaborative_doc", start_fresh=True)
        self.network = NetworkManager(username, listen_port, document_id=(persisted.document_id if persisted else document_id or str(uuid.uuid4())),
                                      state_provider=self.document.get_full_state,
                                      is_document_empty=lambda: not self.document.elements)
        self.discovery = PeerDiscovery(username, peer_id=self.network.peer_id)
        self.network.on_message = self._on_network_message
        self.network.on_event = self._on_network_event
        self.network.on_document_id_changed = self._persist_joined_document_id
        self.discovery_started = False
        if start_network:
            self.start(start_discovery=start_discovery)

    @property
    def document_id(self):
        return self.network.document_id

    def _on_save_status(self, state: str, error: Optional[str]) -> None:
        with self.lock:
            self.save_status, self.save_error = state, error
        self._notify({"type": "save_status", "state": state, "error": error})

    def _persist_joined_document_id(self, document_id: str) -> None:
        if self.persisted is None:
            return
        with self.lock:
            self.persisted.update_document_id(document_id)

    def start(self, *, start_discovery: bool = True) -> bool:
        if not self.network.start_listening():
            return False
        if start_discovery:
            self.discovery.start_broadcast(self.network.port)
            self.discovery_started = True
        return True

    def set_ui_dispatch(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self.ui_dispatch = callback

    def _notify(self, payload: Dict[str, Any]) -> None:
        callback = self.ui_dispatch
        if callback and self.running:
            try:
                callback(payload)
            except Exception:
                pass

    def initialize(self) -> Dict[str, Any]:
        with self.lock:
            return {"text": self.document.get_text(), "version": self.version,
                    "language": "python", "document_id": self.document_id,
                    "ui_state": self.ui_state(), "save_status": self.save_status,
                    "save_error": self.save_error}

    def ui_state(self) -> Dict[str, Any]:
        with self.network.peers_lock:
            connected = [{"peer_id": peer_id, "username": item.username,
                          "endpoint": item.endpoint, "state": item.state}
                         for peer_id, item in self.network.peers.items()]
        discovered = [{"peer_id": peer_id, "username": value[0], "port": value[1], "host": value[3]}
                      for peer_id, value in self.discovery.get_peers().items()
                      if peer_id not in {peer["peer_id"] for peer in connected}]
        return {"connected": connected, "discovered": discovered,
                "listen_port": self.network.port, "document_id": self.document_id,
                "save_status": self.save_status, "save_error": self.save_error}

    def _on_network_event(self, kind: str, data: Dict[str, Any]) -> None:
        self._notify({"type": "network", "kind": kind, "data": data, "ui_state": self.ui_state()})

    def _validate_transaction(self, transaction: Dict[str, Any]):
        if not isinstance(transaction, dict):
            raise ValueError("transaction must be object")
        txid, version, changes = transaction.get("transaction_id"), transaction.get("base_version"), transaction.get("changes")
        if not isinstance(txid, str) or not txid or len(txid) > 256 or not isinstance(version, int) or not isinstance(changes, list):
            raise ValueError("invalid transaction")
        return txid, version, changes

    def apply_local_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Apply one Monaco pre-change transaction and broadcast its CRDT ops."""
        with self.lock:
            txid, base_version, changes = self._validate_transaction(transaction)
            if txid in self.seen_transactions:
                return {"accepted": True, "duplicate": True, "version": self.version}
            if not self.running:
                return {"accepted": False, "reason": "application is closing", "version": self.version}
            before = self.document.get_text()
            if base_version != self.version:
                return {"accepted": False, "reason": "stale model version", "version": self.version, "text": before}
            normalized = []
            for change in changes:
                if not isinstance(change, dict) or any(key not in change for key in ("rangeOffset", "rangeLength", "text")):
                    raise ValueError("invalid edit change")
                if isinstance(change["rangeOffset"], bool) or isinstance(change["rangeLength"], bool) or not isinstance(change["rangeOffset"], int) or not isinstance(change["rangeLength"], int) or change["rangeLength"] < 0 or not isinstance(change["text"], str):
                    raise ValueError("invalid edit change")
                start = utf16_to_codepoint(before, change["rangeOffset"])
                end = utf16_to_codepoint(before, change["rangeOffset"] + change["rangeLength"])
                normalized.append((start, end, change["text"]))
            normalized.sort(reverse=True)
            previous = len(before) + 1
            outbound = []
            for start, end, text in normalized:
                if end < start or end > previous:
                    raise ValueError("overlapping changes")
                deleted = []
                for position in range(end - 1, start - 1, -1):
                    char_id = self.document.delete_local(position)
                    if char_id:
                        deleted.append({"client_id": char_id.client_id, "lamport_clock": char_id.lamport_clock})
                if deleted:
                    outbound.append(CRDTMessage("BATCH_DELETE", char_ids=deleted))
                inserted = self.document.insert_local_batch(text, start)
                if inserted:
                    outbound.append(CRDTMessage("INSERT", elements=[item.to_dict() for item in inserted]))
                previous = start
            self.seen_transactions.add(txid)
            if len(self.seen_transactions) > 20_000:
                self.seen_transactions.pop()
            after = self.document.get_text()
            if after != before:
                self.version += 1
            for message in outbound:
                self.network.broadcast_message(message)
            return {"accepted": True, "version": self.version, "patch": incremental_patch(before, after), "text": after}

    def _on_network_message(self, message: CRDTMessage, _peer_id: Optional[str] = None) -> None:
        with self.lock:
            if not self.running:
                return
            before = self.document.get_text()
            if message.msg_type == "FULL_SYNC":
                self.document.apply_full_state(message.elements)
            elif message.msg_type == "INSERT":
                for raw in message.elements:
                    self.document.insert_remote(CRDTElement.from_dict(raw))
            elif message.msg_type == "DELETE" and message.char_id:
                self.document.delete_remote(CRDTId(**message.char_id))
            elif message.msg_type == "BATCH_DELETE":
                for raw in message.char_ids:
                    self.document.delete_remote(CRDTId(**raw))
            else:
                return
            after = self.document.get_text()
            if after != before:
                self.version += 1
                self._notify({"type": "remote_patch", "patch": incremental_patch(before, after), "version": self.version})

    @staticmethod
    def parse_endpoint(endpoint: str):
        if not isinstance(endpoint, str):
            raise ValueError("endpoint must be text")
        raw = endpoint.strip()
        host, separator, port_text = raw.rpartition(":")
        if not separator:
            host, port_text = raw, "5000"
        if not host:
            raise ValueError("host is required")
        try:
            ipaddress.ip_address(host)
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("enter an IPv4/IPv6 address with an optional port") from exc
        if not 1 <= port <= 65535:
            raise ValueError("port must be 1..65535")
        return host, port

    def connect(self, endpoint: str) -> Dict[str, Any]:
        try:
            host, port = self.parse_endpoint(endpoint)
        except ValueError as exc:
            return {"accepted": False, "reason": str(exc)}
        threading.Thread(target=self.network.connect_to_peer, args=(host, port), daemon=True).start()
        return {"accepted": True, "status": "Connecting"}

    def connect_discovered(self, host: str, port: int) -> Dict[str, Any]:
        return self.connect(f"{host}:{port}")

    def disconnect_peer(self, peer_id: str) -> Dict[str, Any]:
        if not isinstance(peer_id, str) or not peer_id:
            return {"accepted": False, "reason": "invalid peer identity"}
        if self.network.disconnect_peer(peer_id):
            return {"accepted": True, "status": "Disconnected"}
        return {"accepted": False, "reason": "peer is no longer connected"}

    def export(self, path: str) -> Dict[str, Any]:
        if not isinstance(path, str) or not path:
            return {"accepted": False, "reason": "no export path selected"}
        try:
            target = Path(path).expanduser()
            if target.exists() and target.is_dir():
                raise ValueError("export target is a directory")
            with self.lock:
                target.write_text(self.document.get_text(), encoding="utf-8", newline="")
            return {"accepted": True, "path": str(target)}
        except (OSError, ValueError) as exc:
            return {"accepted": False, "reason": str(exc)}

    def shutdown(self) -> None:
        with self.lock:
            if not self.running:
                return
            self.running = False
        self.discovery.stop()
        self.network.close()
        if self.persisted:
            self.persisted.close()
        else:
            self.document.persistence.stop()
