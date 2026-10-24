"""
UI module for P2P collaborative text editor.
"""

from .app import DesktopApplication
from .editor import P2PEditor  # Explicit legacy entry point; not the default runtime.
from . import styles

__all__ = ['DesktopApplication', 'P2PEditor', 'styles']
