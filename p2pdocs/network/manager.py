"""
P2P network manager for peer connections.
"""

import socket
import threading
from typing import Dict, Callable, Optional, Tuple

from ..crdt.message import CRDTMessage


class NetworkManager:
    """True P2P networking - both peers are equal."""
    
    def __init__(self, username: str, port: int = 5000):
        self.username = username
        self.port = port
        self.peers = {}  # {peer_id: (conn, username, is_outgoing)}
        self.server_socket = None
        self._recv_buffers = {}  # {peer_id: buffer}
        self.running = True
        self.on_message: Optional[Callable[[CRDTMessage], None]] = None
        self.peers_lock = threading.RLock()
    
    def start_listening(self) -> bool:
        """Start listening for incoming connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(5)
            
            print(f"[{self.username}] Listening on port {self.port}...")
            threading.Thread(target=self._accept_peers, daemon=True).start()
            return True
        except Exception as e:
            print(f"[{self.username}] Listen error: {e}")
            return False
    
    def connect_to_peer(self, peer_ip: str, peer_port: int = 5000) -> bool:
        """Connect to another peer."""
        try:
            # Check if already connected to this peer (use listening port as canonical ID)
            canonical_peer_id = f"{peer_ip}:{peer_port}"
            with self.peers_lock:
                if canonical_peer_id in self.peers:
                    print(f"[{self.username}] Already connected to {canonical_peer_id}")
                    return True
            
            print(f"[{self.username}] Connecting to {peer_ip}:{peer_port}...")
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(5)
            conn.connect((peer_ip, peer_port))
            conn.settimeout(None)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Enable TCP keepalive to detect silent disconnections
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)  # Start after 60s idle
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Interval 10s
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)  # 3 probes
            
            # Exchange usernames
            conn.sendall(f"{self.username}\n".encode('utf-8'))
            peer_username = conn.recv(1024).decode('utf-8').strip()
            
            # Use canonical peer_id (remote's listening port, not ephemeral port)
            peer_id = canonical_peer_id
            with self.peers_lock:
                self.peers[peer_id] = (conn, peer_username, True)
                self._recv_buffers[peer_id] = b""
            
            print(f"[{self.username}] Connected to {peer_username} at {peer_id}")
            threading.Thread(target=self._handle_peer, args=(peer_id, conn), daemon=True).start()
            return True
        except Exception as e:
            print(f"[{self.username}] Connect error: {e}")
            return False
    
    def _accept_peers(self):
        """Accept incoming connections."""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                # Enable TCP keepalive
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if hasattr(socket, 'TCP_KEEPIDLE'):
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                
                peer_username = conn.recv(1024).decode('utf-8').strip()
                conn.sendall(f"{self.username}\n".encode('utf-8'))
                
                # Use canonical peer_id format: remote_ip:DEFAULT_PORT (assume 5000)
                # This matches the format used by connect_to_peer
                canonical_peer_id = f"{addr[0]}:{self.port}"
                
                # Check for duplicate connection (if we already connected to them)
                with self.peers_lock:
                    if canonical_peer_id in self.peers:
                        print(f"[{self.username}] Duplicate connection from {peer_username}, closing new one")
                        conn.close()
                        continue
                    
                    self.peers[canonical_peer_id] = (conn, peer_username, False)
                    self._recv_buffers[canonical_peer_id] = b""
                
                print(f"[{self.username}] Peer {peer_username} connected from {addr[0]}")
                threading.Thread(target=self._handle_peer, args=(canonical_peer_id, conn), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"[{self.username}] Accept error: {e}")
    
    def _handle_peer(self, peer_id: str, conn: socket.socket):
        """Handle peer connection."""
        try:
            while self.running:
                chunk = conn.recv(4096)
                if not chunk:
                    print(f"[{self.username}] Peer {peer_id} disconnected")
                    break
                
                self._recv_buffers[peer_id] += chunk
                
                while len(self._recv_buffers[peer_id]) >= 4:
                    length = int.from_bytes(self._recv_buffers[peer_id][:4], 'big')
                    if length > 10_000_000:
                        print(f"[{self.username}] Message too large ({length} bytes) from {peer_id}, closing connection")
                        raise ValueError(f"Message size {length} exceeds 10MB limit")
                    
                    if len(self._recv_buffers[peer_id]) < 4 + length:
                        break
                    
                    msg_bytes = self._recv_buffers[peer_id][4:4+length]
                    self._recv_buffers[peer_id] = self._recv_buffers[peer_id][4+length:]
                    
                    try:
                        msg = CRDTMessage.from_json(msg_bytes.decode('utf-8'))
                        print(f"[{self.username}] Received {msg.msg_type} from {peer_id}")
                        if self.on_message:
                            self.on_message(msg)
                    except Exception as e:
                        print(f"[{self.username}] Parse error: {e}")
        except Exception as e:
            print(f"[{self.username}] Peer error: {e}")
        finally:
            with self.peers_lock:
                if peer_id in self.peers:
                    del self.peers[peer_id]
                    if peer_id in self._recv_buffers:
                        del self._recv_buffers[peer_id]
            try:
                conn.close()
            except:
                pass
    
    def broadcast_message(self, msg: CRDTMessage):
        """Broadcast to all connected peers."""
        json_str = msg.to_json()
        json_bytes = json_str.encode('utf-8')
        length = len(json_bytes)
        packet = length.to_bytes(4, 'big') + json_bytes
        
        dead_peers = []
        with self.peers_lock:
            for peer_id, (conn, _, _) in list(self.peers.items()):
                try:
                    conn.sendall(packet)
                except Exception as e:
                    print(f"[{self.username}] Broadcast error to {peer_id}: {e} - marking for removal")
                    dead_peers.append(peer_id)
        
        # Remove dead peers outside of iteration
        if dead_peers:
            with self.peers_lock:
                for peer_id in dead_peers:
                    if peer_id in self.peers:
                        try:
                            self.peers[peer_id][0].close()
                        except:
                            pass
                        del self.peers[peer_id]
                        if peer_id in self._recv_buffers:
                            del self._recv_buffers[peer_id]
                        print(f"[{self.username}] Removed dead peer {peer_id}")
    
    def close(self):
        """Close all connections."""
        self.running = False
        with self.peers_lock:
            for peer_id, (conn, _, _) in list(self.peers.items()):
                try:
                    conn.close()
                except:
                    pass
            self.peers.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
