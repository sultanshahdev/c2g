#!/usr/bin/env python3
"""Build a local PyInstaller onedir desktop distribution after Vite output exists."""
from __future__ import annotations

import subprocess
import sys
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    index = ROOT / "web" / "dist" / "index.html"
    if not index.is_file():
        raise SystemExit("frontend missing: run 'cd web && npm ci && npm run build' first")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(ROOT / "dist"),
               "--workpath", str(ROOT / "build" / "pyinstaller"), str(ROOT / "c2g.spec")]
    subprocess.run(command, cwd=ROOT, check=True)
    application = ROOT / "dist" / "c2g" / ("c2g.exe" if sys.platform == "win32" else "c2g")
    if not application.is_file():
        raise SystemExit(f"PyInstaller completed without expected executable: {application}")
    digest = hashlib.sha256(application.read_bytes()).hexdigest()
    (application.parent / "SHA256SUMS.txt").write_text(f"{digest}  {application.name}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
