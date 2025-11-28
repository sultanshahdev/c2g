
# p2pdocs: Peer-to-Peer CRDT Collaborative Editor

[![PyPI version](https://badge.fury.io/py/p2pdocs.svg)](https://badge.fury.io/py/p2pdocs)
[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**p2pdocs** is a modular, production-ready peer-to-peer collaborative text editor built on Conflict-free Replicated Data Types (CRDTs). It requires no central server—every peer is equal. Designed for reliability, extensibility, and easy packaging (PyPI-ready).


## Features

- **True Peer-to-Peer**: No server required; all peers are equal
- **CRDT Synchronization**: RGA (Replicated Growable Array) for conflict-free merging
- **Real-Time Collaboration**: Instant sync across all connected peers
- **Automatic Peer Discovery**: UDP broadcast for LAN detection
- **Manual Peer Connections**: Connect via IP address
- **Modular Codebase**: Clean separation (CRDT, networking, storage, UI)
- **Modern Tkinter UI**: Professional, minimal interface
- **Persistent State**: Document autosave and recovery
- **Batch Operations**: Efficient bulk insert/delete
- **PyPI Packaging**: Easy install and upgrade


## Installation

### From PyPI
```bash
pip install p2pdocs
```

### From Source
```bash
git clone https://github.com/taaha-0548/P2PDocs
cd p2pdocs
pip install -e .
```


## Quick Start

### CLI Usage
```bash
# Start with automatic peer discovery
p2pdocs alice

# Or connect directly to a peer
p2pdocs bob 192.168.1.100
```

### Python Module
```bash
python -m p2pdocs alice
python -m p2pdocs bob 192.168.1.100
```

### Programmatic Usage
```python
from p2pdocs.ui.editor import P2PEditor
editor = P2PEditor(username="alice", peer_ip="192.168.1.100")
editor.run()
```


## Version

**Current Version:** 1.0.14  
**Dependencies:** None (Python 3.7+ stdlib only)


## Code Structure

```
p2pdocs/
├── crdt/         # CRDT logic (types, document, message)
├── network/      # TCP/UDP peer discovery & sync
├── storage/      # Persistence manager
├── ui/           # Tkinter editor & styles
├── __main__.py   # CLI entry point
├── cli.py        # CLI logic
```


## Architecture Overview

**CRDT (RGA Algorithm):**
- `CRDTId`: Unique operation ID `(client_id, lamport_clock)`
- `CRDTElement`: Character, ID, tombstone flag
- `CRDTDocument`: State machine, merge logic, topological sort

**Networking:**
- `NetworkManager`: TCP peer connections, message sync
- `PeerDiscovery`: UDP LAN peer detection

**Persistence:**
- `PersistenceManager`: Async disk I/O

**UI:**
- `P2PEditor`: Tkinter GUI, event handling


## Why CRDT?

| Aspect                | OT (Old)   | CRDT (New) |
|-----------------------|------------|------------|
| Central server        | Required   | ❌ Not needed |
| Transformation logic  | Complex    | Simple |
| Concurrent ops        | Fragile    | Safe |
| Merge order           | Critical   | Automatic |
| Convergence           | Assumed    | **Proven** |
| Multi-peer            | Difficult  | Natural |


## How RGA Works

Each character is assigned a unique ID `(client_id, lamport_clock)`. Deletions create tombstones (hidden, not removed), so positions never shift. All peers converge automatically.

**Example:**
```
Alice types "H" at pos 0 → ID = (alice-uuid, 1)
Bob types "i" at pos 0  → ID = (bob-uuid, 1)
Result (sorted by ID): "Hi"  ✅ All peers converge!
```


## Thread Safety

```
Main Thread (Tkinter)          Network Thread
     ↓                            ↓
   _on_keystroke()          _recv_message()
     ↓                            ↓
  doc.insert_local()         doc.insert_remote()
     ↓                            ↓
 [doc.lock]◄────────────────[doc.lock]
     ↓                            ↓
  _rebuild_text()            root.after(0, _rebuild_text)
```

**Protected Resources:**
- `doc.elements` — protected by `doc.lock`
- `text` widget — protected by `text_lock`


## Message Protocol

```json
{
   "type": "INSERT",
   "elements": [
      {
         "char_id": {"client_id": "uuid", "lamport_clock": 5},
         "char": "A",
         "visible": true
      }
   ]
}
```

Supported messages:
- `INSERT` — new character
- `DELETE` — mark as tombstone
- `SYNC_REQUEST` — request full state
- `FULL_SYNC` — send all elements


## Testing

1. **Type and see sync:**
   - Alice: type "hello"
   - Bob: instantly sees "hello"
2. **Concurrent edits:**
   - Both type at the same position
   - Automatic convergence
3. **Deletions:**
   - Backspace creates tombstones
   - All peers update instantly
4. **Multi-line:**
   - Newlines and text wrapping sync correctly


## Limitations

- Single connection (1 server ↔ 1 client)
- No multi-peer mesh yet
- No undo/redo support


## Roadmap

- [ ] Multi-peer mesh networking
- [ ] Advanced disk persistence
- [ ] Operation batching
- [ ] Compression
- [ ] Snapshots & garbage collection
- [ ] Rich text formatting
- [ ] Presence/cursor awareness
- [ ] Offline support


## License

MIT License — see LICENSE file for details.

## License

MIT License - see LICENSE file for details.


---

**Status:** Production-Ready (Single Peer)
**Python:** 3.7+
**Dependencies:** None (stdlib only)
