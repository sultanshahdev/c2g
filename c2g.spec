# PyInstaller onedir recipe. Run only after `cd web && npm ci && npm run build`.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)
WEB_DIST = ROOT / "web" / "dist"
if not (WEB_DIST / "index.html").is_file():
    raise SystemExit("web/dist/index.html is missing; build the frontend before invoking PyInstaller")

webview_datas = collect_data_files("webview")
webview_hiddenimports = collect_submodules("webview")

a = Analysis(
    [str(ROOT / "scripts" / "frozen_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(WEB_DIST), "web/dist"), (str(ROOT / "LICENSE"), ".")] + webview_datas,
    hiddenimports=webview_hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["tkinter"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="c2g", console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="c2g")
