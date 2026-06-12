"""P1 (workflow_verification-discipline) — G1 RequirementContract + G6 debug discipline.

Covers spec.md scenarios:
- 可量測需求收斂為合約 (TV-G1-01)
- 不可量測需求 fail fast (TV-G1-02)
- 每輪驗證輸出 pass/fail 對表 (TV-G1-03)
- DRC 失敗先列簡單解釋 (TV-G6-01)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    ORACLE_TOOLS,
    ExtractedRequirement,
    plan_design_intent,
    requirement_passfail_table,
)
from bodesign_workflow_core.orchestration import (
    OrchestrationError,
    dispatch_work_packet,
    get_blocker,
    return_blocker,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class RequirementContractSchemaTests(unittest.TestCase):
    """DD-1 / DD-2: contract fields, closed oracle enum, fail-fast validation."""

    def test_default_fields_keep_existing_shape(self):
        r = ExtractedRequirement("compute", "Compute", "stated", "...stm32...")
        self.assertEqual(r.verification_status, "unverified")
        self.assertEqual(r.metric, "")
        self.assertFalse(r.contractualized)

    def test_oracle_enum_is_closed(self):
        with self.assertRaises(ValueError) as ctx:
            ExtractedRequirement("x", "X", "stated", oracle_tool="magic_oracle")
        self.assertIn("REQ_ORACLE_INVALID", str(ctx.exception))
        # every enum member is accepted
        for tool in ORACLE_TOOLS:
            ExtractedRequirement("x", "X", "stated", oracle_tool=tool)

    def test_oracle_none_forces_unverifiable(self):
        r = ExtractedRequirement("aesthetics", "Aesthetics", "stated", oracle_tool="none")
        self.assertEqual(r.verification_status, "unverifiable")

    def test_pass_without_oracle_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            ExtractedRequirement("x", "X", "stated", verification_status="pass")
        self.assertIn("REQ_VERDICT_NO_EVIDENCE", str(ctx.exception))

    def test_contractualized_requires_metric_threshold_oracle(self):
        r = ExtractedRequirement(
            "board_length", "Board length", "answered", "60mm",
            metric="board_length_mm", threshold="<=60", oracle_tool="drc_gate",
        )
        self.assertTrue(r.contractualized)


class ContractConvergenceTests(unittest.TestCase):
    """TV-G1-01 / TV-G1-02: plan_design_intent converges measurable answers."""

    def test_answered_dimensions_converges_to_contract(self):
        plan = plan_design_intent("STM32 board", {"dimensions": "60mm x 40mm"}).to_dict()
        row = next(r for r in plan["requirements"] if r["key"] == "dimensions")
        self.assertEqual(row["metric"], "board_length_mm")
        self.assertEqual(row["threshold"], "<=60")
        self.assertEqual(row["oracle_tool"], "drc_gate")
        self.assertEqual(row["verification_status"], "unverified")

    def test_stated_dimensions_converges_from_spec_text(self):
        plan = plan_design_intent("board outline 80 mm long with usb-c").to_dict()
        row = next(r for r in plan["requirements"] if r["key"] == "dimensions")
        self.assertEqual(row["metric"], "board_length_mm")
        self.assertEqual(row["threshold"], "<=80")

    def test_binding_without_metric_stays_uncontractualized(self):
        plan = plan_design_intent("usb-c powered board").to_dict()
        row = next(r for r in plan["requirements"] if r["key"] == "power_input")
        self.assertEqual(row["metric"], "")
        self.assertEqual(row["oracle_tool"], "")
        self.assertEqual(row["verification_status"], "unverified")

    def test_existing_callers_see_superset_dict(self):
        plan = plan_design_intent("STM32 board").to_dict()
        for row in plan["requirements"]:
            for legacy_key in ("key", "label", "state", "evidence"):
                self.assertIn(legacy_key, row)


class PassFailTableTests(unittest.TestCase):
    """TV-G1-03 / DD-9: verdicts only via oracle execution records."""

    def _contracts(self):
        return [
            ExtractedRequirement("board_length", "Board length", "answered", "60",
                                 metric="board_length_mm", threshold="<=60", oracle_tool="drc_gate"),
            ExtractedRequirement("usb_dp_dm_skew", "USB skew", "answered", "",
                                 metric="skew_ps", threshold="<=50", oracle_tool="si_check"),
            ExtractedRequirement("net_parity", "Net parity", "answered", "",
                                 metric="net_parity_pct", threshold="==100", oracle_tool="crosscheck"),
            ExtractedRequirement("aesthetics", "Aesthetics", "stated", oracle_tool="none"),
        ]

    def test_table_matches_tv_g1_03(self):
        table = requirement_passfail_table(self._contracts(), [
            {"requirement_key": "board_length", "verdict": "pass", "measured_value": "58.4"},
            {"requirement_key": "net_parity", "verdict": "fail"},
        ])
        by_key = {row["requirement_key"]: row for row in table}
        self.assertEqual(by_key["board_length"]["verdict"], "pass")
        self.assertEqual(by_key["board_length"]["measured_value"], "58.4")
        self.assertEqual(by_key["net_parity"]["verdict"], "fail")
        # DD-9 invariant: no oracle execution record => unverified, never pass.
        self.assertEqual(by_key["usb_dp_dm_skew"]["verdict"], "unverified")
        self.assertEqual(by_key["aesthetics"]["verdict"], "unverifiable")

    def test_no_verdicts_means_all_unverified(self):
        table = requirement_passfail_table(self._contracts())
        verdicts = {row["verdict"] for row in table}
        self.assertEqual(verdicts, {"unverified", "unverifiable"})

    def test_invalid_verdict_value_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            requirement_passfail_table(self._contracts(), [{"requirement_key": "x", "verdict": "maybe"}])
        self.assertIn("REQ_VERDICT_NO_EVIDENCE", str(ctx.exception))

    def test_verdict_row_missing_key_rejected(self):
        with self.assertRaises(ValueError):
            requirement_passfail_table(self._contracts(), [{"verdict": "pass"}])


class SimpleFixCandidatesTests(unittest.TestCase):
    """TV-G6-01 / DD-3: cheap hypotheses attached to blockers, gated rule-outs."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-reqcontract-", dir=PRIVATE_BASE))
        self.packet = dispatch_work_packet(self.work, "C04", "route board")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _blocker(self, candidates):
        return return_blocker(
            self.work, self.packet.packet_id,
            severity="blocked", summary="clearance violation on NET_VBUS",
            question_for_user="accept rule exception?",
            simple_fix_candidates=candidates,
        )

    def test_candidates_serialize_and_roundtrip(self):
        b = self._blocker([
            {"hypothesis": "DRC rule param wrong", "check_method": "inspect rule file", "ruled_out": False},
            {"hypothesis": "single net exception", "check_method": "check net class",
             "ruled_out": True, "evidence_ref": {"kind": "tool_output", "ref": "drc-run-3"}},
        ])
        loaded = get_blocker(self.work, b.blocker_id)
        self.assertEqual(len(loaded.simple_fix_candidates), 2)
        self.assertTrue(loaded.simple_fix_candidates[1]["ruled_out"])
        self.assertEqual(loaded.simple_fix_candidates[1]["evidence_ref"]["ref"], "drc-run-3")

    def test_structural_gate_blocked_until_all_ruled_out(self):
        b = self._blocker([
            {"hypothesis": "rule param", "check_method": "inspect", "ruled_out": False},
        ])
        self.assertFalse(b.structural_proposal_allowed)

    def test_structural_gate_open_when_all_ruled_out(self):
        b = self._blocker([
            {"hypothesis": "rule param", "check_method": "inspect",
             "ruled_out": True, "evidence_ref": {"kind": "tool_output", "ref": "drc-run-1"}},
        ])
        self.assertTrue(b.structural_proposal_allowed)

    def test_ruled_out_without_evidence_rejected(self):
        with self.assertRaises(OrchestrationError) as ctx:
            self._blocker([{"hypothesis": "h", "check_method": "m", "ruled_out": True}])
        self.assertIn("evidence_ref", str(ctx.exception))

    def test_candidate_shape_validated(self):
        with self.assertRaises(OrchestrationError):
            self._blocker([{"check_method": "m"}])
        with self.assertRaises(OrchestrationError):
            self._blocker([{"hypothesis": "h"}])
        with self.assertRaises(OrchestrationError):
            self._blocker(["not-an-object"])

    def test_blocker_without_candidates_unchanged(self):
        b = return_blocker(
            self.work, self.packet.packet_id,
            severity="blocked", summary="s", question_for_user="q",
        )
        self.assertEqual(b.simple_fix_candidates, [])
        self.assertTrue(b.structural_proposal_allowed)


if __name__ == "__main__":
    unittest.main()
