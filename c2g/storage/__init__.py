"""
Storage module for document persistence.

This module handles saving and loading CRDT document state to/from disk.
"""

from .persistence import PersistenceManager

__all__ = ['PersistenceManager']
