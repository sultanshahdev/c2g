# c2g — Code 2gether

c2g is a peer-to-peer collaborative text editor built with Python, Tkinter,
and a character-based CRDT. It is an early modernization of the MIT-licensed
P2PDocs project; its original Git history and license are retained.

## Status

M5-C persistence integration is implemented, but this remains pre-release:
M5-D packaging and native multi-window verification are outstanding.

## Installation

From a source checkout:

```bash
git clone git@github.com:sultanshahdev/c2g.git
cd c2g
python -m pip install -e '.[test]'
```

No package has been published under the c2g identity.

## Run

```bash
c2g alice
c2g bob 192.168.1.100
c2g alice --new
c2g alice --resume <storage-key>

python -m c2g alice
python -m c2g bob 192.168.1.100
```

## Development

```bash
python -m pytest -q
```

The current automated baseline is `51 passed`.

## Structure

```text
c2g/
├── crdt/       # RGA-like document, operations, and message types
├── network/    # TCP peer connections and UDP discovery
├── storage/    # asynchronous local state persistence
└── ui/         # Tkinter editor
```

## Compatibility notes

Normal startup presents New/Resume selection. Monaco replicas autosave validated
JSON state below `~/.c2g`, show completed save status, and never load legacy
pickle state. Corrupt states are preserved; a validated backup is attempted
before resume fails.

## Attribution and license

c2g is derived from the original P2PDocs project by Muhammad Taaha and other
P2PDocs contributors: `https://github.com/taaha-0548/P2PDocs`. Original Git
history, copyright notices, and the MIT [LICENSE](LICENSE) are preserved.
