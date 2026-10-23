"""
Network module for P2P communication.

This module handles all networking aspects:
- TCP connections between peers
- UDP peer discovery
- Message broadcasting
"""

from .manager import NetworkManager
from .discovery import PeerDiscovery

__all__ = ['NetworkManager', 'PeerDiscovery']
