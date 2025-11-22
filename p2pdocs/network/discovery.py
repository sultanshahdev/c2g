"""
Peer Discovery Module - UDP broadcast for discovering peers on LAN
Phase 3: Peer Discovery
"""

import socket
import threading
import logging
import json
from typing import Dict, Callable, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISCOVERY_PORT = 5555
DISCOVERY_BROADCAST = "<broadcast>"  # Use <broadcast> token for proper broadcast


class PeerInfo:
    """Information about a discovered peer"""
    
    def __init__(self, username: str, host: str, port: int, last_seen: datetime = None):
        """
        Initialize peer information
        
        Args:
            username: Username of the peer
            host: IP address of the peer
            port: TCP port of the peer
            last_seen: Timestamp when peer was last seen
        """
        self.username = username
        self.host = host
        self.port = port
        self.last_seen = last_seen or datetime.now()
    
    def is_alive(self, timeout: int = 30) -> bool:
        """Check if peer is still considered alive"""
        elapsed = datetime.now() - self.last_seen
        return elapsed.total_seconds() < timeout
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "username": self.username,
            "host": self.host,
            "port": self.port,
            "last_seen": self.last_seen.isoformat()
        }
    
    def __repr__(self) -> str:
        return f"PeerInfo(username={self.username}, host={self.host}, port={self.port})"


class PeerRegistry:
    """Registry of discovered peers"""
    
    def __init__(self, timeout: int = 30):
        """
        Initialize peer registry
        
        Args:
            timeout: How long before peer is considered dead (seconds)
        """
        self.peers: Dict[str, PeerInfo] = {}
        self.lock = threading.Lock()
        self.timeout = timeout
        self.on_peer_added: Optional[Callable[[PeerInfo], None]] = None
        self.on_peer_removed: Optional[Callable[[str], None]] = None
    
    def add_peer(self, peer_info: PeerInfo):
        """Add or update a peer in the registry"""
        with self.lock:
            if peer_info.username not in self.peers:
                self.peers[peer_info.username] = peer_info
                if self.on_peer_added:
                    self.on_peer_added(peer_info)
                logger.info(f"Peer added: {peer_info}")
            else:
                # Update last seen time
                self.peers[peer_info.username].last_seen = datetime.now()
    
    def remove_peer(self, username: str):
        """Remove a peer from the registry"""
        with self.lock:
            if username in self.peers:
                del self.peers[username]
                if self.on_peer_removed:
                    self.on_peer_removed(username)
                logger.info(f"Peer removed: {username}")
    
    def get_peer(self, username: str) -> Optional[PeerInfo]:
        """Get information about a specific peer"""
        with self.lock:
            return self.peers.get(username)
    
    def get_all_peers(self) -> list:
        """Get list of all peers"""
        with self.lock:
            return list(self.peers.values())
    
    def get_alive_peers(self) -> list:
        """Get list of alive peers"""
        with self.lock:
            return [p for p in self.peers.values() if p.is_alive(self.timeout)]
    
    def cleanup_dead_peers(self) -> int:
        """Remove all dead peers, return count removed"""
        with self.lock:
            dead_peers = [p.username for p in self.peers.values() 
                         if not p.is_alive(self.timeout)]
            
            for username in dead_peers:
                del self.peers[username]
                if self.on_peer_removed:
                    self.on_peer_removed(username)
            
            if dead_peers:
                logger.info(f"Cleaned up {len(dead_peers)} dead peers")
            
            return len(dead_peers)
    
    def get_peer_count(self) -> int:
        """Get number of peers in registry"""
        with self.lock:
            return len(self.peers)


class PeerDiscovery:
    """Sends UDP announcements to discover other peers"""
    
    def __init__(self, username: str, port: int = 5000, discovery_port: int = DISCOVERY_PORT):
        """
        Initialize peer discovery
        
        Args:
            username: Username to announce
            port: TCP port where server is listening
            discovery_port: UDP port for discovery
        """
        self.username = username
        self.port = port
        self.discovery_port = discovery_port
        self.socket = None
        self.is_running = False
        self.discovery_thread = None
    
    def start(self, interval: int = 5):
        """
        Start announcing presence
        
        Args:
            interval: How often to broadcast (seconds)
        """
        if self.is_running:
            logger.warning("Discovery already running")
            return
        
        self.is_running = True
        # Daemon thread for graceful shutdown
        self.discovery_thread = threading.Thread(
            target=self._announce_loop,
            args=(interval,),
            daemon=True
        )
        self.discovery_thread.start()
        logger.info(f"Peer discovery started for {self.username}")
    
    def _announce_loop(self, interval: int):
        """Main announcement loop"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Try to set SO_REUSEPORT if on Linux
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                logger.debug("SO_REUSEPORT enabled for announcer")
            except (AttributeError, OSError):
                pass  # Not available on Windows, that's OK
            
            while self.is_running:
                try:
                    # Create announcement message
                    announcement = {
                        "type": "peer_announcement",
                        "username": self.username,
                        "port": self.port,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Broadcast announcement to all interfaces
                    message = json.dumps(announcement).encode('utf-8')
                    self.socket.sendto(message, ('<broadcast>', self.discovery_port))
                    logger.debug(f"Announced {self.username} on UDP {self.discovery_port}")
                
                except Exception as e:
                    logger.error(f"Error sending announcement: {str(e)}")
                
                # Wait before next announcement
                for _ in range(interval * 10):
                    if not self.is_running:
                        break
                    threading.Event().wait(0.1)
        
        except Exception as e:
            logger.error(f"Discovery announcer error: {str(e)}")
        
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
    
    def stop(self):
        """Stop announcing presence"""
        self.is_running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        logger.info(f"Peer discovery stopped for {self.username}")


class DiscoveryListener:
    """Listens for UDP announcements from other peers"""
    
    def __init__(self, username: str, registry: PeerRegistry, discovery_port: int = DISCOVERY_PORT):
        """
        Initialize discovery listener
        
        Args:
            username: Current user's username (to filter self-announcements)
            registry: PeerRegistry to add discovered peers to
            discovery_port: UDP port to listen on
        """
        self.username = username
        self.registry = registry
        self.discovery_port = discovery_port
        self.socket = None
        self.is_running = False
        self.listener_thread = None
    
    def start(self):
        """Start listening for announcements"""
        if self.is_running:
            logger.warning("Listener already running")
            return
        
        self.is_running = True
        # Daemon thread for graceful shutdown
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True
        )
        self.listener_thread.start()
        logger.info(f"Discovery listener started on UDP {self.discovery_port}")
    
    def _listen_loop(self):
        """Main listening loop"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Try to set SO_REUSEPORT if on Linux
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                logger.debug("SO_REUSEPORT enabled for listener")
            except (AttributeError, OSError):
                pass  # Not available on Windows, that's OK
            
            # Bind to all interfaces on the discovery port
            try:
                self.socket.bind(("0.0.0.0", self.discovery_port))
                logger.info(f"Listening on UDP 0.0.0.0:{self.discovery_port}")
            except OSError as e:
                logger.error(f"Failed to bind UDP port {self.discovery_port}: {e}")
                return
            
            self.socket.settimeout(5)
            
            while self.is_running:
                try:
                    data, addr = self.socket.recvfrom(1024)
                    
                    try:
                        announcement = json.loads(data.decode('utf-8'))
                        
                        if announcement.get("type") == "peer_announcement":
                            username = announcement.get("username")
                            port = announcement.get("port")
                            host = addr[0]
                            
                            # Skip self-announcements
                            if username == self.username:
                                logger.debug(f"Skipping self-announcement from {username}")
                                continue
                            
                            peer_info = PeerInfo(username, host, port)
                            self.registry.add_peer(peer_info)
                            logger.info(f"Discovered peer: {peer_info}")
                    
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Invalid announcement from {addr}: {str(e)}")
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        logger.error(f"Error receiving announcement: {str(e)}")
        
        except Exception as e:
            logger.error(f"Listener error: {str(e)}")
        
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
    
    def stop(self):
        """Stop listening for announcements"""
        self.is_running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        logger.info("Discovery listener stopped")


class DiscoveryManager:
    """Manages both discovery and listening"""
    
    def __init__(self, username: str, port: int = 5000, discovery_port: int = DISCOVERY_PORT):
        """
        Initialize discovery manager
        
        Args:
            username: Username for announcements
            port: TCP port of server
            discovery_port: UDP port for discovery
        """
        self.username = username
        self.port = port
        self.discovery_port = discovery_port
        
        self.registry = PeerRegistry()
        self.announcer = PeerDiscovery(username, port, discovery_port)
        self.listener = DiscoveryListener(username, self.registry, discovery_port)
        
        self.cleanup_thread = None
        self.is_running = False
    
    def start(self):
        """Start discovery (both announcing and listening)"""
        if self.is_running:
            logger.warning("Discovery manager already running")
            return
        
        self.is_running = True
        self.announcer.start(interval=5)
        self.listener.start()
        
        # Start cleanup thread (daemon thread for graceful shutdown)
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
        
        logger.info("Discovery manager started")
    
    def _cleanup_loop(self):
        """Periodically clean up dead peers"""
        while self.is_running:
            threading.Event().wait(10)
            if self.is_running:
                self.registry.cleanup_dead_peers()
    
    def stop(self):
        """Stop discovery"""
        self.is_running = False
        self.announcer.stop()
        self.listener.stop()
        # Join cleanup thread with timeout
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=2)
        logger.info("Discovery manager stopped")
    
    def get_peers(self) -> list:
        """Get list of alive peers"""
        return self.registry.get_alive_peers()
    
    def get_peer(self, username: str) -> Optional[PeerInfo]:
        """Get specific peer"""
        peer = self.registry.get_peer(username)
        if peer and peer.is_alive():
            return peer
        return None
