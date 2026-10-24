"""
c2g — Code 2gether

A peer-to-peer collaborative text editor using Conflict-free Replicated Data Types (CRDT).
All peers are equal - no central server required.
"""

__version__ = "0.1.0"
__author__ = "c2g Contributors"
__license__ = "MIT"

from .crdt import CRDTDocument, CRDTMessage, CRDTElement, CRDTId
from .network import NetworkManager, PeerDiscovery
from .storage import PersistenceManager

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


def __getattr__(name):
    """The legacy Tk editor is intentionally not imported by headless users."""
    if name == "P2PEditor":
        from .ui import P2PEditor
        return P2PEditor
    raise AttributeError(name)
