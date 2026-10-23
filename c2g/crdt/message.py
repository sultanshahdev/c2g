"""
CRDT message protocol for P2P synchronization.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class CRDTMessage:
    """Message for P2P sync."""
    msg_type: str  # INSERT, DELETE, SYNC_REQUEST, FULL_SYNC, BATCH_DELETE
    elements: List[Dict] = field(default_factory=list)
    char_id: Optional[Dict] = None
    char_ids: List[Dict] = field(default_factory=list)  # For batched deletes
    message_id: Optional[str] = None
    
    def to_json(self):
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    def to_dict(self):
        return {
            "msg_type": self.msg_type,
            "elements": self.elements,
            "char_id": self.char_id,
            "char_ids": self.char_ids,
            "message_id": self.message_id
        }
    
    @staticmethod
    def from_json(json_str):
        """Deserialize from JSON string."""
        return CRDTMessage.from_dict(json.loads(json_str))

    @staticmethod
    def from_dict(d):
        if not isinstance(d, dict) or not isinstance(d.get("msg_type"), str):
            raise ValueError("invalid CRDT message")
        return CRDTMessage(
            msg_type=d["msg_type"],
            elements=d.get("elements", []),
            char_id=d.get("char_id"),
            char_ids=d.get("char_ids", []),
            message_id=d.get("message_id")
        )
