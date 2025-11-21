"""
Network Manager - Integrates P2P discovery and document sharing
Handles peer communication, document distribution, and real-time sync
"""

import threading
import json
import logging
from typing import Dict, Callable, Optional, List
from pathlib import Path
from .network.discovery import DiscoveryManager, PeerInfo
from .network.client import P2PClient
from .network.server import P2PServer
from .network.protocol import Message, MessageType
from .storage import StorageManager

logger = logging.getLogger(__name__)


class NetworkManager:
    """Manages network operations and P2P communication"""
    
    def __init__(self, username: str, tcp_port: int = 5000, config_dir: str = None):
        """
        Initialize network manager
        
        Args:
            username: Current user's username
            tcp_port: TCP port for server
            config_dir: Configuration directory
        """
        self.username = username
        self.tcp_port = tcp_port
        self.config_dir = config_dir or str(Path.home() / ".p2pdocs")
        
        # Initialize components
        self.storage = StorageManager(self.config_dir)
        self.discovery_manager = DiscoveryManager(username, tcp_port)
        self.server = P2PServer(host="0.0.0.0", port=tcp_port, username=username)
        self.client = P2PClient(username=username)
        
        # State tracking
        self.connected_peers: Dict[str, PeerInfo] = {}
        self.shared_documents: Dict[str, List[str]] = {}  # doc_name -> [users editing]
        self.callbacks: Dict[str, Callable] = {}
        
        # Register message handlers
        self._register_handlers()
        
        logger.info(f"NetworkManager initialized for {username}")
    
    def _register_handlers(self):
        """Register message handlers for different message types"""
        
        # Update notification handler
        def handle_update_notification(message):
            doc_name = message.document
            content = message.payload.get("content") if message.payload else None
            sender = message.sender
            
            if content:
                # Update local storage
                self.storage.update_document(doc_name, content)
            
            # Notify callback
            if "on_document_updated" in self.callbacks:
                self.callbacks["on_document_updated"](doc_name, sender)
            
            logger.info(f"Document '{doc_name}' updated by {sender}")
        
        # Sync response handler (document creation)
        def handle_sync_response(message):
            doc_name = message.document
            content = message.payload.get("content") if message.payload else None
            owner = message.payload.get("owner") if message.payload else message.sender
            
            if content:
                # Create document locally if doesn't exist
                existing_docs = self.storage.list_documents()
                if doc_name not in existing_docs:
                    self.storage.create_document(doc_name, owner, content)
            
            # Notify callback
            if "on_document_created" in self.callbacks:
                self.callbacks["on_document_created"](doc_name, owner)
            
            logger.info(f"Document '{doc_name}' received from {owner}")
        
        # Peer announced handler
        def handle_peer_announce(message):
            peer_username = message.sender
            
            if "on_peer_joined" in self.callbacks:
                self.callbacks["on_peer_joined"](peer_username)
            
            logger.info(f"Peer {peer_username} announced")
        
        # Register handlers with server
        self.server.register_handler(MessageType.UPDATE_NOTIFICATION, handle_update_notification)
        self.server.register_handler(MessageType.SYNC_RESPONSE, handle_sync_response)
        self.server.register_handler(MessageType.PEER_ANNOUNCE, handle_peer_announce)
    
    def start(self):
        """Start network discovery and server"""
        logger.info("Starting network manager...")
        
        # Start TCP server
        self.server.start()
        
        # Start UDP discovery
        self.discovery_manager.start()
        
        # Start connection monitor thread
        threading.Thread(target=self._monitor_peers, daemon=True).start()
        
        logger.info(f"Network manager started on port {self.tcp_port}")
    
    def stop(self):
        """Stop network manager"""
        logger.info("Stopping network manager...")
        self.discovery_manager.stop()
        self.server.stop()
        self.client.stop()
        logger.info("Network manager stopped")
    
    def _monitor_peers(self):
        """Monitor peers and connect to new ones"""
        while True:
            try:
                # Get alive peers from discovery
                alive_peers = self.discovery_manager.get_peers()
                
                for peer in alive_peers:
                    # Skip self
                    if peer.username == self.username:
                        continue
                    
                    # Connect to new peers
                    if peer.username not in self.connected_peers:
                        self._connect_to_peer(peer)
                
                # Remove disconnected peers
                for username in list(self.connected_peers.keys()):
                    if not self.discovery_manager.get_peer(username):
                        del self.connected_peers[username]
                        logger.info(f"Peer {username} disconnected")
                
                threading.Event().wait(5)  # Check every 5 seconds
            
            except Exception as e:
                logger.error(f"Error monitoring peers: {str(e)}")
                threading.Event().wait(5)
    
    def _connect_to_peer(self, peer: PeerInfo):
        """Connect to a peer"""
        try:
            success = self.client.connect_to_peer(
                peer_host=peer.host,
                peer_port=peer.port,
                peer_username=peer.username
            )
            
            if success:
                self.connected_peers[peer.username] = peer
                logger.info(f"Connected to peer {peer.username} at {peer.host}:{peer.port}")
            else:
                logger.warning(f"Failed to connect to peer {peer.username}")
        
        except Exception as e:
            logger.error(f"Error connecting to peer {peer.username}: {str(e)}")
    
    def register_callback(self, event_name: str, callback: Callable):
        """Register callback for network events"""
        self.callbacks[event_name] = callback
        logger.info(f"Registered callback for {event_name}")
    
    def broadcast_document_update(self, doc_name: str, content: str):
        """Broadcast document update to all peers"""
        message = Message(
            msg_type=MessageType.UPDATE_NOTIFICATION,
            sender=self.username,
            recipient="*",
            document=doc_name,
            payload={
                "content": content
            }
        )
        
        for peer_username in self.connected_peers.keys():
            try:
                self.client.send_message(peer_username, message)
            except Exception as e:
                logger.error(f"Error sending update to {peer_username}: {str(e)}")
    
    def broadcast_document_created(self, doc_name: str, content: str):
        """Broadcast new document to all peers"""
        message = Message(
            msg_type=MessageType.SYNC_RESPONSE,
            sender=self.username,
            recipient="*",
            document=doc_name,
            payload={
                "content": content,
                "owner": self.username
            }
        )
        
        for peer_username in self.connected_peers.keys():
            try:
                self.client.send_message(peer_username, message)
            except Exception as e:
                logger.error(f"Error broadcasting document to {peer_username}: {str(e)}")
    
    def get_connected_peers(self) -> List[PeerInfo]:
        """Get list of connected peers"""
        return list(self.connected_peers.values())
    
    def get_discovered_peers(self) -> List[PeerInfo]:
        """Get list of discovered peers on LAN"""
        peers = self.discovery_manager.get_peers()
        return [p for p in peers if p.username != self.username]
    
    def get_peer_connection_status(self) -> Dict[str, bool]:
        """Get connection status for all peers"""
        status = {}
        
        for peer in self.get_discovered_peers():
            status[peer.username] = peer.username in self.connected_peers
        
        return status
    
    def get_status(self) -> dict:
        """Get network status"""
        return {
            "username": self.username,
            "tcp_port": self.tcp_port,
            "discovered_peers": len(self.get_discovered_peers()),
            "connected_peers": len(self.connected_peers),
            "peers": [
                {
                    "username": p.username,
                    "host": p.host,
                    "port": p.port,
                    "connected": p.username in self.connected_peers
                }
                for p in self.get_discovered_peers()
            ]
        }
