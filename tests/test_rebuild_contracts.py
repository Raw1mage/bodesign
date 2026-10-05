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
    ReleasePolicy,
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
        # Interior '..' and '.' segments (previously accepted)
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="a/..", sha256=digest, byte_size=10)
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="a/./b", sha256=digest, byte_size=10)
        with self.assertRaises(ValueError):
            ArtifactRef(role="board", path="a//b", sha256=digest, byte_size=10)
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

    def test_artifact_manifest_is_deeply_immutable_and_integrity_rechecked(self):
        digest = hashlib.sha256(b"x").hexdigest()
        manifest = ArtifactManifest(
            schema_version="1.0.0",
            revision_id="rev_A1",
            artifacts=[ArtifactRef(role="board", path="b.kicad_pcb", sha256=digest, byte_size=1)],
            dependencies=[DependencyRef(kind="tool", name="kicad", version="8.0.4")],
        )
        # Lists are frozen into tuples; attribute assignment is refused
        self.assertIsInstance(manifest.artifacts, tuple)
        with self.assertRaises(AttributeError):
            manifest.revision_id = "rev_B"
        with self.assertRaises(AttributeError):
            manifest.manifest_sha256 = "0" * 64
        self.assertEqual(manifest.verify_integrity(), manifest.manifest_sha256)
        # Forced bypass is caught at the decision boundary
        object.__setattr__(manifest, "revision_id", "rev_tampered")
        with self.assertRaises(ValueError) as ctx:
            manifest.verify_integrity()
        self.assertIn("MANIFEST_SHA256_MISMATCH", str(ctx.exception))
        with self.assertRaises(ValueError):
            check_baseline_preconditions(manifest, manifest.manifest_sha256)


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
            raw_snapshot={"status": "ok", "unmet": []},
        )
        self.assertEqual(rec.verdict, "pass")
        self.assertEqual(rec.freshness, "current")

    def test_verification_record_pass_requires_raw_evidence_and_tool_deps(self):
        coverage = {"expected_ids": ["n1"], "examined_ids": ["n1"], "omitted": []}
        # No raw evidence and no explicit absence reason -> rejected
        with self.assertRaises(ValueError) as ctx:
            VerificationRecord(
                subject_manifest_sha256=self.subject_sha,
                execution="succeeded",
                verdict="pass",
                coverage=coverage,
                tool_rule_dependencies=[self.tool_dep],
                axis="form",
                freshness="current",
            )
        self.assertIn("raw evidence", str(ctx.exception))
        # Explicit absence reason is accepted
        rec = VerificationRecord(
            subject_manifest_sha256=self.subject_sha,
            execution="succeeded",
            verdict="pass",
            coverage=coverage,
            tool_rule_dependencies=[self.tool_dep],
            axis="form",
            freshness="current",
            raw_evidence_absent_reason="tool emits no raw artifact; summary-only API",
        )
        self.assertEqual(rec.verdict, "pass")
        # No tool/rule dependency identity -> rejected
        with self.assertRaises(ValueError) as ctx:
            VerificationRecord(
                subject_manifest_sha256=self.subject_sha,
                execution="succeeded",
                verdict="pass",
                coverage=coverage,
                tool_rule_dependencies=[],
                axis="form",
                freshness="current",
                raw_snapshot={"status": "ok"},
            )
        self.assertIn("tool_rule_dependencies", str(ctx.exception))

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
        policy = ReleasePolicy(policy_id="release-default", version="1.0.0", required_checks=("drc",))

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
            raw_snapshot={"copper": 0, "unconnected": 0},
        )

        verifications = [passing_verification]
        eligibility = evaluate_release_eligibility(
            approval=approval,
            target_manifest_sha256=self.manifest_sha,
            verification_records=verifications,
            current_dependencies=[dep],
            policy=policy,
        )
        self.assertTrue(eligibility["eligible"])
        self.assertEqual(eligibility["reasons"], [])

        # No policy: required checks cannot be derived from the approval alone
        no_policy = evaluate_release_eligibility(
            approval=approval,
            target_manifest_sha256=self.manifest_sha,
            verification_records=verifications,
            current_dependencies=[dep],
        )
        self.assertFalse(no_policy["eligible"])
        self.assertTrue(any("No explicit versioned release policy" in r for r in no_policy["reasons"]))

        # Approval cannot reduce policy
        wide_policy = ReleasePolicy(policy_id="release-default", version="1.1.0", required_checks=("drc", "si_check"))
        reduced = evaluate_release_eligibility(
            approval=approval,
            target_manifest_sha256=self.manifest_sha,
            verification_records=verifications,
            current_dependencies=[dep],
            policy=wide_policy,
        )
        self.assertFalse(reduced["eligible"])
        self.assertTrue(any("approval cannot reduce policy" in r for r in reduced["reasons"]))
        self.assertTrue(any("'si_check' has no verification record" in r for r in reduced["reasons"]))

        # Empty policy is rejected at construction
        with self.assertRaises(ValueError):
            ReleasePolicy(policy_id="p", version="1", required_checks=())

        # Axis names are not check ids: a record whose deps do not name the check does not cover it
        axis_only_policy = ReleasePolicy(policy_id="p", version="1", required_checks=("electrical",))
        axis_only = evaluate_release_eligibility(
            approval=ReleaseApproval(
                manifest_sha256=self.manifest_sha, decision="approved", actor="a",
                recorded_at="t", required_checks=["electrical"],
            ),
            target_manifest_sha256=self.manifest_sha,
            verification_records=verifications,
            current_dependencies=[dep],
            policy=axis_only_policy,
        )
        self.assertFalse(axis_only["eligible"])

        # Caller-set freshness='current' with absent current deps -> unknown, blocks
        absent_env = evaluate_release_eligibility(
            approval=approval,
            target_manifest_sha256=self.manifest_sha,
            verification_records=verifications,
            current_dependencies=None,
            policy=policy,
        )
        self.assertFalse(absent_env["eligible"])
        self.assertTrue(any("'unknown'" in r for r in absent_env["reasons"]))
        self.assertEqual(passing_verification.freshness, "unknown")

    def test_round2_check_identity_is_tool_or_rule_kind_only(self):
        policy = ReleasePolicy(policy_id="p", version="1", required_checks=("drc",))
        approval = ReleaseApproval(
            manifest_sha256=self.manifest_sha, decision="approved", actor="a",
            recorded_at="t", required_checks=["drc"],
        )
        cov = {"expected_ids": ["t1"], "examined_ids": ["t1"], "omitted": []}
        # A LIBRARY dependency named 'drc' must NOT satisfy the 'drc' check
        lib_named_like_check = DependencyRef(kind="library", name="drc", version="1.0")
        rec_lib = VerificationRecord(
            subject_manifest_sha256=self.manifest_sha, execution="succeeded", verdict="pass",
            coverage=cov, tool_rule_dependencies=[lib_named_like_check], axis="electrical",
            freshness="current", raw_snapshot={"copper": 0},
        )
        res = evaluate_release_eligibility(
            approval=approval, target_manifest_sha256=self.manifest_sha,
            verification_records=[rec_lib], current_dependencies=[lib_named_like_check], policy=policy,
        )
        self.assertFalse(res["eligible"])
        self.assertTrue(any("'drc' has no verification record" in r for r in res["reasons"]))
        # The same through the compat guard
        guard = check_release_preconditions(
            target_manifest=self.manifest, approvals=[approval], verifications=[rec_lib],
            current_dependencies=[lib_named_like_check], policy=policy,
        )
        self.assertFalse(guard["eligible"])
        self.assertTrue(any("'drc' has no verification record" in r for r in guard["reasons"]))
        # A RULE dependency named 'drc' does satisfy it
        rule_dep = DependencyRef(kind="rule", name="drc", version="1.0")
        rec_rule = VerificationRecord(
            subject_manifest_sha256=self.manifest_sha, execution="succeeded", verdict="pass",
            coverage=cov, tool_rule_dependencies=[rule_dep], axis="electrical",
            freshness="current", raw_snapshot={"copper": 0},
        )
        res_ok = evaluate_release_eligibility(
            approval=approval, target_manifest_sha256=self.manifest_sha,
            verification_records=[rec_rule], current_dependencies=[rule_dep], policy=policy,
        )
        self.assertTrue(res_ok["eligible"], res_ok["reasons"])


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

    def test_wrap_operation_outcome_inner_refusal_and_unknown_status_never_ok(self):
        # Inner handler refusal wrapped in a transport ok:true envelope (real MCP shape)
        mcp_inner_refusal = {
            "ok": True,
            "result": {"ok": False, "error": {"code": "NETLIST_MISSING", "message": "no file"}},
        }
        out = wrap_operation_outcome(mcp_inner_refusal, module="A3")
        self.assertEqual(out.outcome, "failed")
        self.assertEqual(out.code, "NETLIST_MISSING")
        # Raw transport preserved
        self.assertEqual(out.details, mcp_inner_refusal)

        # Unknown status string is never promoted to ok
        unknown = {"ok": True, "result_status": "weird-state", "result": {"status": "weird-state"}}
        out_unknown = wrap_operation_outcome(unknown, module="A3")
        self.assertEqual(out_unknown.outcome, "indeterminate")
        self.assertEqual(out_unknown.code, "UNKNOWN_STATUS_WEIRD-STATE")

        # Inner status 'error' (server _apply_result_status flips ok) stays failed
        server_error = {"ok": False, "result": {"status": "error", "note": "boom"},
                        "result_status": "error", "error": "TOOL_REPORTED_ERROR"}
        out_err = wrap_operation_outcome(server_error, module="A3")
        self.assertEqual(out_err.outcome, "failed")
        self.assertEqual(out_err.code, "TOOL_REPORTED_ERROR")


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

    def test_round2_unknown_tool_or_unrecognized_status_never_passes(self):
        full_cov = {"expected_ids": ["n1"], "examined_ids": ["n1"], "omitted": []}
        dep = DependencyRef(kind="tool", name="mystery_checker", version="1.0")
        # Unregistered tool with a plausible success-looking raw result, full coverage/deps/freshness
        raw_unknown_tool = {"status": "ok", "findings": []}
        with self.assertRaises(CompatError) as ctx:
            wrap_raw_verification_result(
                tool="mystery_checker", raw_result=raw_unknown_tool,
                subject_manifest_sha256=self.subject_sha, axis="electrical",
                tool_rule_dependencies=[dep], coverage=full_cov, freshness="current", strict=True,
            )
        self.assertIn("TOOL_STATUS_MAP_UNREGISTERED", str(ctx.exception))
        rec = wrap_raw_verification_result(
            tool="mystery_checker", raw_result=raw_unknown_tool,
            subject_manifest_sha256=self.subject_sha, axis="electrical",
            tool_rule_dependencies=[dep], coverage=full_cov, freshness="current", strict=False,
        )
        self.assertEqual(rec.verdict, "indeterminate")
        self.assertIn("no registered status mapping", rec.reason)

        # Registered tool, MISSING status: zero findings must not read as success
        drc_dep = DependencyRef(kind="tool", name="drc_gate", version="2.0")
        rec_missing = wrap_raw_verification_result(
            tool="drc_gate", raw_result={"copper": 0, "unconnected": 0, "silk": 0},
            subject_manifest_sha256=self.subject_sha, axis="electrical",
            tool_rule_dependencies=[drc_dep], coverage=full_cov, freshness="current", strict=True,
        )
        self.assertEqual(rec_missing.verdict, "indeterminate")
        self.assertIn("not a recognized checker result", rec_missing.reason)

        # Registered tool, UNRECOGNIZED status string
        rec_weird = wrap_raw_verification_result(
            tool="drc_gate", raw_result={"status": "probably-fine", "copper": 0},
            subject_manifest_sha256=self.subject_sha, axis="electrical",
            tool_rule_dependencies=[drc_dep], coverage=full_cov, freshness="current", strict=True,
        )
        self.assertEqual(rec_weird.verdict, "indeterminate")
        self.assertIn("'probably-fine'", rec_weird.reason)

        # Registered tool, explicit recognized success -> PASS
        rec_pass = wrap_raw_verification_result(
            tool="drc_gate", raw_result={"status": "clean", "copper": 0, "unconnected": 0},
            subject_manifest_sha256=self.subject_sha, axis="electrical",
            tool_rule_dependencies=[drc_dep], coverage=full_cov, freshness="current", strict=True,
        )
        self.assertEqual(rec_pass.verdict, "pass")
        self.assertEqual(rec_pass.raw_snapshot, {"status": "clean", "copper": 0, "unconnected": 0})

        # Recognized failure status for a registered tool still fails
        rec_fail = wrap_raw_verification_result(
            tool="constraint_solve", raw_result={"solver_verdict": "unsat", "status": "unsat"},
            subject_manifest_sha256=self.subject_sha, axis="electrical",
            tool_rule_dependencies=[DependencyRef(kind="tool", name="constraint_solve", version="1")],
            coverage=full_cov, freshness="current",
        )
        self.assertEqual(rec_fail.verdict, "fail")


if __name__ == "__main__":
    unittest.main()
