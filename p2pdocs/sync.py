"""
Synchronization and Offline Queue Module
Phase 8: Synchronization protocol with offline support
"""

import json
import threading
import time
import logging
from typing import Optional, List, Dict, Callable
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class QueuedUpdate:
    """An update queued while offline"""
    doc_name: str
    version: int
    operation: str  # "write", "delete", "create"
    content: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)


class OfflineQueue:
    """Queue for storing updates when offline"""
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize offline queue
        
        Args:
            storage_dir: Directory to persist queue
        """
        if storage_dir is None:
            self.storage_dir = Path.home() / ".p2pdocs" / "queue"
        else:
            self.storage_dir = Path(storage_dir)
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.queue: List[QueuedUpdate] = []
        self.lock = threading.Lock()
        self._load_queue()
    
    def _load_queue(self):
        """Load queue from persistent storage"""
        queue_file = self.storage_dir / "pending_updates.json"
        
        if queue_file.exists():
            try:
                data = json.loads(queue_file.read_text())
                self.queue = [QueuedUpdate(**item) for item in data]
                logger.info(f"Loaded {len(self.queue)} pending updates from storage")
            except Exception as e:
                logger.error(f"Error loading queue: {str(e)}")
    
    def _save_queue(self):
        """Save queue to persistent storage"""
        queue_file = self.storage_dir / "pending_updates.json"
        
        try:
            data = [item.to_dict() for item in self.queue]
            queue_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving queue: {str(e)}")
    
    def enqueue(self, update: QueuedUpdate):
        """Add update to queue"""
        with self.lock:
            self.queue.append(update)
            self._save_queue()
            logger.info(f"Queued update for {update.doc_name}")
    
    def dequeue(self) -> Optional[QueuedUpdate]:
        """Remove and return first update from queue"""
        with self.lock:
            if self.queue:
                update = self.queue.pop(0)
                self._save_queue()
                return update
        return None
    
    def peek(self) -> Optional[QueuedUpdate]:
        """View first update without removing"""
        with self.lock:
            return self.queue[0] if self.queue else None
    
    def get_all(self) -> List[QueuedUpdate]:
        """Get all queued updates"""
        with self.lock:
            return list(self.queue)
    
    def clear(self):
        """Clear all queued updates"""
        with self.lock:
            self.queue.clear()
            self._save_queue()
    
    def size(self) -> int:
        """Get queue size"""
        with self.lock:
            return len(self.queue)
    
    def get_for_document(self, doc_name: str) -> List[QueuedUpdate]:
        """Get all queued updates for a document"""
        with self.lock:
            return [u for u in self.queue if u.doc_name == doc_name]


class SyncProtocol:
    """Handles synchronization between peers"""
    
    def __init__(self, username: str):
        """
        Initialize sync protocol
        
        Args:
            username: Username of this peer
        """
        self.username = username
        self.offline_queue = OfflineQueue()
        self.sync_callbacks: Dict[str, Callable] = {}
        self.is_online = True
        self.sync_in_progress = False
    
    def register_sync_handler(self, operation: str, callback: Callable):
        """Register handler for a sync operation"""
        self.sync_callbacks[operation] = callback
        logger.info(f"Registered sync handler for {operation}")
    
    def set_online_status(self, is_online: bool):
        """Update online/offline status"""
        was_online = self.is_online
        self.is_online = is_online
        
        logger.info(f"Status changed to {'online' if is_online else 'offline'}")
        
        # If coming back online, trigger sync
        if not was_online and is_online:
            logger.info("Connection restored, beginning sync...")
            self.sync_in_progress = True
    
    def queue_update(self, doc_name: str, version: int, operation: str, 
                    content: Optional[str] = None):
        """
        Queue an update (when offline)
        
        Args:
            doc_name: Document name
            version: Document version
            operation: Operation type (write, delete, create)
            content: Document content (if applicable)
        """
        update = QueuedUpdate(
            doc_name=doc_name,
            version=version,
            operation=operation,
            content=content
        )
        
        if self.is_online:
            # Try to apply immediately
            if not self._apply_update(update):
                # Failed, queue it
                self.offline_queue.enqueue(update)
        else:
            # Offline, queue for later
            self.offline_queue.enqueue(update)
    
    def _apply_update(self, update: QueuedUpdate) -> bool:
        """
        Apply update via registered handler
        
        Returns:
            True if applied successfully, False otherwise
        """
        if update.operation not in self.sync_callbacks:
            logger.warning(f"No handler for operation: {update.operation}")
            return False
        
        try:
            handler = self.sync_callbacks[update.operation]
            handler(update)
            logger.info(f"Applied {update.operation} on {update.doc_name}")
            return True
        except Exception as e:
            logger.error(f"Error applying update: {str(e)}")
            return False
    
    def sync_with_peer(self, peer_username: str, 
                      sync_callback: Callable[[QueuedUpdate], bool]) -> bool:
        """
        Synchronize all queued updates with a peer
        
        Args:
            peer_username: Username of peer to sync with
            sync_callback: Callback to send update to peer
            
        Returns:
            True if all updates synced, False if any failed
        """
        if not self.offline_queue.size():
            logger.info("No updates to sync")
            return True
        
        updates = self.offline_queue.get_all()
        success_count = 0
        
        for update in updates:
            try:
                if sync_callback(update):
                    self.offline_queue.dequeue()
                    success_count += 1
                    logger.info(f"Synced {update.operation} on {update.doc_name}")
                else:
                    logger.warning(f"Failed to sync {update.operation} on {update.doc_name}")
                    break
            except Exception as e:
                logger.error(f"Error during sync: {str(e)}")
                break
        
        self.sync_in_progress = False
        
        if success_count == len(updates):
            logger.info(f"Successfully synced all {len(updates)} updates")
            return True
        else:
            logger.warning(f"Synced {success_count}/{len(updates)} updates")
            return False
    
    def get_pending_updates(self, doc_name: Optional[str] = None) -> List[QueuedUpdate]:
        """Get pending updates"""
        if doc_name:
            return self.offline_queue.get_for_document(doc_name)
        return self.offline_queue.get_all()
    
    def get_status(self) -> dict:
        """Get synchronization status"""
        return {
            "username": self.username,
            "is_online": self.is_online,
            "sync_in_progress": self.sync_in_progress,
            "pending_updates": self.offline_queue.size(),
            "pending_by_doc": {
                doc_name: len(self.offline_queue.get_for_document(doc_name))
                for doc_name in set(u.doc_name for u in self.offline_queue.get_all())
            }
        }


class ConflictResolver:
    """Resolves conflicts during synchronization"""
    
    @staticmethod
    def resolve_write_conflict(local_version: dict, remote_version: dict) -> dict:
        """
        Resolve write conflict
        
        Strategy: Last-write-wins with timestamp comparison
        
        Args:
            local_version: Local version info
            remote_version: Remote version info
            
        Returns:
            Resolved version info
        """
        local_time = datetime.fromisoformat(local_version.get("timestamp", "1970-01-01T00:00:00"))
        remote_time = datetime.fromisoformat(remote_version.get("timestamp", "1970-01-01T00:00:00"))
        
        if remote_time > local_time:
            logger.info("Using remote version (newer)")
            return remote_version
        else:
            logger.info("Using local version (newer or equal)")
            return local_version
    
    @staticmethod
    def merge_concurrent_edits(local_content: str, remote_content: str) -> str:
        """
        Merge concurrent edits
        
        Strategy: Simple line-based merge
        
        Args:
            local_content: Local document content
            remote_content: Remote document content
            
        Returns:
            Merged content
        """
        local_lines = local_content.split("\n")
        remote_lines = remote_content.split("\n")
        
        # Simple merge: if both added lines, combine them
        merged_lines = set(local_lines + remote_lines)
        return "\n".join(sorted(merged_lines))


class SyncManager:
    """Manages overall synchronization"""
    
    def __init__(self, username: str):
        """Initialize sync manager"""
        self.username = username
        self.protocol = SyncProtocol(username)
        self.conflict_resolver = ConflictResolver()
        self.sync_thread = None
        self.is_running = False
    
    def start(self):
        """Start sync manager"""
        if self.is_running:
            return
        
        self.is_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info("Sync manager started")
    
    def _sync_loop(self):
        """Main sync loop"""
        while self.is_running:
            if self.protocol.sync_in_progress:
                # Sync is in progress, wait
                time.sleep(5)
            else:
                # Check periodically
                time.sleep(30)
    
    def stop(self):
        """Stop sync manager"""
        self.is_running = False
    
    def get_status(self) -> dict:
        """Get sync status"""
        return self.protocol.get_status()
