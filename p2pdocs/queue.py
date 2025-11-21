"""
Lock Queue Management Module
Phase 9: Fair distribution of edit locks using FIFO queue
"""

import threading
import time
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LockRequest:
    """Request to acquire a document lock"""
    doc_name: str
    username: str
    requested_at: float
    priority: int = 0  # Higher priority = goes sooner
    
    def __lt__(self, other):
        """Compare for priority queue (higher priority first)"""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.requested_at < other.requested_at  # Earlier request first


class LockRequestQueue:
    """Queue for managing lock requests"""
    
    def __init__(self):
        """Initialize lock request queue"""
        self.queues: Dict[str, List[LockRequest]] = {}  # One queue per document
        self.lock = threading.Lock()
    
    def enqueue(self, doc_name: str, username: str, priority: int = 0) -> int:
        """
        Add lock request to queue
        
        Args:
            doc_name: Document name
            username: Requesting user
            priority: Request priority (0=normal)
            
        Returns:
            Position in queue
        """
        with self.lock:
            if doc_name not in self.queues:
                self.queues[doc_name] = []
            
            request = LockRequest(doc_name, username, time.time(), priority)
            self.queues[doc_name].append(request)
            
            # Sort by priority and time
            self.queues[doc_name].sort()
            
            position = self.queues[doc_name].index(request) + 1
            logger.info(f"Lock request queued for {doc_name} by {username} at position {position}")
            
            return position
    
    def dequeue(self, doc_name: str) -> Optional[LockRequest]:
        """Remove first request from queue"""
        with self.lock:
            if doc_name in self.queues and self.queues[doc_name]:
                request = self.queues[doc_name].pop(0)
                logger.info(f"Lock request dequeued for {doc_name}: {request.username}")
                return request
        return None
    
    def peek(self, doc_name: str) -> Optional[LockRequest]:
        """View first request without removing"""
        with self.lock:
            if doc_name in self.queues and self.queues[doc_name]:
                return self.queues[doc_name][0]
        return None
    
    def remove_user_requests(self, doc_name: str, username: str) -> int:
        """Remove all requests from a user for a document"""
        with self.lock:
            if doc_name not in self.queues:
                return 0
            
            before = len(self.queues[doc_name])
            self.queues[doc_name] = [r for r in self.queues[doc_name] 
                                     if r.username != username]
            removed = before - len(self.queues[doc_name])
            
            if removed:
                logger.info(f"Removed {removed} requests from {username} for {doc_name}")
            
            return removed
    
    def get_queue_position(self, doc_name: str, username: str) -> Optional[int]:
        """Get position of user's request in queue"""
        with self.lock:
            if doc_name not in self.queues:
                return None
            
            for i, request in enumerate(self.queues[doc_name]):
                if request.username == username:
                    return i + 1
        return None
    
    def get_queue_length(self, doc_name: str) -> int:
        """Get length of queue for a document"""
        with self.lock:
            return len(self.queues.get(doc_name, []))
    
    def get_queue_for_document(self, doc_name: str) -> List[str]:
        """Get list of usernames in queue for a document"""
        with self.lock:
            if doc_name not in self.queues:
                return []
            return [r.username for r in self.queues[doc_name]]
    
    def clear_queue(self, doc_name: str):
        """Clear all requests for a document"""
        with self.lock:
            self.queues.pop(doc_name, None)


class FairLockManager:
    """Manages locks with fair FIFO queue distribution"""
    
    def __init__(self, default_lock_duration: int = 300):
        """
        Initialize fair lock manager
        
        Args:
            default_lock_duration: Lock duration in seconds
        """
        self.request_queue = LockRequestQueue()
        self.lock_holders: Dict[str, Tuple[str, float]] = {}  # doc_name -> (username, expiry_time)
        self.lock = threading.Lock()
        self.default_lock_duration = default_lock_duration
        self.cleanup_thread = None
        self.is_running = False
    
    def start(self):
        """Start the fair lock manager"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("Fair lock manager started")
    
    def stop(self):
        """Stop the fair lock manager"""
        self.is_running = False
    
    def _cleanup_loop(self):
        """Periodically clean up expired locks"""
        while self.is_running:
            self.cleanup_expired_locks()
            time.sleep(10)
    
    def request_lock(self, doc_name: str, username: str, 
                    priority: int = 0) -> Tuple[bool, str, int]:
        """
        Request a lock on a document
        
        Returns:
            Tuple (acquired, message, queue_position)
        """
        with self.lock:
            # Check if document is locked
            if doc_name in self.lock_holders:
                holder, expiry = self.lock_holders[doc_name]
                
                if time.time() < expiry:
                    # Lock is still active, add to queue
                    position = self.request_queue.enqueue(doc_name, username, priority)
                    msg = f"Lock held by {holder}, you are #{position} in queue"
                    logger.info(msg)
                    return False, msg, position
                else:
                    # Lock expired, release it
                    del self.lock_holders[doc_name]
            
            # Lock not held, acquire it
            expiry_time = time.time() + self.default_lock_duration
            self.lock_holders[doc_name] = (username, expiry_time)
            
            msg = f"Lock acquired for {doc_name}"
            logger.info(f"{msg} by {username}")
            
            return True, msg, 1
    
    def release_lock(self, doc_name: str, username: str) -> Tuple[bool, str]:
        """
        Release a lock and grant to next in queue
        
        Returns:
            Tuple (success, message)
        """
        with self.lock:
            if doc_name not in self.lock_holders:
                return False, f"No lock on {doc_name}"
            
            holder, _ = self.lock_holders[doc_name]
            
            if holder != username:
                return False, f"Lock owned by {holder}, not {username}"
            
            # Release lock
            del self.lock_holders[doc_name]
            logger.info(f"Lock released for {doc_name} by {username}")
            
            # Grant to next in queue
            next_request = self.request_queue.dequeue(doc_name)
            
            if next_request:
                expiry_time = time.time() + self.default_lock_duration
                self.lock_holders[doc_name] = (next_request.username, expiry_time)
                msg = f"Lock granted to {next_request.username}"
                logger.info(f"{msg} for {doc_name}")
                return True, msg
            
            return True, f"Lock released, no one in queue"
    
    def renew_lock(self, doc_name: str, username: str, 
                  duration: int = None) -> Tuple[bool, str]:
        """Renew an existing lock"""
        if duration is None:
            duration = self.default_lock_duration
        
        with self.lock:
            if doc_name not in self.lock_holders:
                return False, f"No lock on {doc_name}"
            
            holder, _ = self.lock_holders[doc_name]
            
            if holder != username:
                return False, f"Lock owned by {holder}, not {username}"
            
            expiry_time = time.time() + duration
            self.lock_holders[doc_name] = (username, expiry_time)
            
            remaining = int(expiry_time - time.time())
            msg = f"Lock renewed, {remaining}s remaining"
            logger.info(f"{msg} for {doc_name} by {username}")
            
            return True, msg
    
    def cancel_lock_request(self, doc_name: str, username: str) -> Tuple[bool, str]:
        """Cancel a pending lock request"""
        removed = self.request_queue.remove_user_requests(doc_name, username)
        
        if removed:
            msg = f"Cancelled {removed} lock request(s) for {doc_name}"
            logger.info(msg)
            return True, msg
        else:
            msg = f"No pending requests from {username} for {doc_name}"
            logger.info(msg)
            return False, msg
    
    def get_queue_status(self, doc_name: str) -> dict:
        """Get status of lock and queue for a document"""
        with self.lock:
            if doc_name in self.lock_holders:
                holder, expiry = self.lock_holders[doc_name]
                remaining = max(0, int(expiry - time.time()))
            else:
                holder = None
                remaining = 0
            
            queue = self.request_queue.get_queue_for_document(doc_name)
            queue_length = len(queue)
            
            return {
                "document": doc_name,
                "lock_holder": holder,
                "lock_remaining": remaining,
                "queue_length": queue_length,
                "queue": queue
            }
    
    def get_user_position(self, doc_name: str, username: str) -> Optional[int]:
        """Get user's position in lock queue"""
        position = self.request_queue.get_queue_position(doc_name, username)
        
        if position:
            logger.debug(f"{username} is #{position} for {doc_name}")
            return position
        
        return None
    
    def cleanup_expired_locks(self) -> int:
        """Remove expired locks"""
        with self.lock:
            current_time = time.time()
            expired = [doc for doc, (_, expiry) in self.lock_holders.items() 
                      if current_time > expiry]
            
            for doc_name in expired:
                del self.lock_holders[doc_name]
                logger.debug(f"Expired lock cleaned up for {doc_name}")
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired locks")
            
            return len(expired)
    
    def get_all_locks(self) -> list:
        """Get all active locks"""
        with self.lock:
            return [
                {
                    "document": doc,
                    "holder": holder,
                    "remaining": max(0, int(expiry - time.time()))
                }
                for doc, (holder, expiry) in self.lock_holders.items()
                if expiry > time.time()
            ]
    
    def get_user_locks(self, username: str) -> list:
        """Get all locks held by a user"""
        with self.lock:
            return [
                {
                    "document": doc,
                    "remaining": max(0, int(expiry - time.time()))
                }
                for doc, (holder, expiry) in self.lock_holders.items()
                if holder == username and expiry > time.time()
            ]
