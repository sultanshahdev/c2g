# c2g — Code 2gether

c2g is a peer-to-peer collaborative text editor built with Python, Monaco,
pywebview, and a character-based CRDT. It is an early modernization of the MIT-licensed
P2PDocs project; its original Git history and license are retained.

## Status

M7 validation is **G6 PARTIAL**: 68 Python tests and 100 deterministic
three-replica seeds pass; Ubuntu GTK source and frozen native automation pass.
This remains a pre-release Linux acceptance candidate. Windows desktop builds,
Docker execution, physical-LAN discovery, and complete human GUI acceptance
remain unverified. See [M7 validation report](docs/M7_FINAL_VALIDATION_REPORT.md).
No public release has been approved.

## Installation

From a source checkout:

```bash
git clone git@github.com:sultanshahdev/c2g.git
cd c2g
python -m pip install -e '.[test]'
```

No package has been published under the c2g identity.

Requires Python 3.12 or later. The CRDT, network, and JSON storage layers have
no GUI dependency. For the source-tree desktop host, install
`python -m pip install -e '.[desktop]'` plus pywebview's platform renderer
prerequisites (a supported GTK/WebKitGTK stack on Ubuntu; WebView2 on Windows).
Those native dependencies are deliberately not required for headless testing.
Build the local assets before source desktop launch (Node 24 was validated):

```bash
cd web
npm ci
npm run build
cd ..
```

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

The current automated baseline is `68 passed`, including 100 deterministic
three-replica convergence seeds (0–99).

## Structure

```text
c2g/
├── crdt/       # RGA-like document, operations, and message types
├── network/    # TCP peer connections and UDP discovery
├── storage/    # asynchronous local state persistence
└── ui/         # Monaco/pywebview desktop host; legacy Tk compatibility
```

## Compatibility notes

Normal startup presents New/Resume selection. Monaco replicas autosave validated
JSON state below `~/.c2g`, show completed save status, and never load legacy
pickle state. Corrupt states are preserved; a validated backup is attempted
before resume fails.

The persisted format is JSON schema v1. Each local storage key has a
cross-process advisory ownership lock; distinct local replicas of the same
shared document use distinct keys. Autosave coalesces complete snapshots and
flushes at normal shutdown; save failures retain in-memory content and are
reported in the UI.

## Packaging

`pyproject.toml` is canonical. Build artifacts with `python -m build` and
validate them with `twine check dist/*`. Wheel installations provide the
headless core and CLI. Monaco `web/dist` assets are not yet bundled in wheels,
so a wheel-installed desktop launch gives a clear missing-assets diagnostic;
the onedir distribution below includes those assets.

## Desktop onedir build

Install the desktop build extra, build the local frontend, then create a
platform-native onedir folder:

```bash
python -m pip install -e '.[desktop-build]'
cd web && npm ci && npm run build && cd ..
python scripts/build_desktop.py
```

The executable is `dist/c2g/c2g` on Linux and `dist/c2g/c2g.exe` on Windows.
The build embeds `web/dist` under its internal resources, including Monaco
workers, and writes `SHA256SUMS.txt` beside the executable. It keeps user JSON
documents in `~/.c2g` (or `C2G_STORAGE_ROOT`), never inside the distribution.
Keep the complete `dist/c2g` folder intact, including `_internal`; copying only
the executable will not work. On Linux, launch from any working directory:

```bash
/path/to/c2g/c2g alice --new
```

For an isolated acceptance profile use `C2G_STORAGE_ROOT=/path/to/disposable-profile`.
`--listen-port 0` allocates an ephemeral TCP port for same-machine checks;
manual peers must use the actual chosen IP:port. Resume uses the saved directory
key: `c2g alice --resume STORAGE_KEY`.

The verified target is Ubuntu 24.04.4 x86_64 with GTK/WebKitGTK 2.52.6 and X11.
Compatible system GTK/WebKitGTK libraries are required; other Linux distributions
and Wayland are not fully qualified. Windows/WebView2 builds are configured but
**NOT VERIFIED** and are not a supported-platform claim. Build output must be
produced and tested on its target platform. The executable checksum is in
`SHA256SUMS.txt`; it does not cover every onedir resource.

For headless protocol/persistence simulation, run
`python -m pytest -q tests/test_m6_headless_peers.py`. `Dockerfile.tests`
provides the same loopback-only suite; it does not validate native GUI behavior
or physical-LAN UDP discovery.

M6 pins DOMPurify 3.4.17 and routes Monaco's embedded sanitizer import to that
audited runtime during Vite builds. This is verified in the shipped bundle; do
not remove the Vite resolver without separately validating Monaco's sanitizer.

## Network and offline limits

Protocol v2 is for trusted LANs only: peer traffic is unauthenticated and
unencrypted. Do not expose peer/discovery ports to the Internet; connected
peers receive and can modify the selected document. Nonempty unrelated documents
are rejected rather than automatically merged. Physical-LAN discovery remains
unverified; the M7 report provides the two-machine procedure.

The frontend and Monaco worker are bundled and need no CDN. pywebview serves
these assets on a random **127.0.0.1-only** HTTP port, rooted at the bundled
`web/dist`; user JSON documents are stored separately. The intentional P2P TCP
listener binds non-loopback interfaces. No central service is required.

## Attribution and license

c2g is derived from the original P2PDocs project by Muhammad Taaha and other
P2PDocs contributors: `https://github.com/taaha-0548/P2PDocs`. Original Git
history, copyright notices, and the MIT [LICENSE](LICENSE) are preserved.
