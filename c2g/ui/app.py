"""Native pywebview lifecycle for the M4 Monaco editor."""
from __future__ import annotations

from pathlib import Path

from .bridge import DesktopBridge
from .controller import ApplicationController


class DesktopApplication:
    def __init__(self, username: str, peer: str | None = None, listen_port: int = 5000):
        self.controller = ApplicationController(username, listen_port)
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
        if not self.controller.start(start_discovery=True):
            self.controller.shutdown()
            raise RuntimeError("c2g could not start its P2P listener; choose a different --listen-port")
        bridge = DesktopBridge(self.controller)
        window = webview.create_window("c2g — Code 2gether", str(index), js_api=bridge, width=1200, height=760, min_size=(800, 500))
        bridge.attach_window(window)
        window.events.closed += self.controller.shutdown
        if self.peer:
            self.controller.connect(self.peer)
        try:
            webview.start(debug=False, http_server=False)
        finally:
            self.controller.shutdown()
