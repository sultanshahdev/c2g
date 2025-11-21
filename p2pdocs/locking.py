"""
Distributed Lock Management Module
Phase 6: Distributed Lock System
"""

import threading
import time
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class LockStatus(Enum):
    """Status of a lock"""
    AVAILABLE = "available"
    LOCKED = "locked"
    PENDING = "pending"


class DocumentLock:
    """Represents a lock on a document"""
    
    def __init__(self, doc_name: str, owner: str, duration: int = 300):
        """
        Initialize document lock
        
        Args:
            doc_name: Name of document
            owner: Username who holds the lock
            duration: Lock duration in seconds
        """
        self.doc_name = doc_name
        self.owner = owner
        self.duration = duration
        self.acquired_at = datetime.now()
        self.expires_at = self.acquired_at + timedelta(seconds=duration)
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        return datetime.now() > self.expires_at
    
    def time_remaining(self) -> int:
        """Get time remaining on lock in seconds"""
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def renew(self, duration: int = None):
        """Renew the lock"""
        if duration is None:
            duration = self.duration
        self.acquired_at = datetime.now()
        self.expires_at = self.acquired_at + timedelta(seconds=duration)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "doc_name": self.doc_name,
            "owner": self.owner,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "duration": self.duration
        }


class LockManager:
    """Manages locks for multiple documents"""
    
    def __init__(self, default_duration: int = 300):
        """
        Initialize lock manager
        
        Args:
            default_duration: Default lock duration in seconds
        """
        self.locks: Dict[str, DocumentLock] = {}
        self.lock = threading.Lock()
        self.default_duration = default_duration
        self.cleanup_thread = None
        self.is_running = False
    
    def start(self):
        """Start the lock manager (cleanup thread)"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("Lock manager started")
    
    def stop(self):
        """Stop the lock manager"""
        self.is_running = False
    
    def _cleanup_loop(self):
        """Periodically clean up expired locks"""
        while self.is_running:
            self.cleanup_expired_locks()
            time.sleep(10)  # Check every 10 seconds
    
    def acquire_lock(self, doc_name: str, username: str, 
                    duration: int = None) -> Tuple[bool, str]:
        """
        Attempt to acquire a lock on a document
        
        Args:
            doc_name: Document to lock
            username: User requesting lock
            duration: Lock duration in seconds
            
        Returns:
            Tuple (success, message)
        """
        if duration is None:
            duration = self.default_duration
        
        with self.lock:
            # Check if document is already locked
            if doc_name in self.locks:
                existing_lock = self.locks[doc_name]
                
                if existing_lock.is_expired():
                    # Lock expired, acquire new lock
                    self.locks[doc_name] = DocumentLock(doc_name, username, duration)
                    logger.info(f"Lock acquired for {doc_name} by {username} (expired lock)")
                    return True, f"Lock acquired for {doc_name}"
                else:
                    # Lock still active
                    remaining = existing_lock.time_remaining()
                    msg = f"Document locked by {existing_lock.owner}, expires in {remaining}s"
                    logger.warning(f"{msg}")
                    return False, msg
            else:
                # Document not locked, acquire lock
                self.locks[doc_name] = DocumentLock(doc_name, username, duration)
                logger.info(f"Lock acquired for {doc_name} by {username}")
                return True, f"Lock acquired for {doc_name}"
    
    def release_lock(self, doc_name: str, username: str) -> Tuple[bool, str]:
        """
        Release a lock on a document
        
        Args:
            doc_name: Document to unlock
            username: User releasing lock
            
        Returns:
            Tuple (success, message)
        """
        with self.lock:
            if doc_name not in self.locks:
                return False, f"No lock on {doc_name}"
            
            lock = self.locks[doc_name]
            
            if lock.owner != username:
                return False, f"Lock owned by {lock.owner}, not {username}"
            
            del self.locks[doc_name]
            logger.info(f"Lock released for {doc_name} by {username}")
            return True, f"Lock released for {doc_name}"
    
    def renew_lock(self, doc_name: str, username: str, 
                  duration: int = None) -> Tuple[bool, str]:
        """
        Renew an existing lock
        
        Args:
            doc_name: Document to renew lock for
            username: User renewing lock
            duration: New lock duration
            
        Returns:
            Tuple (success, message)
        """
        with self.lock:
            if doc_name not in self.locks:
                return False, f"No lock on {doc_name}"
            
            lock = self.locks[doc_name]
            
            if lock.owner != username:
                return False, f"Lock owned by {lock.owner}, not {username}"
            
            lock.renew(duration or self.default_duration)
            remaining = lock.time_remaining()
            logger.info(f"Lock renewed for {doc_name} by {username}, {remaining}s remaining")
            return True, f"Lock renewed, {remaining}s remaining"
    
    def get_lock(self, doc_name: str) -> Optional[DocumentLock]:
        """Get lock information for a document"""
        with self.lock:
            lock = self.locks.get(doc_name)
            if lock and lock.is_expired():
                del self.locks[doc_name]
                return None
            return lock
    
    def is_locked(self, doc_name: str) -> bool:
        """Check if document is locked"""
        lock = self.get_lock(doc_name)
        return lock is not None
    
    def get_lock_owner(self, doc_name: str) -> Optional[str]:
        """Get username of lock owner"""
        lock = self.get_lock(doc_name)
        return lock.owner if lock else None
    
    def get_lock_status(self, doc_name: str) -> dict:
        """Get detailed lock status"""
        lock = self.get_lock(doc_name)
        
        if not lock:
            return {
                "status": LockStatus.AVAILABLE.value,
                "doc_name": doc_name,
                "owner": None,
                "remaining": 0
            }
        
        return {
            "status": LockStatus.LOCKED.value,
            "doc_name": doc_name,
            "owner": lock.owner,
            "remaining": lock.time_remaining(),
            "acquired_at": lock.acquired_at.isoformat(),
            "expires_at": lock.expires_at.isoformat()
        }
    
    def get_all_locks(self) -> list:
        """Get list of all active locks"""
        with self.lock:
            active_locks = []
            for doc_name, lock in list(self.locks.items()):
                if not lock.is_expired():
                    active_locks.append(lock.to_dict())
            return active_locks
    
    def cleanup_expired_locks(self) -> int:
        """Remove all expired locks"""
        with self.lock:
            expired_docs = [doc for doc, lock in self.locks.items() 
                          if lock.is_expired()]
            
            for doc in expired_docs:
                lock = self.locks.pop(doc)
                logger.debug(f"Expired lock cleaned up for {doc} (owner: {lock.owner})")
            
            if expired_docs:
                logger.info(f"Cleaned up {len(expired_docs)} expired locks")
            
            return len(expired_docs)
    
    def force_release_lock(self, doc_name: str) -> bool:
        """Force release a lock (admin operation)"""
        with self.lock:
            if doc_name in self.locks:
                lock = self.locks.pop(doc_name)
                logger.warning(f"Lock forcefully released for {doc_name} (was owned by {lock.owner})")
                return True
            return False
    
    def get_user_locks(self, username: str) -> list:
        """Get all locks held by a user"""
        with self.lock:
            user_locks = [lock.to_dict() for lock in self.locks.values() 
                         if lock.owner == username and not lock.is_expired()]
            return user_locks
