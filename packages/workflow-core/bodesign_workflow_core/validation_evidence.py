"""A5 (workflow_verification-discipline) — unified ValidationEvidence envelope.

DD-6: the envelope is a WRAPPER layer, not a replacement. Native tool returns
are preserved untouched under `raw_result`; adapters map native fields onto the
shared shape `{tool, inputs, findings[], severity, anchors[], requirement_refs[]}`
without reinterpreting values. New tools must emit the envelope natively;
existing tools (si_check / drc_gate / crosscheck) are wrapped at the MCP tool
layer via `wrap_validation_evidence`.

Fail-fast (errors.md): ENV_TOOL_UNKNOWN, ENV_RAW_RESULT_MISSING.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from .requirement_planning import ORACLE_TOOLS

VALIDATION_EVIDENCE_SCHEMA = "bodesign.validation_evidence.v1"

_SEVERITIES: tuple[str, ...] = ("critical", "major", "minor", "info")
_SEVERITY_RANK = {s: i for i, s in enumerate(_SEVERITIES)}


class ValidationEvidenceError(ValueError):
    """Raised for envelope wrapping failures (ENV_* family)."""


@dataclass(slots=True)
class ValidationFinding:
    id: str
    severity: str
    message: str
    anchor: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "severity": self.severity, "message": self.message}
        if self.anchor is not None:
            out["anchor"] = self.anchor
        return out


@dataclass(slots=True)
class ValidationEvidence:
    tool: str
    inputs: dict[str, Any]
    findings: list[ValidationFinding] = field(default_factory=list)
    severity: str = "info"
    anchors: list[dict[str, Any]] = field(default_factory=list)
    requirement_refs: list[str] = field(default_factory=list)
    raw_result: dict[str, Any] = field(default_factory=dict)
    schema: str = VALIDATION_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.tool not in ORACLE_TOOLS:
            raise ValidationEvidenceError(
                f"ENV_TOOL_UNKNOWN: no envelope adapter registered for tool '{self.tool}' "
                f"(allowed: {', '.join(ORACLE_TOOLS)})"
            )
        if self.severity not in _SEVERITIES:
            raise ValidationEvidenceError(
                f"envelope severity {self.severity!r} invalid (allowed: {', '.join(_SEVERITIES)})"
            )
        for i, f in enumerate(self.findings):
            if f.severity not in _SEVERITIES:
                raise ValidationEvidenceError(
                    f"findings[{i}].severity {f.severity!r} invalid (allowed: {', '.join(_SEVERITIES)})"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "tool": self.tool,
            "inputs": dict(self.inputs),
            "findings": [f.to_dict() for f in self.findings],
            "severity": self.severity,
            "anchors": list(self.anchors),
            "requirement_refs": list(self.requirement_refs),
            "raw_result": dict(self.raw_result),
        }


def _max_severity(findings: list[ValidationFinding]) -> str:
    """Envelope severity = max severity across findings; 'info' when empty."""
    if not findings:
        return "info"
    return min((f.severity for f in findings), key=lambda s: _SEVERITY_RANK[s])


def _adapt_drc_gate(raw: dict[str, Any]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if raw.get("copper", 0):
        findings.append(ValidationFinding(
            "drc-copper", "major", f"{raw['copper']} copper DRC violation(s)",
            {"kind": "tool_output", "ref": "drc_gate.copper"}))
    if raw.get("unconnected", 0):
        findings.append(ValidationFinding(
            "drc-unconnected", "major", f"{raw['unconnected']} unconnected item(s)",
            {"kind": "tool_output", "ref": "drc_gate.unconnected"}))
    if raw.get("silk", 0):
        findings.append(ValidationFinding(
            "drc-silk", "minor", f"{raw['silk']} silkscreen (cosmetic) violation(s)",
            {"kind": "tool_output", "ref": "drc_gate.silk"}))
    return findings


def _adapt_si_check(raw: dict[str, Any]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    sev = {"fail": "major", "warn": "minor"}
    for row in raw.get("nets", []):
        status = row.get("status")
        if status in sev:
            findings.append(ValidationFinding(
                f"si-{row.get('net')}", sev[status],
                f"net {row.get('net')}: overshoot {row.get('overshoot_pct')}% / "
                f"undershoot {row.get('undershoot_pct')}% ({status})",
                {"kind": "net", "ref": str(row.get("net"))}))
    return findings


def _adapt_crosscheck(raw: dict[str, Any]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for net in raw.get("missing", []):
        findings.append(ValidationFinding(
            f"xchk-missing-{net}", "major", f"reference net {net} missing in generated design",
            {"kind": "net", "ref": str(net)}))
    for net in raw.get("extra", []):
        findings.append(ValidationFinding(
            f"xchk-extra-{net}", "minor", f"generated net {net} absent from reference (verify)",
            {"kind": "net", "ref": str(net)}))
    return findings


def _adapt_spice(raw: dict[str, Any]) -> list[ValidationFinding]:
    """Adapt a SPICE result (simulate SimResult or smoke) into findings.

    Accepts two raw shapes (both deterministic, no reinterpretation):
    - simulate: {results: [{type, status, model_source}, ...]} — each
      warn/fail subcircuit becomes a finding; model_source is surfaced so a
      generic-default model behind a finding is visible (honesty over silence).
    - smoke: {smoke: "pass|fail|skipped-no-simulator", stderr_excerpt} — a
      failed smoke becomes a finding.
    """
    findings: list[ValidationFinding] = []
    sev = {"fail": "major", "warn": "minor"}
    for row in raw.get("results", []):
        status = row.get("status")
        if status in sev:
            source = row.get("model_source", "generic-default")
            findings.append(ValidationFinding(
                f"spice-{row.get('type')}", sev[status],
                f"subcircuit {row.get('type')}: {status} (model_source={source})",
                {"kind": "tool_output", "ref": str(row.get("type"))}))
    smoke = raw.get("smoke")
    if smoke == "fail":
        findings.append(ValidationFinding(
            "spice-smoke", "major",
            f"model card smoke failed: {str(raw.get('stderr_excerpt', ''))[:120]}",
            {"kind": "tool_output", "ref": "smoke"}))
    return findings


_ADAPTERS: dict[str, Callable[[dict[str, Any]], list[ValidationFinding]]] = {
    "drc_gate": _adapt_drc_gate,
    "si_check": _adapt_si_check,
    "crosscheck": _adapt_crosscheck,
    "spice": _adapt_spice,
}


def wrap_validation_evidence(
    tool: str,
    raw_result: dict[str, Any],
    *,
    inputs: dict[str, Any] | None = None,
    requirement_refs: list[str] | None = None,
) -> ValidationEvidence:
    """Wrap a native tool result into the unified envelope (DD-6).

    The native result is preserved untouched under `raw_result`; the adapter
    performs a one-way mapping into findings and never reinterprets values.
    """
    if tool not in _ADAPTERS:
        raise ValidationEvidenceError(
            f"ENV_TOOL_UNKNOWN: no envelope adapter registered for tool '{tool}' "
            f"(adapters: {', '.join(sorted(_ADAPTERS))})"
        )
    if not isinstance(raw_result, dict) or not raw_result:
        raise ValidationEvidenceError(
            f"ENV_RAW_RESULT_MISSING: cannot wrap empty tool result for '{tool}'"
        )
    findings = _ADAPTERS[tool](raw_result)
    anchors = [f.anchor for f in findings if f.anchor is not None]
    return ValidationEvidence(
        tool=tool,
        inputs=dict(inputs or {}),
        findings=findings,
        severity=_max_severity(findings),
        anchors=anchors,
        requirement_refs=list(requirement_refs or []),
        raw_result=dict(raw_result),
    )
