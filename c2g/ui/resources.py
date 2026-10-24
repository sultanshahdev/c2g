"""Locate immutable frontend resources in source and frozen distributions."""
from __future__ import annotations

import sys
from pathlib import Path


class FrontendAssetsMissingError(RuntimeError):
    """The installed application does not contain the Vite production output."""


def frontend_directory() -> Path:
    """Return the Vite ``dist`` directory without relying on the CWD."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base) / "web" / "dist"
    # c2g/ui/resources.py -> source repository root in development.
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def frontend_index() -> Path:
    index = frontend_directory() / "index.html"
    if not index.is_file():
        raise FrontendAssetsMissingError(
            "Monaco frontend assets are missing. Build them with 'cd web && npm ci && npm run build', "
            "or use an M6 desktop distribution that includes web/dist."
        )
    return index
