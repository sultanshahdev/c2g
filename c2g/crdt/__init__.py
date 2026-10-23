"""
CRDT (Conflict-free Replicated Data Type) module.

This module implements RGA (Replicated Growable Array) for collaborative text editing.
"""

from .types import CRDTId, CRDTElement
from .message import CRDTMessage
from .document import CRDTDocument

__all__ = ['CRDTId', 'CRDTElement', 'CRDTMessage', 'CRDTDocument']
