from c2g.crdt.types import CRDTElement, CRDTId
from c2g.storage.recovered_document import PersistedCrdt

def test_restart_preserves_ids_tombstones_pending_and_clock(tmp_path):
    saved=PersistedCrdt.create(tmp_path,"alice"); doc=saved.document
    doc.insert_local_batch("A😀B",0); deleted=doc.delete_local(1); unknown=CRDTId("remote",9); doc.delete_remote(unknown); saved.close()
    restored=PersistedCrdt.open(tmp_path,"alice"); again=restored.document
    assert again.get_text()=="AB" and unknown in again.pending_deletes and not again.elements[deleted].visible
    next_item=again.insert_local("!",2); assert next_item.char_id.lamport_clock > 3
    again.insert_remote(CRDTElement(unknown,"X")); assert again.get_text()=="AB!"

def test_two_restored_replicas_converge(tmp_path):
    a=PersistedCrdt.create(tmp_path,"a"); b=PersistedCrdt.create(tmp_path,"b")
    a.document.insert_local_batch("hello",0); b.document.apply_full_state(a.document.get_full_state()); b.document.delete_local(1)
    a.close(); b.close(); a=PersistedCrdt.open(tmp_path,"a"); b=PersistedCrdt.open(tmp_path,"b")
    a.document.apply_full_state(b.document.get_full_state()); b.document.apply_full_state(a.document.get_full_state())
    assert a.document.get_text()==b.document.get_text()=="hllo"
