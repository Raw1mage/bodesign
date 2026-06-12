"""G3 (workflow_verification-discipline) — standardized four-part root-cause report.

Schema (data-schema.json `RootCauseReport`): methodology / findings / evidence /
fix. Every evidence entry carries an anchor (file/net/component/coordinate/
tool_output/document) so the causal chain is traceable. Reports are persisted
into the client project folder and a `rootcause.reported` event is appended to
the orchestration spine log (observability.md).

Fail-fast: incomplete reports raise RootCauseError; nothing is persisted.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .orchestration import _append_log, _orch_root

ROOT_CAUSE_SCHEMA = "bodesign.root_cause_report.v1"
_REPORT_REL_DIR = Path("_root_cause")

_ANCHOR_KINDS: tuple[str, ...] = ("file", "net", "component", "coordinate", "tool_output", "document")


class RootCauseError(ValueError):
    """Raised for incomplete/invalid root-cause reports."""


def _validate_anchor(anchor: Any, where: str) -> dict[str, Any]:
    if not isinstance(anchor, dict):
        raise RootCauseError(f"{where} must be an object with `kind` and `ref`")
    kind, ref = anchor.get("kind"), anchor.get("ref")
    if kind not in _ANCHOR_KINDS:
        raise RootCauseError(f"{where}.kind {kind!r} invalid (allowed: {', '.join(_ANCHOR_KINDS)})")
    if not isinstance(ref, str) or not ref.strip():
        raise RootCauseError(f"{where}.ref requires a non-empty string")
    out: dict[str, Any] = {"kind": kind, "ref": ref.strip()}
    if anchor.get("detail"):
        out["detail"] = str(anchor["detail"])
    return out


@dataclass(slots=True)
class RootCauseReport:
    subject: str  # the divergence/failure being explained (e.g. "net INT_N missing")
    methodology: list[str]
    findings: list[str]
    evidence: list[dict[str, Any]]
    fix: str
    schema: str = ROOT_CAUSE_SCHEMA

    def __post_init__(self) -> None:
        problems: list[str] = []
        if not self.subject or not self.subject.strip():
            problems.append("subject")
        if not self.methodology or not all(isinstance(s, str) and s.strip() for s in self.methodology):
            problems.append("methodology (non-empty step list)")
        if not self.findings or not all(isinstance(s, str) and s.strip() for s in self.findings):
            problems.append("findings (non-empty list)")
        if not self.fix or not self.fix.strip():
            problems.append("fix")
        if problems:
            raise RootCauseError(
                f"root-cause report incomplete: {', '.join(problems)} — all four parts "
                "(methodology/findings/evidence/fix) are mandatory"
            )
        if not self.evidence:
            raise RootCauseError("root-cause report requires at least one anchored evidence entry")
        self.evidence = [_validate_anchor(a, f"evidence[{i}]") for i, a in enumerate(self.evidence)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "subject": self.subject,
            "methodology": list(self.methodology),
            "findings": list(self.findings),
            "evidence": list(self.evidence),
            "fix": self.fix,
        }


def record_root_cause(
    folder: str | Path,
    *,
    subject: str,
    methodology: list[str],
    findings: list[str],
    evidence: list[dict[str, Any]],
    fix: str,
) -> RootCauseReport:
    """Validate, persist (client project folder) and log a root-cause report.

    Persists to `_root_cause/<NNNN>.json` (count-based, deterministic) and
    appends a `rootcause.reported` event to the spine `log.jsonl`.
    """
    report = RootCauseReport(
        subject=subject, methodology=list(methodology), findings=list(findings),
        evidence=list(evidence), fix=fix,
    )
    root = _orch_root(folder)
    report_dir = root / _REPORT_REL_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    report_id = f"RC-{len(list(report_dir.glob('RC-*.json'))) + 1:04d}"
    (report_dir / f"{report_id}.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _append_log(root, {"event": "rootcause.reported", "report_id": report_id,
                       "subject": report.subject, "fix": report.fix})
    return report


def load_root_cause_reports(folder: str | Path) -> list[RootCauseReport]:
    root = _orch_root(folder)
    report_dir = root / _REPORT_REL_DIR
    if not report_dir.exists():
        return []
    reports: list[RootCauseReport] = []
    for path in sorted(report_dir.glob("RC-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != ROOT_CAUSE_SCHEMA:
            raise RootCauseError(f"unsupported root-cause schema {data.get('schema')!r} at {path}")
        reports.append(RootCauseReport(
            subject=data.get("subject", ""), methodology=data.get("methodology", []),
            findings=data.get("findings", []), evidence=data.get("evidence", []),
            fix=data.get("fix", ""),
        ))
    return reports
