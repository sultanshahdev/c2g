"""
UDP-based peer discovery for LAN networks.
"""

import socket
import threading
import json
import time
from typing import Dict, Tuple


class PeerDiscovery:
    """UDP-based LAN peer discovery."""
    
    def __init__(self, username: str, port: int = 5001):
        self.username = username
        self.port = port
        self.peers: Dict[str, Tuple[str, float]] = {}  # {ip: (username, timestamp)}
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
                msg = json.dumps({"username": self.username, "port": server_port, "timestamp": time.time()})
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
                msg = json.loads(data.decode())
                
                if msg["username"] != self.username:
                    with self.lock:
                        self.peers[addr[0]] = (msg["username"], msg["timestamp"])
            except:
                pass
    
    def get_peers(self) -> Dict[str, Tuple[str, float]]:
        """Return peers, filtering stale ones (>20s)."""
        with self.lock:
            now = time.time()
            active = {ip: (u, ts) for ip, (u, ts) in self.peers.items() if now - ts < 20}
            self.peers = active
            return active
    
    def stop(self):
        """Stop discovery."""
        self.running = False
