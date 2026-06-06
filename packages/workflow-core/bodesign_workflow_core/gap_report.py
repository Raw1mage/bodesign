"""Consolidate evidence-package gaps into a reviewable report + dashboard data.

This is the deterministic builder behind OpenMV task O8 / roadmap R1: it ingests
the evidence artifacts a forward-design source package produced (component
knowledge, pin tables, subsystem constraints, source manifest, validation
records) and rolls their recorded gaps/blockers/validation facts up into:

  - a markdown gap report (human review), and
  - a structured dashboard-data dict (the web evidence dashboard, R4).

It never invents gaps: every item is sourced from a field in an input artifact.
It does perform one *cross-artifact reconciliation* — a blocker recorded by an
early seed artifact is downgraded to "resolved (superseded)" when a later
artifact carries an explicit resolution signal (e.g. a validated pin table or
`o4_unblocked`), so a stale seed does not misreport a closed gap as blocking.
"""

from dataclasses import dataclass, field
from pathlib import Path
import json

# Keyword -> area classification (first match wins, deterministic order).
_AREA_RULES = [
    ("layout", ("layout", "pcb", "placement", "impedance", "stackup")),
    ("footprint", ("footprint", "pad geometry", "bga pad", "land")),
    ("symbol/pin", ("pin table", "pin name", "ball coordinate", "symbol generation", "pinout", "ordering suffix", "package variant")),
    ("datasheet-normalization", ("datasheet normalization", "deeper datasheet", "page span", "reference manual", "materializ")),
    ("redistribution", ("redistribut", "raw pdf", "copyright", "vendor terms")),
    ("source-integrity", ("sha", "hash", "duplicate sha")),
    ("schematic-completeness", ("schematic", "electrical correctness", "finished design", "nc/dnu", "human review")),
]


@dataclass(slots=True)
class GapItem:
    area: str
    severity: str  # "blocking" | "open" | "resolved-superseded"
    text: str
    source_artifact: str
    note: str = ""


@dataclass(slots=True)
class ResolvedFact:
    text: str
    source_artifact: str


@dataclass(slots=True)
class EvidenceArtifactSummary:
    name: str
    role: str
    confidence: float | None
    open_gaps: int
    blockers: int


@dataclass(slots=True)
class SourceGapReport:
    package_id: str
    title: str
    artifacts: list[EvidenceArtifactSummary] = field(default_factory=list)
    resolved_facts: list[ResolvedFact] = field(default_factory=list)
    gap_items: list[GapItem] = field(default_factory=list)
    readiness_state: str = "unknown"
    readiness_summary: str = ""
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def dashboard_data(self) -> dict[str, object]:
        return {
            "package_id": self.package_id,
            "title": self.title,
            "readiness": {"state": self.readiness_state, "summary": self.readiness_summary},
            "counts": self.counts,
            "artifacts": [
                {
                    "name": artifact.name,
                    "role": artifact.role,
                    "confidence": artifact.confidence,
                    "open_gaps": artifact.open_gaps,
                    "blockers": artifact.blockers,
                }
                for artifact in self.artifacts
            ],
            "resolved_facts": [
                {"text": fact.text, "source_artifact": fact.source_artifact} for fact in self.resolved_facts
            ],
            "gaps": [
                {
                    "area": gap.area,
                    "severity": gap.severity,
                    "text": gap.text,
                    "source_artifact": gap.source_artifact,
                    "note": gap.note,
                }
                for gap in self.gap_items
            ],
        }


def _classify_area(text: str) -> str:
    lowered = text.lower()
    for area, keywords in _AREA_RULES:
        if any(keyword in lowered for keyword in keywords):
            return area
    return "other"


def _role_of(data: dict, filename: str) -> str:
    for key in ("artifact_id", "component_id", "manifest_id"):
        if isinstance(data.get(key), str):
            return data[key]
    return filename


def _confidence_of(data: dict) -> float | None:
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        return round(float(confidence), 3)
    if isinstance(confidence, dict):
        values = [float(v) for v in confidence.values() if isinstance(v, (int, float))]
        if values:
            return round(sum(values) / len(values), 3)
    return None


def _resolution_signals(artifacts: list[tuple[str, dict]]) -> set[str]:
    signals: set[str] = set()
    for _name, data in artifacts:
        review = data.get("validation_summary")
        if isinstance(review, dict) and review.get("o4_unblocked") is True:
            signals.add("symbol-generation-unblocked")
        if data.get("status") == "validated" and data.get("missing_required_pins") == [] and data.get("missing_balls") == []:
            signals.add("symbol-generation-unblocked")
    return signals


def collect_source_gap_report(package_id: str, title: str, artifact_paths: list[str]) -> SourceGapReport:
    loaded: list[tuple[str, dict]] = []
    for path in artifact_paths:
        file = Path(path)
        if not file.exists():
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            loaded.append((file.name, data))

    signals = _resolution_signals(loaded)
    report = SourceGapReport(package_id=package_id, title=title)

    for name, data in loaded:
        role = _role_of(data, name)
        open_gaps = 0
        blockers = 0

        for gap_text in [*_as_list(data.get("gaps")), *_as_list(data.get("global_gaps"))]:
            report.gap_items.append(GapItem(_classify_area(gap_text), "open", gap_text, name))
            open_gaps += 1

        for blocker_text in _as_list(data.get("blockers")):
            report.gap_items.append(GapItem(_classify_area(blocker_text), "blocking", blocker_text, name))
            blockers += 1

        pin_status = data.get("pin_table_status")
        if isinstance(pin_status, dict) and pin_status.get("blocked_symbol_generation") is True:
            reason = str(pin_status.get("reason") or "symbol generation blocked pending pin-table materialization")
            if "symbol-generation-unblocked" in signals:
                report.resolved_facts.append(
                    ResolvedFact(f"Superseded: {reason} — resolved by validated VFBGA223 pin table (O3a/O3b/O4).", name)
                )
                report.gap_items.append(
                    GapItem("symbol/pin", "resolved-superseded", reason, name, note="superseded by validated pin table")
                )
            else:
                report.gap_items.append(GapItem("symbol/pin", "blocking", reason, name))
                blockers += 1

        _append_resolved_facts(report, name, data)

        report.artifacts.append(
            EvidenceArtifactSummary(name=name, role=role, confidence=_confidence_of(data), open_gaps=open_gaps, blockers=blockers)
        )

    blocking = sum(1 for gap in report.gap_items if gap.severity == "blocking")
    open_count = sum(1 for gap in report.gap_items if gap.severity == "open")
    superseded = sum(1 for gap in report.gap_items if gap.severity == "resolved-superseded")
    report.counts = {
        "artifacts": len(report.artifacts),
        "blocking": blocking,
        "open": open_count,
        "resolved_superseded": superseded,
        "resolved_facts": len(report.resolved_facts),
    }

    if blocking:
        report.readiness_state = "blocked"
        report.readiness_summary = f"{blocking} blocking gap(s) must be resolved before the package is reusable."
    elif open_count:
        report.readiness_state = "reusable-as-source-evidence-with-gaps"
        report.readiness_summary = (
            f"No blocking gaps. {open_count} open gap(s) remain (footprint/layout/normalization); "
            "the package is reusable as schematic-level source evidence, not a finished or send-to-fab design."
        )
    else:
        report.readiness_state = "reusable"
        report.readiness_summary = "No recorded gaps remain."
    return report


def _append_resolved_facts(report: SourceGapReport, name: str, data: dict) -> None:
    if data.get("status") == "validated" and data.get("missing_balls") == []:
        count = data.get("unique_ball_count") or data.get("actual_count")
        report.resolved_facts.append(ResolvedFact(f"Pin table validated ({count} balls, no missing/duplicate).", name))
    review = data.get("validation_summary")
    if isinstance(review, dict):
        if review.get("o4_unblocked") is True:
            report.resolved_facts.append(ResolvedFact("AI pin-table review passed; KiCad symbol generation unblocked.", name))
        if review.get("all_required_present") is True:
            required = review.get("required_subsystem_ids")
            n = len(required) if isinstance(required, list) else "all"
            report.resolved_facts.append(ResolvedFact(f"All {n} required subsystems present in constraints.", name))


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def render_gap_report_markdown(report: SourceGapReport) -> str:
    lines: list[str] = []
    lines.append(f"# Gap & Evidence Report: {report.title}")
    lines.append("")
    lines.append(f"- Package: `{report.package_id}`")
    lines.append(f"- Readiness: **{report.readiness_state}**")
    lines.append(f"- {report.readiness_summary}")
    counts = report.counts
    lines.append(
        f"- Counts: {counts.get('artifacts', 0)} artifacts · {counts.get('blocking', 0)} blocking · "
        f"{counts.get('open', 0)} open · {counts.get('resolved_superseded', 0)} superseded · "
        f"{counts.get('resolved_facts', 0)} resolved facts"
    )
    lines.append("")
    lines.append("> Generated deterministically from package evidence artifacts. No gap is invented; "
                 "each item is sourced from a recorded field. Not a send-to-fab design.")
    lines.append("")

    lines.append("## Resolved / validated")
    if report.resolved_facts:
        for fact in report.resolved_facts:
            lines.append(f"- {fact.text}  _(source: `{fact.source_artifact}`)_")
    else:
        lines.append("- _none recorded_")
    lines.append("")

    by_area: dict[str, list[GapItem]] = {}
    for gap in report.gap_items:
        if gap.severity == "resolved-superseded":
            continue
        by_area.setdefault(gap.area, []).append(gap)
    lines.append("## Open gaps by area")
    if by_area:
        for area in sorted(by_area):
            lines.append(f"### {area}")
            for gap in by_area[area]:
                tag = "🔴 blocking" if gap.severity == "blocking" else "🟡 open"
                lines.append(f"- {tag}: {gap.text}  _(source: `{gap.source_artifact}`)_")
            lines.append("")
    else:
        lines.append("- _none_")
        lines.append("")

    superseded = [gap for gap in report.gap_items if gap.severity == "resolved-superseded"]
    if superseded:
        lines.append("## Superseded (stale-seed blockers resolved later)")
        for gap in superseded:
            lines.append(f"- ~~{gap.text}~~ — {gap.note}  _(source: `{gap.source_artifact}`)_")
        lines.append("")

    lines.append("## Per-artifact summary")
    lines.append("| Artifact | Role | Confidence | Open | Blocking |")
    lines.append("|---|---|---|---|---|")
    for artifact in report.artifacts:
        confidence = "" if artifact.confidence is None else f"{artifact.confidence:.2f}"
        lines.append(f"| `{artifact.name}` | {artifact.role} | {confidence} | {artifact.open_gaps} | {artifact.blockers} |")
    lines.append("")
    return "\n".join(lines)
