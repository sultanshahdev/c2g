"""
Persistence manager for CRDT document state.
"""

import os
import pickle
import queue
import threading
import time
from typing import Dict, Set, Optional


class PersistenceManager:
    """Disk-based state persistence using pickle with async writes.
    
    Uses a bounded queue to prevent unbounded memory growth.
    Flushes all writes on shutdown to ensure no data loss.
    """
    
    def __init__(self, doc_name: str = "collaborative_doc"):
        self.state_dir = os.path.expanduser("~/.p2p_crdt")
        self.state_file = os.path.join(self.state_dir, f".{doc_name}_state.pkl")
        os.makedirs(self.state_dir, exist_ok=True)
        
        # Bounded async write queue: keep last state, discard old ones
        self.write_queue = queue.Queue(maxsize=5)  # Keep only last 5 states
        self.running = True
        self.last_state = None
        threading.Thread(target=self._write_worker, daemon=True).start()
    
    def _write_worker(self):
        """Background thread: writes queued states to disk."""
        while self.running:
            try:
                state = self.write_queue.get(timeout=1)
                if state is None:  # Shutdown signal
                    break
                self.last_state = state
                self._write_sync(state)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[PERSIST] Write error: {e}")
    
    def _write_sync(self, state: Dict):
        """Synchronously write state to disk."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'wb') as f:
                pickle.dump(state, f)
        except Exception as e:
            print(f"[PERSIST] Sync error: {e}")
    
    def save_state(self, elements_data: Dict, applied_ops: Set, lamport_clock: int):
        """Queue state for async write. If queue full, drops oldest (we have latest)."""
        try:
            state = {
                "elements": elements_data,
                "applied_ops": applied_ops,
                "lamport_clock": lamport_clock,
                "timestamp": time.time()
            }
            # Try non-blocking first
            try:
                self.write_queue.put(state, block=False)
            except queue.Full:
                # Queue full: remove and discard oldest, keep this one
                try:
                    self.write_queue.get_nowait()
                    self.write_queue.put(state, block=False)
                except:
                    pass  # Queue still full, skip this save
        except Exception as e:
            print(f"[PERSIST] Queue error: {e}")
    
    def load_state(self) -> Optional[Dict]:
        """Load state from disk (blocking, only on startup)."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            print(f"[PERSIST] Load error: {e}")
        return None
    
    def clear(self):
        """Clear persisted state."""
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        except:
            pass
    
    def flush(self):
        """Flush all pending writes before shutdown."""
        while not self.write_queue.empty():
            try:
                state = self.write_queue.get(timeout=1)
                if state is not None:
                    self._write_sync(state)
            except queue.Empty:
                break
    
    def stop(self):
        """Stop background writer and flush pending writes."""
        self.flush()  # Ensure all writes complete
        self.running = False
        self.write_queue.put(None)
