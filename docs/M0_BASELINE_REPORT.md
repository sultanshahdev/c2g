# c2g M0 Baseline Report

## A. Environment

- The supplied directory initially had no `.git` directory. M0 recovery safely
  initialized `main`, added the verified original remote, fetched `origin/main`, and
  populated the index from `5bf7a3b` using a mixed reset only (no working-tree
  overwrite, commit, or push). M0 files remain uncommitted.
- OS: Linux `khadija`, kernel `7.0.0-38-generic` (Ubuntu 24.04-derived), x86_64.
- Python: 3.12.3. The existing virtual environment is `.venv`.
- Package: `c2g 0.1.0`, installed editable from the supplied directory.
- Test dependency: pytest 8.x, declared as `pytest>=7,<9` in the `test` extra.
- Graphify: 0.9.59 installed. `graphify extract . --code-only --no-cluster`
  produced ignored `graphify-out/graph.json` (155 nodes, 294 edges at initial
  extraction; refreshed after test additions); `graphify codex install` added
  its managed `AGENTS.md` section and ignored local `.codex/hooks.json` hook.
- The three planning documents are restored under `docs/`. Their active c2g
  project/package paths and milestone status were aligned during final M0
  validation. `docs/MODERNIZATION_RESEARCH.md` is explicitly retained as a
  historical P2PDocs archive-evidence record; original P2PDocs attribution,
  source paths, Git history, and MIT licensing remain intact.

Core imports succeeded headlessly:
`from c2g.crdt.document import CRDTDocument` and
`from c2g.crdt.types import CRDTId, CRDTElement`. The console entry point is
`c2g = c2g.cli:main`; invoking it requires a username and then starts
the Tkinter application, so it was not used as a headless test command.

## B. Baseline Tests

| Test | Expected | Actual | Result | Relevant File |
|---|---|---|---|---|
| BASIC-01 | empty text | `""` | pass | `document.py` |
| BASIC-02 | sequential append | `"AB"` | pass | `document.py` |
| BASIC-03 | remote insert | `"A"` | pass | `document.py` |
| BASIC-04 | duplicate ignored | one `A` | pass | `document.py` |
| BASIC-05 | local delete | `""` | pass | `document.py` |
| BASIC-06 | element round trip | equivalent element | pass | `types.py` |
| REG-01 | `AXB` | `ABX` | strict xfail | `document.py` |
| REG-02 | `XAB` | `ABX` | strict xfail | `document.py` |
| REG-03 | replicated delete | delete rejected; target `A` | strict xfail | `document.py` |
| REG-04 | delayed insert hidden | target `A` | strict xfail | `document.py` |
| REG-05 | `BH` | `HB` | strict xfail | `document.py` |
| REG-06 | merged tombstone hidden | target `A` | strict xfail | `document.py` |

## C. Confirmed Defects

- `test_reg_01_insertion_in_the_middle`: A, B, then X at visual index 1 gives
  `ABX`, not `AXB`. `_get_sorted_visible_elements()` sorts siblings by CRDT ID
  and depth-first traversal does not preserve the requested sequential middle
  position. M1.
- `test_reg_02_insertion_at_the_beginning`: A, B, then X at index 0 gives
  `ABX`, not `XAB`; head ID ordering places the later element after existing
  heads. M1.
- `test_reg_03_full_state_then_remote_delete`: `apply_full_state()` records an
  element's insertion ID in `applied_ops`; `delete_remote()` treats the same
  key as an already processed deletion. M1.
- `test_reg_04_delete_before_insert_is_retained`: `delete_remote()` records an
  unknown deletion but `insert_remote()` never consults that state, so a later
  separately serialized insert becomes visible. M1.
- `test_reg_05_tombstone_preserves_descendant_order`: visible-only traversal
  treats a descendant of an invisible predecessor as a head. The crafted RGA
  order should be `BH`, but is `HB`. M1.
- `test_reg_06_full_state_merge_does_not_resurrect_tombstone`: an existing
  visible element's key prevents a subsequent tombstone representation from
  replacing it in `apply_full_state()`. M1.

## D. Testing Infrastructure

`tests/conftest.py` replaces only `c2g.crdt.document.PersistenceManager`
with a minimal in-memory double before documents are constructed. This avoids
`~/.p2p_crdt/`, pickle loading, persistence threads, sockets, and Tk windows.
Replicas get distinct peer IDs. Run `python -m pytest -q`; CI uses the same
command after `python -m pip install -e '.[test]'`. Strict xfails keep known M1
defects visible while still failing CI on any unexpected failure or xpass.

## E. Files Changed

- `AGENTS.md`, `CONTEXT.md`, `.gitignore`, `pyproject.toml`
- `.github/workflows/tests.yml`
- `tests/conftest.py`, `tests/test_crdt_basics.py`, `tests/test_crdt_regressions.py`
- `docs/M0_BASELINE_REPORT.md`

Ignored generated local artifacts: `graphify-out/` and `.codex/hooks.json`.

No production source files changed.

## F. Verification

Executed:

```text
./.venv/bin/python --version                                 # Python 3.12.3
./.venv/bin/python -m pip show c2g pytest                    # editable c2g; pytest installed
./.venv/bin/python -m pytest -q --runxfail tests/test_crdt_regressions.py
                                                               # 6 failed as strict defect probes
./.venv/bin/python -m pytest -q                               # 6 passed, 6 xfailed
./.venv/bin/python -c "import c2g"                           # headless import succeeds
git init -b main; git fetch origin main --no-tags              # recovered upstream history safely
git reset --mixed origin/main                                  # indexed baseline; working tree preserved
graphify --version                                             # graphify 0.9.59
graphify extract . --code-only --no-cluster                   # local AST graph generated
graphify query "M0 baseline test harness CRDTDocument README package identity"
                                                               # scoped graph consulted for final validation
```

## G. Technical Decisions

Confirmed for M0: pytest is the minimal harness; test persistence is replaced
at the module seam; confirmed defects use strict xfails; Graphify output stays
untracked. Pending M1 approval: ordering/traversal invariants, missing
predecessor buffering, delete-before-insert retention, tombstone retention,
separate operation deduplication, monotonic full-state merge, persisted replica
and document identity, and versioned network/persistence formats.

## H. c2g Migration and Attribution

The package was Git-renamed from `p2pdocs/` to `c2g/`, with the `c2g` console
script and `python -m c2g` module entry point. Human-facing branding is now
“c2g — Code 2gether”; packaging metadata is independently versioned as `0.1.0`
and points to `https://github.com/sultanshahdev/c2g`.

The repository root is `/home/sultan/Desktop/repos/c2g`; it has exactly one
`.git` directory and `main`
still reaches historical commit `5bf7a3b`. Both fetch and push URLs for the
sole `origin` remote are `git@github.com:sultanshahdev/c2g.git`. No migration
commit or push was made.

The staged deletion of the old README and its untracked c2g replacement were
reviewed together. The replacement is the intended complete README: it describes
the c2g source installation, CLI, M0 test baseline, current limitations, and
P2PDocs/MIT provenance without unsupported production-ready claims.

The original P2PDocs Git history, MIT LICENSE, copyright notice, and an
attribution/provenance note are retained. The former publishing workflow is
preserved as `publish.yml.disabled` so this migration cannot publish the old
package identity. The historical `~/.p2p_crdt/` persistence path and existing
wire message types are unchanged. Since persistence currently pickles only
basic dictionaries, sets, and scalar data in the saved state, the import rename
does not by itself change that format; nevertheless, loading untrusted pickle
data remains unsafe and a formal migration is deferred to M5.

## I. Remaining Risks

Production persistence uses pickle and is not exercised with untrusted data.
The CRDT defects above remain. The legacy `p2pdocs` editable distribution is
still installed in the local virtual environment, but c2g imports resolve to
this checkout; it is an environment residue, not a repository artifact.

## J. Gate G0 Outcome

**PASS.** The isolated test harness, six passing baseline tests, six executable
strict expected-failure reproductions, CI job, Graphify index/instructions,
restored and validated planning records, complete c2g README with preserved
P2PDocs attribution, original Git history, and verified c2g SSH remote are in
place without changing application logic. No G0 acceptance criterion remains
unmet. M1 remains unstarted and requires explicit authorization.
