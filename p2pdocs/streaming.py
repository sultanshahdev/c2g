"""
Real-time Keystroke Streaming Module
Phase 7: Real-time keystroke synchronization (5-10ms latency target)
"""

import threading
import time
import logging
from typing import Callable, Optional, Dict, List
from queue import Queue, Empty
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Keystroke:
    """Represents a single keystroke event"""
    char: str              # Character typed (or special key name)
    position: int         # Position in document
    timestamp: float      # Timestamp when keystroke occurred
    user: str            # Username of typer
    doc_name: str        # Document name
    
    def __lt__(self, other):
        """For sorting by timestamp"""
        return self.timestamp < other.timestamp


class KeystrokeBuffer:
    """Buffer for managing keystroke events"""
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize keystroke buffer
        
        Args:
            max_size: Maximum keystrokes to buffer
        """
        self.buffer: List[Keystroke] = []
        self.max_size = max_size
        self.lock = threading.Lock()
    
    def add_keystroke(self, keystroke: Keystroke):
        """Add keystroke to buffer"""
        with self.lock:
            self.buffer.append(keystroke)
            # Maintain max size
            if len(self.buffer) > self.max_size:
                self.buffer = self.buffer[-self.max_size:]
    
    def get_keystrokes(self, from_time: float = 0) -> List[Keystroke]:
        """Get keystrokes after a certain time"""
        with self.lock:
            return [k for k in self.buffer if k.timestamp >= from_time]
    
    def clear(self):
        """Clear buffer"""
        with self.lock:
            self.buffer.clear()
    
    def size(self) -> int:
        """Get current buffer size"""
        with self.lock:
            return len(self.buffer)


class KeystrokeStreamer:
    """Streams keystrokes to connected peers in real-time"""
    
    def __init__(self, username: str, doc_name: str, 
                 send_callback: Callable[[Keystroke], None]):
        """
        Initialize keystroke streamer
        
        Args:
            username: Username of this peer
            doc_name: Document being edited
            send_callback: Callback to send keystroke to peers
        """
        self.username = username
        self.doc_name = doc_name
        self.send_callback = send_callback
        
        self.keystroke_queue = Queue()
        self.is_running = False
        self.sender_thread = None
        self.last_keystroke_time = time.time()
        
        # Performance tracking
        self.keystroke_count = 0
        self.total_latency = 0
    
    def start(self):
        """Start the keystroke streamer"""
        if self.is_running:
            logger.warning("Keystroke streamer already running")
            return
        
        self.is_running = True
        self.sender_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.sender_thread.start()
        logger.info(f"Keystroke streamer started for {self.doc_name}")
    
    def stop(self):
        """Stop the keystroke streamer"""
        self.is_running = False
    
    def _send_loop(self):
        """Main send loop - processes keystrokes with minimal latency"""
        while self.is_running:
            try:
                # Wait up to 10ms for keystroke
                keystroke = self.keystroke_queue.get(timeout=0.01)
                
                # Send immediately
                self.send_callback(keystroke)
                
                # Track latency
                latency = (time.time() - keystroke.timestamp) * 1000  # Convert to ms
                self.total_latency += latency
                self.keystroke_count += 1
                
                if latency > 10:
                    logger.warning(f"High latency keystroke: {latency:.2f}ms")
            
            except Empty:
                # No keystroke, continue
                continue
            except Exception as e:
                logger.error(f"Error in send loop: {str(e)}")
    
    def queue_keystroke(self, char: str, position: int):
        """
        Queue a keystroke for streaming
        
        Args:
            char: Character typed
            position: Position in document
        """
        keystroke = Keystroke(
            char=char,
            position=position,
            timestamp=time.time(),
            user=self.username,
            doc_name=self.doc_name
        )
        
        self.keystroke_queue.put(keystroke)
    
    def get_average_latency(self) -> float:
        """Get average keystroke latency in milliseconds"""
        if self.keystroke_count == 0:
            return 0
        return self.total_latency / self.keystroke_count
    
    def get_stats(self) -> dict:
        """Get streaming statistics"""
        return {
            "username": self.username,
            "doc_name": self.doc_name,
            "keystrokes_sent": self.keystroke_count,
            "average_latency_ms": self.get_average_latency(),
            "queue_size": self.keystroke_queue.qsize()
        }


class KeystrokeReceiver:
    """Receives and applies keystrokes in real-time"""
    
    def __init__(self, username: str, apply_callback: Optional[Callable] = None):
        """
        Initialize keystroke receiver
        
        Args:
            username: Username of this peer
            apply_callback: Callback to apply keystroke to document
        """
        self.username = username
        self.apply_callback = apply_callback
        
        self.keystroke_buffer = KeystrokeBuffer()
        self.is_running = False
        self.processor_thread = None
        
        # Performance tracking
        self.keystrokes_received = 0
        self.keystrokes_applied = 0
    
    def start(self):
        """Start the keystroke receiver"""
        if self.is_running:
            logger.warning("Keystroke receiver already running")
            return
        
        self.is_running = True
        self.processor_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.processor_thread.start()
        logger.info(f"Keystroke receiver started")
    
    def stop(self):
        """Stop the keystroke receiver"""
        self.is_running = False
    
    def _process_loop(self):
        """Main process loop - applies received keystrokes"""
        while self.is_running:
            try:
                # Process buffered keystrokes
                keystrokes = self.keystroke_buffer.get_keystrokes()
                
                for keystroke in keystrokes:
                    if self.apply_callback:
                        self.apply_callback(keystroke)
                    self.keystrokes_applied += 1
                
                # Sleep briefly to avoid busy waiting
                time.sleep(0.001)  # 1ms
            
            except Exception as e:
                logger.error(f"Error in process loop: {str(e)}")
    
    def receive_keystroke(self, keystroke: Keystroke):
        """
        Receive a keystroke from a peer
        
        Args:
            keystroke: Keystroke object to apply
        """
        self.keystroke_buffer.add_keystroke(keystroke)
        self.keystrokes_received += 1
        logger.debug(f"Received keystroke from {keystroke.user}: '{keystroke.char}'")
    
    def get_stats(self) -> dict:
        """Get receiver statistics"""
        return {
            "username": self.username,
            "keystrokes_received": self.keystrokes_received,
            "keystrokes_applied": self.keystrokes_applied,
            "buffer_size": self.keystroke_buffer.size()
        }


class KeystrokeSync:
    """Coordinates keystroke streaming between peers"""
    
    def __init__(self, username: str, doc_name: str):
        """
        Initialize keystroke synchronization
        
        Args:
            username: Username of this peer
            doc_name: Document being edited
        """
        self.username = username
        self.doc_name = doc_name
        
        self.streamer: Optional[KeystrokeStreamer] = None
        self.receivers: Dict[str, KeystrokeReceiver] = {}
        self.lock = threading.Lock()
    
    def create_streamer(self, send_callback: Callable) -> KeystrokeStreamer:
        """Create keystroke streamer"""
        self.streamer = KeystrokeStreamer(self.username, self.doc_name, send_callback)
        self.streamer.start()
        return self.streamer
    
    def create_receiver(self, peer_username: str, 
                       apply_callback: Optional[Callable] = None) -> KeystrokeReceiver:
        """Create keystroke receiver for a peer"""
        with self.lock:
            if peer_username not in self.receivers:
                receiver = KeystrokeReceiver(peer_username, apply_callback)
                receiver.start()
                self.receivers[peer_username] = receiver
            return self.receivers[peer_username]
    
    def receive_keystroke_from_peer(self, peer_username: str, keystroke: Keystroke):
        """Receive keystroke from a peer"""
        with self.lock:
            if peer_username not in self.receivers:
                logger.warning(f"Receiver for {peer_username} not found")
                return
            
            self.receivers[peer_username].receive_keystroke(keystroke)
    
    def get_all_stats(self) -> dict:
        """Get statistics from all streamers/receivers"""
        stats = {
            "document": self.doc_name,
            "username": self.username
        }
        
        if self.streamer:
            stats["streaming"] = self.streamer.get_stats()
        
        with self.lock:
            stats["receiving"] = {
                peer: receiver.get_stats() 
                for peer, receiver in self.receivers.items()
            }
        
        return stats
    
    def stop_all(self):
        """Stop all streamers and receivers"""
        if self.streamer:
            self.streamer.stop()
        
        with self.lock:
            for receiver in self.receivers.values():
                receiver.stop()
            self.receivers.clear()
