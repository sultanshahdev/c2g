#!/usr/bin/env python3
"""Opt-in Linux GTK/X11 acceptance smoke; uses only disposable storage.

Run from the repository: .venv/bin/python scripts/validate_desktop.py MODE ROOT
MODE is picker, resume, or new. Reuse ROOT for resume. X11 events are synthetic,
not human physical acceptance. Requires the installed desktop dependencies.
"""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['GDK_BACKEND'] = 'x11'
import webview
from c2g.ui.app import DesktopApplication
from c2g.ui.bridge import DesktopBridge
from c2g.ui.resources import frontend_index


def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise AssertionError('native acceptance timed out')


class Keyboard:
    def __init__(self, window):
        self.x = ctypes.CDLL('libX11.so.6')
        self.xt = ctypes.CDLL('libXtst.so.6')
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.display = self.x.XOpenDisplay(None)
        assert self.display, 'X11 display required'
        self.x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x.XStringToKeysym.restype = ctypes.c_ulong
        self.x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.XKeysymToKeycode.restype = ctypes.c_uint
        self.xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.x.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.x.XSetInputFocus(self.display, window.native.get_window().get_xid(), 2, 0)
        self.x.XFlush(self.display)

    def chord(self, *names):
        codes = [self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(name.encode())) for name in names]
        for code in codes:
            self.xt.XTestFakeKeyEvent(self.display, code, 1, 0)
        for code in reversed(codes):
            self.xt.XTestFakeKeyEvent(self.display, code, 0, 0)
        self.x.XFlush(self.display)

    def close(self):
        self.x.XCloseDisplay(self.display)


def main():
    mode, root = sys.argv[1:]
    assert mode in ('picker', 'resume', 'new')
    root = Path(root).resolve()
    # Explicit marker prevents accidental use of a real profile.
    marker = root / '.m7-disposable'
    if mode == 'resume':
        assert marker.is_file(), 'resume requires a profile created by this smoke'
    else:
        root.mkdir(parents=True, exist_ok=True)
        assert not (root / 'documents').exists(), 'new smoke requires an empty profile'
        marker.touch()
    app = DesktopApplication('m7-smoke', listen_port=0, storage_root=root, new=mode == 'new')
    bridge = DesktopBridge(app)
    window = webview.create_window('c2g M7 isolated acceptance', str(frontend_index()), js_api=bridge)
    bridge.attach_window(window)
    errors = []

    def check():
        keyboard = None
        try:
            js = window.evaluate_js
            wait_for(lambda: js("document.querySelector('#picker') !== null && (document.querySelector('#state').textContent !== 'Starting…' || !document.querySelector('#picker').hidden)"))
            if mode != 'new':
                assert js("!picker.hidden && getComputedStyle(picker).display === 'grid'")
                js("document.querySelector('#recent-documents button').click()" if mode == 'resume'
                   else "document.querySelector('#new-document').click()")
            wait_for(lambda: app.controller is not None and js("picker.hidden && getComputedStyle(picker).display === 'none'"))
            assert js("typeof window.c2gApplyRemotePatch === 'function'")
            assert js("(()=>{let r=document.querySelector('#editor').getBoundingClientRect();return !!document.elementFromPoint(r.x+80,r.y+80).closest('#editor')})()")
            assert js("(()=>{let e=document.querySelector('#endpoint'),r=e.getBoundingClientRect();return document.elementFromPoint(r.x+5,r.y+5)===e})()")
            js("document.querySelector('.monaco-editor textarea').focus()")
            keyboard = Keyboard(window)
            before = app.controller.document.get_text()
            keyboard.chord('a')
            wait_for(lambda: app.controller.document.get_text() != before)
            keyboard.chord('Control_L', 'a')
            wait_for(lambda: js("document.querySelector('.monaco-editor textarea').value.length > 0"))
            keyboard.chord('BackSpace')
            wait_for(lambda: app.controller.document.get_text() == '')
            text = 'multiline 😀\nمرحبا e\u0301\n'
            js('document.execCommand("insertText", false, ' + json.dumps(text) + ')')
            wait_for(lambda: app.controller.document.get_text() == text)
            keyboard.chord('Control_L', 'z')
            wait_for(lambda: app.controller.document.get_text() != text)
            keyboard.chord('Control_L', 'y')
            wait_for(lambda: app.controller.document.get_text() == text)
            controller = app.controller
            controller.persisted.flush()
            wait_for(lambda: controller.save_status == 'saved')
            wait_for(lambda: js("document.querySelector('#state').textContent === 'Saved locally'"))
            output = root / 'export.txt'
            assert controller.export(str(output))['accepted']
            assert output.read_text(encoding='utf-8') == text
            original = controller.persisted._autosave._save
            try:
                def fail(_):
                    raise OSError('M7 injected write failure')
                controller.persisted._autosave._save = fail
                controller.persisted.save()
                wait_for(lambda: controller.save_status == 'failed')
                wait_for(lambda: js("document.querySelector('#state').textContent.includes('Save failed')"))
            finally:
                controller.persisted._autosave._save = original
                controller.persisted.save(); controller.persisted.flush()
            js("document.querySelector('#endpoint').value='invalid';document.querySelector('#connect-form').requestSubmit()")
            wait_for(lambda: js("document.querySelector('#state').textContent.includes('IPv4/IPv6')"))
            listeners = __import__('subprocess').check_output(['ss', '-ltnp'], text=True)
            own = [line for line in listeners.splitlines() if f'pid={os.getpid()},' in line]
            assert all(f':{controller.network.port} ' in line or '127.0.0.1:' in line for line in own), own
            assert Path(window._server.root_path) == frontend_index().parent
            from urllib.request import urlopen
            from urllib.error import HTTPError
            try:
                urlopen(window._server.address + '../CONTEXT.md', timeout=2)
            except HTTPError as error:
                assert error.code in (403, 404)
            else:
                raise AssertionError('frontend server allowed parent traversal')
            resources = js("performance.getEntriesByType('resource').map(item=>item.name)")
            assert not any(name.startswith(('http://', 'https://')) and not name.startswith(window._server.address) for name in resources), resources
            print(json.dumps({'native': mode, 'passed': True, 'text': text,
                              'resources': resources, 'input': 'synthetic X11 keyboard + DOM insertion; mouse hit-testing'}), flush=True)
        except Exception as exc:
            print('native text:', repr(app.controller.document.get_text()) if app.controller else None, flush=True); errors.append(repr(exc)); __import__('traceback').print_exc(); print('NATIVE FAIL', mode, repr(exc), flush=True)
        finally:
            if keyboard:
                keyboard.close()
            window.destroy()

    try:
        webview.start(check, gui='gtk', debug=False, http_server=False)
    finally:
        app.shutdown()
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
