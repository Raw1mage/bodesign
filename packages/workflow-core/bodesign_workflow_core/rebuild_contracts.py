"""Unified Collaborative Rebuild — Workflow, Evidence & Policy Contracts (P1/DD-1..12).

Implements VerificationRecord, InterferenceRecord, ChangeProposal, ReleaseApproval,
OperationOutcome, and freshness / baseline mismatch / release eligibility evaluation
per data-schema.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from bodesign_design_ir.rebuild_contracts import (
    ArtifactManifest,
    ArtifactRef,
    DependencyRef,
)


# ---------------------------------------------------------------------------
# 2.1 VerificationRecord Contract
# ---------------------------------------------------------------------------

EXECUTION_STATES = frozenset({"succeeded", "failed", "not-run"})
VERDICT_STATES = frozenset({"pass", "fail", "indeterminate", "not-applicable"})
AXIS_DOMAINS = frozenset({"electrical", "form", "mechanical", "manufacturing"})
FRESHNESS_STATES = frozenset({"current", "stale", "unknown"})


@dataclass
class VerificationRecord:
    """Artifact-bound verification record with coverage, findings, and freshness."""
    subject_manifest_sha256: str
    execution: Literal["succeeded", "failed", "not-run"]
    verdict: Literal["pass", "fail", "indeterminate", "not-applicable"]
    coverage: dict[str, Any]
    tool_rule_dependencies: list[DependencyRef]
    axis: Literal["electrical", "form", "mechanical", "manufacturing"]
    findings: list[dict[str, Any]] = field(default_factory=list)
    raw_result_ref: ArtifactRef | None = None
    reason: str | None = None
    freshness: Literal["current", "stale", "unknown"] = "unknown"

    def __post_init__(self) -> None:
        if not self.subject_manifest_sha256:
            raise ValueError("VerificationRecord requires subject_manifest_sha256")
        if self.execution not in EXECUTION_STATES:
            raise ValueError(f"execution must be in {sorted(EXECUTION_STATES)}, got {self.execution!r}")
        if self.verdict not in VERDICT_STATES:
            raise ValueError(f"verdict must be in {sorted(VERDICT_STATES)}, got {self.verdict!r}")
        if self.axis not in AXIS_DOMAINS:
            raise ValueError(f"axis must be in {sorted(AXIS_DOMAINS)}, got {self.axis!r}")
        if self.freshness not in FRESHNESS_STATES:
            raise ValueError(f"freshness must be in {sorted(FRESHNESS_STATES)}, got {self.freshness!r}")

        # Coverage validation
        for k in ("expected_ids", "examined_ids", "omitted"):
            if k not in self.coverage:
                raise ValueError(f"VerificationRecord coverage missing required field: {k!r}")

        expected = set(self.coverage.get("expected_ids", []))
        examined = set(self.coverage.get("examined_ids", []))
        omitted_records = self.coverage.get("omitted", [])
        omitted_ids = {o["id"] for o in omitted_records if isinstance(o, dict) and "id" in o}

        # Examined must be subset of expected
        if not examined.issubset(expected):
            diff = examined - expected
            raise ValueError(f"examined_ids contains IDs not in expected_ids: {sorted(diff)}")

        # Omitted must match expected minus examined exactly
        expected_omitted = expected - examined
        if omitted_ids != expected_omitted:
            raise ValueError(
                f"Coverage inconsistency: omitted IDs {sorted(omitted_ids)} != (expected - examined) {sorted(expected_omitted)}"
            )

        # Verdict: PASS invariants
        if self.verdict == "pass":
            if self.execution != "succeeded":
                raise ValueError(f"Verdict 'pass' requires execution 'succeeded', got {self.execution!r}")
            if not examined:
                raise ValueError("Verdict 'pass' requires non-empty examined_ids")
            if omitted_ids:
                raise ValueError(f"Verdict 'pass' forbidden with unexamined/omitted IDs: {sorted(omitted_ids)}")

        # Verdict: NOT-APPLICABLE invariants
        if self.verdict == "not-applicable" and not self.reason:
            raise ValueError("Verdict 'not-applicable' requires explicit justification in 'reason'")

        # Incomplete / failed execution requires reason
        if (self.execution in ("failed", "not-run") or self.verdict == "indeterminate") and not self.reason:
            raise ValueError(f"VerificationRecord with execution={self.execution!r}, verdict={self.verdict!r} requires reason")

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_manifest_sha256": self.subject_manifest_sha256,
            "execution": self.execution,
            "verdict": self.verdict,
            "coverage": self.coverage,
            "tool_rule_dependencies": [d.to_dict() for d in self.tool_rule_dependencies],
            "axis": self.axis,
            "findings": self.findings,
            "raw_result_ref": self.raw_result_ref.to_dict() if self.raw_result_ref else None,
            "reason": self.reason,
            "freshness": self.freshness,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationRecord:
        deps = [DependencyRef.from_dict(d) for d in data.get("tool_rule_dependencies", [])]
        raw_ref = ArtifactRef.from_dict(data["raw_result_ref"]) if data.get("raw_result_ref") else None
        return cls(
            subject_manifest_sha256=str(data["subject_manifest_sha256"]),
            execution=data["execution"],
            verdict=data["verdict"],
            coverage=dict(data.get("coverage", {})),
            tool_rule_dependencies=deps,
            axis=data["axis"],
            findings=list(data.get("findings", [])),
            raw_result_ref=raw_ref,
            reason=data.get("reason"),
            freshness=data.get("freshness", "unknown"),
        )


# ---------------------------------------------------------------------------
# 2.4 InterferenceRecord Contract
# ---------------------------------------------------------------------------

INTERFERENCE_METHODS = frozenset({"aabb-broad-phase", "exact-solid"})


@dataclass
class InterferenceRecord:
    """Mechanical collision check record with broad-phase vs exact distinction."""
    subject_manifest_sha256: str
    method: Literal["aabb-broad-phase", "exact-solid"]
    pairs: list[dict[str, Any]]
    policy: dict[str, Any]
    coverage: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.subject_manifest_sha256:
            raise ValueError("InterferenceRecord requires subject_manifest_sha256")
        if self.method not in INTERFERENCE_METHODS:
            raise ValueError(f"method must be in {sorted(INTERFERENCE_METHODS)}, got {self.method!r}")

        # Policy requirements
        for req in ("required_clearance_mm", "declared_contacts", "tolerance_mm", "backend", "backend_version"):
            if req not in self.policy:
                raise ValueError(f"InterferenceRecord.policy missing required key: {req!r}")

        # Coverage requirements
        for req in ("expected_model_ids", "available_solid_ids", "missing_ids"):
            if req not in self.coverage:
                raise ValueError(f"InterferenceRecord.coverage missing required key: {req!r}")

    @property
    def is_exact_certified(self) -> bool:
        """AABB broad-phase CANNOT certify exact mechanical clearance."""
        if self.method != "exact-solid":
            return False
        if bool(self.coverage.get("missing_ids")):
            return False
        if self.policy.get("tolerance_mm") is None or self.policy.get("required_clearance_mm") is None:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_manifest_sha256": self.subject_manifest_sha256,
            "method": self.method,
            "pairs": self.pairs,
            "policy": self.policy,
            "coverage": self.coverage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterferenceRecord:
        return cls(
            subject_manifest_sha256=str(data["subject_manifest_sha256"]),
            method=data["method"],
            pairs=list(data.get("pairs", [])),
            policy=dict(data.get("policy", {})),
            coverage=dict(data.get("coverage", {})),
        )


# ---------------------------------------------------------------------------
# 2.1 & 2.2 ChangeProposal & Concurrency Evaluation
# ---------------------------------------------------------------------------

@dataclass
class ChangeProposal:
    """Baseline-aware proposal with declared supported edit classes and lock preservation."""
    baseline_manifest_sha256: str
    supported_edit_classes: list[str]
    operations: list[dict[str, Any]]
    locked_object_ids: list[str]
    approval_ref: str | None = None
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.baseline_manifest_sha256:
            raise ValueError("baseline_manifest_sha256 is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_manifest_sha256": self.baseline_manifest_sha256,
            "supported_edit_classes": list(self.supported_edit_classes),
            "operations": list(self.operations),
            "locked_object_ids": list(self.locked_object_ids),
            "approval_ref": self.approval_ref,
            "conflicts": list(self.conflicts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeProposal:
        return cls(
            baseline_manifest_sha256=str(data["baseline_manifest_sha256"]),
            supported_edit_classes=list(data.get("supported_edit_classes", [])),
            operations=list(data.get("operations", [])),
            locked_object_ids=list(data.get("locked_object_ids", [])),
            approval_ref=data.get("approval_ref"),
            conflicts=list(data.get("conflicts", [])),
        )


def evaluate_change_proposal(
    proposal: ChangeProposal,
    current_native_manifest_sha256: str,
) -> list[dict[str, Any]]:
    """Evaluate change proposal against current baseline and edit constraints.

    Returns non-empty conflict list on any mismatch or unsupported operation;
    caller must stop before writing, leaving client source unchanged.
    """
    conflicts: list[dict[str, Any]] = []

    # 1. Baseline precondition check
    if current_native_manifest_sha256.lower() != proposal.baseline_manifest_sha256.lower():
        conflicts.append({
            "type": "BASELINE_MISMATCH",
            "message": f"Native manifest has changed: expected {proposal.baseline_manifest_sha256}, current is {current_native_manifest_sha256}",
            "baseline_expected": proposal.baseline_manifest_sha256,
            "baseline_current": current_native_manifest_sha256,
        })

    locked_set = set(proposal.locked_object_ids)
    supported_classes = set(proposal.supported_edit_classes)

    # 2. Operations check
    for op in proposal.operations:
        op_id = op.get("target_id")
        op_class = op.get("edit_class")

        if op_id in locked_set:
            conflicts.append({
                "type": "LOCKED_OBJECT_MUTATION",
                "target_id": op_id,
                "message": f"Target object {op_id!r} is locked and cannot be modified without explicit unlock",
            })

        if op_class not in supported_classes:
            conflicts.append({
                "type": "UNSUPPORTED_EDIT_CLASS",
                "edit_class": op_class,
                "target_id": op_id,
                "message": f"Edit class {op_class!r} is not in supported_edit_classes {sorted(supported_classes)}",
            })

    proposal.conflicts = list(conflicts)
    return conflicts


# ---------------------------------------------------------------------------
# 2.1 & 2.2 ReleaseApproval & Release Eligibility Evaluation
# ---------------------------------------------------------------------------

@dataclass
class ReleaseApproval:
    """Explicit human-issued release approval bound to final artifact manifest."""
    manifest_sha256: str
    decision: Literal["approved", "rejected"]
    actor: str
    recorded_at: str
    required_checks: list[str]

    def __post_init__(self) -> None:
        if not self.manifest_sha256:
            raise ValueError("ReleaseApproval manifest_sha256 is required")
        if self.decision not in ("approved", "rejected"):
            raise ValueError(f"ReleaseApproval decision must be 'approved' or 'rejected', got {self.decision!r}")
        if not self.actor:
            raise ValueError("ReleaseApproval actor is required")
        if not self.recorded_at:
            raise ValueError("ReleaseApproval recorded_at is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_sha256": self.manifest_sha256,
            "decision": self.decision,
            "actor": self.actor,
            "recorded_at": self.recorded_at,
            "required_checks": list(self.required_checks),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleaseApproval:
        return cls(
            manifest_sha256=str(data["manifest_sha256"]),
            decision=data["decision"],
            actor=str(data["actor"]),
            recorded_at=str(data["recorded_at"]),
            required_checks=list(data.get("required_checks", [])),
        )


def evaluate_freshness(
    current_dependencies: dict[str, str],
    record_dependencies: list[DependencyRef],
) -> Literal["current", "stale", "unknown"]:
    """Derive verification record freshness by comparing recorded dependencies with current environment."""
    if not record_dependencies:
        return "unknown"

    for dep in record_dependencies:
        curr_ver = current_dependencies.get(dep.name)
        if curr_ver is None:
            # Missing dependency in current environment
            return "unknown"

        recorded = dep.version or dep.digest
        if not recorded:
            return "unknown"

        if recorded != curr_ver:
            # Version or digest mismatch -> stale
            return "stale"

    return "current"


def evaluate_release_eligibility(
    approval: ReleaseApproval | None,
    target_manifest_sha256: str,
    verification_records: list[VerificationRecord],
    current_dependencies: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Verify that all required release checks are satisfied with current, non-stale evidence."""
    reasons: list[str] = []

    # 1. Human Approval Check
    if approval is None:
        return {"eligible": False, "reasons": ["Human approval is absent"]}
    if approval.decision != "approved":
        return {"eligible": False, "reasons": [f"Human decision is {approval.decision!r}, not 'approved'"]}
    if approval.manifest_sha256.lower() != target_manifest_sha256.lower():
        reasons.append(
            f"Approval manifest mismatch: approved {approval.manifest_sha256} != target {target_manifest_sha256}"
        )

    # Index records by check / tool name and axis
    records_by_key: dict[str, list[VerificationRecord]] = {}
    for r in verification_records:
        records_by_key.setdefault(r.axis, []).append(r)
        for dep in r.tool_rule_dependencies:
            records_by_key.setdefault(dep.name, []).append(r)

    # 2. Required Checks Coverage & Verdict
    for check_id in approval.required_checks:
        matching = records_by_key.get(check_id, [])
        if not matching:
            reasons.append(f"Required check {check_id!r} has no verification record")
            continue

        # Evaluate every matching record
        for rec in matching:
            # Subject manifest must match release target
            if rec.subject_manifest_sha256.lower() != target_manifest_sha256.lower():
                reasons.append(f"Check {check_id!r} subject {rec.subject_manifest_sha256} != release target {target_manifest_sha256}")

            # Freshness evaluation
            freshness = rec.freshness
            if current_dependencies is not None:
                freshness = evaluate_freshness(current_dependencies, rec.tool_rule_dependencies)
                rec.freshness = freshness

            if freshness != "current":
                reasons.append(f"Check {check_id!r} evidence is {freshness!r}, not 'current'")

            # Verdict evaluation
            if rec.verdict not in ("pass", "not-applicable"):
                reasons.append(f"Check {check_id!r} verdict is {rec.verdict!r} (reason: {rec.reason})")

    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 2.1 OperationOutcome Contract
# ---------------------------------------------------------------------------

OPERATION_MODULES = frozenset({"A1", "A2", "A3", "A4"})
OPERATION_OUTCOMES = frozenset({"ok", "failed", "not-run", "empty", "indeterminate"})


@dataclass
class OperationOutcome:
    """Structured operation outcome contract matching IDEF0 transition boundaries."""
    module: Literal["A1", "A2", "A3", "A4"]
    outcome: Literal["ok", "failed", "not-run", "empty", "indeterminate"]
    code: str | None = None
    subject_ref: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.module not in OPERATION_MODULES:
            raise ValueError(f"module must be in {sorted(OPERATION_MODULES)}, got {self.module!r}")
        if self.outcome not in OPERATION_OUTCOMES:
            raise ValueError(f"outcome must be in {sorted(OPERATION_OUTCOMES)}, got {self.outcome!r}")
        if self.outcome != "ok" and not self.code:
            raise ValueError(f"Non-ok outcome {self.outcome!r} requires a typed error/gap code")

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "outcome": self.outcome,
            "code": self.code,
            "subject_ref": self.subject_ref,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperationOutcome:
        return cls(
            module=data["module"],
            outcome=data["outcome"],
            code=data.get("code"),
            subject_ref=data.get("subject_ref"),
            details=dict(data.get("details", {})),
        )
