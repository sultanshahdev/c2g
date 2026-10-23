"""
UDP-based peer discovery for LAN networks.
"""

import socket
import threading
import json
import time
import uuid
from typing import Dict, Tuple


class PeerDiscovery:
    """UDP-based LAN peer discovery."""
    
    def __init__(self, username: str, port: int = 5001, *, peer_id=None, protocol_version=2):
        self.username = username
        self.port = port
        self.peer_id = peer_id or str(uuid.uuid4())
        self.protocol_version = protocol_version
        self.peers: Dict[str, Tuple[str, int, float]] = {}  # peer_id: username, tcp port, local receipt time
        self.running = False
        self.lock = threading.RLock()
        self.discovery_port = 5001
    
    def start_broadcast(self, server_port: int):
        """Start UDP broadcast and listen threads."""
        self.running = True
        threading.Thread(target=self._broadcast_loop, args=(server_port,), daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()
    
    def _broadcast_loop(self, server_port: int):
        """Broadcast presence every 5 seconds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        while self.running:
            try:
                msg = json.dumps({"protocol":"c2g", "protocol_version":self.protocol_version,
                                  "peer_id":self.peer_id, "username":self.username, "port":server_port})
                sock.sendto(msg.encode(), ("255.255.255.255", self.discovery_port))
                time.sleep(5)
            except:
                pass
    
    def _listen_loop(self):
        """Listen for peer broadcasts."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.discovery_port))
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                self.process_announcement(data, addr[0])
            except:
                pass

    def process_announcement(self, data, host, received_at=None):
        """Validate one datagram; separated for deterministic headless tests."""
        try:
            msg = json.loads(data.decode("utf-8")) if isinstance(data, bytes) else data
            valid = (isinstance(msg, dict) and msg.get("protocol") == "c2g" and
                     msg.get("protocol_version") == self.protocol_version and
                     isinstance(msg.get("peer_id"), str) and 0 < len(msg["peer_id"]) <= 128 and
                     isinstance(msg.get("username"), str) and 0 < len(msg["username"]) <= 128 and
                     isinstance(msg.get("port"), int) and 1 <= msg["port"] <= 65535 and
                     isinstance(host, str) and msg["peer_id"] != self.peer_id)
            if not valid: return False
            with self.lock:
                self.peers[msg["peer_id"]] = (msg["username"], msg["port"], received_at if received_at is not None else time.monotonic(), host)
            return True
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError): return False
    
    def get_peers(self) -> Dict[str, Tuple[str, int, float, str]]:
        """Return peers, filtering stale ones (>20s)."""
        with self.lock:
            now = time.monotonic()
            active = {pid: value for pid, value in self.peers.items() if now - value[2] < 20}
            self.peers = active
            return active
    
    def stop(self):
        """Stop discovery."""
        self.running = False
