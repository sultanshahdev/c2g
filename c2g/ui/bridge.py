"""Narrow pywebview API for the production web editor."""
from __future__ import annotations

from typing import Any, Optional

from .controller import ApplicationController


class DesktopBridge:
    def __init__(self, controller: ApplicationController):
        # DesktopApplication supplies the picker lifecycle; tests and legacy
        # callers may still supply an already-active controller.
        self.application = controller if hasattr(controller, "startup_state") else None
        self.controller = getattr(controller, "controller", controller)
        self.window = None

    def attach_window(self, window) -> None:
        self.window = window
        if self.controller:
            self.controller.set_ui_dispatch(self._deliver)

    def _deliver(self, payload: dict) -> None:
        if self.window is None:
            return
        # pywebview serializes the value rather than interpolating untrusted text.
        self.window.evaluate_js("window.c2gReceive && window.c2gReceive(" + __import__("json").dumps(payload) + ")")

    def editor_ready(self):
        if self.controller:
            return self.controller.initialize()
        startup = self.application.startup_state()
        if startup["forced_resume"]:
            return self.resume_document(startup["forced_resume"])
        if startup["forced_new"]:
            return self.create_document()
        return {"picker": startup}

    def create_document(self, name="Untitled"):
        if not self.application: return {"accepted": False, "reason": "startup picker unavailable"}
        result = self.application.create_document(name)
        if result.get("accepted"):
            self.controller = self.application.controller; self.controller.set_ui_dispatch(self._deliver)
        return result

    def resume_document(self, storage_key):
        if not self.application: return {"accepted": False, "reason": "startup picker unavailable"}
        result = self.application.resume_document(storage_key)
        if result.get("accepted"):
            self.controller = self.application.controller; self.controller.set_ui_dispatch(self._deliver)
        return result

    def apply_local_transaction(self, transaction: dict):
        if not self.controller: return {"accepted": False, "reason": "select a document first"}
        return self.controller.apply_local_transaction(transaction)

    def connect(self, endpoint: str):
        if not self.controller: return {"accepted": False, "reason": "select a document first"}
        return self.controller.connect(endpoint)

    def connect_discovered(self, host: str, port: int):
        return self.controller.connect_discovered(host, port)

    def disconnect_peer(self, peer_id: str):
        return self.controller.disconnect_peer(peer_id)

    def ui_state(self):
        return self.controller.ui_state() if self.controller else {"picker": self.application.startup_state()}

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
