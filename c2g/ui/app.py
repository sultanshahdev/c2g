"""Native pywebview lifecycle for the M4 Monaco editor."""
from __future__ import annotations

from pathlib import Path
import os
import re

from .bridge import DesktopBridge
from .controller import ApplicationController
from ..storage.json_store import JsonDocumentStore, StateValidationError
from ..storage.recovered_document import PersistedCrdt


class DesktopApplication:
    def __init__(self, username: str, peer: str | None = None, listen_port: int = 5000, *, storage_root=None,
                 new=False, resume=None):
        self.username, self.peer, self.listen_port = username, peer, listen_port
        self.storage_root = Path(storage_root or os.environ.get("C2G_STORAGE_ROOT", Path.home() / ".c2g"))
        self.controller = None
        self.new, self.resume = new, resume

    @staticmethod
    def valid_storage_key(key):
        return isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", key) is not None

    def recent_documents(self):
        root = self.storage_root / "documents"
        if not root.exists(): return []
        result = []
        for child in sorted(root.iterdir()):
            if not child.is_dir() or not self.valid_storage_key(child.name): continue
            try:
                store = JsonDocumentStore(self.storage_root, child.name); state = store.load()
                if state is not None:
                    result.append({"storage_key": child.name, "name": state["document_name"],
                                   "last_saved": store.state_path.stat().st_mtime, "corrupt": False})
            except (OSError, StateValidationError):
                result.append({"storage_key": child.name, "name": child.name, "last_saved": None, "corrupt": True})
        return result

    def _activate(self, saved):
        self.controller = ApplicationController(self.username, self.listen_port, persisted=saved)
        if not self.controller.start(start_discovery=True):
            self.controller.shutdown(); self.controller = None
            raise RuntimeError("c2g could not start its P2P listener; choose a different --listen-port")
        if self.peer: self.controller.connect(self.peer)
        return self.controller.initialize()

    def create_document(self, name="Untitled"):
        if self.controller: return {"accepted": False, "reason": "document already selected"}
        if not isinstance(name, str) or not name.strip() or len(name) > 128: return {"accepted": False, "reason": "invalid document name"}
        import uuid
        key = str(uuid.uuid4())
        try: return {"accepted": True, **self._activate(PersistedCrdt.create(self.storage_root, key, name.strip()))}
        except Exception as exc: return {"accepted": False, "reason": str(exc)}

    def resume_document(self, storage_key):
        if self.controller: return {"accepted": False, "reason": "document already selected"}
        if not self.valid_storage_key(storage_key): return {"accepted": False, "reason": "invalid storage key"}
        try: return {"accepted": True, **self._activate(PersistedCrdt.open(self.storage_root, storage_key))}
        except Exception as exc: return {"accepted": False, "reason": str(exc)}

    def startup_state(self):
        return {"documents": self.recent_documents(), "forced_new": self.new, "forced_resume": self.resume}
        self.peer = peer

    def run(self) -> None:
        root = Path(__file__).resolve().parents[2]
        index = root / "web" / "dist" / "index.html"
        if not index.exists():
            raise RuntimeError("Monaco frontend build is missing; run: cd web && npm ci && npm run build")
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview and a supported native renderer are required for c2g M4") from exc
        bridge = DesktopBridge(self)
        window = webview.create_window("c2g — Code 2gether", str(index), js_api=bridge, width=1200, height=760, min_size=(800, 500))
        bridge.attach_window(window)
        window.events.closed += self.shutdown
        try:
            webview.start(debug=False, http_server=False)
        finally:
            self.shutdown()

    def shutdown(self):
        if self.controller:
            self.controller.shutdown()
