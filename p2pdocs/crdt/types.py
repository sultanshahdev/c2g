"""
CRDT data types and structures.

This module defines the core data structures for the CRDT implementation:
- CRDTId: Globally unique operation identifier
- CRDTElement: Character element in the CRDT document
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CRDTId:
    """Globally unique operation ID: (client_id, lamport_clock)"""
    client_id: str
    lamport_clock: int
    
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
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            "char_id": {"client_id": self.char_id.client_id, "lamport_clock": self.char_id.lamport_clock},
            "char": self.char,
            "after_id": {
                "client_id": self.after_id.client_id,
                "lamport_clock": self.after_id.lamport_clock
            } if self.after_id else None,
            "visible": self.visible
        }
    
    @staticmethod
    def from_dict(d):
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
            
            return CRDTElement(char_id=cid, char=d["char"], after_id=after_cid, visible=d["visible"])
        except (KeyError, ValueError, TypeError) as e:
            print(f"[CRDT] Error deserializing element: {e}, data={d}")
            raise
