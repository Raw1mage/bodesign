"""Fail-loud-on-invisible-path regression suite.

bodesign MCP runs containerized; a host path the container cannot see (an unmounted FUSE mount,
or a typo) must produce a LOUD, DISTINGUISHABLE signal across the whole readiness family —
never a syntactically clean `readiness_pct: 0` that looks like a genuinely-empty folder.

Covers: ingest root_exists; package + c00..c06 root_visible; the honesty invariant that any
invisibility-caused 0% always carries root_visible:false + a warning; and backward-compat
(a visible folder is a superset of the pre-change output shape).
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_reverse_core import ingest_project_folder
from bodesign_workflow_core import (
    assess_c00_prd_readiness,
    assess_c01_package_readiness,
    assess_c02_constraint_readiness,
    assess_c04_layout_readiness,
    assess_c05_fw_readiness,
    assess_c06_readiness,
    assess_package_readiness,
    render_readiness_markdown,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"
NONEXISTENT = "/nonexistent/bodesign/invisible/path/xyz123"


class IngestRootExistsTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-invis-ingest-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_nonexistent_root_is_distinguishable_from_empty(self):
        idx = ingest_project_folder(NONEXISTENT)
        self.assertFalse(idx.root_exists)
        self.assertTrue(idx.warnings)
        self.assertEqual(0, len(idx.files))
        self.assertFalse(idx.to_dict()["root_exists"])

        # An existing-but-empty dir is the OPPOSITE case: visible root, no files.
        empty = ingest_project_folder(self.work)
        self.assertTrue(empty.root_exists)
        self.assertEqual([], empty.warnings)
        self.assertEqual(0, len(empty.files))


class PackageReadinessInvisibleTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-invis-pkg-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_invisible_path_is_loud_not_a_false_zero(self):
        r = assess_package_readiness(NONEXISTENT, "POC")
        d = r.to_dict()
        self.assertFalse(d["root_visible"])
        self.assertTrue(d["warnings"])
        self.assertIn("file model", d["next_step"].lower())
        # honesty invariant: a 0% caused by invisibility MUST carry the signal.
        self.assertEqual(0, d["readiness_pct"])
        banner = render_readiness_markdown(r)
        self.assertIn("not visible", banner.lower())

    def test_visible_folder_is_backward_compatible_superset(self):
        d = assess_package_readiness(self.work, "POC").to_dict()
        self.assertTrue(d["root_visible"])
        self.assertEqual([], d["warnings"])
        # Pre-change keys all still present (additive-only schema change, R1).
        for key in ("folder", "milestone", "readiness_pct", "next_step", "summary",
                    "external_sections", "open_blockers", "deliverables"):
            self.assertIn(key, d)


class PerStageInvisibleTests(unittest.TestCase):
    """Every per-stage readiness fn yields a distinct not-visible signal, not blanket missing."""

    def _assert_not_visible(self, payload):
        self.assertFalse(payload["root_visible"])
        self.assertTrue(payload["warnings"])

    def test_c00(self):
        self._assert_not_visible(assess_c00_prd_readiness(NONEXISTENT).to_dict())

    def test_c01(self):
        self._assert_not_visible(assess_c01_package_readiness(NONEXISTENT).to_dict())

    def test_c02_from_folder(self):
        # Reading from a folder must guard; inline constraints (no path) must NOT be affected.
        self._assert_not_visible(assess_c02_constraint_readiness(None, NONEXISTENT).to_dict())
        inline = assess_c02_constraint_readiness({"board_outline": {"w": 10, "h": 10}}, None).to_dict()
        self.assertTrue(inline["root_visible"])  # inline data has no path to be invisible

    def test_c04(self):
        d = assess_c04_layout_readiness(NONEXISTENT).to_dict()
        self._assert_not_visible(d)
        self.assertEqual("path-not-visible", d["status"])

    def test_c05(self):
        d = assess_c05_fw_readiness(NONEXISTENT).to_dict()
        self._assert_not_visible(d)
        self.assertEqual("path-not-visible", d["status"])

    def test_c06(self):
        d = assess_c06_readiness(NONEXISTENT).to_dict()
        self._assert_not_visible(d)
        self.assertEqual("path-not-visible", d["status"])


if __name__ == "__main__":
    unittest.main()
