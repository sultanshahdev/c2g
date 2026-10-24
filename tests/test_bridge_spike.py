import pytest

from c2g.ui.bridge_spike import BridgeController, codepoint_to_utf16, incremental_patch, utf16_to_codepoint


def tx(identifier, version, *changes):
    return {"transaction_id": identifier, "base_version": version, "changes": list(changes)}


def change(offset, length, text):
    return {"rangeOffset": offset, "rangeLength": length, "text": text}


def test_utf16_conversion_handles_emoji_combining_and_multiline():
    text = "A😀e\u0301\nسلام"
    assert codepoint_to_utf16(text, 2) == 3
    assert utf16_to_codepoint(text, 3) == 2
    with pytest.raises(ValueError): utf16_to_codepoint(text, 2)
    assert utf16_to_codepoint(text, codepoint_to_utf16(text, len(text))) == len(text)


def test_transactions_cover_start_middle_end_replace_and_duplicate():
    bridge = BridgeController("bridge-test")
    first = bridge.apply_local_transaction(tx("a", 1, change(0, 0, "AB")))
    assert first["text"] == "AB"
    second = bridge.apply_local_transaction(tx("b", 2, change(1, 0, "😀")))
    assert second["text"] == "A😀B"
    replacement = bridge.apply_local_transaction(tx("c", 3, change(1, 2, "X\n")))
    assert replacement["text"] == "AX\nB"
    assert bridge.apply_local_transaction(tx("c", 3, change(1, 2, "X\n")))["duplicate"]


def test_multi_edit_stale_rejection_and_incremental_remote_patch():
    bridge = BridgeController("multi-test")
    assert bridge.apply_local_transaction(tx("a", 1, change(0, 0, "abcd")))["accepted"]
    # Monaco offsets are pre-change offsets: replace b and d in one event.
    result = bridge.apply_local_transaction(tx("b", 2, change(1, 1, "X"), change(3, 1, "Y")))
    assert result["text"] == "aXcY"
    assert not bridge.apply_local_transaction(tx("stale", 2, change(0, 0, "!")))["accepted"]
    remote = bridge.apply_remote_text("a😀\n")
    assert remote["patch"]["offset"] == 1
    assert bridge.document.get_text() == "a😀\n"


def test_large_unicode_multiline_transaction_reaches_crdt():
    bridge = BridgeController("large-test")
    payload = ("😀alpha\n" * 1429)  # 10,003 Python code points
    result = bridge.apply_local_transaction(tx("large", 1, change(0, 0, payload)))
    assert result["accepted"] and bridge.document.get_text() == payload


def test_patch_is_contiguous_and_does_not_require_full_reset():
    assert incremental_patch("ab😀cd", "abXcd") == {"offset": 2, "length": 2, "text": "X"}
