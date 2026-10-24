"""Explicit JSON-backed CRDT factory used by the production document lifecycle."""
from collections import OrderedDict
import uuid

from ..crdt.document import CRDTDocument
from ..crdt.types import CRDTElement, CRDTId
from .json_store import JsonDocumentStore, StateValidationError
from .lifecycle import AutosaveCoordinator, DocumentLock


class _JsonBackend:
    def __init__(self, owner): self.owner = owner
    def clear(self): pass
    def stop(self): pass
    def load_state(self): return None
    def save_state(self, elements, applied, clock, pending=None):
        self.owner._queue_save(elements, applied, clock, pending or [])


class PersistedCrdt:
    def __init__(self, store, document_id, replica_id, name="Untitled", status_callback=None):
        self.store, self.document_id, self.replica_id, self.name = store, document_id, replica_id, name
        self._lock = DocumentLock(store.directory)
        self._autosave = AutosaveCoordinator(store.save, status_callback)
        self.document = CRDTDocument(replica_id, doc_name="json-backed", start_fresh=False, persistence_backend=_JsonBackend(self))

    @classmethod
    def create(cls, root, storage_key, name="Untitled", status_callback=None):
        store = JsonDocumentStore(root, storage_key)
        if store.load() is not None: raise FileExistsError("saved document already exists")
        item = cls(store, str(uuid.uuid4()), str(uuid.uuid4()), name, status_callback)
        try:
            item.save(); item.flush(); return item
        except Exception:
            item.close()
            raise

    @classmethod
    def open(cls, root, storage_key, status_callback=None):
        store = JsonDocumentStore(root, storage_key); state = store.load()
        if state is None: raise FileNotFoundError("saved document does not exist")
        elements = [CRDTElement.from_dict(raw) for raw in state["elements"]]
        records = {element.char_id: element for element in elements}
        # Reject invalid ancestry before acquiring ownership or starting a writer.
        if len(records) != len(elements) or CRDTDocument._has_predecessor_cycle(records):
            raise StateValidationError("invalid CRDT ancestry")
        item = cls(store, state["document_id"], state["replica_id"], state["document_name"], status_callback)
        doc = item.document
        with doc.lock:
            doc.elements = OrderedDict((element.char_id, element) for element in elements)
            doc.pending_deletes = {CRDTId(**raw) for raw in state["pending_deletes"]}
            doc.applied_ops = set(state["applied_ops"])
            for char_id in doc.pending_deletes & set(doc.elements): doc.elements[char_id].visible = False
            doc.lamport_clock = state["lamport_clock"]; doc._rebuild_resolution_indexes(); doc._ensure_safe_clock()
        return item

    def _state(self, elements, applied, clock, pending):
        return {"format":"c2g-document","schema_version":1,"document_id":self.document_id,"replica_id":self.replica_id,"document_name":self.name,"lamport_clock":clock,"elements":list(elements.values()),"pending_deletes":pending,"applied_ops":sorted(applied),"metadata":{}}

    def _queue_save(self, elements, applied, clock, pending):
        self._autosave.request(self._state(elements, applied, clock, pending))
    def save(self):
        doc=self.document
        with doc.lock: self._queue_save({doc._key(cid):e.to_dict() for cid,e in doc.elements.items()}, doc.applied_ops, doc.lamport_clock, [doc._id_to_dict(cid) for cid in sorted(doc.pending_deletes)])
    def update_document_id(self, document_id):
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("invalid document identity")
        self.document_id = document_id
        self.save()
    def flush(self): self._autosave.flush()
    def set_status_callback(self, callback): self._autosave.set_status_callback(callback)
    def close(self):
        try:
            self.save(); self._autosave.close()
        finally:
            self._lock.close()
