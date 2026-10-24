"""Narrow pywebview API for the production web editor."""
from __future__ import annotations

from typing import Any, Optional

from .controller import ApplicationController


class DesktopBridge:
    def __init__(self, controller: ApplicationController):
        self.controller = controller
        self.window = None

    def attach_window(self, window) -> None:
        self.window = window
        self.controller.set_ui_dispatch(self._deliver)

    def _deliver(self, payload: dict) -> None:
        if self.window is None:
            return
        # pywebview serializes the value rather than interpolating untrusted text.
        self.window.evaluate_js("window.c2gReceive && window.c2gReceive(" + __import__("json").dumps(payload) + ")")

    def editor_ready(self):
        return self.controller.initialize()

    def apply_local_transaction(self, transaction: dict):
        return self.controller.apply_local_transaction(transaction)

    def connect(self, endpoint: str):
        return self.controller.connect(endpoint)

    def connect_discovered(self, host: str, port: int):
        return self.controller.connect_discovered(host, port)

    def disconnect_peer(self, peer_id: str):
        return self.controller.disconnect_peer(peer_id)

    def ui_state(self):
        return self.controller.ui_state()

    def export_document(self):
        if self.window is None:
            return {"accepted": False, "reason": "window is unavailable"}
        try:
            import webview
            paths = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename="c2g-document.txt", file_types=("Text files (*.txt)", "All files (*.*)"))
            path = paths[0] if paths else None
        except Exception as exc:
            return {"accepted": False, "reason": str(exc)}
        return self.controller.export(path)

    def report_error(self, message: Any):
        return {"accepted": False, "reason": str(message)[:500]}
