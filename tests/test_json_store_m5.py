import json
from pathlib import Path

import pytest

from c2g.storage.json_store import JsonDocumentStore, StateValidationError


def state():
    first = {"char_id":{"client_id":"replica", "lamport_clock":1}, "char":"😀", "after_id":None, "before_id":None, "visible":False}
    second = {"char_id":{"client_id":"replica", "lamport_clock":2}, "char":"x", "after_id":first["char_id"], "before_id":None, "visible":True}
    return {"format":"c2g-document", "schema_version":1, "document_id":"document", "replica_id":"replica", "document_name":"Unicode", "lamport_clock":2, "elements":[first, second], "pending_deletes":[{"client_id":"missing", "lamport_clock":5}], "applied_ops":["replica:1"], "metadata":{"saved_at":"test"}}


def test_json_state_round_trip_isolated_and_preserves_crdt_records(tmp_path):
    one, two = JsonDocumentStore(tmp_path, "one"), JsonDocumentStore(tmp_path, "two")
    one.save(state())
    assert one.load() == state() and two.load() is None
    assert one.state_path.parent != two.state_path.parent


def test_rejects_invalid_schema_and_duplicate_identity(tmp_path):
    store = JsonDocumentStore(tmp_path, "safe")
    bad = state(); bad["schema_version"] = 2
    with pytest.raises(StateValidationError): store.save(bad)
    bad = state(); bad["elements"].append(dict(bad["elements"][0]))
    with pytest.raises(StateValidationError): store.save(bad)
    with pytest.raises(ValueError): JsonDocumentStore(tmp_path, "../escape")


def test_corrupt_primary_recovers_valid_backup_and_temp_never_commits(tmp_path):
    store = JsonDocumentStore(tmp_path, "safe")
    old, new = state(), state(); new["document_name"] = "new"
    store.save(old); store.save(new)
    store.state_path.write_text("{not-json", encoding="utf-8")
    (store.directory / ".state-abandoned.tmp").write_text("bad", encoding="utf-8")
    assert store.load() == old


def test_both_corrupt_states_fail_without_overwriting(tmp_path):
    store = JsonDocumentStore(tmp_path, "safe")
    store.directory.mkdir(parents=True)
    store.state_path.write_bytes(b"\xff")
    store.backup_path.write_text("{}", encoding="utf-8")
    with pytest.raises(StateValidationError): store.load()
    assert store.state_path.read_bytes() == b"\xff"


def test_failed_save_after_backup_recovery_preserves_valid_backup(tmp_path, monkeypatch):
    import os
    store = JsonDocumentStore(tmp_path, 'recovered')
    old = state()
    store.save(old); store.save(old)
    store.state_path.write_text('{corrupt', encoding='utf-8')
    assert store.load() == old
    replace = os.replace
    def fail_primary(source, target):
        if Path(target) == store.state_path:
            raise OSError('injected final replace failure')
        return replace(source, target)
    monkeypatch.setattr(os, 'replace', fail_primary)
    with pytest.raises(OSError, match='injected'):
        store.save(old)
    assert store.load() == old


def test_cyclic_resume_rejects_without_leaking_writer_or_lock(tmp_path):
    import subprocess
    import sys
    store = JsonDocumentStore(tmp_path, 'cycle')
    value = state()
    value['elements'][0]['after_id'] = value['elements'][1]['char_id']
    store.save(value)
    code = '''
import sys
from c2g.storage.recovered_document import PersistedCrdt
from c2g.storage.json_store import StateValidationError
from c2g.storage.lifecycle import DocumentLock
try:
    PersistedCrdt.open(sys.argv[1], 'cycle')
except StateValidationError:
    pass
else:
    raise AssertionError('cyclic state was accepted')
lock = DocumentLock(__import__('pathlib').Path(sys.argv[1]) / 'documents' / 'cycle')
lock.close()
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
