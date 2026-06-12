"""P2 (workflow_verification-discipline) — G2 Design Review Gate + G3 structured diff.

Covers spec.md scenarios:
- 子系統設計審查產出裁決 (TV-G2-01)
- review 不可被跳過 (TV-G2-02)
- crosscheck 輸出 CrossCheckDiff (TV-G3-01)
- root-cause 報告標準化 (TV-G3-02)
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    CrossCheckError,
    DesignReviewError,
    RootCauseError,
    crosscheck_diff,
    load_design_review,
    load_root_cause_reports,
    plan_reference_board_workflow,
    record_design_review,
    record_root_cause,
    review_gate_status,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _scenarios():
    return [
        {"name": "power sequencing", "walkthrough": "3V3 before 1V8; EN tied to PG", "conclusion": "ok", "severity": "minor"},
        {"name": "I2C address conflict", "walkthrough": "0x48 sensor vs 0x49 ADC", "conclusion": "no conflict", "severity": "info"},
        {"name": "level compatibility", "walkthrough": "1V8 MCU GPIO drives 3V3 enable", "conclusion": "needs level shifter", "severity": "major"},
    ]


class DesignReviewRecordTests(unittest.TestCase):
    """TV-G2-01: review record validation + persistence."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-review-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_record_persists_with_counts_and_verdict(self):
        record_design_review(self.work, subject="MCU + USB-C PD + buck intent",
                             scenarios=_scenarios(), verdict="APPROVE_WITH_CONCERNS")
        loaded = load_design_review(self.work)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.verdict, "APPROVE_WITH_CONCERNS")
        self.assertEqual(loaded.counts, {"critical": 0, "major": 1, "minor": 1})
        # persisted into client project folder as evidence
        path = self.work / "_design_review" / "design_review.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text())
        self.assertEqual(data["schema"], "bodesign.design_review.v1")
        self.assertIn("counts", data)

    def test_empty_scenarios_rejected(self):
        with self.assertRaises(DesignReviewError) as ctx:
            record_design_review(self.work, subject="x", scenarios=[], verdict="APPROVE")
        self.assertIn("REVIEW_VERDICT_INVALID", str(ctx.exception))

    def test_invalid_verdict_rejected(self):
        with self.assertRaises(DesignReviewError):
            record_design_review(self.work, subject="x", scenarios=_scenarios(), verdict="LGTM")

    def test_scenario_fields_validated(self):
        bad = [{"name": "power sequencing", "walkthrough": "", "conclusion": "ok", "severity": "minor"}]
        with self.assertRaises(DesignReviewError):
            record_design_review(self.work, subject="x", scenarios=bad, verdict="APPROVE")
        bad2 = [{"name": "n", "walkthrough": "w", "conclusion": "c", "severity": "fatal"}]
        with self.assertRaises(DesignReviewError):
            record_design_review(self.work, subject="x", scenarios=bad2, verdict="APPROVE")

    def test_nothing_persisted_on_invalid_record(self):
        with self.assertRaises(DesignReviewError):
            record_design_review(self.work, subject="", scenarios=[], verdict="APPROVE")
        self.assertIsNone(load_design_review(self.work))


class ReviewGateTests(unittest.TestCase):
    """TV-G2-02: the gate cannot be skipped; REJECT keeps validation blocked."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-reviewgate-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _plan(self, folder=None):
        return plan_reference_board_workflow("p1", "bd1", 3, 10, 20, 0, project_folder=folder)

    def _stage(self, plan, stage_id):
        return next(s for s in plan.stages if s.stage_id == stage_id)

    def test_stage_sequence_inserts_design_review(self):
        ids = [s.stage_id for s in self._plan().stages]
        self.assertIn("design-review", ids)
        self.assertLess(ids.index("propose-layout-intent"), ids.index("design-review"))
        self.assertLess(ids.index("design-review"), ids.index("deterministic-validation"))

    def test_missing_review_blocks_validation(self):
        plan = self._plan()  # no project folder => no review record
        self.assertEqual(self._stage(plan, "design-review").status, "required")
        dv = self._stage(plan, "deterministic-validation")
        self.assertTrue(any("REVIEW_MISSING" in b for b in dv.blockers))

    def test_reject_keeps_validation_blocked(self):
        record_design_review(self.work, subject="x", verdict="REJECT", scenarios=[
            {"name": "reset chain", "walkthrough": "w", "conclusion": "broken", "severity": "critical"}])
        plan = self._plan(self.work)
        self.assertEqual(self._stage(plan, "design-review").status, "rejected")
        dv = self._stage(plan, "deterministic-validation")
        self.assertTrue(any("REVIEW_REJECTED" in b for b in dv.blockers))

    def test_approve_clears_review_blockers(self):
        record_design_review(self.work, subject="x", verdict="APPROVE", scenarios=_scenarios())
        plan = self._plan(self.work)
        self.assertEqual(self._stage(plan, "design-review").status, "approved")
        dv = self._stage(plan, "deterministic-validation")
        self.assertFalse(any("REVIEW" in b for b in dv.blockers))

    def test_gate_status_tuple_shape(self):
        status, blockers = review_gate_status(None)
        self.assertEqual(status, "required")
        self.assertEqual(len(blockers), 1)


class CrossCheckDiffTests(unittest.TestCase):
    """TV-G3-01: structured diff with first_divergence + dimension-unavailable."""

    def test_tv_g3_01_net_diff(self):
        diff = crosscheck_diff(
            {"net": {"GND", "VBUS", "SDA0", "SCL0"}},
            {"net": {"GND", "VBUS", "SDA0", "SCL0", "INT_N"}},
            "openmv-ref",
        ).to_dict()
        missing = [i for i in diff["items"] if i["status"] == "missing"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["key"], "INT_N")
        self.assertEqual(missing[0]["severity"], "major")
        fd = diff["items"][diff["first_divergence"]]
        self.assertEqual(fd["key"], "INT_N")
        # dual track: coverage identical to crosscheck_nets behavior (4/5 = 80%)
        self.assertEqual(diff["coverage_pct"], 80)
        self.assertTrue(diff["verdict"])

    def test_dimension_unavailable_reported_not_faked(self):
        diff = crosscheck_diff(
            {"net": {"GND"}, "pad": {"U1-1"}},
            {"net": {"GND"}},
            "x",
        ).to_dict()
        self.assertEqual(diff["dimensions_available"], ["net"])
        self.assertEqual(diff["dimensions_unavailable"][0]["dimension"], "pad")
        self.assertNotIn("pad", {i["dimension"] for i in diff["items"]})

    def test_fully_matched_has_null_first_divergence(self):
        diff = crosscheck_diff({"net": {"A", "B"}}, {"net": {"A", "B"}}, "x").to_dict()
        self.assertIsNone(diff["first_divergence"])
        self.assertTrue(all(i["status"] == "matched" for i in diff["items"]))

    def test_empty_reference_fails_fast(self):
        with self.assertRaises(CrossCheckError) as ctx:
            crosscheck_diff({"net": {"GND"}}, {"net": set()}, "x")
        self.assertIn("XCHK_EMPTY_REFERENCE", str(ctx.exception))

    def test_unknown_dimension_fails_fast(self):
        with self.assertRaises(CrossCheckError):
            crosscheck_diff({"voltage": {"3V3"}}, {"net": {"GND"}}, "x")

    def test_deterministic_output(self):
        a = json.dumps(crosscheck_diff({"net": {"A", "B", "C"}}, {"net": {"B", "C", "D"}}, "x").to_dict())
        b = json.dumps(crosscheck_diff({"net": {"C", "A", "B"}}, {"net": {"D", "B", "C"}}, "x").to_dict())
        self.assertEqual(a, b)


class RootCauseReportTests(unittest.TestCase):
    """TV-G3-02: four-part report, anchored evidence, written to events."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-rootcause-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _record(self, **overrides):
        kwargs = dict(
            subject="net INT_N missing",
            methodology=["diff reference vs generated nets", "trace INT_N source pin"],
            findings=["INT_N originates from U3 pin 7; interrupt line never wired"],
            evidence=[{"kind": "net", "ref": "INT_N"}, {"kind": "tool_output", "ref": "crosscheck-run-1"}],
            fix="wire U3 pin 7 to MCU EXTI via net INT_N",
        )
        kwargs.update(overrides)
        return record_root_cause(self.work, **kwargs)

    def test_report_persists_and_logs_event(self):
        self._record()
        reports = load_root_cause_reports(self.work)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].fix, "wire U3 pin 7 to MCU EXTI via net INT_N")
        log_path = self.work / "_orchestration" / "log.jsonl"
        events = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
        self.assertEqual(events[-1]["event"], "rootcause.reported")

    def test_all_four_parts_mandatory(self):
        for missing_field, value in (
            ("methodology", []), ("findings", []), ("fix", ""), ("subject", ""),
        ):
            with self.assertRaises(RootCauseError, msg=missing_field):
                self._record(**{missing_field: value})

    def test_evidence_requires_anchor(self):
        with self.assertRaises(RootCauseError):
            self._record(evidence=[{"ref": "no-kind"}])
        with self.assertRaises(RootCauseError):
            self._record(evidence=[])

    def test_invalid_report_persists_nothing(self):
        with self.assertRaises(RootCauseError):
            self._record(fix="")
        self.assertEqual(load_root_cause_reports(self.work), [])


if __name__ == "__main__":
    unittest.main()
