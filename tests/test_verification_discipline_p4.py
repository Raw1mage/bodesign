"""P4 (workflow_verification-discipline) — A1 編排表面統一.

Covers spec.md scenarios:
- stage 狀態從 spine 推導 (TV-A1-01)
- spine 未初始化 fail fast (TV-A1-02)
- API 向後相容 (TV-A1-03)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    derive_workflow_plan,
    dispatch_work_packet,
    ingest_blocker,
    plan_reference_board_workflow,
    record_design_review,
    return_blocker,
    return_evidence,
    wrap_validation_evidence,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _stage(plan, stage_id):
    return next(s for s in plan.stages if s.stage_id == stage_id)


class SpineDerivationTests(unittest.TestCase):
    """TV-A1-01: stage status computed from spine state, not argument snapshots."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-derive-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _derive(self):
        return derive_workflow_plan("p1", "bd1", self.work, artifact_count=3,
                                    component_count=10, net_count=20)

    def test_dispatched_packet_moves_stage_to_dispatched(self):
        dispatch_work_packet(self.work, "C04", "route board")
        # validation stage carries the review gate (G2), so strip it via APPROVE
        record_design_review(self.work, subject="x", verdict="APPROVE", scenarios=[
            {"name": "power sequencing", "walkthrough": "w", "conclusion": "ok", "severity": "info"}])
        plan = self._derive()
        self.assertEqual(_stage(plan, "deterministic-validation").status, "dispatched")
        self.assertEqual(plan.status, "in-progress")

    def test_open_blocker_blocks_stage_with_reference(self):
        p = dispatch_work_packet(self.work, "C04", "route board")
        b = return_blocker(self.work, p.packet_id, severity="blocked",
                           summary="clearance violation", question_for_user="accept?")
        plan = self._derive()
        dv = _stage(plan, "deterministic-validation")
        self.assertEqual(dv.status, "blocked")
        self.assertTrue(any(b.blocker_id in x for x in dv.blockers))
        self.assertEqual(plan.status, "blocked")

    def test_resolved_blocker_plus_evidence_unblocks(self):
        p = dispatch_work_packet(self.work, "C04", "route board")
        b = return_blocker(self.work, p.packet_id, severity="blocked",
                           summary="s", question_for_user="q")
        ingest_blocker(self.work, b.blocker_id, resolved_state="answered", decision="accept")
        env = wrap_validation_evidence(
            "drc_gate", {"copper": 0, "unconnected": 0, "silk": 0, "clean": True}).to_dict()
        return_evidence(self.work, p.packet_id, envelope=env)
        record_design_review(self.work, subject="x", verdict="APPROVE", scenarios=[
            {"name": "power sequencing", "walkthrough": "w", "conclusion": "ok", "severity": "info"}])
        plan = self._derive()
        dv = _stage(plan, "deterministic-validation")
        self.assertEqual(dv.status, "evidence-received")
        self.assertEqual(plan.status, "in-progress")

    def test_intent_layer_blockers_map_to_intent_stage(self):
        p = dispatch_work_packet(self.work, "C03", "mechanical constraints")
        return_blocker(self.work, p.packet_id, severity="decision",
                       summary="enclosure conflict", question_for_user="which enclosure?")
        plan = self._derive()
        intent = _stage(plan, "propose-layout-intent")
        self.assertEqual(intent.status, "blocked")
        self.assertTrue(any("enclosure conflict" in x for x in intent.blockers))

    def test_review_gate_survives_spine_derivation(self):
        # spine is clean but review missing -> validation stays blocked (G2 not spine state)
        dispatch_work_packet(self.work, "C04", "route board")
        plan = self._derive()
        dv = _stage(plan, "deterministic-validation")
        self.assertEqual(dv.status, "blocked")
        self.assertTrue(any("REVIEW_MISSING" in x for x in dv.blockers))

    def test_same_spine_state_derives_deterministically(self):
        p = dispatch_work_packet(self.work, "C04", "route board")
        return_blocker(self.work, p.packet_id, severity="blocked", summary="s", question_for_user="q")
        a = self._derive().to_dict()
        b = self._derive().to_dict()
        self.assertEqual(a, b)


class SpineNotInitializedTests(unittest.TestCase):
    """TV-A1-02: missing _orchestration/ is an explicit blocker, never a fallback."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-nospine-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_uninitialized_spine_reports_explicit_blocker(self):
        plan = derive_workflow_plan("p1", "bd1", self.work, artifact_count=3)
        self.assertEqual(plan.status, "spine-not-initialized")
        for stage_id in ("propose-layout-intent", "deterministic-validation"):
            stage = _stage(plan, stage_id)
            self.assertEqual(stage.status, "blocked")
            self.assertTrue(any("SPINE_NOT_INITIALIZED" in b for b in stage.blockers))

    def test_no_fallback_to_parameter_snapshot(self):
        # the static plan with rich counts would mark ingest-sources available and
        # reconstruct partial — the derived plan must NOT echo snapshot status on
        # spine-owned stages even with generous counts.
        plan = derive_workflow_plan("p1", "bd1", self.work, artifact_count=99,
                                    component_count=99, net_count=99)
        dv = _stage(plan, "deterministic-validation")
        self.assertEqual(dv.status, "blocked")
        self.assertTrue(any("no fallback" in b for b in dv.blockers))


class ApiCompatibilityTests(unittest.TestCase):
    """TV-A1-03: return shape identical to the static template plan."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-compat-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_template_function_still_pure_and_unchanged_shape(self):
        plan = plan_reference_board_workflow("p1", "bd1", 3, 10, 20, 0)
        d = plan.to_dict()
        self.assertEqual(sorted(d.keys()),
                         ["approval_gates", "board_design_id", "orchestration_model",
                          "project_id", "stages", "status", "warnings"])
        self.assertEqual(d["status"], "planned-with-blockers")

    def test_derived_plan_same_top_level_shape(self):
        dispatch_work_packet(self.work, "C04", "route")
        derived = derive_workflow_plan("p1", "bd1", self.work).to_dict()
        static = plan_reference_board_workflow("p1", "bd1", 0, 0, 0, 0).to_dict()
        self.assertEqual(sorted(derived.keys()), sorted(static.keys()))
        self.assertEqual(
            sorted(derived["stages"][0].keys()), sorted(static["stages"][0].keys()))

    def test_stage_sequence_identical(self):
        dispatch_work_packet(self.work, "C04", "route")
        derived = derive_workflow_plan("p1", "bd1", self.work)
        static = plan_reference_board_workflow("p1", "bd1", 0, 0, 0, 0)
        self.assertEqual([s.stage_id for s in derived.stages],
                         [s.stage_id for s in static.stages])


class McpToolTests(unittest.TestCase):
    """4.3: bodesign_reference_board_workflow uses the derived path."""

    def setUp(self):
        import importlib
        self.server = importlib.import_module("services.mcp.server")
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-wfmcp-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _rt(self, name, args):
        result = self.server.run_tool(name, args)
        self.assertTrue(result.get("ok"), result)
        return result["result"]

    def test_tool_reports_spine_not_initialized(self):
        plan = self._rt("bodesign_reference_board_workflow",
                        {"project_id": "p1", "board_design_id": "bd1", "folder": str(self.work)})
        self.assertEqual(plan["status"], "spine-not-initialized")

    def test_tool_derives_from_spine(self):
        self._rt("bodesign_dispatch_work_packet",
                 {"folder": str(self.work), "target_layer": "C04", "objective": "route"})
        plan = self._rt("bodesign_reference_board_workflow",
                        {"project_id": "p1", "board_design_id": "bd1", "folder": str(self.work)})
        self.assertEqual(plan["status"], "in-progress")


if __name__ == "__main__":
    unittest.main()
