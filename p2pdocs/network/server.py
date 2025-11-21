"""
P2P Server Module - Accepts and handles peer connections
Phase 2: TCP Socket Communication - Server side
"""

import socket
import threading
import logging
from typing import Callable, Dict, Optional
from queue import Queue
from .protocol import Message, MessageType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class P2PServer:
    """P2P Server that listens for incoming connections"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5000, username: str = "unknown"):
        """
        Initialize P2P Server
        
        Args:
            host: Host to bind to (0.0.0.0 for all interfaces)
            port: Port to listen on (default: 5000)
            username: Username of this peer
        """
        self.host = host
        self.port = port
        self.username = username
        self.socket = None
        self.is_running = False
        self.connected_peers: Dict[str, socket.socket] = {}
        self.peer_lock = threading.Lock()
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.server_thread = None
        self.client_threads = {}
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a message handler for a specific message type"""
        self.message_handlers[msg_type] = handler
        logger.info(f"Registered handler for {msg_type.value}")
    
    def start(self):
        """Start the server in a background thread"""
        if self.is_running:
            logger.warning("Server already running")
            return
        
        self.server_thread = threading.Thread(target=self._run, daemon=True)
        self.server_thread.start()
        logger.info(f"Server started on {self.host}:{self.port}")
    
    def _run(self):
        """Main server loop (runs in background thread)"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.is_running = True
            
            logger.info(f"Server listening on {self.host}:{self.port}")
            
            while self.is_running:
                try:
                    # Accept incoming connection
                    client_socket, client_addr = self.socket.accept()
                    logger.info(f"New connection from {client_addr}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_addr),
                        daemon=True
                    )
                    client_thread.start()
                    self.client_threads[str(client_addr)] = client_thread
                
                except Exception as e:
                    if self.is_running:
                        logger.error(f"Error accepting connection: {str(e)}")
        
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
        
        finally:
            self.stop()
    
    def _handle_client(self, client_socket: socket.socket, client_addr: tuple):
        """Handle a single client connection"""
        peer_name = None
        
        try:
            # Receive peer announcement first
            data = client_socket.recv(4096)
            if not data:
                logger.warning(f"Connection from {client_addr} closed immediately")
                return
            
            try:
                msg = Message.from_json(data.decode('utf-8'))
                
                if msg.msg_type == MessageType.PEER_ANNOUNCE:
                    peer_name = msg.payload.get("username", "unknown")
                    logger.info(f"Peer {peer_name} announced from {client_addr}")
                    
                    # Store the peer connection
                    with self.peer_lock:
                        self.connected_peers[peer_name] = client_socket
                    
                    # Call handler if registered
                    if MessageType.PEER_ANNOUNCE in self.message_handlers:
                        self.message_handlers[MessageType.PEER_ANNOUNCE](msg)
                
                # Keep connection alive for incoming messages
                while self.is_running and peer_name:
                    try:
                        data = client_socket.recv(4096)
                        if not data:
                            logger.info(f"Peer {peer_name} disconnected")
                            break
                        
                        msg = Message.from_json(data.decode('utf-8'))
                        logger.debug(f"Received from {peer_name}: {msg.msg_type.value}")
                        
                        # Route to appropriate handler
                        if msg.msg_type in self.message_handlers:
                            self.message_handlers[msg.msg_type](msg)
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON from {peer_name}: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error handling message from {peer_name}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error parsing initial message: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error handling client: {str(e)}")
        
        finally:
            # Cleanup
            if peer_name:
                with self.peer_lock:
                    self.connected_peers.pop(peer_name, None)
                logger.info(f"Peer {peer_name} removed from registry")
            
            try:
                client_socket.close()
            except:
                pass
    
    def send_to_peer(self, peer_name: str, message: Message) -> bool:
        """Send a message to a specific peer"""
        with self.peer_lock:
            if peer_name not in self.connected_peers:
                logger.warning(f"Peer {peer_name} not connected")
                return False
            
            peer_socket = self.connected_peers[peer_name]
        
        try:
            peer_socket.sendall(message.to_json().encode('utf-8'))
            logger.debug(f"Sent to {peer_name}: {message.msg_type.value}")
            return True
        except Exception as e:
            logger.error(f"Error sending to {peer_name}: {str(e)}")
            # Remove dead peer
            with self.peer_lock:
                self.connected_peers.pop(peer_name, None)
            return False
    
    def broadcast_message(self, message: Message, exclude_sender: bool = True) -> int:
        """Broadcast a message to all connected peers"""
        sent_count = 0
        
        with self.peer_lock:
            for peer_name in list(self.connected_peers.keys()):
                if exclude_sender and peer_name == message.sender:
                    continue
                
                if self.send_to_peer(peer_name, message):
                    sent_count += 1
        
        return sent_count
    
    def get_connected_peers(self) -> list:
        """Get list of connected peer names"""
        with self.peer_lock:
            return list(self.connected_peers.keys())
    
    def stop(self):
        """Stop the server"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Close all peer connections
        with self.peer_lock:
            for peer_socket in self.connected_peers.values():
                try:
                    peer_socket.close()
                except:
                    pass
            self.connected_peers.clear()
        
        # Close server socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        logger.info("Server stopped")


import json
