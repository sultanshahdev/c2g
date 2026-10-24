import sys
import subprocess

import pytest

from c2g.ui import resources
from c2g.ui.app import DesktopApplication


def test_source_frontend_path_is_repository_relative(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert resources.frontend_directory().name == "dist"
    assert resources.frontend_directory().parent.name == "web"


def test_frozen_frontend_path_uses_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    expected = tmp_path / "web" / "dist" / "index.html"
    expected.parent.mkdir(parents=True); expected.write_text("<!doctype html>", encoding="utf-8")
    assert resources.frontend_index() == expected


def test_missing_frontend_has_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    with pytest.raises(resources.FrontendAssetsMissingError, match="Monaco frontend assets are missing"):
        resources.frontend_index()


def test_production_ui_import_does_not_eagerly_import_legacy_tkinter():
    result = subprocess.run(
        [sys.executable, "-c", "import sys,c2g.ui; print('tkinter' in sys.modules)"],
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.strip() == "False"


def test_default_storage_is_user_specific(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert DesktopApplication("alice").storage_root == tmp_path / ".c2g"
