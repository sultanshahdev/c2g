# M6 Release Tooling and Headless Simulation Report

## Summary

M6 adds a reproducible PyInstaller onedir recipe, bundled Vite resources, a
headless three-peer simulation, a Docker test-image definition, and CI build
configuration. It does not publish artifacts or begin M7.

## Build architecture

Vite retains relative (`./`) URLs, so local pywebview file loading needs no CDN,
Node process, or frontend HTTP listener at runtime. `c2g.ui.resources` resolves
source execution to `web/dist` and frozen execution to
`sys._MEIPASS/web/dist`, independent of CWD. Missing resources have an
actionable error. `c2g.spec` packages the complete tree, pywebview hook data,
and license; `scripts/frozen_entry.py` imports the package before the CLI;
`scripts/build_desktop.py` produces a SHA-256 manifest.

## Linux outcome

`./.venv/bin/python scripts/build_desktop.py` completed with PyInstaller
6.22.3, Python 3.12.3, and GTK pywebview hooks. Extracted onedir size: **363
MB**. Bundled Vite assets: **14 MB**, 96 files, including `index.html` and
`editor.worker-CRz__AKW.js`. PyInstaller log timing was **34.2 s**. The
executable passed `--help` from `/tmp`; checksum:
`a30355eb21076c50dedda88dab1994c2cf175307d509fe0f9ba55090f0ffb3ed`
for `c2g`, also stored in ignored `dist/c2g/SHA256SUMS.txt`.

A disposable-profile frozen native launch reached GTK/pywebview (and did not
report a missing frontend asset) but timed out after GTK native-property
warnings, so it could not support reliable interactive assertions. Frozen
New/Resume, autosave, dialogs, and peer workflow are **NOT EXECUTED**.
GTK/WebKitGTK system libraries remain prerequisites; this Ubuntu build is not
claimed portable to every Linux distribution.

## Windows outcome

The same spec and a `windows-latest` CI build job are configured to check
`c2g.exe`, HTML, worker assets, and checksum before artifact upload. The
workflow has not run remotely: Windows build/WebView2 GUI behavior is
**CONFIGURED / NOT VERIFIED**. WebView2 is a documented host prerequisite.

## Headless simulation and Docker

`tests/test_m6_headless_peers.py` uses real persisted controllers and protocol
v2 on ephemeral ports: three-peer chain/cycle, deduplication, reconnect full
sync, offline insert/delete reconciliation, and tombstones. Existing M2/M5
tests cover malformed frames, two-peer recovery, autosave, and locking.

`Dockerfile.tests` runs this headless set only. Docker access was denied for
`/var/run/docker.sock`, so Docker execution is **CONFIGURED / NOT EXECUTED**;
it cannot prove physical-LAN UDP discovery in any event.

## CI, security, and handoff

The CI workflow has a least-privilege Python/frontend test job and Linux/Windows
desktop-build matrix that uploads checksummed onedir artifacts without release
publication. It is **CONFIGURED / NOT VERIFIED** remotely.

Monaco 0.57.0 is the current registry release and embeds its own DOMPurify
3.4.15 source at `esm/vs/base/browser/dompurify/dompurify.js`; a lockfile
override alone therefore would not remediate the shipped runtime. M6 pins and
overrides DOMPurify to **3.4.17**, then uses a narrowly scoped Vite resolver to
replace only Monaco's embedded sanitizer import with
`node_modules/dompurify/dist/purify.es.mjs`. This leaves Monaco itself at 0.57.0
and preserves its sanitizer API.

After a clean `npm ci`, `npm ls` resolves Monaco and DOMPurify to 0.57.0 and
3.4.17 respectively; `npm audit --omit=dev` reports **0 vulnerabilities**.
The production `dist/assets/index-*.js` contains the `3.4.17` version marker
and no `3.4.15` marker, proving that Vite used the replacement rather than
Monaco's embedded source. `npm run build` completed and retained the Monaco
editor worker. This resolves the known critical DOMPurify advisory for the
shipped Vite bundle. Native renderer behavior is still unverified, and future
Monaco upgrades must retain or revisit the explicit resolver path.

## Final local verification

`./.venv/bin/python -m pytest -q` completed **61 passed**. `cd web && npm run
build` completed successfully. The existing Linux onedir artifact still
contains `dist/c2g/c2g`, `_internal/web/dist/index.html`, and Monaco's
`assets/ts.worker-DIAQkoB3.js`; its size is **363 MB**. Running `sha256sum -c
SHA256SUMS.txt` from `dist/c2g` returned `c2g: OK`, and launching the binary's
`--help` from `/tmp` succeeded. No PyInstaller rebuild was needed because
packaged Python and required assets were unchanged.

## Pre-G6 gate and M7 handoff

**Pre-G6: PARTIAL.** Implemented and locally verified: source/frozen resource
resolution, Linux onedir construction and checksum, Monaco asset bundling and
DOMPurify remediation, headless persisted three-peer convergence/reconnect/state
preservation, and frontend build. Configured but not executed: Docker, Windows
CI/build, and physical-LAN discovery. Native Linux GTK/pywebview remains
non-interactive and timed out, so native frozen New/Resume, autosave, dialogs,
and peer UI behavior are unverified. M7 must obtain actual Windows, Docker,
physical-LAN, and interactive native-GUI evidence; it must not treat this report
as release approval.

**Pre-G6: PARTIAL.** Linux construction/resource/CLI verification and headless
simulation pass. M7 needs native frozen GUI validation, actual Windows build,
Docker execution, physical-LAN evidence, and security-risk resolution.
