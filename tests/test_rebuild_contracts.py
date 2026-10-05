"""Unit tests for Phase 1 Shared Contracts (Task 2.1 / AC1..AC5, AC9).

Covers:
- Versioned serialization and invariants per data-schema.json:
  ArtifactManifest, DesignRepresentations, VerificationRecord,
  ChangeProposal, ReleaseApproval, OperationOutcome.
- Deterministic hashing and canonical serialization.
- Compatibility adapter wrapping of raw tool outputs without mutating raw results.
- Strict rejection of default PASS on unknown coverage, missing dependencies,
  or non-current freshness.
"""

import copy
import hashlib
import json
import unittest

from bodesign_design_ir.rebuild_contracts import (
    ArtifactManifest,
    ArtifactRef,
    DependencyRef,
    DesignRepresentations,
)
from bodesign_workflow_core.rebuild_contracts import (
    ChangeProposal,
    OperationOutcome,
    ReleaseApproval,
    VerificationRecord,
    evaluate_change_proposal,
    evaluate_release_eligibility,
)
from bodesign_workflow_core.rebuild_compat import (
    CompatError,
    check_baseline_preconditions,
    check_release_preconditions,
    wrap_operation_outcome,
    wrap_raw_verification_result,
)


class TestArtifactAndDependencyContracts(unittest.TestCase):
    """Tests for ArtifactRef, DependencyRef, and ArtifactManifest."""

    def test_artifact_ref_valid_and_round_trip(self):
        digest = hashlib.sha256(b"dummy board content").hexdigest()
        ref = ArtifactRef(role="board", path="cad/board.kicad_pcb", sha256=digest, byte_size=1234)
        self.assertEqual(ref.role, "board")
        self.assertEqual(ref.path, "cad/board.kicad_pcb")
        self.assertEqual(ref.sha256, digest)
        self.assertEqual(ref.byte_size, 1234)

        d = ref.to_dict()
        self.assertEqual(d["path"], "cad/board.kicad_pcb")
        restored = ArtifactRef.from_dict(d)
        self.assertEqual(restored, ref)

    def test_artifact_ref_rejects_path_traversal_and_invalid_inputs(self):
        digest = "a" * 64
        # Traversal attempts
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="../outside.pcb", sha256=digest, byte_size=10)
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="/abs/path.pcb", sha256=digest, byte_size=10)
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="sub/../../escape.pcb", sha256=digest, byte_size=10)
        # Invalid hash length
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="board.pcb", sha256="tooshort", byte_size=10)
        # Negative byte size
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="board.pcb", sha256=digest, byte_size=-1)

    def test_dependency_ref_invariants(self):
        dep = DependencyRef(kind="tool", name="kicad_cli", version="8.0.4", digest="abc1234")
        self.assertEqual(dep.kind, "tool")
        self.assertEqual(dep.name, "kicad_cli")
        self.assertEqual(dep.version, "8.0.4")

        # Round trip
        d = dep.to_dict()
        restored = DependencyRef.from_dict(d)
        self.assertEqual(restored, dep)

        # Rejects unknown kind
        with self.assertRaises(ValueError):
            DependencyRef(kind="invalid_kind", name="foo", version="1.0")  # type: ignore

        # Rejects when both version and digest are None
        with self.assertRaises(ValueError):
            DependencyRef(kind="tool", name="foo", version=None, digest=None)

    def test_artifact_manifest_canonical_hashing_and_round_trip(self):
        digest1 = hashlib.sha256(b"netlist").hexdigest()
        digest2 = hashlib.sha256(b"schematic").hexdigest()
        artifacts = [
            ArtifactRef(role="schematic", path="sch/root.kicad_sch", sha256=digest2, byte_size=2000),
            ArtifactRef(role="netlist", path="sch/design.net", sha256=digest1, byte_size=500),
        ]
        deps = [
            DependencyRef(kind="tool", name="kicad", version="8.0.4"),
            DependencyRef(kind="rule", name="kicad_drc_rules", version="v2"),
        ]

        manifest = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_A1",
            artifacts=artifacts,
            dependencies=deps,
        )

        manifest_sha = manifest.manifest_sha256
        self.assertEqual(len(manifest_sha), 64)

        # Deterministic: regardless of initial artifact order in constructor,
        # canonical JSON sorts by path
        manifest_reversed = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_A1",
            artifacts=list(reversed(artifacts)),
            dependencies=deps,
        )
        self.assertEqual(manifest_reversed.manifest_sha256, manifest_sha)

        # Round-trip serialization
        m_dict = manifest.to_dict()
        restored = ArtifactManifest.from_dict(m_dict)
        self.assertEqual(restored.manifest_sha256, manifest_sha)


class TestDesignRepresentations(unittest.TestCase):
    """Tests for DesignRepresentations contract."""

    def test_design_representations_invariants(self):
        sha = "f" * 64
        dr = DesignRepresentations(
            intent_revision="rev_c03_01",
            native_manifest_sha256=sha,
            circuit={"nets": 10, "components": 5},
            presentation={"sheets": 1, "coordinates": "scaled"},
            layout_constraints={"layers": 4},
            reconciliation="consistent",
        )
        self.assertEqual(dr.reconciliation, "consistent")
        self.assertEqual(dr.intent_revision, "rev_c03_01")

        d = dr.to_dict()
        restored = DesignRepresentations.from_dict(d)
        self.assertEqual(restored.reconciliation, "consistent")
        self.assertEqual(restored.layout_constraints, {"layers": 4})


class TestVerificationRecord(unittest.TestCase):
    """Tests for VerificationRecord contract and invariants."""

    def setUp(self):
        self.subject_sha = "e" * 64
        self.tool_dep = DependencyRef(kind="tool", name="readability_gate", version="1.0.0")

    def test_verification_record_valid_pass(self):
        coverage = {
            "expected_ids": ["net_0", "net_1"],
            "examined_ids": ["net_0", "net_1"],
            "omitted": [],
        }
        rec = VerificationRecord(
            subject_manifest_sha256=self.subject_sha,
            execution="succeeded",
            verdict="pass",
            coverage=coverage,
            tool_rule_dependencies=[self.tool_dep],
            axis="form",
            findings=[],
            freshness="current",
        )
        self.assertEqual(rec.verdict, "pass")
        self.assertEqual(rec.freshness, "current")

    def test_verification_record_rejects_pass_with_unexamined_or_omitted_ids(self):
        # Omitted items prevent PASS
        coverage_omitted = {
            "expected_ids": ["net_0", "net_1"],
            "examined_ids": ["net_0"],
            "omitted": [{"id": "net_1", "reason": "unrouted"}],
        }
        with self.assertRaises(ValueError):
            VerificationRecord(
                subject_manifest_sha256=self.subject_sha,
                execution="succeeded",
                verdict="pass",
                coverage=coverage_omitted,
                tool_rule_dependencies=[self.tool_dep],
                axis="form",
            )

    def test_verification_record_rejects_pass_with_empty_examined_ids(self):
        coverage_empty = {
            "expected_ids": [],
            "examined_ids": [],
            "omitted": [],
        }
        with self.assertRaises(ValueError):
            VerificationRecord(
                subject_manifest_sha256=self.subject_sha,
                execution="succeeded",
                verdict="pass",
                coverage=coverage_empty,
                tool_rule_dependencies=[self.tool_dep],
                axis="form",
            )

    def test_verification_record_requires_reason_for_non_pass(self):
        coverage = {"expected_ids": ["net_0"], "examined_ids": ["net_0"], "omitted": []}
        # Incomplete / indeterminate requires reason
        with self.assertRaises(ValueError):
            VerificationRecord(
                subject_manifest_sha256=self.subject_sha,
                execution="succeeded",
                verdict="indeterminate",
                coverage=coverage,
                tool_rule_dependencies=[self.tool_dep],
                axis="electrical",
                reason=None,  # missing reason
            )

        # Not-applicable requires reason
        with self.assertRaises(ValueError):
            VerificationRecord(
                subject_manifest_sha256=self.subject_sha,
                execution="succeeded",
                verdict="not-applicable",
                coverage={"expected_ids": [], "examined_ids": [], "omitted": []},
                tool_rule_dependencies=[self.tool_dep],
                axis="electrical",
                reason=None,
            )


class TestChangeProposalAndReleaseApproval(unittest.TestCase):
    """Tests for ChangeProposal and ReleaseApproval contracts."""

    def setUp(self):
        self.sha = "1" * 64
        self.art = ArtifactRef(role="board", path="board.kicad_pcb", sha256=self.sha, byte_size=100)
        self.dep = DependencyRef(kind="tool", name="kicad", version="8.0")
        self.manifest = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_A1",
            artifacts=[self.art],
            dependencies=[self.dep],
        )
        self.manifest_sha = self.manifest.manifest_sha256

    def test_change_proposal_conflict_detection(self):
        # Proposal with pinned object mutation
        op_violating_pin = {
            "edit_class": "move_component",
            "target_id": "CONN1",
            "parameters": {"x": 50.0, "y": 20.0},
        }
        proposal = ChangeProposal(
            baseline_manifest_sha256=self.manifest_sha,
            supported_edit_classes=["move_component"],
            operations=[op_violating_pin],
            locked_object_ids=["CONN1", "HOLE1"],
        )

        conflicts = evaluate_change_proposal(proposal, self.manifest_sha)
        self.assertTrue(any(c["type"] == "LOCKED_OBJECT_MUTATION" for c in conflicts))

        # Check baseline precondition guard
        res = check_baseline_preconditions(self.manifest, self.manifest_sha, proposal)
        self.assertFalse(res["allowed"])
        self.assertEqual(res["conflict_code"], "PROPOSAL_CONFLICT")
        self.assertTrue(res["client_source_preserved"])

    def test_release_approval_evaluation(self):
        approval = ReleaseApproval(
            manifest_sha256=self.manifest_sha,
            decision="approved",
            actor="lead_engineer",
            recorded_at="2026-10-06T00:00:00Z",
            required_checks=["drc"],
        )

        dep = DependencyRef(kind="tool", name="drc", version="1.0")
        cov = {"expected_ids": ["t1"], "examined_ids": ["t1"], "omitted": []}
        passing_verification = VerificationRecord(
            subject_manifest_sha256=self.manifest_sha,
            execution="succeeded",
            verdict="pass",
            coverage=cov,
            tool_rule_dependencies=[dep],
            axis="electrical",
            freshness="current",
        )

        verifications = [passing_verification]
        eligibility = evaluate_release_eligibility(
            approval=approval,
            target_manifest_sha256=self.manifest_sha,
            verification_records=verifications,
            current_dependencies={"drc": "1.0"},
        )
        self.assertTrue(eligibility["eligible"])
        self.assertEqual(eligibility["reasons"], [])


class TestOperationOutcomeContract(unittest.TestCase):
    """Tests for OperationOutcome contract and envelope wrapping."""

    def test_operation_outcome_invariants(self):
        outcome_ok = OperationOutcome(
            module="A3",
            outcome="ok",
            code=None,
            subject_ref="board.kicad_pcb",
            details={"step": "route"},
        )
        self.assertEqual(outcome_ok.module, "A3")
        self.assertEqual(outcome_ok.outcome, "ok")
        self.assertIsNone(outcome_ok.code)

        # Non-ok outcome requires typed code
        with self.assertRaises(ValueError):
            OperationOutcome(module="A1", outcome="failed", code=None)

        # Invalid module
        with self.assertRaises(ValueError):
            OperationOutcome(module="B1", outcome="ok")  # type: ignore

    def test_wrap_operation_outcome_mcp_and_landing_envelopes(self):
        # 1. MCP ok envelope
        mcp_ok = {"ok": True, "result_status": "ok", "result": {"nets": 10}}
        out1 = wrap_operation_outcome(mcp_ok, module="A2")
        self.assertEqual(out1.outcome, "ok")
        self.assertIsNone(out1.code)
        self.assertEqual(out1.details["ok"], True)

        # 2. MCP error envelope
        mcp_err = {"ok": False, "error": {"code": "READABILITY_ARGS_INVALID", "message": "missing n"}}
        out2 = wrap_operation_outcome(mcp_err, module="A3")
        self.assertEqual(out2.outcome, "failed")
        self.assertEqual(out2.code, "READABILITY_ARGS_INVALID")

        # 3. Landing runner empty status envelope
        landing_empty = {"status": "empty", "code": "NO_NETS", "reason": "empty net list"}
        out3 = wrap_operation_outcome(landing_empty, module="A4")
        self.assertEqual(out3.outcome, "empty")
        self.assertEqual(out3.code, "NO_NETS")


class TestRebuildCompatAdapters(unittest.TestCase):
    """Tests for rebuild_compat wrapping existing raw tool results."""

    def setUp(self):
        self.subject_sha = "2" * 64
        self.tool_dep = DependencyRef(kind="tool", name="readability_gate", version="1.0.0")

    def test_raw_result_is_never_mutated(self):
        raw_result = {
            "status": "failed",
            "unmet": [
                {"criterion": "junctions", "observed": 5, "threshold": "> 20", "source": "BR_20260905"}
            ],
            "N": 10,
        }
        raw_copy = copy.deepcopy(raw_result)

        coverage = {"expected_ids": ["n1"], "examined_ids": ["n1"], "omitted": []}
        rec = wrap_raw_verification_result(
            tool="readability_gate",
            raw_result=raw_result,
            subject_manifest_sha256=self.subject_sha,
            axis="form",
            tool_rule_dependencies=[self.tool_dep],
            coverage=coverage,
            freshness="current",
        )

        # Raw result input must be strictly untouched
        self.assertEqual(raw_result, raw_copy)
        self.assertEqual(rec.verdict, "fail")
        self.assertEqual(len(rec.findings), 1)
        self.assertEqual(rec.findings[0]["id"], "readability-junctions")

    def test_unknown_coverage_or_freshness_rejects_default_pass(self):
        raw_ok = {
            "status": "ok",
            "unmet": [],
            "N": 0,  # Unknown / zero coverage
        }

        # Strict mode: rejects unknown coverage with CompatError
        with self.assertRaises(CompatError):
            wrap_raw_verification_result(
                tool="readability_gate",
                raw_result=raw_ok,
                subject_manifest_sha256=self.subject_sha,
                axis="form",
                tool_rule_dependencies=[self.tool_dep],
                coverage=None,
                freshness="current",
                strict=True,
            )

        # Non-strict mode: downgrades verdict to indeterminate, never PASS
        rec = wrap_raw_verification_result(
            tool="readability_gate",
            raw_result=raw_ok,
            subject_manifest_sha256=self.subject_sha,
            axis="form",
            tool_rule_dependencies=[self.tool_dep],
            coverage=None,
            freshness="current",
            strict=False,
        )
        self.assertEqual(rec.verdict, "indeterminate")
        self.assertIn("rejected", rec.reason.lower())

        # Unknown freshness must also reject PASS
        coverage = {"expected_ids": ["n1"], "examined_ids": ["n1"], "omitted": []}
        with self.assertRaises(CompatError):
            wrap_raw_verification_result(
                tool="readability_gate",
                raw_result=raw_ok,
                subject_manifest_sha256=self.subject_sha,
                axis="form",
                tool_rule_dependencies=[self.tool_dep],
                coverage=coverage,
                freshness="unknown",
                strict=True,
            )


if __name__ == "__main__":
    unittest.main()
