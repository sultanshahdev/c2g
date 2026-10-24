"""Runtime ownership and coalesced durable writes for JSON documents."""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Callable


class DocumentInUseError(RuntimeError):
    """Raised when another local process owns a saved replica."""


class DocumentLock:
    """Advisory per-replica lock.  flock is released by kernel on process exit."""
    def __init__(self, directory: Path):
        self.path = directory / ".c2g.lock"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0); self.handle.write(b"0"); self.handle.flush()
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            raise DocumentInUseError("saved document is already open by another local process") from exc

    def close(self) -> None:
        if not self.handle:
            return
        try:
            if os.name == "nt":
                import msvcrt; self.handle.seek(0); msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl; fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close(); self.handle = None


class AutosaveCoordinator:
    """One bounded latest-snapshot writer; completion status is generation-based."""
    def __init__(self, save: Callable[[dict], None], status: Callable[[str, str | None], None] | None = None):
        self._save, self._status = save, status or (lambda *_: None)
        self._condition = threading.Condition()
        self._pending = None
        self._generation = self._written = 0
        self._error: Exception | None = None
        self._stopping = False
        self._thread = threading.Thread(target=self._run, name="c2g-json-autosave", daemon=False)
        self._thread.start()

    def request(self, state: dict) -> int:
        # State comes from under the CRDT lock.  Copy before that lock is released.
        snapshot = copy.deepcopy(state)
        with self._condition:
            if self._stopping:
                raise RuntimeError("persistence writer is stopping")
            self._generation += 1; generation = self._generation
            self._pending = (generation, snapshot)  # bounded: newest complete snapshot wins
            self._error = None
            self._condition.notify()
        self._status("saving", None)
        return generation

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._stopping:
                    self._condition.wait()
                if self._pending is None and self._stopping:
                    return
                generation, state = self._pending; self._pending = None
            try:
                self._save(state)
            except Exception as exc:  # retain in-memory state; a later mutation/retry can supersede it
                with self._condition:
                    self._error = exc; self._condition.notify_all()
                self._status("failed", str(exc))
            else:
                with self._condition:
                    self._written = max(self._written, generation); self._error = None; self._condition.notify_all()
                    current = self._generation
                if self._written >= current:
                    self._status("saved", None)

    def flush(self) -> None:
        """Wait for the latest requested generation, raising its write error."""
        with self._condition:
            target = self._generation
            while self._written < target and self._error is None:
                self._condition.wait()
            if self._written < target:
                raise self._error or RuntimeError("latest document state was not written")

    def retry(self) -> None:
        # Caller supplies a current snapshot through request; this method is intentionally no-op.
        # It exists so UI clients can use one status API without claiming durability.
        return None

    def set_status_callback(self, status: Callable[[str, str | None], None]) -> None:
        self._status = status

    def close(self) -> None:
        failure = None
        try:
            self.flush()
        except Exception as exc:
            failure = exc
        with self._condition:
            self._stopping = True; self._condition.notify_all()
        self._thread.join()
        if failure:
            raise failure
