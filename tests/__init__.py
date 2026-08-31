"""Test-package bootstrap: put every ``packages/*/`` source root on ``sys.path``.

WHY THIS FILE EXISTS (BR_20260831a, family ``G13-harness-disclosure``)
---------------------------------------------------------------------
Before 2026-09-01 this repo had no test bootstrap at all. Running the suite
required an orally-transmitted incantation::

    PYTHONPATH="$(ls -d packages/*/ | tr '\\n' ':')" python3 -m unittest tests.foo

Forgetting it produced::

    Ran 1 test in 0.000s
    FAILED (errors=1)                       # rc=1

which is **byte-for-byte identical** to the output of "the target module does
not exist" and shares its exit code with "a real test regressed". One output,
three mutually exclusive situations. That is the defect this file removes.

``tests/__init__.py`` is executed by the interpreter whenever ANY
``tests.<module>`` is imported, so it covers ``python3 -m unittest`` (the path
every test in this repo actually uses) as well as pytest. A root
``conftest.py`` would only have covered pytest.

CONTROL-GROUP SWITCH
--------------------
``BODESIGN_TEST_BOOTSTRAP=0`` disables the path injection. It exists so the
reverse control group ("prove the bootstrap is load-bearing") can be run
without mutating this file on disk — an on-disk mutation is unreliable here,
because a same-second same-length edit leaves the stale ``.pyc`` valid and the
mutant is silently never applied (AGENTS.md §6.3). Do not set it in normal use.

FAIL-LOUD, NOT FAIL-QUIET
-------------------------
If ``packages/`` is missing or contains no directories this module raises
``RuntimeError`` naming the path it looked at. A bootstrap that silently
injects nothing would recreate the very ambiguity it was written to remove.

WHY ``os.environ['PYTHONPATH']`` IS ALSO SET
--------------------------------------------
``sys.path`` covers only THIS interpreter. Several tests in this repo assert
their invariant in a **fresh child interpreter** for true isolation — e.g.
``tests/test_copper_geometry.py`` runs ``subprocess.run([sys.executable, '-c',
...])`` to prove ``copper_geometry`` never transitively imports ``pcbnew``,
because the parent's ``sys.modules`` is contaminated by sibling tests. Such a
child inherits the parent's ENVIRONMENT, not the parent's ``sys.path``. Under
the old oral ``PYTHONPATH=... python3 -m unittest`` recipe those children
worked by accident, via inheritance of the env var. A ``sys.path``-only
bootstrap silently breaks them — measured: exactly one test
(``NoPcbnewTests.test_no_pcbnew_import``) went green→red that way, and its
failure text read ``ModuleNotFoundError: No module named
'bodesign_gerber_core'``, i.e. it reported the child's env gap as if the
invariant under test had been violated. So the bootstrap must repair the
environment as well as the path, or it just relocates the ambiguity into
subprocesses.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Repo root, derived from this file's location. Never hard-code an absolute
#: path here: the repo is cloned to different roots in dev and in containers.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Directory holding the per-package source roots.
PACKAGES_DIR = REPO_ROOT / "packages"

#: Set this env var to "0" to skip the injection (reverse control group only).
BOOTSTRAP_ENV = "BODESIGN_TEST_BOOTSTRAP"


def package_source_roots() -> list[str]:
    """Return every ``packages/*/`` directory as an absolute path string.

    Raises:
        RuntimeError: if ``packages/`` is absent or holds no subdirectory. The
            message names the exact path inspected, so "there is nothing to
            add" never masquerades as "everything is already fine".
    """
    if not PACKAGES_DIR.is_dir():
        raise RuntimeError(
            f"bodesign test bootstrap: expected package source roots under "
            f"{PACKAGES_DIR}, but that directory does not exist. "
            f"REPO_ROOT was derived as {REPO_ROOT} from {__file__}."
        )
    roots = [str(p) for p in sorted(PACKAGES_DIR.iterdir()) if p.is_dir()]
    if not roots:
        raise RuntimeError(
            f"bodesign test bootstrap: {PACKAGES_DIR} exists but contains no "
            f"package directories, so no source root could be added to sys.path."
        )
    return roots


def _bootstrap() -> list[str]:
    if os.environ.get(BOOTSTRAP_ENV) == "0":
        return []
    roots = package_source_roots()

    # (1) this interpreter
    missing = [r for r in roots if r not in sys.path]
    if missing:
        sys.path[:0] = missing

    # (2) any child interpreter this process spawns. Our roots are prepended,
    # and whatever the caller already had is preserved after them.
    #
    # De-duplication here is TEXTUAL (`p not in roots` compares strings), so
    # it drops only entries byte-identical to a root we just added. Paths that
    # are equivalent but spelled differently — a relative "packages/shared/"
    # against our absolute form, or a trailing-slash variant — are NOT merged
    # and both survive into PYTHONPATH.
    #
    # Measured 2026-09-01, before deciding not to normalise: with
    # PYTHONPATH="packages/shared/" exported plus our 11 absolute roots, the
    # child saw 22 entries — textually unique 22, realpath-unique 11. Across a
    # gen0 -> gen3 chain of nested child interpreters the count stayed 22 at
    # every generation: the duplication does NOT accumulate, and import
    # resolution was unaffected (the first matching entry wins either way).
    #
    # `os.path.realpath` was considered and rejected on that evidence: it
    # would introduce symlink resolution as new behaviour — this repo has
    # `.venv` and container bind-mounts whose symlink semantics were not
    # measured — in exchange for a harm measured at zero.
    existing = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    merged = roots + [p for p in existing if p not in roots]
    os.environ["PYTHONPATH"] = os.pathsep.join(merged)

    return roots


#: The package source roots this module ENSURED are on ``sys.path`` — not
#: only the ones it had to insert. A root already present (e.g. because the
#: caller also exported ``PYTHONPATH``) is still listed, because the meaning
#: of this list is "these are covered", not "these were missing". It is empty
#: only when the bootstrap was disabled via ``BODESIGN_TEST_BOOTSTRAP=0``, so
#: a caller — notably ``scripts/run_tests.sh --self-test`` — can assert the
#: bootstrap actually ran instead of inferring it from a green suite.
BOOTSTRAPPED_PATHS: list[str] = _bootstrap()
