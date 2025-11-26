# P2P CRDT Collaborative Text Editor

[![PyPI version](https://badge.fury.io/py/p2pdocs.svg)](https://badge.fury.io/py/p2pdocs)
[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A peer-to-peer collaborative text editor using **Conflict-free Replicated Data Types (CRDT)**. No central server required - all peers are equal!

## Features

- **True P2P Architecture**: No server needed, all peers are equal
- **CRDT Synchronization**: Uses RGA (Replicated Growable Array) for conflict-free merging
- **Real-time Collaboration**: Changes sync instantly across all connected peers
- **Automatic Peer Discovery**: UDP broadcast for LAN peer detection
- **Manual Connections**: Connect to peers via IP address
- **Modern UI**: Clean, professional Tkinter interface
- **Persistent State**: Document state saved to disk
- **Batch Operations**: Optimized bulk delete/insert operations

## Installation

### From PyPI (when published)

```bash
pip install p2pdocs
```

### From Source

```bash
git clone https://github.com/yourusername/p2pdocs.git
cd p2pdocs
pip install -e .
```

## Usage

### Start the Editor

```bash
# Start with automatic peer discovery
p2pdocs alice

# Or connect directly to a peer
p2pdocs bob 192.168.1.100
```

### Alternative (as Python module)

```bash
python -m p2pdocs alice
python -m p2pdocs bob 192.168.1.100
```

### Programmatic Usage

```python
from p2pdocs import P2PEditor

# Create and run editor
editor = P2PEditor(username="alice", peer_ip="192.168.1.100")
editor.run()
```

## Version

**Current Version: 1.0.14**
✅ **Zero Dependencies** — Python 3.8+ stdlib only  

## Quick Start

### Terminal 1: Start Server (Alice)
```bash
python p2p_crdt_editor.py server alice
```
Output:
```
[alice] Listening on port 5000...
```

### Terminal 2: Start Client (Bob)
```bash
python p2p_crdt_editor.py client bob 127.0.0.1
```
Output:
```
[bob] Connecting to 127.0.0.1:5000...
[bob] Connected to alice
```

### Start Editing
- **Alice types** → Bob sees it instantly
- **Bob types** → Alice sees it instantly
- Both type simultaneously → **automatic convergence**

## Architecture

See [CRDT_ARCHITECTURE.md](./CRDT_ARCHITECTURE.md) for detailed design:

- **CRDTId**: Unique operation identifier `(client_id, lamport_clock)`
- **CRDTElement**: Character + ID + visibility flag
- **CRDTDocument**: CRDT state machine with merge logic
- **NetworkManager**: TCP peer connection handler
- **P2PEditor**: GUI + orchestration layer

## Why CRDT?

| Aspect | Operational Transform (Old) | CRDT (New) |
|--------|-------|--------|
| Central server | Required | ❌ Not needed |
| Transformation logic | Complex | Simple |
| Concurrent ops | Fragile | Guaranteed safe |
| Merge order | Critical | Automatic |
| Convergence | Assumed | **Proven** |
| Multi-peer | Difficult | Natural |

## How RGA Works

Each character gets a **unique ID**: `(client_id, lamport_clock)`

**Example:**
```
Alice types "H" at pos 0 → ID = (alice-uuid, 1)
Bob types "i" at pos 0  → ID = (bob-uuid, 1)

Result (sorted by ID): "Hi"  ✅ All peers converge!
```

Deletions create **tombstones** (not removed), so positions never shift.

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
   - Alice types at pos 0
   - Bob types at pos 0 simultaneously
   - Both converge to same text

3. **Deletions:**
   - Alice presses backspace
   - Bob sees character disappear
   - Text remains consistent

4. **Multi-line:**
   - Type newlines, text wraps correctly
   - All peers sync properly

## Limitations

- Single connection (1 server ↔ 1 client)
- No persistence (resets on restart)
- No multi-peer mesh yet
- No undo/redo support

## Future Work

- [ ] Multi-peer mesh networking
- [ ] Disk persistence
- [ ] Operation batching
- [ ] Compression
- [ ] Snapshots + garbage collection
- [ ] Rich text formatting
- [ ] Presence awareness (cursor position)
- [ ] Offline support

## Code Structure

```
p2p_crdt_editor.py (570 lines)
├── CRDTId ......................... Unique operation ID
├── CRDTElement .................... Char + metadata
├── CRDTDocument ................... State machine
├── NetworkManager ................. TCP networking
└── P2PEditor ...................... GUI + orchestration
```

## License

MIT License - see LICENSE file for details.

---

**Status**: ✅ Production-Ready (Single Peer)  
**Python**: 3.8+  
**Dependencies**: None (stdlib only)
