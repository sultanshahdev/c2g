"""M3 experimental Monaco/pywebview host; it is not the production Tk editor."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import uuid
from typing import Any, Dict, List

from ..crdt import CRDTDocument


def utf16_to_codepoint(text: str, offset: int) -> int:
    """Map a JavaScript UTF-16 offset to a Python code-point index.

    An offset in the middle of a surrogate pair is rejected; Monaco normally
    never supplies one for a cursor boundary.
    """
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("invalid UTF-16 offset")
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > offset:
            raise ValueError("offset splits a surrogate pair")
        units += width
    if units == offset:
        return len(text)
    raise ValueError("UTF-16 offset past text")


def codepoint_to_utf16(text: str, index: int) -> int:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= len(text):
        raise ValueError("invalid code-point index")
    return len(text[:index].encode("utf-16-le")) // 2


def incremental_patch(before: str, after: str) -> Dict[str, Any]:
    """Smallest contiguous patch, expressed in Monaco UTF-16 offsets."""
    prefix = 0
    while prefix < min(len(before), len(after)) and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    while suffix < len(before) - prefix and suffix < len(after) - prefix and before[-1-suffix] == after[-1-suffix]:
        suffix += 1
    end = len(before) - suffix
    return {"offset": codepoint_to_utf16(before, prefix),
            "length": codepoint_to_utf16(before, end) - codepoint_to_utf16(before, prefix),
            "text": after[prefix:len(after)-suffix if suffix else len(after)]}


class BridgeController:
    """Serialized, minimal API exposed to JavaScript by the optional host."""
    def __init__(self, client_id="m3-spike"):
        self.document = CRDTDocument(client_id, doc_name="m3_spike", start_fresh=True)
        self.lock = threading.RLock()
        self.version = 1
        self.seen_transactions = set()
        self.ready = False

    def initialize(self):
        with self.lock:
            return {"text": self.document.get_text(), "version": self.version, "language": "python"}

    def editor_ready(self):
        self.ready = True
        return self.initialize()

    def apply_local_transaction(self, transaction: Dict[str, Any]):
        """Apply Monaco changes sorted descending against their pre-change model."""
        with self.lock:
            if not isinstance(transaction, dict): raise ValueError("transaction must be object")
            txid, version, changes = transaction.get("transaction_id"), transaction.get("base_version"), transaction.get("changes")
            if not isinstance(txid, str) or not txid or not isinstance(changes, list): raise ValueError("invalid transaction")
            if txid in self.seen_transactions: return {"accepted": True, "duplicate": True, "version": self.version}
            if version != self.version: return {"accepted": False, "reason": "stale model version", "version": self.version, "text": self.document.get_text()}
            before = self.document.get_text()
            normalized = []
            for change in changes:
                if not isinstance(change, dict) or not isinstance(change.get("rangeOffset"), int) or not isinstance(change.get("rangeLength"), int) or not isinstance(change.get("text"), str):
                    raise ValueError("invalid edit change")
                start = utf16_to_codepoint(before, change["rangeOffset"])
                end = utf16_to_codepoint(before, change["rangeOffset"] + change["rangeLength"])
                if end < start: raise ValueError("invalid edit range")
                normalized.append((start, end, change["text"]))
            # Monaco changes are non-overlapping in its pre-event coordinates.
            normalized.sort(reverse=True)
            previous = len(before) + 1
            for start, end, text in normalized:
                if end > previous: raise ValueError("overlapping changes")
                for _ in range(end - start): self.document.delete_local(start)
                self.document.insert_local_batch(text, start)
                previous = start
            self.version += 1; self.seen_transactions.add(txid)
            return {"accepted": True, "version": self.version, "text": self.document.get_text(), "patch": incremental_patch(before, self.document.get_text())}

    def apply_remote_text(self, text: str):
        """M3 simulation of a remote CRDT integration, returned as an incremental patch."""
        if not isinstance(text, str): raise ValueError("remote text must be string")
        with self.lock:
            before = self.document.get_text()
            # Use public CRDT operations; this is deliberately a spike adapter.
            for _ in range(len(before)): self.document.delete_local(0)
            for index, char in enumerate(text): self.document.insert_local(char, index)
            self.version += 1
            return {"patch": incremental_patch(before, text), "version": self.version, "text": text}


class WebviewApi:
    def __init__(self, controller): self.controller = controller
    def editor_ready(self): return self.controller.editor_ready()
    def apply_local_transaction(self, transaction): return self.controller.apply_local_transaction(transaction)
    def remote_demo(self): return self.controller.apply_remote_text("# remote update\nprint('😀')\n")
    def report_error(self, message):
        return {"accepted": False, "reason": str(message)[:500]}


def main():
    root = Path(__file__).resolve().parents[2]
    index = root / "web" / "dist" / "index.html"
    if not index.exists():
        raise SystemExit("M3 frontend build missing; run: cd web && npm ci && npm run build")
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("pywebview is not installed. Install the optional M3 desktop dependency and Linux renderer prerequisites.") from exc
    controller = BridgeController("m3-" + str(uuid.uuid4()))
    # pywebview serves local paths with its internal local server; no public HTTP listener.
    window = webview.create_window("c2g M3 Monaco Spike", str(index), js_api=WebviewApi(controller), width=1100, height=750)
    webview.start(debug=False)


if __name__ == "__main__": main()
