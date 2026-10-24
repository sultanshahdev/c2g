from contextlib import closing

from c2g.crdt.types import CRDTElement, CRDTId
from c2g.storage.recovered_document import PersistedCrdt


def test_restart_preserves_ids_tombstones_pending_and_clock(tmp_path):
    with closing(PersistedCrdt.create(tmp_path, 'alice')) as saved:
        doc = saved.document
        doc.insert_local_batch('A😀B', 0)
        deleted = doc.delete_local(1)
        unknown = CRDTId('remote', 9)
        doc.delete_remote(unknown)
    with closing(PersistedCrdt.open(tmp_path, 'alice')) as restored:
        again = restored.document
        assert again.get_text() == 'AB' and unknown in again.pending_deletes and not again.elements[deleted].visible
        next_item = again.insert_local('!', 2)
        assert next_item.char_id.lamport_clock > 3
        again.insert_remote(CRDTElement(unknown, 'X'))
        assert again.get_text() == 'AB!'


def test_two_restored_replicas_converge(tmp_path):
    with closing(PersistedCrdt.create(tmp_path, 'a')) as a, closing(PersistedCrdt.create(tmp_path, 'b')) as b:
        a.document.insert_local_batch('hello', 0)
        b.document.apply_full_state(a.document.get_full_state())
        b.document.delete_local(1)
    with closing(PersistedCrdt.open(tmp_path, 'a')) as a, closing(PersistedCrdt.open(tmp_path, 'b')) as b:
        a.document.apply_full_state(b.document.get_full_state())
        b.document.apply_full_state(a.document.get_full_state())
        assert a.document.get_text() == b.document.get_text() == 'hllo'
