"""Unified Collaborative Rebuild — Workflow, Evidence & Policy Contracts (P1/DD-1..12).

Implements VerificationRecord, InterferenceRecord, ChangeProposal, ReleaseApproval,
OperationOutcome, and freshness / baseline mismatch / release eligibility evaluation
per data-schema.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
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
    raw_snapshot: dict[str, Any] | None = None
    raw_evidence_absent_reason: str | None = None

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
            if not self.tool_rule_dependencies:
                raise ValueError("Verdict 'pass' requires non-empty tool_rule_dependencies (tool/rule identity)")
            has_raw = self.raw_result_ref is not None or bool(self.raw_snapshot)
            if not has_raw and not self.raw_evidence_absent_reason:
                raise ValueError(
                    "Verdict 'pass' requires raw evidence (raw_result_ref or raw_snapshot) "
                    "or an explicit raw_evidence_absent_reason"
                )

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
            "raw_snapshot": self.raw_snapshot,
            "raw_evidence_absent_reason": self.raw_evidence_absent_reason,
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
            raw_snapshot=dict(data["raw_snapshot"]) if isinstance(data.get("raw_snapshot"), dict) else None,
            raw_evidence_absent_reason=data.get("raw_evidence_absent_reason"),
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

    @staticmethod
    def _finite_nonneg(value: Any) -> bool:
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0)

    @property
    def certification_blockers(self) -> list[str]:
        """Why this record cannot certify exact clearance (empty list == certifiable)."""
        blockers: list[str] = []
        if self.method != "exact-solid":
            blockers.append(f"method {self.method!r} is broad-phase only; AABB overlap is not exact collision")
        if bool(self.coverage.get("missing_ids")):
            blockers.append(f"missing solids: {sorted(self.coverage['missing_ids'])}")
        if not self._finite_nonneg(self.policy.get("tolerance_mm")):
            blockers.append(f"policy.tolerance_mm is not a finite non-negative number: {self.policy.get('tolerance_mm')!r}")
        if not self._finite_nonneg(self.policy.get("required_clearance_mm")):
            blockers.append(f"policy.required_clearance_mm is not a finite non-negative number: {self.policy.get('required_clearance_mm')!r}")
        if not self.policy.get("backend") or not self.policy.get("backend_version"):
            blockers.append("policy.backend / backend_version must be declared")
        if not isinstance(self.policy.get("declared_contacts"), list):
            blockers.append("policy.declared_contacts must be a list")
        if not self.pairs:
            blockers.append("no executed pairs: pairs=[] is absence of evidence, not clearance")
            return blockers
        contacts = {tuple(sorted(c)) for c in self.policy.get("declared_contacts", []) if isinstance(c, (list, tuple)) and len(c) == 2}
        required = self.policy.get("required_clearance_mm")
        tol = self.policy.get("tolerance_mm")
        for i, pair in enumerate(self.pairs):
            if not isinstance(pair, dict) or "a" not in pair or "b" not in pair:
                blockers.append(f"pair[{i}] missing object ids a/b")
                continue
            key = tuple(sorted((str(pair["a"]), str(pair["b"]))))
            if not isinstance(pair.get("collides"), bool):
                blockers.append(f"pair[{i}] {key} has no executed collision result")
                continue
            clearance = pair.get("clearance_mm")
            if not isinstance(clearance, (int, float)) or isinstance(clearance, bool) or not math.isfinite(clearance):
                blockers.append(f"pair[{i}] {key} has no finite clearance result")
                continue
            if key in contacts:
                continue
            if pair["collides"]:
                blockers.append(f"pair[{i}] {key} collides")
            elif isinstance(required, (int, float)) and isinstance(tol, (int, float)) and clearance + tol < required:
                blockers.append(f"pair[{i}] {key} clearance {clearance} mm < required {required} mm")
        return blockers

    @property
    def is_exact_certified(self) -> bool:
        """Exact clearance is certified only by executed exact-solid pairs with
        collision + clearance results against a finite valid policy. AABB
        broad-phase and pairs=[] never certify."""
        return not self.certification_blockers

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


def _conflict_key(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def evaluate_change_proposal(
    proposal: ChangeProposal,
    current_native_manifest_sha256: str,
    adapter_capabilities: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate change proposal against current baseline and edit constraints.

    `supported_edit_classes` is the client's ALLOWLIST (what the proposal author
    permits), not proof the adapter can perform the edit. Capability is validated
    separately against `adapter_capabilities` when supplied; when it is None the
    capability axis is reported as UNVERIFIED via a conflict record, never assumed.

    Returns non-empty conflict list on any mismatch or unsupported operation;
    caller must stop before writing, leaving client source unchanged.
    Pre-existing `proposal.conflicts` are preserved and merged (deduplicated), never dropped.
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

        if adapter_capabilities is None:
            conflicts.append({
                "type": "CAPABILITY_UNVERIFIED",
                "edit_class": op_class,
                "target_id": op_id,
                "message": f"Adapter capability for edit class {op_class!r} was not verified (no adapter_capabilities supplied)",
            })
        elif op_class not in adapter_capabilities:
            conflicts.append({
                "type": "ADAPTER_CAPABILITY_MISSING",
                "edit_class": op_class,
                "target_id": op_id,
                "message": f"Adapter cannot perform edit class {op_class!r}; capabilities are {sorted(adapter_capabilities)}",
            })

    # Preserve pre-existing conflicts; append only new ones.
    merged = list(proposal.conflicts)
    seen = {_conflict_key(c) for c in merged}
    for c in conflicts:
        k = _conflict_key(c)
        if k not in seen:
            merged.append(c)
            seen.add(k)
    proposal.conflicts = merged
    return merged


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
    current_dependencies: dict[str, Any] | list[DependencyRef] | None,
    record_dependencies: list[DependencyRef],
) -> Literal["current", "stale", "unknown"]:
    """Derive verification record freshness from dependency identity (kind, name, version, digest).

    - `current_dependencies` as list[DependencyRef] binds the full identity: a recorded
      dep is matched on (kind, name); any recorded version or digest that differs from
      the current one is 'stale' (unchanged version + changed digest is STALE).
    - Legacy dict[str, str] (name -> version-or-digest) binds name only. If the record
      carries BOTH version and digest, a single string cannot bind both -> 'unknown'.
    - Absent current environment (None) -> 'unknown'; caller-set freshness is never trusted.
    """
    if not record_dependencies:
        return "unknown"
    if current_dependencies is None:
        return "unknown"

    by_identity: dict[tuple[str, str], DependencyRef] = {}
    by_name: dict[str, Any] = {}
    if isinstance(current_dependencies, dict):
        for k, v in current_dependencies.items():
            if isinstance(v, DependencyRef):
                by_identity[(v.kind, v.name)] = v
            else:
                by_name[str(k)] = v
    else:
        for cur in current_dependencies:
            if not isinstance(cur, DependencyRef):
                return "unknown"
            by_identity[(cur.kind, cur.name)] = cur

    verdict: Literal["current", "stale", "unknown"] = "current"
    for dep in record_dependencies:
        cur = by_identity.get((dep.kind, dep.name))
        if cur is not None:
            if dep.version is not None:
                if cur.version is None:
                    verdict = "unknown"
                    continue
                if cur.version != dep.version:
                    return "stale"
            if dep.digest is not None:
                if cur.digest is None:
                    verdict = "unknown"
                    continue
                if cur.digest != dep.digest:
                    return "stale"
            continue
        legacy = by_name.get(dep.name)
        if legacy is None:
            # Missing dependency in current environment (or kind mismatch)
            verdict = "unknown"
            continue
        if dep.version is not None and dep.digest is not None:
            # A bare string cannot bind both version and digest.
            verdict = "unknown"
            continue
        recorded = dep.version if dep.version is not None else dep.digest
        if recorded != str(legacy):
            return "stale"
    return verdict


@dataclass(frozen=True)
class ReleasePolicy:
    """Explicit versioned release policy: the authoritative source of required checks."""
    policy_id: str
    version: str
    required_checks: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("ReleasePolicy policy_id is required")
        if not self.version:
            raise ValueError("ReleasePolicy version is required")
        checks = tuple(self.required_checks)
        if not checks or any(not isinstance(c, str) or not c for c in checks):
            raise ValueError("ReleasePolicy required_checks must be a non-empty list of check ids (empty policy rejected)")
        if len(set(checks)) != len(checks):
            raise ValueError("ReleasePolicy required_checks must not contain duplicates")
        object.__setattr__(self, "required_checks", checks)

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "version": self.version, "required_checks": list(self.required_checks)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleasePolicy:
        return cls(
            policy_id=str(data["policy_id"]),
            version=str(data["version"]),
            required_checks=tuple(data.get("required_checks", [])),
        )


def resolve_required_checks(policy: ReleasePolicy | None, approval: ReleaseApproval) -> tuple[list[str], list[str]]:
    """Required checks come from the policy. Returns (required, reasons).

    An approval may ADD checks but can never remove a policy check; a missing
    policy is itself a blocking reason (no implicit required set)."""
    reasons: list[str] = []
    if policy is None:
        return [], ["No explicit versioned release policy supplied; required checks cannot be derived from approval alone"]
    missing = [c for c in policy.required_checks if c not in approval.required_checks]
    if missing:
        reasons.append(
            f"Approval required_checks omit policy {policy.policy_id}@{policy.version} checks {missing}; approval cannot reduce policy"
        )
    required = list(policy.required_checks)
    for c in approval.required_checks:
        if c not in required:
            required.append(c)
    return required, reasons


def evaluate_release_eligibility(
    approval: ReleaseApproval | None,
    target_manifest_sha256: str,
    verification_records: list[VerificationRecord],
    current_dependencies: dict[str, Any] | list[DependencyRef] | None = None,
    policy: ReleasePolicy | None = None,
) -> dict[str, Any]:
    """Verify that all policy-required release checks are satisfied with current, non-stale evidence.

    Required checks come from the explicit versioned `policy` (approval may add, never
    reduce). Each required check must be covered by a verification record whose
    tool/rule dependency names include the check id (axis names are NOT check ids).
    Freshness is always recomputed from `current_dependencies`; a caller-set
    `freshness='current'` with absent current deps evaluates to 'unknown'.
    """
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

    required_checks, policy_reasons = resolve_required_checks(policy, approval)
    reasons.extend(policy_reasons)

    # Index records by tool/rule dependency name (the check identity)
    records_by_key: dict[str, list[VerificationRecord]] = {}
    for r in verification_records:
        for dep in r.tool_rule_dependencies:
            records_by_key.setdefault(dep.name, []).append(r)

    # 2. Required Checks Coverage & Verdict
    for check_id in required_checks:
        matching = records_by_key.get(check_id, [])
        if not matching:
            reasons.append(f"Required check {check_id!r} has no verification record")
            continue

        # Evaluate every matching record
        for rec in matching:
            # Subject manifest must match release target
            if rec.subject_manifest_sha256.lower() != target_manifest_sha256.lower():
                reasons.append(f"Check {check_id!r} subject {rec.subject_manifest_sha256} != release target {target_manifest_sha256}")

            # Freshness is derived, never trusted from the record
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
