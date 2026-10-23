# c2g — Code 2gether

c2g is a peer-to-peer collaborative text editor built with Python, Tkinter,
and a character-based CRDT. It is an early modernization of the MIT-licensed
P2PDocs project; its original Git history and license are retained.

## Status

This repository is in an early modernization stage. The M0 test baseline is
established, but six known CRDT correctness defects remain intentionally marked
as strict expected failures pending M1. It must not be represented as
production-ready.

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

python -m c2g alice
python -m c2g bob 192.168.1.100
```

## Development

```bash
python -m pytest -q
```

The expected M0 baseline is `6 passed, 6 xfailed`. The tests use an in-memory
persistence substitute and do not open Tkinter windows or make network
connections.

## Structure

```text
c2g/
├── crdt/       # RGA-like document, operations, and message types
├── network/    # TCP peer connections and UDP discovery
├── storage/    # asynchronous local state persistence
└── ui/         # Tkinter editor
```

## Compatibility notes

The application currently keeps the historical `~/.p2p_crdt/` persistence
location and existing network message types unchanged. The persisted state is
currently pickle-based; do not load untrusted files. A data/path migration is
deferred to M5, and protocol versioning is deferred to M2.

## Attribution and license

c2g is derived from the original P2PDocs project by Muhammad Taaha and other
P2PDocs contributors: `https://github.com/taaha-0548/P2PDocs`. Original Git
history, copyright notices, and the MIT [LICENSE](LICENSE) are preserved.
