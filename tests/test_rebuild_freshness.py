"""Unit tests for Freshness & Mismatch Enforcement (Task 2.2 / AC3, AC6, AC7).

Covers:
- Dependency-derived staleness (subject hash change, tool version bump,
  rule update, library change, missing dependency).
- Baseline/proposal/approval mismatch rejected before any write.
- Client source unchanged on conflict.
- Raw results preserved untouched across compatibility wrapping.
- Release precondition enforcement against stale/unapproved states.
"""

import copy
import hashlib
import unittest

from bodesign_design_ir.rebuild_contracts import (
    ArtifactManifest,
    ArtifactRef,
    DependencyRef,
)
from bodesign_workflow_core.rebuild_contracts import (
    ChangeProposal,
    ReleaseApproval,
    VerificationRecord,
    evaluate_change_proposal,
    evaluate_freshness,
    evaluate_release_eligibility,
)
from bodesign_workflow_core.rebuild_compat import (
    CompatError,
    check_baseline_preconditions,
    check_release_preconditions,
    wrap_raw_verification_result,
)


class TestDependencyDerivedFreshness(unittest.TestCase):
    """Tests for evaluate_freshness across tool, rule, library, and source changes."""

    def setUp(self):
        self.tool_dep = DependencyRef(kind="tool", name="kicad_cli", version="8.0.4")
        self.rule_dep = DependencyRef(kind="rule", name="jlcpcb_4layer", version="v2.1")
        self.lib_dep = DependencyRef(kind="library", name="device_symbols", digest="d" * 64)

    def test_current_when_all_dependencies_match(self):
        current_env = {
            "kicad_cli": "8.0.4",
            "jlcpcb_4layer": "v2.1",
            "device_symbols": "d" * 64,
        }
        res = evaluate_freshness(current_env, [self.tool_dep, self.rule_dep, self.lib_dep])
        self.assertEqual(res, "current")

    def test_stale_when_tool_version_bumped(self):
        # Current tool updated to 8.0.5
        current_env = {
            "kicad_cli": "8.0.5",
            "jlcpcb_4layer": "v2.1",
            "device_symbols": "d" * 64,
        }
        res = evaluate_freshness(current_env, [self.tool_dep, self.rule_dep, self.lib_dep])
        self.assertEqual(res, "stale")

    def test_stale_when_rule_version_changed(self):
        # DRC rule updated to v2.2
        current_env = {
            "kicad_cli": "8.0.4",
            "jlcpcb_4layer": "v2.2",
            "device_symbols": "d" * 64,
        }
        res = evaluate_freshness(current_env, [self.tool_dep, self.rule_dep])
        self.assertEqual(res, "stale")

    def test_stale_when_library_digest_differs(self):
        # Library hash updated
        current_env = {
            "kicad_cli": "8.0.4",
            "device_symbols": "e" * 64,
        }
        res = evaluate_freshness(current_env, [self.tool_dep, self.lib_dep])
        self.assertEqual(res, "stale")

    def test_unknown_when_dependency_missing_from_environment(self):
        # Environment does not have jlcpcb_4layer
        current_env = {
            "kicad_cli": "8.0.4",
        }
        res = evaluate_freshness(current_env, [self.tool_dep, self.rule_dep])
        self.assertEqual(res, "unknown")

    def test_unknown_when_no_dependencies_recorded(self):
        current_env = {"kicad_cli": "8.0.4"}
        res = evaluate_freshness(current_env, [])
        self.assertEqual(res, "unknown")


class TestBaselineAndProposalMismatchEnforcement(unittest.TestCase):
    """Tests for rejecting mutations before write and preserving client sources."""

    def setUp(self):
        self.art = ArtifactRef(role="board", path="cad/board.kicad_pcb", sha256="a" * 64, byte_size=1000)
        self.dep = DependencyRef(kind="tool", name="kicad", version="8.0.4")
        self.manifest_v1 = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_1",
            artifacts=[self.art],
            dependencies=[self.dep],
        )
        self.manifest_v1_sha = self.manifest_v1.manifest_sha256

        # Second manifest representing concurrent edit
        art_v2 = ArtifactRef(role="board", path="cad/board.kicad_pcb", sha256="b" * 64, byte_size=1020)
        self.manifest_v2 = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_2",
            artifacts=[art_v2],
            dependencies=[self.dep],
        )
        self.manifest_v2_sha = self.manifest_v2.manifest_sha256

    def test_baseline_mismatch_stops_write_and_preserves_source(self):
        # Proposal created against v1 baseline, but workspace is now at v2
        proposal = ChangeProposal(
            baseline_manifest_sha256=self.manifest_v1_sha,
            supported_edit_classes=["move_component"],
            operations=[{"edit_class": "move_component", "target_id": "R1", "x": 10.0}],
            locked_object_ids=[],
        )

        res = check_baseline_preconditions(self.manifest_v2, self.manifest_v1_sha, proposal)
        self.assertFalse(res["allowed"])
        self.assertEqual(res["conflict_code"], "BASELINE_MISMATCH")
        self.assertTrue(res["client_source_preserved"])
        self.assertIn("does not match", res["reason"])

    def test_locked_object_conflict_stops_write(self):
        proposal = ChangeProposal(
            baseline_manifest_sha256=self.manifest_v1_sha,
            supported_edit_classes=["move_component"],
            operations=[{"edit_class": "move_component", "target_id": "CONN_USB", "x": 10.0}],
            locked_object_ids=["CONN_USB"],  # Edge connector locked to enclosure
        )

        res = check_baseline_preconditions(self.manifest_v1, self.manifest_v1_sha, proposal)
        self.assertFalse(res["allowed"])
        self.assertEqual(res["conflict_code"], "PROPOSAL_CONFLICT")
        self.assertTrue(res["client_source_preserved"])
        self.assertTrue(any(c["type"] == "LOCKED_OBJECT_MUTATION" for c in res["conflicts"]))

    def test_unsupported_edit_class_conflict_stops_write(self):
        proposal = ChangeProposal(
            baseline_manifest_sha256=self.manifest_v1_sha,
            supported_edit_classes=["move_component"],
            operations=[{"edit_class": "delete_net", "target_id": "NET_GND"}],
            locked_object_ids=[],
        )

        res = check_baseline_preconditions(self.manifest_v1, self.manifest_v1_sha, proposal)
        self.assertFalse(res["allowed"])
        self.assertEqual(res["conflict_code"], "PROPOSAL_CONFLICT")
        self.assertTrue(res["client_source_preserved"])
        self.assertTrue(any(c["type"] == "UNSUPPORTED_EDIT_CLASS" for c in res["conflicts"]))


class TestReleasePreconditionEnforcement(unittest.TestCase):
    """Tests release eligibility refusing unapproved, changed, or stale states."""

    def setUp(self):
        self.art = ArtifactRef(role="board", path="board.kicad_pcb", sha256="c" * 64, byte_size=5000)
        self.dep = DependencyRef(kind="tool", name="drc_gate", version="2.0.0")
        self.manifest = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_rel",
            artifacts=[self.art],
            dependencies=[self.dep],
        )
        self.manifest_sha = self.manifest.manifest_sha256

        self.valid_approval = ReleaseApproval(
            manifest_sha256=self.manifest_sha,
            decision="approved",
            actor="qa_lead",
            recorded_at="2026-10-06T01:00:00Z",
            required_checks=["drc_gate"],
        )

    def test_post_validation_manifest_change_invalidates_prior_release(self):
        cov = {"expected_ids": ["item1"], "examined_ids": ["item1"], "omitted": []}
        verification = VerificationRecord(
            subject_manifest_sha256=self.manifest_sha,
            execution="succeeded",
            verdict="pass",
            coverage=cov,
            tool_rule_dependencies=[self.dep],
            axis="electrical",
            freshness="current",
        )

        # Mutated manifest post-validation
        mutated_art = ArtifactRef(role="board", path="board.kicad_pcb", sha256="f" * 64, byte_size=5050)
        mutated_manifest = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_rel_mutated",
            artifacts=[mutated_art],
            dependencies=[self.dep],
        )

        # Evaluating against mutated manifest MUST fail
        eligibility = check_release_preconditions(
            target_manifest=mutated_manifest,
            approvals=[self.valid_approval],
            verifications=[verification],
            current_dependencies=[self.dep],
        )
        self.assertFalse(eligibility["eligible"])
        self.assertTrue(any("Approval manifest mismatch" in r or "!=" in r for r in eligibility["reasons"]))

    def test_stale_evidence_blocks_release(self):
        cov = {"expected_ids": ["item1"], "examined_ids": ["item1"], "omitted": []}
        # Evidence was run with drc_gate version 2.0.0
        verification = VerificationRecord(
            subject_manifest_sha256=self.manifest_sha,
            execution="succeeded",
            verdict="pass",
            coverage=cov,
            tool_rule_dependencies=[self.dep],
            axis="electrical",
            freshness="current",
        )

        # Current environment bumped drc_gate to 2.1.0
        bumped_dep = DependencyRef(kind="tool", name="drc_gate", version="2.1.0")

        eligibility = check_release_preconditions(
            target_manifest=self.manifest,
            approvals=[self.valid_approval],
            verifications=[verification],
            current_dependencies=[bumped_dep],
        )
        self.assertFalse(eligibility["eligible"])
        self.assertTrue(any("must be 'current'" in r or "stale" in r for r in eligibility["reasons"]))

    def test_unapproved_release_blocks_release(self):
        rejected_approval = ReleaseApproval(
            manifest_sha256=self.manifest_sha,
            decision="rejected",
            actor="qa_lead",
            recorded_at="2026-10-06T01:00:00Z",
            required_checks=["drc_gate"],
        )
        cov = {"expected_ids": ["item1"], "examined_ids": ["item1"], "omitted": []}
        verification = VerificationRecord(
            subject_manifest_sha256=self.manifest_sha,
            execution="succeeded",
            verdict="pass",
            coverage=cov,
            tool_rule_dependencies=[self.dep],
            axis="electrical",
            freshness="current",
        )

        eligibility = check_release_preconditions(
            target_manifest=self.manifest,
            approvals=[rejected_approval],
            verifications=[verification],
            current_dependencies=[self.dep],
        )
        self.assertFalse(eligibility["eligible"])
        self.assertTrue(any("decision is 'rejected'" in r for r in eligibility["reasons"]))


class TestRawResultImmutability(unittest.TestCase):
    """Tests ensuring raw checker outputs are preserved untouched across adapters."""

    def test_raw_result_dictionary_is_never_mutated(self):
        raw_complex_tool_result = {
            "status": "failed",
            "copper": 3,
            "unconnected": 1,
            "silk": 0,
            "details": {
                "nets": ["VCC", "GND"],
                "violations": [{"id": "v1", "pos": [10.5, 20.2]}],
            },
        }
        original_copy = copy.deepcopy(raw_complex_tool_result)

        dep = DependencyRef(kind="tool", name="drc_gate", version="1.0.0")
        cov = {"expected_ids": ["n1"], "examined_ids": ["n1"], "omitted": []}

        # Wrap in compatibility adapter
        rec = wrap_raw_verification_result(
            tool="drc_gate",
            raw_result=raw_complex_tool_result,
            subject_manifest_sha256="0" * 64,
            axis="electrical",
            tool_rule_dependencies=[dep],
            coverage=cov,
            freshness="current",
        )

        # Assert raw dict is strictly unmodified
        self.assertEqual(raw_complex_tool_result, original_copy)
        self.assertEqual(raw_complex_tool_result["copper"], 3)
        self.assertEqual(raw_complex_tool_result["details"]["violations"][0]["id"], "v1")


if __name__ == "__main__":
    unittest.main()
