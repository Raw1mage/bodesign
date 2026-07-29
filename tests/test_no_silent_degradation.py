"""Regression tests for checkers/no_silent_degradation.py (control.quality.no-silent-degradation).

The lint exists because BR_20260729's five defects all passed the full test suite.
So these tests assert the thing that was missing: that the rule FIRES on the shape
it was written for and STAYS SILENT on the honest shape — anchored to the real
before/after source of the defects it distilled.

Run:
    PP=$(ls -d packages/*/ | tr '\n' ':') && PYTHONPATH="$PP" python3 tests/test_no_silent_degradation.py
"""

import ast
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MOD = _REPO / "packages/workflow-core/bodesign_workflow_core/checkers/no_silent_degradation.py"

# Load the module directly: it is a pure-AST lint with no IR dependencies, and the
# package __init__ pulls in the whole workflow-core stack (pcbnew, design-ir, ...).
_spec = importlib.util.spec_from_file_location("nsd", _MOD)
nsd = importlib.util.module_from_spec(_spec)
sys.modules["nsd"] = nsd  # slots=True dataclasses need the module registered
_spec.loader.exec_module(nsd)


def _scan(src: str, *, advisory: bool = False):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        path = f.name
    return nsd.check_file(path, include_advisory=advisory)


def _rules(findings) -> dict:
    out: dict = {}
    for f in findings:
        out[f.rule] = out.get(f.rule, 0) + 1
    return out


class L2SwallowedExcept(unittest.TestCase):
    """§C/§D: `except` that only passes, in a function that returns a value."""

    def test_fires_on_bare_pass(self):
        src = (
            "def f(x):\n"
            "    try:\n"
            "        v = x.compute()\n"
            "    except Exception:\n"
            "        pass\n"
            "    return {'ok': True}\n"
        )
        self.assertEqual(_rules(_scan(src)).get("L2"), 1)

    def test_fires_on_log_only(self):
        src = (
            "import logging\n"
            "log = logging.getLogger(__name__)\n"
            "def f(x):\n"
            "    try:\n"
            "        v = x.compute()\n"
            "    except Exception:\n"
            "        log.warning('oops')\n"
            "    return {'ok': True}\n"
        )
        self.assertEqual(_rules(_scan(src)).get("L2"), 1)

    def test_silent_when_failure_is_recorded(self):
        src = (
            "def f(x):\n"
            "    dropped = []\n"
            "    try:\n"
            "        v = x.compute()\n"
            "    except Exception:\n"
            "        dropped.append(x)\n"
            "    return {'ok': not dropped, 'dropped': dropped}\n"
        )
        self.assertNotIn("L2", _rules(_scan(src)))

    def test_silent_when_it_reraises(self):
        src = (
            "def f(x):\n"
            "    try:\n"
            "        return x.compute()\n"
            "    except Exception:\n"
            "        raise ValueError('COMPUTE_FAILED')\n"
        )
        self.assertNotIn("L2", _rules(_scan(src)))

    def test_silent_in_procedure_with_no_return_value(self):
        # Nothing to mislead the caller with — the invariant is about return values.
        src = (
            "def f(x):\n"
            "    try:\n"
            "        x.compute()\n"
            "    except Exception:\n"
            "        pass\n"
        )
        self.assertNotIn("L2", _rules(_scan(src)))


class L6SilentKeyLookup(unittest.TestCase):
    """§D: caller-supplied key fails `.get()` and the element vanishes with no else."""

    def test_fires_on_the_plane_layers_shape(self):
        # Verbatim shape of the §D defect: no `continue`, the element just falls
        # off the end of the loop body. This is why L1 alone did not catch it.
        src = (
            "def build(board, plane_layers):\n"
            "    lymap = {'In1': 1, 'In2': 2}\n"
            "    for nm in plane_layers:\n"
            "        ly = lymap.get(nm)\n"
            "        if ly is not None:\n"
            "            board.SetLayerType(ly, 'POWER')\n"
            "    return {'ok': True}\n"
        )
        self.assertEqual(_rules(_scan(src)).get("L6"), 1)

    def test_silent_when_the_miss_is_recorded(self):
        src = (
            "def build(board, plane_layers):\n"
            "    lymap = {'In1': 1, 'In2': 2}\n"
            "    unknown = []\n"
            "    for nm in plane_layers:\n"
            "        ly = lymap.get(nm)\n"
            "        if ly is not None:\n"
            "            board.SetLayerType(ly, 'POWER')\n"
            "        else:\n"
            "            unknown.append(nm)\n"
            "    return {'ok': not unknown, 'unknown': unknown}\n"
        )
        self.assertNotIn("L6", _rules(_scan(src)))

    def test_reports_each_source_line_once(self):
        # A nested loop reaches the same `if` from both walks; dedupe by line.
        src = (
            "def build(rows, cols, m):\n"
            "    for r in rows:\n"
            "        for c in cols:\n"
            "            v = m.get(c)\n"
            "            if v is not None:\n"
            "                r.apply(v)\n"
            "    return {'ok': True}\n"
        )
        self.assertEqual(_rules(_scan(src)).get("L6"), 1)


class L8ScatteredMeasurement(unittest.TestCase):
    """§E: the same physical quantity measured by independent implementations."""

    def test_fires_when_two_functions_measure_the_same_thing(self):
        src = (
            "def a(fp):\n"
            "    return fp.GetBoundingBox()\n"
            "def b(fp):\n"
            "    return fp.GetBoundingBox()\n"
        )
        self.assertEqual(_rules(_scan(src)).get("L8"), 1)

    def test_silent_when_converged_on_one_helper(self):
        src = (
            "def extent(fp):\n"
            "    return fp.GetBoundingBox()\n"
            "def a(fp):\n"
            "    return extent(fp)\n"
            "def b(fp):\n"
            "    return extent(fp)\n"
        )
        self.assertNotIn("L8", _rules(_scan(src)))

    def test_different_receivers_are_different_quantities(self):
        # pad.GetBoundingBox() measures a pad; fp.GetBoundingBox() measures a whole
        # part. Conflating them reported _pad_radius_iu vs footprint_extent as a
        # duplicate implementation — a false positive found while calibrating.
        src = (
            "def pad_radius(pad):\n"
            "    return pad.GetBoundingBox()\n"
            "def part_extent(fp):\n"
            "    return fp.GetBoundingBox()\n"
        )
        self.assertNotIn("L8", _rules(_scan(src)))


class L1IsAdvisoryOnly(unittest.TestCase):
    """L1's signal-to-noise did not justify blocking — it must stay opt-in."""

    SRC = (
        "def f(items):\n"
        "    out = []\n"
        "    for it in items:\n"
        "        if not it.valid:\n"
        "            continue\n"
        "        out.append(it)\n"
        "    return out\n"
    )

    def test_hidden_by_default(self):
        self.assertNotIn("L1", _rules(_scan(self.SRC)))

    def test_visible_when_requested(self):
        self.assertEqual(_rules(_scan(self.SRC, advisory=True)).get("L1"), 1)


class L10ScanReportsItsOwnCoverage(unittest.TestCase):
    """L10: a checker that returns only findings is itself the anti-pattern.

    On "0 findings" the caller must be able to tell `clean` from `never scanned`.
    This is not hypothetical: this checker's own default roots once omitted
    services/, so the documented 11-finding baseline printed as 5 and a CI run
    would have gone green over unscanned code.
    """

    def _tree(self) -> str:
        d = tempfile.mkdtemp()
        Path(d, "pkg").mkdir()
        Path(d, "pkg/ok.py").write_text("def f():\n    return 1\n")
        Path(d, "pkg/test_skipme.py").write_text("def f():\n    return 1\n")
        Path(d, "pkg/broken.py").write_text("def f(:\n")
        return d

    def test_reports_roots_and_file_count(self):
        d = self._tree()
        _, cov = nsd.check_paths([Path(d, "pkg")], with_coverage=True)
        self.assertEqual(cov.files_scanned, 1)
        self.assertEqual(cov.files_skipped, 1, "test_*.py is skipped, and said so")

    def test_a_nonexistent_root_is_a_coverage_gap_not_an_empty_result(self):
        findings, cov = nsd.check_paths(["does/not/exist"], with_coverage=True)
        self.assertEqual(findings, [], "nothing to find")
        self.assertEqual(cov.missing_roots, ["does/not/exist"],
                         "a typo'd root must not masquerade as a clean scan")

    def test_unparsable_file_is_surfaced_not_swallowed(self):
        d = self._tree()
        _, cov = nsd.check_paths([Path(d, "pkg")], with_coverage=True)
        self.assertEqual(len(cov.unparsable), 1)
        self.assertTrue(cov.unparsable[0].endswith("broken.py"))

    def test_coverage_is_opt_in_so_existing_callers_are_unchanged(self):
        d = self._tree()
        self.assertIsInstance(nsd.check_paths([Path(d, "pkg")]), list)


class AnchoredToTheRealDefects(unittest.TestCase):
    """The calibration claim in the control object, asserted against real history.

    Guards the tier decision itself: T-A rules must fire on the pre-fix source of
    BR_20260729 and go silent on the post-fix source. If a later refactor breaks
    that property the tier is no longer justified, and this fails.
    """

    TARGET = "packages/eda-bridge/bodesign_eda_bridge/routing.py"

    def _at(self, rev: str) -> str:
        proc = subprocess.run(["git", "show", f"{rev}:{self.TARGET}"],
                              cwd=_REPO, capture_output=True, text=True)
        if proc.returncode != 0:
            self.skipTest(f"revision {rev} unavailable (shallow clone?)")
        return proc.stdout

    def test_ta_rules_fire_before_the_fixes(self):
        found = _rules(_scan(self._at("1269a20~1")))
        self.assertEqual(found.get("L2"), 2, "§D's two `except: pass`")
        self.assertEqual(found.get("L6"), 1, "§D's plane_layers lookup")
        self.assertEqual(found.get("L8"), 1, "§E's split extent measurement")

    def test_ta_rules_are_clean_after_the_fixes(self):
        self.assertEqual(_scan(self._at("HEAD")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
