"""
UI module for P2P collaborative text editor.
"""

from .app import DesktopApplication
from . import styles

__all__ = ["DesktopApplication", "P2PEditor", "styles"]


def __getattr__(name):
    """Keep the Tk compatibility editor opt-in for frozen Monaco builds."""
    if name == "P2PEditor":
        from .editor import P2PEditor
        return P2PEditor
    raise AttributeError(name)
