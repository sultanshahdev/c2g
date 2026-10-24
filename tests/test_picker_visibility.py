"""Exercise the real CSS cascade without adding a frontend test framework."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_picker_hidden_attribute_controls_display(tmp_path):
    chrome = next((str(p) for p in (
        Path('/opt/google/chrome/chrome'),
        Path(shutil.which('chromium') or '/nonexistent'),
        Path(shutil.which('google-chrome') or '/nonexistent'),
    ) if p.is_file()), None)
    if chrome is None:
        pytest.skip('Chrome/Chromium is required for the CSS cascade regression')
    root = Path(__file__).resolve().parents[1] / 'web'
    html = (root / 'index.html').read_text()
    html = html.replace('<head>', '<head><style>' + (root / 'src/style.css').read_text() + '</style>')
    html = html.replace('<script type="module" src="/src/main.js"></script>', '''<script>
    const picker = document.getElementById('picker');
    const states = [];
    const capture = () => states.push([picker.hidden, getComputedStyle(picker).display]);
    capture(); // --new: initially hidden
    picker.hidden = false; capture(); // selection required
    picker.hidden = true; capture(); // New/Resume accepted
    document.body.dataset.pickerPass = JSON.stringify(states) ===
      JSON.stringify([[true, 'none'], [false, 'grid'], [true, 'none']]);
    </script>''')
    page = tmp_path / 'picker.html'
    page.write_text(html)
    result = subprocess.run(
        [chrome, '--headless', '--no-sandbox', '--disable-gpu',
         f'--user-data-dir={tmp_path / "chrome"}', '--dump-dom', page.as_uri()],
        capture_output=True, text=True, timeout=30, check=True,
    )
    assert 'data-picker-pass="true"' in result.stdout, result.stdout + result.stderr
