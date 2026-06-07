"""C06 verification — test-plan / bring-up assembler over the verify verdicts.

The C03 verify tools (simulate / EMC / thermal / reference cross-check) already
produce verdicts; their output IS C06 content. The missing piece is assembling a
bring-up + test-plan document over those verdicts. This module does that and nothing
more: it records each check's status from its verdict, leaves checks that were never
run explicitly `not-run`, and never fabricates a pass or claims certification —
EVT/DVT and compliance certification remain external-lab gates.

Inputs (all optional): `verdicts` = {simulate, emc, thermal, crosscheck} verdict
dicts; `certification_targets` = PRD §3/§9/§10 certification/compliance goals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

C06_FOLDER = Path("C06-Verification")
C06_SUMMARY = C06_FOLDER / "Verification_Summary.json"
C06_TEST_PLAN = C06_FOLDER / "Test_Plan.md"
C06_BRINGUP = C06_FOLDER / "Bring_Up_Checklist.md"

_CHECKS = ["simulate", "emc", "thermal", "crosscheck"]
_CHECK_TITLES = {
    "simulate": "SPICE simulation (analog subcircuits)",
    "emc": "EMC / EMI pre-compliance",
    "thermal": "Thermal analysis",
    "crosscheck": "Reference cross-check (control group)",
}


def _check_status(name: str, verdict: dict[str, Any] | None) -> str:
    """Map a heterogeneous verify verdict to pass | warn | fail | reported | not-run."""
    if not verdict or not isinstance(verdict, dict):
        return "not-run"
    # Explicit failure/skip signals first.
    status = str(verdict.get("status", "")).lower()
    if status.startswith("skip"):
        return "not-run"
    if status in {"failed", "fail", "error"}:
        return "fail"
    # Count-based verdicts (simulate).
    failed = verdict.get("failed")
    warned = verdict.get("warned")
    if isinstance(failed, int) and failed > 0:
        return "fail"
    if isinstance(warned, int) and warned > 0:
        return "warn"
    # Coverage-based verdict (crosscheck).
    if name == "crosscheck" and "coverage_pct" in verdict:
        if verdict.get("missing"):
            return "warn"
        return "pass" if verdict.get("coverage_pct") == 100 else "warn"
    if status == "ok" or (isinstance(failed, int) and failed == 0 and status):
        return "pass"
    return "reported"


@dataclass(slots=True)
class C06Readiness:
    folder: str
    check_statuses: dict[str, str]
    run_count: int
    not_run: list[str]
    has_failures: bool
    status: str
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "check_statuses": dict(self.check_statuses),
            "run_count": self.run_count,
            "not_run": list(self.not_run),
            "has_failures": self.has_failures,
            "status": self.status,
            "next_step": self.next_step,
            "certified": False,
            "evt_dvt_passed": False,
        }


@dataclass(slots=True)
class C06Result:
    folder: str
    files: list[str]
    summary: dict[str, Any]
    readiness: C06Readiness

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "files": list(self.files),
            "summary": self.summary,
            "readiness": self.readiness.to_dict(),
            "certified": False,
        }


def _build_summary(verdicts: dict[str, Any] | None, certification_targets: list[Any] | None) -> dict[str, Any]:
    verdicts = verdicts or {}
    checks = []
    for name in _CHECKS:
        v = verdicts.get(name)
        checks.append({
            "check": name,
            "title": _CHECK_TITLES[name],
            "status": _check_status(name, v),
            "has_verdict": bool(v),
        })
    return {
        "schema": "bodesign.c06.verification_summary.v1",
        "state": "drafted",
        "checks": checks,
        "certification_targets": list(certification_targets or []),
        "note": "C06 records verify-tool verdicts. Pass/warn/fail reflect tool output only; "
                "EVT/DVT and compliance certification are external-lab gates, never claimed here.",
    }


def _render_test_plan(summary: dict[str, Any]) -> str:
    lines = [
        "# C06 — Verification & Test Plan (DRAFT)",
        "",
        "> Assembled from the C03 verify-tool verdicts. Checks with no verdict are `not-run`.",
        "> Certification (FCC/CE/EVT/DVT) is an external-lab gate and is never marked here.",
        "",
        "## Check status",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for check in summary["checks"]:
        lines.append(f"| {check['title']} | `{check['status']}` |")
    lines += ["", "## Per-check plan", ""]
    for check in summary["checks"]:
        lines.append(f"### {check['title']}")
        if check["status"] == "not-run":
            lines.append(f"- Run the corresponding verify tool (`{check['check']}`) and re-assemble.")
        elif check["status"] in {"warn", "fail"}:
            lines.append("- Investigate the reported issues before EVT.")
        else:
            lines.append("- Verdict recorded; retain as evidence for the design review.")
        lines.append("")
    if summary["certification_targets"]:
        lines += ["## Certification targets (external-lab owned)", ""]
        for target in summary["certification_targets"]:
            lines.append(f"- {target} — external lab; not certifiable by bodesign.")
    return "\n".join(lines) + "\n"


def _render_bringup(summary: dict[str, Any]) -> str:
    lines = [
        "# C06 — Bring-Up Checklist (DRAFT)",
        "",
        "> First-power-on / bring-up sequence. Tool verdicts inform, but hardware bring-up",
        "> is performed and signed off by the engineer.",
        "",
        "- [ ] Visual inspection + power rails (no shorts, correct voltages)",
        "- [ ] Programmer/debugger connects; MCU ID reads back",
        "- [ ] C03 pin map sanity (see C05 Pin_Map_Bridge.json)",
    ]
    for check in summary["checks"]:
        mark = "x" if check["status"] in {"pass", "reported"} else " "
        lines.append(f"- [{mark}] {check['title']} — `{check['status']}`")
    lines += [
        "- [ ] Functional smoke test against PRD §7 modes",
        "- [ ] Hand to EVT/DVT (external) for certification",
    ]
    return "\n".join(lines) + "\n"


def assemble_c06_test_plan(
    out_dir: str | Path,
    verdicts: dict[str, Any] | None = None,
    certification_targets: list[Any] | None = None,
) -> C06Result:
    """Assemble the C06 test-plan / bring-up package from verify verdicts."""
    root = Path(out_dir)
    summary = _build_summary(verdicts, certification_targets)
    files: list[str] = []
    for rel, content in (
        (C06_SUMMARY, json.dumps(summary, ensure_ascii=False, indent=2) + "\n"),
        (C06_TEST_PLAN, _render_test_plan(summary)),
        (C06_BRINGUP, _render_bringup(summary)),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        files.append(str(rel))
    return C06Result(str(root), files, summary, assess_c06_readiness(root))


def assess_c06_readiness(folder: str | Path) -> C06Readiness:
    root = Path(folder)
    summary_path = root / C06_SUMMARY
    if not summary_path.exists():
        return C06Readiness(str(root), {}, 0, list(_CHECKS), False,
                            "missing", "Run bodesign_c06_assemble_test_plan with the verify verdicts.")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        summary = {"checks": []}
    statuses = {c["check"]: c["status"] for c in summary.get("checks", [])}
    not_run = [name for name, st in statuses.items() if st == "not-run"]
    run_count = len(statuses) - len(not_run)
    has_failures = any(st == "fail" for st in statuses.values())

    if not statuses:
        status, next_step = "missing", "Assemble the C06 test plan from verify verdicts."
    elif run_count == 0:
        status, next_step = "blocked", "No verify tools have produced verdicts yet — run simulate/emc/thermal/crosscheck."
    elif has_failures:
        status, next_step = "has_failures", "Resolve failing checks before EVT; re-run the failing verify tools."
    else:
        status, next_step = "test_plan_drafted", "Use as the design-review/bring-up evidence; certification remains external."

    return C06Readiness(str(root), statuses, run_count, not_run, has_failures, status, next_step)
