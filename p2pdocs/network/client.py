"""
P2P Client Module - Connects to and communicates with peers
Phase 2: TCP Socket Communication - Client side
"""

import socket
import threading
import logging
import time
from typing import Callable, Dict, Optional
from queue import Queue, Empty
from .protocol import Message, MessageType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class P2PClient:
    """P2P Client that connects to peer servers"""
    
    def __init__(self, username: str = "unknown", timeout: int = 10):
        """
        Initialize P2P Client
        
        Args:
            username: Username of this peer
            timeout: Socket timeout in seconds
        """
        self.username = username
        self.timeout = timeout
        self.connections: Dict[str, socket.socket] = {}
        self.conn_lock = threading.Lock()
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.outgoing_queue = Queue()
        self.message_threads = {}
        self.is_running = False
        self.sender_thread = None
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a message handler for a specific message type"""
        self.message_handlers[msg_type] = handler
        logger.info(f"Registered handler for {msg_type.value}")
    
    def connect_to_peer(self, peer_host: str, peer_port: int, peer_username: str) -> bool:
        """
        Connect to a peer server
        
        Args:
            peer_host: Host/IP of peer
            peer_port: Port of peer
            peer_username: Username of peer
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.settimeout(self.timeout)
            peer_socket.connect((peer_host, peer_port))
            
            # Send announcement
            announce_msg = Message(
                msg_type=MessageType.PEER_ANNOUNCE,
                sender=self.username,
                recipient="*",
                payload={"username": self.username, "peer_username": peer_username}
            )
            peer_socket.sendall(announce_msg.to_json().encode('utf-8'))
            
            # Store connection
            with self.conn_lock:
                self.connections[peer_username] = peer_socket
            
            # Start listener thread
            listener_thread = threading.Thread(
                target=self._listen_to_peer,
                args=(peer_socket, peer_username),
                daemon=True
            )
            listener_thread.start()
            self.message_threads[peer_username] = listener_thread
            
            logger.info(f"Connected to {peer_username} at {peer_host}:{peer_port}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to connect to {peer_username}: {str(e)}")
            return False
    
    def _listen_to_peer(self, peer_socket: socket.socket, peer_username: str):
        """Listen for messages from a specific peer"""
        try:
            while self.is_running:
                try:
                    data = peer_socket.recv(4096)
                    if not data:
                        logger.info(f"Connection closed by {peer_username}")
                        break
                    
                    try:
                        msg = Message.from_json(data.decode('utf-8'))
                        logger.debug(f"Received from {peer_username}: {msg.msg_type.value}")
                        
                        # Route to handler
                        if msg.msg_type in self.message_handlers:
                            self.message_handlers[msg.msg_type](msg)
                    
                    except ValueError as e:
                        logger.warning(f"Invalid message from {peer_username}: {str(e)}")
                
                except socket.timeout:
                    # Timeout is normal, continue listening
                    continue
                except Exception as e:
                    logger.error(f"Error receiving from {peer_username}: {str(e)}")
                    break
        
        finally:
            # Cleanup
            with self.conn_lock:
                self.connections.pop(peer_username, None)
            try:
                peer_socket.close()
            except:
                pass
            logger.info(f"Listener for {peer_username} stopped")
    
    def send_message(self, peer_username: str, message: Message) -> bool:
        """Send a message to a specific peer"""
        with self.conn_lock:
            if peer_username not in self.connections:
                logger.warning(f"Not connected to {peer_username}")
                return False
            peer_socket = self.connections[peer_username]
        
        try:
            peer_socket.sendall(message.to_json().encode('utf-8'))
            logger.debug(f"Sent to {peer_username}: {message.msg_type.value}")
            return True
        except Exception as e:
            logger.error(f"Error sending to {peer_username}: {str(e)}")
            with self.conn_lock:
                self.connections.pop(peer_username, None)
            return False
    
    def broadcast_message(self, message: Message) -> int:
        """Send a message to all connected peers"""
        sent_count = 0
        
        with self.conn_lock:
            for peer_username in list(self.connections.keys()):
                if self.send_message(peer_username, message):
                    sent_count += 1
        
        return sent_count
    
    def get_connected_peers(self) -> list:
        """Get list of connected peer names"""
        with self.conn_lock:
            return list(self.connections.keys())
    
    def start(self):
        """Start the client (heartbeat sender)"""
        if self.is_running:
            logger.warning("Client already running")
            return
        
        self.is_running = True
        logger.info("Client started")
    
    def stop(self):
        """Stop the client"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Close all connections
        with self.conn_lock:
            for peer_socket in self.connections.values():
                try:
                    peer_socket.close()
                except:
                    pass
            self.connections.clear()
        
        logger.info("Client stopped")
    
    def is_connected_to(self, peer_username: str) -> bool:
        """Check if connected to a specific peer"""
        with self.conn_lock:
            return peer_username in self.connections
