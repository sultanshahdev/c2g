"""M5-A safe, versioned document-state storage; not wired into runtime yet."""
from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from ..crdt.types import CRDTElement, CRDTId

FORMAT = "c2g-document"
SCHEMA_VERSION = 1
MAX_ELEMENTS = 100_000


class StateValidationError(ValueError):
    pass


def _id(value: Any) -> CRDTId:
    if not isinstance(value, dict) or set(value) != {"client_id", "lamport_clock"}:
        raise StateValidationError("invalid CRDT id")
    try:
        return CRDTId(value["client_id"], value["lamport_clock"])
    except (TypeError, ValueError) as exc:
        raise StateValidationError("invalid CRDT id") from exc


def validate_state(value: Any) -> Dict[str, Any]:
    """Strictly validate JSON data before it can become a document state."""
    if not isinstance(value, dict) or value.get("format") != FORMAT or value.get("schema_version") != SCHEMA_VERSION:
        raise StateValidationError("unsupported document schema")
    required = {"format", "schema_version", "document_id", "replica_id", "document_name", "lamport_clock", "elements", "pending_deletes", "applied_ops", "metadata"}
    if set(value) != required:
        raise StateValidationError("unexpected document state fields")
    for field in ("document_id", "replica_id", "document_name"):
        if not isinstance(value[field], str) or not value[field] or len(value[field]) > 128:
            raise StateValidationError("invalid document metadata")
    if isinstance(value["lamport_clock"], bool) or not isinstance(value["lamport_clock"], int) or value["lamport_clock"] < 0:
        raise StateValidationError("invalid Lamport clock")
    if not isinstance(value["elements"], list) or len(value["elements"]) > MAX_ELEMENTS:
        raise StateValidationError("invalid elements")
    if not isinstance(value["pending_deletes"], list) or not isinstance(value["applied_ops"], list) or not isinstance(value["metadata"], dict):
        raise StateValidationError("invalid state collections")
    ids = set()
    for raw in value["elements"]:
        try:
            element = CRDTElement.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise StateValidationError("invalid element") from exc
        if element.char_id in ids:
            raise StateValidationError("duplicate element identity")
        ids.add(element.char_id)
    for pending in value["pending_deletes"]:
        _id(pending)
    if not all(isinstance(item, str) and len(item) <= 256 for item in value["applied_ops"]):
        raise StateValidationError("invalid applied operations")
    # Return only JSON-compatible immutable-copy data after validation.
    return copy.deepcopy(value)


class JsonDocumentStore:
    """One isolated document directory with atomic primary/backup snapshots."""
    def __init__(self, root: str | Path, storage_key: str):
        if not isinstance(storage_key, str) or not storage_key or "/" in storage_key or "\\" in storage_key or storage_key in {".", ".."}:
            raise ValueError("invalid storage key")
        self.directory = Path(root) / "documents" / storage_key
        self.state_path = self.directory / "state.json"
        self.backup_path = self.directory / "state.backup.json"

    def save(self, state: Dict[str, Any]) -> None:
        checked = validate_state(state)
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(checked, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        fd, temporary = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=self.directory)
        temp_path = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            if self.state_path.exists():
                # Existing primary was previously accepted by save/load; retain it
                # as recovery material before replacing it.
                os.replace(self.state_path, self.backup_path)
            os.replace(temp_path, self.state_path)
            try:
                directory_fd = os.open(self.directory, os.O_RDONLY)
                try: os.fsync(directory_fd)
                finally: os.close(directory_fd)
            except OSError: pass  # Not supported on all platforms.
        finally:
            if temp_path.exists(): temp_path.unlink()

    def _read(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return validate_state(json.load(handle))

    def load(self) -> Dict[str, Any] | None:
        if not self.state_path.exists() and not self.backup_path.exists():
            return None
        try:
            return self._read(self.state_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StateValidationError):
            try:
                return self._read(self.backup_path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, StateValidationError) as exc:
                raise StateValidationError("no valid primary or backup state") from exc
