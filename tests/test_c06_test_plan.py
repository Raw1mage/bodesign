import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import assemble_c06_test_plan, assess_c06_readiness

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class C06TestPlanTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c06-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_assemble_maps_verdicts_to_status(self):
        verdicts = {
            "simulate": {"status": "ok", "passed": 3, "warned": 0, "failed": 0},
            "emc": {"status": "ok", "failed": 2},
            "crosscheck": {"coverage_pct": 100, "missing": []},
            # thermal omitted -> not-run
        }
        res = assemble_c06_test_plan(self.work, verdicts=verdicts, certification_targets=["FCC Part 15"])
        statuses = {c["check"]: c["status"] for c in res.summary["checks"]}
        self.assertEqual(statuses["simulate"], "pass")
        self.assertEqual(statuses["emc"], "fail")
        self.assertEqual(statuses["crosscheck"], "pass")
        self.assertEqual(statuses["thermal"], "not-run")
        rd = res.readiness.to_dict()
        self.assertFalse(rd["certified"])
        self.assertFalse(rd["evt_dvt_passed"])
        self.assertTrue(rd["has_failures"])
        self.assertEqual(rd["status"], "has_failures")

    def test_crosscheck_with_missing_is_warn(self):
        res = assemble_c06_test_plan(self.work, verdicts={"crosscheck": {"coverage_pct": 80, "missing": ["VBUS"]}})
        statuses = {c["check"]: c["status"] for c in res.summary["checks"]}
        self.assertEqual(statuses["crosscheck"], "warn")

    def test_no_verdicts_is_blocked_not_certified(self):
        res = assemble_c06_test_plan(self.work)
        self.assertEqual(res.readiness.status, "blocked")
        self.assertEqual(res.readiness.run_count, 0)
        self.assertEqual(len(res.readiness.not_run), 4)

    def test_clean_run_is_test_plan_drafted(self):
        verdicts = {
            "simulate": {"status": "ok", "failed": 0},
            "emc": {"status": "ok", "failed": 0},
            "thermal": {"status": "ok", "failed": 0},
            "crosscheck": {"coverage_pct": 100, "missing": []},
        }
        res = assemble_c06_test_plan(self.work, verdicts=verdicts)
        self.assertEqual(res.readiness.status, "test_plan_drafted")
        self.assertFalse(res.readiness.has_failures)
        # Certification targets still external even when checks pass.
        self.assertFalse(res.readiness.to_dict()["certified"])

    def test_certification_targets_render_as_external(self):
        assemble_c06_test_plan(self.work, verdicts={"simulate": {"status": "ok", "failed": 0}},
                               certification_targets=["CE", "FCC"])
        plan = (self.work / "C06-Verification" / "Test_Plan.md").read_text()
        self.assertIn("external lab", plan)

    def test_readiness_missing_before_assemble(self):
        self.assertEqual(assess_c06_readiness(self.work).status, "missing")


if __name__ == "__main__":
    unittest.main()
