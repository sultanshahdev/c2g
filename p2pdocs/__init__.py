"""
P2P CRDT Collaborative Text Editor

A peer-to-peer collaborative text editor using Conflict-free Replicated Data Types (CRDT).
All peers are equal - no central server required.
"""

__version__ = "1.0.14"
__author__ = "Your Name"
__license__ = "MIT"

from .crdt import CRDTDocument, CRDTMessage, CRDTElement, CRDTId
from .network import NetworkManager, PeerDiscovery
from .storage import PersistenceManager
from .ui import P2PEditor

__all__ = [
    'CRDTDocument',
    'CRDTMessage',
    'CRDTElement',
    'CRDTId',
    'NetworkManager',
    'PeerDiscovery',
    'PersistenceManager',
    'P2PEditor',
]
