"""Unified Collaborative Rebuild — Compatibility Adapters (P1/Tasks 2.1 & 2.2).

Wraps existing raw tool results, MCP response envelopes, and landing runner
outputs into typed VerificationRecord and OperationOutcome contracts without
mutating raw inputs.

Enforces:
- Raw result immutability (input dictionaries are never modified).
- Rejection of default PASS on unknown coverage, unknown version, or stale/unknown freshness.
- Baseline/proposal/approval mismatch checks before any mutation.
- Client source preservation on conflict.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Literal

from bodesign_design_ir.rebuild_contracts import (
    ArtifactManifest,
    ArtifactRef,
    DependencyRef,
)
from bodesign_workflow_core.rebuild_contracts import (
    ChangeProposal,
    OperationOutcome,
    ReleaseApproval,
    VerificationRecord,
    evaluate_change_proposal,
    evaluate_freshness,
    evaluate_release_eligibility,
)


REBUILD_COMPAT_VERSION = "1.0.0"


class CompatError(ValueError):
    """Raised for compatibility adapter violations."""


# ---------------------------------------------------------------------------
# Tool Finding Adapters (pure, non-mutating)
# ---------------------------------------------------------------------------

def _adapt_drc_gate_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if raw.get("copper", 0):
        findings.append({
            "id": "drc-copper",
            "severity": "major",
            "message": f"{raw['copper']} copper DRC violation(s)",
            "anchor": {"kind": "tool_output", "ref": "drc_gate.copper"},
        })
    if raw.get("unconnected", 0):
        findings.append({
            "id": "drc-unconnected",
            "severity": "major",
            "message": f"{raw['unconnected']} unconnected item(s)",
            "anchor": {"kind": "tool_output", "ref": "drc_gate.unconnected"},
        })
    if raw.get("silk", 0):
        findings.append({
            "id": "drc-silk",
            "severity": "minor",
            "message": f"{raw['silk']} silkscreen (cosmetic) violation(s)",
            "anchor": {"kind": "tool_output", "ref": "drc_gate.silk"},
        })
    return findings


def _adapt_si_check_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sev_map = {"fail": "major", "warn": "minor"}
    for row in raw.get("nets", []) or []:
        status = row.get("status")
        if status in sev_map:
            net_name = str(row.get("net", "unknown"))
            findings.append({
                "id": f"si-{net_name}",
                "severity": sev_map[status],
                "message": (
                    f"net {net_name}: overshoot {row.get('overshoot_pct')}% / "
                    f"undershoot {row.get('undershoot_pct')}% ({status})"
                ),
                "anchor": {"kind": "net", "ref": net_name},
            })
    return findings


def _adapt_readability_gate_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for i, u in enumerate(raw.get("unmet", []) or []):
        crit = str(u.get("criterion", f"criterion_{i}"))
        findings.append({
            "id": f"readability-{crit}",
            "severity": "major",
            "message": (
                f"Readability unmet criterion '{crit}': observed {u.get('observed')} "
                f"vs threshold {u.get('threshold')} (source: {u.get('source')})"
            ),
            "anchor": {"kind": "criterion", "ref": crit},
        })
    # Check for missing fields if not-run
    for field in raw.get("missing_fields", []) or []:
        findings.append({
            "id": f"readability-missing-{field}",
            "severity": "major",
            "message": f"Readability route_stats missing required task-6.0 field '{field}'",
            "anchor": {"kind": "field", "ref": field},
        })
    return findings


def _adapt_fidelity_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for i, item in enumerate(raw.get("fused", []) or []):
        findings.append({
            "id": f"fidelity-fused-{i}",
            "severity": "critical",
            "message": f"Nets fused into single net: {item}",
            "anchor": {"kind": "net_group", "ref": str(item)},
        })
    for i, item in enumerate(raw.get("split", []) or []):
        findings.append({
            "id": f"fidelity-split-{i}",
            "severity": "major",
            "message": f"Net split into disconnected components: {item}",
            "anchor": {"kind": "net_group", "ref": str(item)},
        })
    node_diff = raw.get("node_diff", {})
    if isinstance(node_diff, dict):
        for net, nodes in (node_diff.get("spec_only", []) or []):
            findings.append({
                "id": f"fidelity-spec-only-{net}",
                "severity": "major",
                "message": f"Nodes present in spec but missing in emitted net '{net}': {nodes}",
                "anchor": {"kind": "net", "ref": str(net)},
            })
        for net, nodes in (node_diff.get("emitted_only", []) or []):
            findings.append({
                "id": f"fidelity-emitted-only-{net}",
                "severity": "major",
                "message": f"Nodes present in emitted netlist but missing in spec '{net}': {nodes}",
                "anchor": {"kind": "net", "ref": str(net)},
            })
    for i, item in enumerate(raw.get("nc_wired", []) or []):
        findings.append({
            "id": f"fidelity-nc-wired-{i}",
            "severity": "major",
            "message": f"Spec-declared no-connect node wired to net: {item}",
            "anchor": {"kind": "node", "ref": str(item)},
        })
    for i, item in enumerate(raw.get("regrouped", []) or []):
        findings.append({
            "id": f"fidelity-regrouped-{i}",
            "severity": "critical",
            "message": f"Node regrouped across disjoint nets: {item}",
            "anchor": {"kind": "node", "ref": str(item)},
        })
    return findings


def _adapt_crosscheck_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for net in raw.get("missing", []) or []:
        findings.append({
            "id": f"xchk-missing-{net}",
            "severity": "major",
            "message": f"Reference net {net} missing in generated design",
            "anchor": {"kind": "net", "ref": str(net)},
        })
    for net in raw.get("extra", []) or []:
        findings.append({
            "id": f"xchk-extra-{net}",
            "severity": "minor",
            "message": f"Generated net {net} absent from reference (verify)",
            "anchor": {"kind": "net", "ref": str(net)},
        })
    return findings


def _adapt_spice_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sev_map = {"fail": "major", "warn": "minor"}
    for row in raw.get("results", []) or []:
        st = row.get("status")
        if st in sev_map:
            sub = str(row.get("type", "unknown"))
            src = row.get("model_source", "generic-default")
            findings.append({
                "id": f"spice-{sub}",
                "severity": sev_map[st],
                "message": f"Subcircuit {sub}: {st} (model_source={src})",
                "anchor": {"kind": "tool_output", "ref": sub},
            })
    if raw.get("smoke") == "fail":
        findings.append({
            "id": "spice-smoke",
            "severity": "major",
            "message": f"Model card smoke failed: {str(raw.get('stderr_excerpt', ''))[:120]}",
            "anchor": {"kind": "tool_output", "ref": "smoke"},
        })
    return findings


def _adapt_erc_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    buckets = (
        ("real_short", "critical"),
        ("unconnected", "major"),
        ("pad_net_bug", "minor"),
        ("other", "minor"),
    )
    for bucket, sev in buckets:
        cnt = int(raw.get(bucket, 0) or 0)
        for i in range(cnt):
            findings.append({
                "id": f"erc-{bucket}-{i}",
                "severity": sev,
                "message": f"{bucket.replace('_', ' ')} ERC violation",
                "anchor": {"kind": "tool_output", "ref": f"erc.{bucket}"},
            })
    return findings


def _adapt_constraint_solve_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for i, d in enumerate(raw.get("deficiencies", []) or []):
        kind = str(d.get("kind", "unknown"))
        findings.append({
            "id": f"cts-{kind}-{i}",
            "severity": "major",
            "message": f"{kind}: {str(d.get('detail', ''))[:160]}",
            "anchor": {"kind": "source", "ref": str(d.get("source_anchor", ""))} if d.get("source_anchor") else None,
        })
    if str(raw.get("solver_verdict", "")).lower() == "unsat" and not findings:
        findings.append({
            "id": "cts-unsat",
            "severity": "major",
            "message": "Constraint system unsatisfiable",
            "anchor": {"kind": "tool_output", "ref": "constraint_solve.solver_verdict"},
        })
    return findings


_FINDING_ADAPTERS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    "drc_gate": _adapt_drc_gate_findings,
    "si_check": _adapt_si_check_findings,
    "readability_gate": _adapt_readability_gate_findings,
    "verify_netlist_fidelity": _adapt_fidelity_findings,
    "crosscheck": _adapt_crosscheck_findings,
    "spice": _adapt_spice_findings,
    "erc": _adapt_erc_findings,
    "constraint_solve": _adapt_constraint_solve_findings,
}


# ---------------------------------------------------------------------------
# 2.1 Raw Verification Result Wrapping
# ---------------------------------------------------------------------------

def wrap_raw_verification_result(
    tool: str,
    raw_result: dict[str, Any],
    *,
    subject_manifest_sha256: str,
    axis: Literal["electrical", "form", "mechanical", "manufacturing"],
    tool_rule_dependencies: list[DependencyRef] | None = None,
    coverage: dict[str, Any] | None = None,
    raw_result_ref: ArtifactRef | None = None,
    freshness: Literal["current", "stale", "unknown"] = "unknown",
    reason: str | None = None,
    strict: bool = True,
) -> VerificationRecord:
    """Wraps an existing raw verification result into a typed VerificationRecord.

    Invariants (per DD-1..12, spec.md AC3/AC4/AC5, tasks.md 2.1 & 2.2):
    1. Raw results are preserved untouched (deep copy preserved, input never mutated).
    2. Unknown coverage, unknown version/dependencies, or stale/unknown freshness
       CANNOT default to 'pass'.
    3. In strict mode (default), attempting to construct a passing record with unknown
       coverage, missing tool version, or non-current freshness raises CompatError.
       In non-strict mode, verdict is downgraded to 'indeterminate' with an explicit reason.
    4. Succeeded execution + zero findings alone DOES NOT imply PASS without complete coverage.
    """
    if not isinstance(raw_result, dict) or not raw_result:
        raise CompatError(f"Cannot wrap empty raw_result for tool '{tool}'")

    # Raw results preserved untouched
    raw_snapshot = copy.deepcopy(raw_result)

    # 1. Adapt findings
    adapter = _FINDING_ADAPTERS.get(tool)
    if adapter:
        findings = adapter(raw_snapshot)
    else:
        # Fallback to existing findings if present in raw
        findings = [dict(f) for f in raw_snapshot.get("findings", []) if isinstance(f, dict)]

    # 2. Determine execution state
    status_str = str(raw_snapshot.get("status", "")).lower()
    if status_str == "not-run" or raw_snapshot.get("code") in ("READABILITY_STATS_ABSENT", "ENV_RAW_RESULT_MISSING"):
        execution: Literal["succeeded", "failed", "not-run"] = "not-run"
    elif raw_snapshot.get("ok") is False or status_str == "failed":
        execution = "failed"
    else:
        execution = "succeeded"

    # 3. Assess dependency version knowledge
    deps = list(tool_rule_dependencies or [])
    deps_known = len(deps) > 0 and all(
        (dep.version is not None or dep.digest is not None) for dep in deps
    )

    # 4. Assess coverage completeness
    coverage_known = False
    valid_coverage: dict[str, Any] = {"expected_ids": [], "examined_ids": [], "omitted": []}

    if coverage is not None:
        if all(k in coverage for k in ("expected_ids", "examined_ids", "omitted")):
            expected = list(coverage.get("expected_ids", []))
            examined = list(coverage.get("examined_ids", []))
            omitted = list(coverage.get("omitted", []))
            if expected and set(examined) == set(expected) and not omitted:
                coverage_known = True
                valid_coverage = {
                    "expected_ids": expected,
                    "examined_ids": examined,
                    "omitted": omitted,
                }
            else:
                valid_coverage = {
                    "expected_ids": expected,
                    "examined_ids": examined,
                    "omitted": omitted,
                }
    elif tool == "readability_gate" and raw_snapshot.get("N", 0) > 0:
        # Check if readability provided explicit N nets
        n_count = raw_snapshot.get("N", 0)
        net_ids = [f"net_{i}" for i in range(n_count)]
        valid_coverage = {
            "expected_ids": net_ids,
            "examined_ids": net_ids,
            "omitted": [],
        }
        coverage_known = True

    # 5. Determine tentative verdict
    critical_or_major_findings = [
        f for f in findings if f.get("severity") in ("critical", "major")
    ]

    has_failures = bool(critical_or_major_findings) or (status_str == "failed")
    is_empty_or_na = status_str == "empty"
    is_indeterminate = status_str == "indeterminate" or execution != "succeeded"

    tentative_verdict: Literal["pass", "fail", "indeterminate", "not-applicable"]
    tentative_reason: str | None = reason or raw_snapshot.get("reason")

    if has_failures:
        tentative_verdict = "fail"
        if not tentative_reason:
            tentative_reason = f"Verification failed with {len(critical_or_major_findings)} blocking finding(s)"
    elif is_empty_or_na:
        tentative_verdict = "not-applicable"
        if not tentative_reason:
            tentative_reason = "No items eligible for scoring (empty subject)"
    elif is_indeterminate:
        tentative_verdict = "indeterminate"
        if not tentative_reason:
            tentative_reason = f"Execution inconclusive ({status_str or 'incomplete'})"
    else:
        # Clean execution and zero blocking findings.
        # Check invariants: Unknown coverage/version/freshness MUST REJECT, NEVER default to PASS.
        rejection_reasons: list[str] = []
        if not coverage_known:
            rejection_reasons.append("unknown or incomplete coverage")
        if not deps_known:
            rejection_reasons.append("unknown tool/rule dependency versions")
        if freshness != "current":
            rejection_reasons.append(f"freshness is {freshness!r} (must be 'current')")

        if rejection_reasons:
            if strict:
                raise CompatError(
                    f"Default PASS rejected for tool '{tool}': {'; '.join(rejection_reasons)}"
                )
            tentative_verdict = "indeterminate"
            tentative_reason = f"PASS rejected due to: {'; '.join(rejection_reasons)}"
        else:
            tentative_verdict = "pass"

    # Build final VerificationRecord
    # Ensure reason is supplied when required by contract invariants
    if (execution in ("failed", "not-run") or tentative_verdict in ("indeterminate", "not-applicable")) and not tentative_reason:
        tentative_reason = f"Result status: {status_str or execution}"

    # If verdict is pass, examined_ids must be non-empty and equal to expected_ids
    if tentative_verdict == "pass" and not valid_coverage["examined_ids"]:
        if strict:
            raise CompatError("Verdict 'pass' requires non-empty examined_ids in coverage")
        tentative_verdict = "indeterminate"
        tentative_reason = "Verdict 'pass' rejected: examined_ids is empty"

    return VerificationRecord(
        subject_manifest_sha256=subject_manifest_sha256,
        execution=execution,
        verdict=tentative_verdict,
        coverage=valid_coverage,
        tool_rule_dependencies=deps,
        axis=axis,
        findings=findings,
        raw_result_ref=raw_result_ref,
        reason=tentative_reason,
        freshness=freshness,
    )


# ---------------------------------------------------------------------------
# 2.1 OperationOutcome Envelope Wrapping
# ---------------------------------------------------------------------------

def wrap_operation_outcome(
    raw_envelope: dict[str, Any],
    module: Literal["A1", "A2", "A3", "A4"],
    *,
    subject_ref: str | None = None,
) -> OperationOutcome:
    """Wraps an MCP tool envelope or landing runner output into an OperationOutcome.

    Preserves raw transport details untouched under `details`.
    Maps transport status codes to the closed outcome set:
    ('ok', 'failed', 'not-run', 'empty', 'indeterminate').
    """
    if not isinstance(raw_envelope, dict):
        raise CompatError(f"wrap_operation_outcome requires dict envelope, got {type(raw_envelope).__name__}")

    details = copy.deepcopy(raw_envelope)

    # 1. Domain status inspection (checks status, result_status, or inner result.status)
    status = str(raw_envelope.get("status", raw_envelope.get("result_status", ""))).lower()
    if not status and isinstance(raw_envelope.get("result"), dict):
        status = str(raw_envelope["result"].get("status", "")).lower()

    if status == "ok":
        return OperationOutcome(
            module=module,
            outcome="ok",
            code=None,
            subject_ref=subject_ref,
            details=details,
        )
    elif status == "empty":
        code = str(raw_envelope.get("code", "EMPTY_RESULT"))
        return OperationOutcome(
            module=module,
            outcome="empty",
            code=code,
            subject_ref=subject_ref,
            details=details,
        )
    elif status == "not-run":
        code = str(raw_envelope.get("code", "NOT_RUN"))
        return OperationOutcome(
            module=module,
            outcome="not-run",
            code=code,
            subject_ref=subject_ref,
            details=details,
        )
    elif status == "indeterminate":
        code = str(raw_envelope.get("code", "INDETERMINATE_RESULT"))
        return OperationOutcome(
            module=module,
            outcome="indeterminate",
            code=code,
            subject_ref=subject_ref,
            details=details,
        )
    elif status == "failed":
        code = str(raw_envelope.get("code", "VERIFICATION_FAILED"))
        return OperationOutcome(
            module=module,
            outcome="failed",
            code=code,
            subject_ref=subject_ref,
            details=details,
        )

    # 2. Refusal / error envelope
    if raw_envelope.get("ok") is False:
        err = raw_envelope.get("error", {})
        code = str(err.get("code") if isinstance(err, dict) else raw_envelope.get("code") or "OPERATION_FAILED")
        return OperationOutcome(
            module=module,
            outcome="failed",
            code=code,
            subject_ref=subject_ref,
            details=details,
        )

    # 3. Default fallback for generic ok envelope
    if raw_envelope.get("ok") is True:
        return OperationOutcome(
            module=module,
            outcome="ok",
            code=None,
            subject_ref=subject_ref,
            details=details,
        )

    return OperationOutcome(
        module=module,
        outcome="failed",
        code=f"UNKNOWN_STATUS_{status.upper() if status else 'UNSPECIFIED'}",
        subject_ref=subject_ref,
        details=details,
    )


# ---------------------------------------------------------------------------
# 2.2 Baseline & Release Precondition Guards
# ---------------------------------------------------------------------------

def check_baseline_preconditions(
    baseline_manifest: ArtifactManifest,
    proposed_baseline_sha256: str,
    proposal: ChangeProposal | None = None,
) -> dict[str, Any]:
    """Precondition check on baseline manifest before any mutation.

    Enforces that the baseline digest matches exactly and checks change proposal
    conflicts against locked/pinned objects.
    Preserves client source completely on conflict.
    """
    actual_sha = baseline_manifest.manifest_sha256
    if proposed_baseline_sha256.lower() != actual_sha.lower():
        return {
            "allowed": False,
            "conflict_code": "BASELINE_MISMATCH",
            "reason": (
                f"Proposed baseline {proposed_baseline_sha256[:12]}... does not match "
                f"current baseline manifest {actual_sha[:12]}... Source preserved unchanged."
            ),
            "client_source_preserved": True,
        }

    if proposal is not None:
        conflicts = evaluate_change_proposal(proposal, actual_sha)
        if conflicts:
            return {
                "allowed": False,
                "conflict_code": "PROPOSAL_CONFLICT",
                "conflicts": conflicts,
                "reason": f"Change proposal has {len(conflicts)} conflict(s) with baseline. Source preserved unchanged.",
                "client_source_preserved": True,
            }

    return {
        "allowed": True,
        "conflict_code": None,
        "reason": None,
        "client_source_preserved": True,
    }


def check_release_preconditions(
    target_manifest: ArtifactManifest,
    approvals: list[ReleaseApproval],
    verifications: list[VerificationRecord],
    current_dependencies: list[DependencyRef] | dict[str, str] | None = None,
) -> dict[str, Any]:
    """Precondition check on release readiness before emission.

    Enforces:
    1. Human release approval exists and matches target manifest sha256.
    2. All verification checks match target manifest sha256.
    3. Verification evidence is evaluated for freshness; stale/unknown evidence blocks release.
    4. All required check verdicts are 'pass' (or justified 'not-applicable').
    """
    if not approvals:
        return {
            "eligible": False,
            "reasons": ["No release approval provided"],
        }

    reasons: list[str] = []
    target_sha = target_manifest.manifest_sha256.lower()

    # Normalize current dependencies
    curr_deps_map: dict[str, str] | None = None
    if current_dependencies is not None:
        if isinstance(current_dependencies, dict):
            curr_deps_map = current_dependencies
        else:
            curr_deps_map = {
                dep.name: (dep.version or dep.digest or "")
                for dep in current_dependencies
            }

    # Check approvals
    for app in approvals:
        if app.decision != "approved":
            reasons.append(f"Release approval (actor={app.actor!r}) decision is {app.decision!r}, not 'approved'")
        if app.manifest_sha256.lower() != target_sha:
            reasons.append(
                f"Release approval target {app.manifest_sha256[:12]}... "
                f"!= target manifest {target_sha[:12]}..."
            )

    # Check verifications
    for v in verifications:
        # Subject manifest check
        if v.subject_manifest_sha256.lower() != target_sha:
            reasons.append(
                f"Verification evidence for axis {v.axis!r} subject {v.subject_manifest_sha256[:12]}... "
                f"!= target manifest {target_sha[:12]}..."
            )

        # Freshness evaluation
        freshness = v.freshness
        if curr_deps_map is not None:
            freshness = evaluate_freshness(curr_deps_map, v.tool_rule_dependencies)
            v.freshness = freshness

        if freshness != "current":
            reasons.append(f"Verification evidence for axis {v.axis!r} is {freshness!r} (must be 'current')")

        # Verdict check
        if v.verdict not in ("pass", "not-applicable"):
            reasons.append(f"Verification check on axis {v.axis!r} has non-passing verdict {v.verdict!r} ({v.reason})")

    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
    }
