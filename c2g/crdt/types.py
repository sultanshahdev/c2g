"""
CRDT data types and structures.

This module defines the core data structures for the CRDT implementation:
- CRDTId: Globally unique operation identifier
- CRDTElement: Character element in the CRDT document
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CRDTId:
    """Globally unique operation ID: (client_id, lamport_clock)"""
    client_id: str
    lamport_clock: int

    def __post_init__(self):
        if not isinstance(self.client_id, str) or not self.client_id or len(self.client_id) > 128:
            raise ValueError("client_id must be a non-empty string of at most 128 characters")
        if isinstance(self.lamport_clock, bool) or not isinstance(self.lamport_clock, int) or self.lamport_clock < 0:
            raise ValueError("lamport_clock must be a non-negative integer")
    
    def __lt__(self, other):
        """Total ordering for deterministic merge."""
        if self.lamport_clock != other.lamport_clock:
            return self.lamport_clock < other.lamport_clock
        return self.client_id < other.client_id


@dataclass
class CRDTElement:
    """Character in CRDT: RGA with position tracking.
    
    Structure: (client_id, lamport_clock) with reference to position (after_id).
    Insert after_id determines position, not absolute index.
    """
    char_id: CRDTId
    char: str
    after_id: Optional[CRDTId] = None  # Element ID this was inserted after (None = start)
    visible: bool = True
    before_id: Optional[CRDTId] = None

    def __post_init__(self):
        if not isinstance(self.char, str) or len(self.char) != 1:
            raise ValueError("char must contain exactly one Python Unicode code point")
        if not isinstance(self.visible, bool):
            raise ValueError("visible must be a boolean")
        if self.after_id == self.char_id or self.before_id == self.char_id:
            raise ValueError("an element cannot reference itself")
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            "char_id": {"client_id": self.char_id.client_id, "lamport_clock": self.char_id.lamport_clock},
            "char": self.char,
            "after_id": {
                "client_id": self.after_id.client_id,
                "lamport_clock": self.after_id.lamport_clock
            } if self.after_id else None,
            "visible": self.visible,
            "before_id": {
                "client_id": self.before_id.client_id,
                "lamport_clock": self.before_id.lamport_clock
            } if self.before_id else None,
        }
    
    @staticmethod
    def from_dict(d: Dict[str, Any]):
        """Deserialize from dict with robust error handling."""
        try:
            # Validate required fields
            if not isinstance(d, dict):
                raise ValueError(f"Expected dict, got {type(d)}")
            
            if "char_id" not in d:
                raise KeyError("Missing required field: char_id")
            if "char" not in d:
                raise KeyError("Missing required field: char")
            if "visible" not in d:
                raise KeyError("Missing required field: visible")
            
            # Parse char_id
            char_id_dict = d["char_id"]
            if not isinstance(char_id_dict, dict):
                raise ValueError(f"char_id must be dict, got {type(char_id_dict)}")
            if "client_id" not in char_id_dict or "lamport_clock" not in char_id_dict:
                raise KeyError("char_id missing client_id or lamport_clock")
            
            cid = CRDTId(char_id_dict["client_id"], char_id_dict["lamport_clock"])
            
            # Parse optional after_id
            after_cid = None
            if d.get("after_id"):
                after_id_dict = d["after_id"]
                if not isinstance(after_id_dict, dict):
                    raise ValueError(f"after_id must be dict, got {type(after_id_dict)}")
                if "client_id" not in after_id_dict or "lamport_clock" not in after_id_dict:
                    raise KeyError("after_id missing client_id or lamport_clock")
                after_cid = CRDTId(after_id_dict["client_id"], after_id_dict["lamport_clock"])
            before_cid = None
            if d.get("before_id"):
                before_id_dict = d["before_id"]
                if not isinstance(before_id_dict, dict):
                    raise ValueError(f"before_id must be dict, got {type(before_id_dict)}")
                if "client_id" not in before_id_dict or "lamport_clock" not in before_id_dict:
                    raise KeyError("before_id missing client_id or lamport_clock")
                before_cid = CRDTId(before_id_dict["client_id"], before_id_dict["lamport_clock"])
            
            return CRDTElement(char_id=cid, char=d["char"], after_id=after_cid, visible=d["visible"], before_id=before_cid)
        except (KeyError, ValueError, TypeError) as e:
            print(f"[CRDT] Error deserializing element: {e}, data={d}")
            raise
