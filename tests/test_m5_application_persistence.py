import time
import subprocess
import sys

import pytest

from c2g.storage.lifecycle import DocumentInUseError
from c2g.storage.recovered_document import PersistedCrdt
from c2g.ui.controller import ApplicationController
from c2g.ui.app import DesktopApplication


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError("timed out")


def tx(identifier, version, offset, length, text):
    return {"transaction_id": identifier, "base_version": version,
            "changes": [{"rangeOffset": offset, "rangeLength": length, "text": text}]}


def test_controller_autosaves_resume_and_preserves_replica(tmp_path):
    saved = PersistedCrdt.create(tmp_path, "alice")
    replica, document_id = saved.replica_id, saved.document_id
    controller = ApplicationController("alice", 0, persisted=saved)
    try:
        assert controller.apply_local_transaction(tx("one", 1, 0, 0, "line one\nline two"))["accepted"]
    finally:
        controller.shutdown()
    restored = PersistedCrdt.open(tmp_path, "alice")
    try:
        assert restored.replica_id == replica and restored.document_id == document_id
        assert restored.document.get_text() == "line one\nline two"
        assert restored.document.insert_local("!", len(restored.document.get_text())).char_id.client_id == replica
    finally:
        restored.close()


def test_same_saved_replica_is_exclusive_and_released(tmp_path):
    one = PersistedCrdt.create(tmp_path, "one")
    with pytest.raises(DocumentInUseError): PersistedCrdt.open(tmp_path, "one")
    other = PersistedCrdt.create(tmp_path, "two")
    other.close(); one.close()
    reopened = PersistedCrdt.open(tmp_path, "one"); reopened.close()


def test_linux_cross_process_lock_contention(tmp_path):
    saved = PersistedCrdt.create(tmp_path, "shared"); saved.close()
    code = ("import sys,time; from c2g.storage.recovered_document import PersistedCrdt; "
            "d=PersistedCrdt.open(sys.argv[1], 'shared'); print('locked', flush=True); time.sleep(1); d.close()")
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(DocumentInUseError): PersistedCrdt.open(tmp_path, "shared")
    finally:
        child.wait(timeout=3)
    reopened = PersistedCrdt.open(tmp_path, "shared"); reopened.close()


def test_joined_document_identity_survives_restart(tmp_path):
    alice_saved = PersistedCrdt.create(tmp_path, "alice")
    alice_document_id = alice_saved.document_id
    bob_saved = PersistedCrdt.create(tmp_path, "bob")
    alice = ApplicationController("alice", 0, persisted=alice_saved, start_network=True, start_discovery=False)
    bob = ApplicationController("bob", 0, persisted=bob_saved, start_network=True, start_discovery=False)
    try:
        assert bob.connect(f"127.0.0.1:{alice.network.port}")["accepted"]
        wait_for(lambda: bob.document_id == alice.document_id)
    finally:
        alice.shutdown(); bob.shutdown()
    restored = PersistedCrdt.open(tmp_path, "bob")
    try:
        assert restored.document_id == alice_document_id
    finally:
        restored.close()


def test_picker_lists_documents_and_rejects_bad_key(tmp_path):
    app = DesktopApplication("alice", storage_root=tmp_path)
    assert app.create_document("Notes")["accepted"]
    app.shutdown()
    assert app.recent_documents()[0]["name"] == "Notes"
    another = DesktopApplication("alice", storage_root=tmp_path)
    assert not another.resume_document("../bad")["accepted"]
