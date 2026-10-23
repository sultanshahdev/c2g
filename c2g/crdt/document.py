"""
CRDT Document implementation using RGA (Replicated Growable Array).
"""

import threading
from typing import Dict, List, Optional, Set
from collections import OrderedDict

from .types import CRDTId, CRDTElement
from ..storage.persistence import PersistenceManager


class CRDTDocument:
    """RGA-based CRDT with persistence."""
    
    def __init__(self, client_id: str, doc_name: str = "collaborative_doc", start_fresh: bool = True):
        self.client_id = client_id
        self.doc_name = doc_name
        self.lamport_clock = 0
        self.elements: Dict[CRDTId, CRDTElement] = OrderedDict()
        self.applied_ops: Set[str] = set()
        self.lock = threading.RLock()
        
        self.persistence = PersistenceManager(doc_name)
        
        # Clear old state if starting fresh
        if start_fresh:
            print(f"[CRDT] Starting with fresh document (clearing old state)")
            self.persistence.clear()
        else:
            self._load_state()
    
    def _load_state(self):
        """Load persisted state and rebuild sort order.
        
        Loaded elements maintain their after_id references even if
        they were stored in different physical order on disk.
        """
        with self.lock:
            state = self.persistence.load_state()
            if state:
                self.lamport_clock = state.get("lamport_clock", 0)
                self.applied_ops = state.get("applied_ops", set())
                
                elements_data = state.get("elements", {})
                # Load all elements first
                for id_str, elem_dict in elements_data.items():
                    try:
                        cid = CRDTId(elem_dict["char_id"]["client_id"], elem_dict["char_id"]["lamport_clock"])
                        after_cid = None
                        if elem_dict.get("after_id"):
                            after_cid = CRDTId(
                                elem_dict["after_id"]["client_id"],
                                elem_dict["after_id"]["lamport_clock"]
                            )
                        elem = CRDTElement(
                            char_id=cid,
                            char=elem_dict["char"],
                            after_id=after_cid,
                            visible=elem_dict.get("visible", True)
                        )
                        self.elements[cid] = elem
                    except Exception as e:
                        print(f"[CRDT] Load error for {id_str}: {e}")
                
                # Validate after_id references: ensure they exist
                # If element references deleted/missing element, mark as deleted (don't reset to None)
                invalid_refs = 0
                for cid, elem in self.elements.items():
                    if elem.after_id and elem.after_id not in self.elements:
                        print(f"[CRDT] Invalid after_id reference {elem.after_id} for {cid}, marking as deleted")
                        # Don't reset to None - that would create orphan heads
                        # Instead mark as deleted (tombstone) so it won't appear in text
                        elem.visible = False
                        invalid_refs += 1
                
                if invalid_refs > 0:
                    print(f"[CRDT] Fixed {invalid_refs} invalid references by marking as deleted")
                
                print(f"[CRDT] Loaded {len(self.elements)} elements from disk")
    
    def _persist_state(self):
        """Save state to disk."""
        try:
            elements_data = {}
            for elem_id, elem in self.elements.items():
                elements_data[f"{elem_id.client_id}:{elem_id.lamport_clock}"] = elem.to_dict()
            
            self.persistence.save_state(elements_data, self.applied_ops, self.lamport_clock)
        except:
            pass
    
    def _increment_clock(self):
        """Increment Lamport clock."""
        self.lamport_clock += 1
    
    def _sync_clock(self, remote_clock: int):
        """Sync with remote clock."""
        self.lamport_clock = max(self.lamport_clock, remote_clock) + 1
    
    def insert_local(self, char: str, position: int) -> CRDTElement:
        """Insert character locally at visual position.
        
        Finds which element this should be inserted after, then creates new element
        with after_id pointing to that element.
        
        Position is safely bounded: if position > len(visible), use last element.
        """
        with self.lock:
            self._increment_clock()
            
            # Find which element to insert after (based on current visible order)
            after_id = None
            visible_elements = self._get_sorted_visible_elements()
            
            if position < 0:
                position = 0
            elif position > len(visible_elements):
                position = len(visible_elements)
            
            if position > 0:
                after_id = visible_elements[position - 1].char_id
            
            new_id = CRDTId(self.client_id, self.lamport_clock)
            element = CRDTElement(char_id=new_id, char=char, after_id=after_id, visible=True)
            self.elements[new_id] = element
            self._persist_state()
            return element
    
    def _get_sorted_visible_elements(self) -> List[CRDTElement]:
        """Get visible elements in RGA order (topological sort based on after_id).
        
        RGA maintains insertion order via after_id references:
        - Elements reference what they were inserted after
        - Sorting by after_id creates proper insertion sequence
        - Falls back to CRDTId for elements with same after_id
        """
        # Topological sort: build order based on after_id references
        visible = {elem_id: elem for elem_id, elem in self.elements.items() if elem.visible}
        
        # Find all elements with no predecessor (after_id=None or after_id not in visible set)
        ordered = []
        
        # Group elements by their after_id (what they were inserted after)
        after_map = {}  # after_id → [elements that come after it]
        heads = []  # Elements with no predecessor
        
        for elem_id, elem in visible.items():
            if elem.after_id is None or elem.after_id not in visible:
                # This is a head element (nothing before it in visible set)
                heads.append(elem)
            else:
                # Link to its predecessor
                if elem.after_id not in after_map:
                    after_map[elem.after_id] = []
                after_map[elem.after_id].append(elem)
        
        # Sort heads by CRDTId for deterministic ordering
        heads.sort(key=lambda e: e.char_id)
        
        # Depth-first traversal: follow after_id chains
        def visit(elem: CRDTElement):
            ordered.append(elem)
            # Get elements that come after this one, sort by CRDTId
            successors = after_map.get(elem.char_id, [])
            successors.sort(key=lambda e: e.char_id)
            for successor in successors:
                visit(successor)
        
        for head in heads:
            visit(head)
        
        return ordered
    
    def insert_remote(self, element: CRDTElement) -> bool:
        """Insert remote element."""
        with self.lock:
            # Check if element already exists (duplicate insert)
            if element.char_id in self.elements:
                return False
            
            self.elements[element.char_id] = element
            self._sync_clock(element.char_id.lamport_clock)
            self._persist_state()
            return True
    
    def delete_local(self, position: int) -> Optional[CRDTId]:
        """Delete at visual position (0-based index in visible text).
        
        Works on sorted visible elements, not insertion order.
        """
        with self.lock:
            if position < 0:
                return None
            
            visible_elements = self._get_sorted_visible_elements()
            if position >= len(visible_elements):
                return None
            
            target_element = visible_elements[position]
            target_element.visible = False
            
            # Mark operation as applied to prevent duplicate processing
            op_key = f"{target_element.char_id.client_id}:{target_element.char_id.lamport_clock}"
            self.applied_ops.add(op_key)
            
            self._persist_state()
            return target_element.char_id
    
    def delete_remote(self, char_id: CRDTId) -> bool:
        """Delete remote element."""
        with self.lock:
            op_key = f"{char_id.client_id}:{char_id.lamport_clock}"
            if op_key in self.applied_ops:
                return False
            
            self.applied_ops.add(op_key)
            
            if char_id in self.elements:
                self.elements[char_id].visible = False
                self._sync_clock(char_id.lamport_clock)
                self._persist_state()
                return True
            
            return False
    
    def get_text(self) -> str:
        """Get visible text in CRDT sort order."""
        with self.lock:
            return "".join(elem.char for elem in self._get_sorted_visible_elements())
    
    def get_full_state(self) -> List[Dict]:
        """Get all elements."""
        with self.lock:
            return [elem.to_dict() for elem in self.elements.values()]
    
    def apply_full_state(self, elements: List[Dict]) -> None:
        """Apply full state."""
        with self.lock:
            for elem_dict in elements:
                elem = CRDTElement.from_dict(elem_dict)
                op_key = f"{elem.char_id.client_id}:{elem.char_id.lamport_clock}"
                
                if op_key not in self.applied_ops:
                    self.applied_ops.add(op_key)
                    self.elements[elem.char_id] = elem
                    self._sync_clock(elem.char_id.lamport_clock)
            
            self._persist_state()
