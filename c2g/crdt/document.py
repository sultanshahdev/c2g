"""Deterministic character RGA with causal buffering.

Insertions are immutable records. ``after_id`` is structural ancestry and the
optional ``before_id`` captures the right-hand visual anchor for local edits.
That small addition makes a requested local gap unambiguous; old peers may omit
it. Visibility is a monotonic false-dominates-true register.
"""

from collections import OrderedDict, defaultdict, deque
import threading
from typing import Dict, List, Optional, Set

from .types import CRDTElement, CRDTId
from ..storage.persistence import PersistenceManager


class CRDTDocument:
    """Bounded RGA-style document retaining causally pending insertions."""

    MAX_ELEMENTS = 100_000
    MAX_PENDING = 20_000
    MAX_SNAPSHOT_ELEMENTS = 100_000

    def __init__(self, client_id: str, doc_name: str = "collaborative_doc", start_fresh: bool = True, persistence_backend=None):
        self.client_id = CRDTId(client_id, 0).client_id
        self.doc_name = doc_name
        self.lamport_clock = 0
        self.elements: Dict[CRDTId, CRDTElement] = OrderedDict()
        # Legacy UI code inspects this. It tracks delete targets only and is
        # deliberately not used to deduplicate inserts.
        self.applied_ops: Set[str] = set()
        self.pending_deletes: Set[CRDTId] = set()
        self.pending_by_predecessor: Dict[CRDTId, Set[CRDTId]] = defaultdict(set)
        self._resolved_ids: Set[CRDTId] = set()
        self.lock = threading.RLock()
        self.persistence = persistence_backend or PersistenceManager(doc_name)
        if start_fresh:
            self.persistence.clear()
        else:
            self._load_state()

    @staticmethod
    def _key(char_id: CRDTId) -> str:
        return f"{char_id.client_id}:{char_id.lamport_clock}"

    @staticmethod
    def _id_to_dict(char_id: CRDTId) -> Dict[str, object]:
        return {"client_id": char_id.client_id, "lamport_clock": char_id.lamport_clock}

    @staticmethod
    def _id_from_dict(data: object) -> CRDTId:
        if not isinstance(data, dict):
            raise ValueError("ID must be a dictionary")
        return CRDTId(data["client_id"], data["lamport_clock"])

    def _load_state(self):
        with self.lock:
            state = self.persistence.load_state()
            if not isinstance(state, dict):
                return
            raw_elements = state.get("elements", {})
            if not isinstance(raw_elements, dict) or len(raw_elements) > self.MAX_ELEMENTS:
                return
            for raw in raw_elements.values():
                try:
                    element = CRDTElement.from_dict(raw)
                    if element.char_id not in self.elements and self._valid_new_element(element):
                        self.elements[element.char_id] = element
                except (KeyError, TypeError, ValueError):
                    continue
            for raw_id in state.get("pending_deletes", []):
                try:
                    self.pending_deletes.add(self._id_from_dict(raw_id))
                except (KeyError, TypeError, ValueError):
                    continue
            legacy = state.get("applied_ops", set())
            self.applied_ops = set(legacy) if isinstance(legacy, (set, list, tuple)) else set()
            for char_id in self.pending_deletes & set(self.elements):
                self.elements[char_id].visible = False
            self._rebuild_resolution_indexes()
            stored = state.get("lamport_clock", 0)
            self.lamport_clock = stored if isinstance(stored, int) and stored >= 0 else 0
            self._ensure_safe_clock()

    def _persist_state(self):
        data = {self._key(char_id): element.to_dict() for char_id, element in self.elements.items()}
        pending = [self._id_to_dict(char_id) for char_id in sorted(self.pending_deletes)]
        try:
            self.persistence.save_state(data, set(self.applied_ops), self.lamport_clock, pending)
        except TypeError:  # M0-compatible persistence doubles
            self.persistence.save_state(data, set(self.applied_ops), self.lamport_clock)

    def _ensure_safe_clock(self):
        own_max = max((cid.lamport_clock for cid in self.elements if cid.client_id == self.client_id), default=0)
        self.lamport_clock = max(self.lamport_clock, own_max)

    def _increment_clock(self):
        self._ensure_safe_clock()
        self.lamport_clock += 1

    def _sync_clock(self, remote_clock: int):
        if isinstance(remote_clock, int) and remote_clock >= 0:
            self.lamport_clock = max(self.lamport_clock, remote_clock)
        self._ensure_safe_clock()

    def _mark_resolved(self, char_id: CRDTId):
        queue = deque([char_id])
        while queue:
            current = queue.popleft()
            if current in self._resolved_ids or current not in self.elements:
                continue
            parent = self.elements[current].after_id
            if parent is not None and parent not in self._resolved_ids:
                self.pending_by_predecessor[parent].add(current)
                continue
            self._resolved_ids.add(current)
            queue.extend(sorted(self.pending_by_predecessor.pop(current, set())))

    def _index_resolution(self, element: CRDTElement):
        if element.after_id is None or element.after_id in self._resolved_ids:
            self._mark_resolved(element.char_id)
        else:
            self.pending_by_predecessor[element.after_id].add(element.char_id)

    def _rebuild_resolution_indexes(self):
        self.pending_by_predecessor = defaultdict(set)
        self._resolved_ids = set()
        for char_id, element in self.elements.items():
            if element.after_id is not None:
                self.pending_by_predecessor[element.after_id].add(char_id)
        for char_id, element in self.elements.items():
            if element.after_id is None:
                self._mark_resolved(char_id)

    def _valid_new_element(self, element: CRDTElement) -> bool:
        if len(self.elements) >= self.MAX_ELEMENTS or element.char_id in self.elements:
            return False
        if element.after_id == element.char_id or element.before_id == element.char_id:
            return False
        # A delayed child can already be waiting on this ID. Only then is a
        # predecessor-cycle check needed; ordinary append chains stay O(1).
        if element.char_id in self.pending_by_predecessor:
            queue, seen = deque(self.pending_by_predecessor[element.char_id]), set()
            while queue:
                current = queue.popleft()
                if current == element.after_id:
                    return False
                if current not in seen:
                    seen.add(current)
                    queue.extend(self.pending_by_predecessor.get(current, ()))
        return True

    @staticmethod
    def _same_immutable(left: CRDTElement, right: CRDTElement) -> bool:
        return left.char == right.char and left.after_id == right.after_id and left.before_id == right.before_id

    @staticmethod
    def _has_predecessor_cycle(records: Dict[CRDTId, CRDTElement]) -> bool:
        """Detect cycles in immutable ancestry in linear time."""
        colors: Dict[CRDTId, int] = {}
        for start in records:
            if colors.get(start, 0):
                continue
            current, trail = start, []
            while current in records and colors.get(current, 0) == 0:
                colors[current] = 1
                trail.append(current)
                current = records[current].after_id
            if current in records and colors.get(current) == 1:
                return True
            for char_id in trail:
                colors[char_id] = 2
        return False

    def _base_order(self) -> List[CRDTId]:
        children: Dict[Optional[CRDTId], List[CRDTId]] = defaultdict(list)
        for char_id in self._resolved_ids:
            children[self.elements[char_id].after_id].append(char_id)
        for values in children.values():
            values.sort()
        result, stack = [], list(reversed(children[None]))
        while stack:
            char_id = stack.pop()
            result.append(char_id)
            stack.extend(reversed(children.get(char_id, ())))
        return result

    def _linearized_ids(self) -> List[CRDTId]:
        """Iterative topological order of ancestry and visual-gap constraints."""
        base = self._base_order()
        rank = {char_id: index for index, char_id in enumerate(base)}
        edges = {char_id: set() for char_id in base}
        indegree = {char_id: 0 for char_id in base}
        def reaches(start, target):
            queue, seen = deque([start]), set()
            while queue:
                current = queue.popleft()
                if current == target:
                    return True
                if current not in seen:
                    seen.add(current)
                    queue.extend(edges[current])
            return False
        for char_id in base:
            element = self.elements[char_id]
            source, target = element.after_id, char_id
            if source in edges and target in edges and target not in edges[source]:
                edges[source].add(target)
                indegree[target] += 1
        # Concurrent local views can yield contradictory right anchors. Add
        # them in stable ID order and deterministically discard only an anchor
        # that would close a cycle; ancestry is never discarded.
        for char_id in sorted(base):
            target = self.elements[char_id].before_id
            if target in edges and target not in edges[char_id] and not reaches(target, char_id):
                edges[char_id].add(target)
                indegree[target] += 1
        ready = [char_id for char_id in base if not indegree[char_id]]
        result = []
        while ready:
            ready.sort(key=lambda char_id: rank[char_id], reverse=True)
            current = ready.pop()
            result.append(current)
            for target in sorted(edges[current], key=lambda char_id: rank[char_id]):
                indegree[target] -= 1
                if not indegree[target]:
                    ready.append(target)
        if len(result) != len(base):
            raise ValueError("cyclic CRDT ordering constraints")
        return result

    def _get_sorted_visible_elements(self) -> List[CRDTElement]:
        return [self.elements[char_id] for char_id in self._linearized_ids() if self.elements[char_id].visible]

    def insert_local(self, char: str, position: int) -> CRDTElement:
        with self.lock:
            if not isinstance(char, str) or len(char) != 1:
                raise ValueError("local insertion requires exactly one Python Unicode code point")
            visible = self._get_sorted_visible_elements()
            position = max(0, min(position, len(visible)))
            after_id = visible[position - 1].char_id if position else None
            before_id = visible[position].char_id if position < len(visible) else None
            self._increment_clock()
            element = CRDTElement(CRDTId(self.client_id, self.lamport_clock), char, after_id, True, before_id)
            self.elements[element.char_id] = element
            self._index_resolution(element)
            self._persist_state()
            return element

    def insert_local_batch(self, text: str, position: int) -> List[CRDTElement]:
        """Insert consecutive local code points into one existing visual gap.

        This has the same immutable anchors as calling ``insert_local`` for
        every character at consecutive positions, but resolves the gap and
        persists only once.  It deliberately retains one CRDT element and
        Lamport tick per code point, preserving the M1 wire/state model.
        """
        with self.lock:
            if not isinstance(text, str):
                raise ValueError("local batch insertion requires text")
            if not text:
                return []
            visible = self._get_sorted_visible_elements()
            position = max(0, min(position, len(visible)))
            after_id = visible[position - 1].char_id if position else None
            before_id = visible[position].char_id if position < len(visible) else None
            inserted = []
            self._ensure_safe_clock()
            for char in text:
                # The document lock keeps this local run contiguous; after the
                # single safety scan above, each newly assigned ID advances the
                # maximum for this client.
                self.lamport_clock += 1
                element = CRDTElement(CRDTId(self.client_id, self.lamport_clock), char, after_id, True, before_id)
                self.elements[element.char_id] = element
                self._index_resolution(element)
                inserted.append(element)
                after_id = element.char_id
            self._persist_state()
            return inserted

    def insert_remote(self, element: CRDTElement) -> bool:
        """Accept an insertion record; true means a new/changed record was accepted."""
        with self.lock:
            existing = self.elements.get(element.char_id)
            if existing is not None:
                if not self._same_immutable(existing, element):
                    raise ValueError("conflicting immutable CRDT element identity")
                if not element.visible and existing.visible:
                    existing.visible = False
                    self._persist_state()
                    return True
                return False
            if not self._valid_new_element(element):
                return False
            pending_count = sum(len(waiting) for waiting in self.pending_by_predecessor.values())
            if element.after_id is not None and element.after_id not in self._resolved_ids and pending_count >= self.MAX_PENDING:
                return False
            if element.char_id in self.pending_deletes:
                element.visible = False
                self.pending_deletes.discard(element.char_id)
            self.elements[element.char_id] = element
            self._sync_clock(element.char_id.lamport_clock)
            self._index_resolution(element)
            self._persist_state()
            return True

    def delete_local(self, position: int) -> Optional[CRDTId]:
        with self.lock:
            visible = self._get_sorted_visible_elements()
            if position < 0 or position >= len(visible):
                return None
            char_id = visible[position].char_id
            self.elements[char_id].visible = False
            self.pending_deletes.discard(char_id)
            self.applied_ops.add(self._key(char_id))
            self._persist_state()
            return char_id

    def delete_remote(self, char_id: CRDTId) -> bool:
        """Apply or remember a delete; true means visible text changed."""
        with self.lock:
            self._sync_clock(char_id.lamport_clock)
            self.applied_ops.add(self._key(char_id))
            element = self.elements.get(char_id)
            if element is None:
                if len(self.pending_deletes) < self.MAX_PENDING:
                    self.pending_deletes.add(char_id)
                    self._persist_state()
                return False
            if not element.visible:
                return False
            element.visible = False
            self.pending_deletes.discard(char_id)
            self._persist_state()
            return True

    def get_text(self) -> str:
        with self.lock:
            return "".join(element.char for element in self._get_sorted_visible_elements())

    def get_full_state(self) -> List[Dict]:
        with self.lock:
            resolved = self._linearized_ids()
            unresolved = sorted(set(self.elements) - set(resolved))
            records = [self.elements[char_id].to_dict() for char_id in resolved + unresolved]
            # Keep the public list payload while carrying deletes whose insert
            # has not arrived yet. M2 must version/negotiate this extension.
            records.extend({"_crdt_pending_delete": self._id_to_dict(char_id)} for char_id in sorted(self.pending_deletes))
            return records

    def apply_full_state(self, elements: List[Dict]) -> None:
        """Commutatively merge compatible immutable records and tombstones."""
        if not isinstance(elements, list) or len(elements) > self.MAX_SNAPSHOT_ELEMENTS:
            raise ValueError("invalid or oversized CRDT snapshot")
        with self.lock:
            pending = []
            raw_elements = []
            for raw in elements:
                if isinstance(raw, dict) and "_crdt_pending_delete" in raw:
                    pending.append(self._id_from_dict(raw["_crdt_pending_delete"]))
                else:
                    raw_elements.append(raw)
            parsed = [CRDTElement.from_dict(raw) for raw in raw_elements]
            incoming: Dict[CRDTId, CRDTElement] = {}
            for element in parsed:
                duplicate = incoming.get(element.char_id)
                if duplicate is not None and not self._same_immutable(duplicate, element):
                    raise ValueError("conflicting duplicate identity in snapshot")
                if duplicate is None:
                    incoming[element.char_id] = element
                elif not element.visible:
                    duplicate.visible = False
            for char_id, element in incoming.items():
                existing = self.elements.get(char_id)
                if existing is not None and not self._same_immutable(existing, element):
                    raise ValueError("conflicting immutable CRDT element identity")
            combined = dict(self.elements)
            combined.update(incoming)
            if self._has_predecessor_cycle(combined):
                raise ValueError("cyclic CRDT predecessor graph")
            for element in incoming.values():
                existing = self.elements.get(element.char_id)
                if existing is None:
                    if not self._valid_new_element(element):
                        continue
                    if element.char_id in self.pending_deletes:
                        element.visible = False
                        self.pending_deletes.discard(element.char_id)
                    self.elements[element.char_id] = element
                elif not element.visible:
                    existing.visible = False
                self._sync_clock(element.char_id.lamport_clock)
            for char_id in pending:
                element = self.elements.get(char_id)
                if element is None:
                    if len(self.pending_deletes) >= self.MAX_PENDING:
                        continue
                    self.pending_deletes.add(char_id)
                else:
                    element.visible = False
            self._rebuild_resolution_indexes()
            self._persist_state()
