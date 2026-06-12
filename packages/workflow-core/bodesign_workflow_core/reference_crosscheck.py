"""Reference cross-check (G7) — the trust layer for a non-EE user.

The circuit design is a black box to a non-EE owner, so reliability must be
*demonstrated*, not asserted. The strongest available anchor is a known-good
dev-board product (a known-good reference board): treat it as a **control group** and
compare bodesign's generated artifacts against it.

This compares net sets (and carries the reference's provenance), reporting:
  - matched   — generated nets that exist in the reference (confidence)
  - missing   — reference nets the generated design did NOT wire (reliability gap)
  - extra     — generated nets absent from the reference (novel / to verify)
and a coverage % + plain-language verdict.

Honest scope: agreement proves *faithful reuse* of the proven design (high
confidence for an OpenMV-derived V1); it does NOT validate novel parts or
deviations — those still need the analysis skills (`kicad`/`emc`/`spice`) or EE
review. The reference itself must be a trustworthy shipped product.
"""

from dataclasses import dataclass, field
import re
from pathlib import Path

GLOBAL_LABEL_RE = re.compile(r'global_label "([^"]+)"')


@dataclass(slots=True)
class ReferenceCheck:
    label: str
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    coverage_pct: int = 0
    verdict: str = ""
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label, "coverage_pct": self.coverage_pct, "verdict": self.verdict,
            "matched": self.matched, "missing": self.missing, "extra": self.extra,
            "provenance": self.provenance,
        }


def crosscheck_nets(generated: set[str], reference: set[str], label: str, provenance: dict | None = None) -> ReferenceCheck:
    matched = sorted(generated & reference)
    missing = sorted(reference - generated)
    extra = sorted(generated - reference)
    coverage = round(100 * len(matched) / max(len(reference), 1))
    if not missing and not extra:
        verdict = f"matches the reference exactly ({len(matched)} nets)."
    elif not missing:
        verdict = f"covers all {len(reference)} reference nets; {len(extra)} extra net(s) not in the reference (verify)."
    else:
        verdict = (f"incomplete vs reference: {len(matched)}/{len(reference)} nets wired ({coverage}%); "
                   f"missing {len(missing)} — {', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}.")
    return ReferenceCheck(label=label, matched=matched, missing=missing, extra=extra,
                          coverage_pct=coverage, verdict=verdict, provenance=provenance or {})


# ── G3/DD-5: structured multi-dimension diff (generalization, not replacement) ──

DIFF_DIMENSIONS: tuple[str, ...] = ("net", "pad", "component", "pin", "component_value", "layout_rule")
_SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2, "info": 3}


class CrossCheckError(ValueError):
    """Raised for invalid crosscheck inputs (XCHK_* family)."""


@dataclass(slots=True)
class CrossCheckDiffItem:
    dimension: str
    key: str
    status: str  # "matched" | "missing" | "extra"
    severity: str  # "critical" | "major" | "minor" | "info"
    evidence_refs: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"dimension": self.dimension, "key": self.key, "status": self.status,
                "severity": self.severity, "evidence_refs": list(self.evidence_refs)}


@dataclass(slots=True)
class CrossCheckDiff:
    label: str
    items: list[CrossCheckDiffItem] = field(default_factory=list)
    first_divergence: int | None = None
    coverage_pct: int = 0
    verdict: str = ""
    provenance: dict = field(default_factory=dict)
    dimensions_available: list[str] = field(default_factory=list)
    dimensions_unavailable: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "items": [i.to_dict() for i in self.items],
            "first_divergence": self.first_divergence,
            "coverage_pct": self.coverage_pct,
            "verdict": self.verdict,
            "provenance": self.provenance,
            "dimensions_available": list(self.dimensions_available),
            "dimensions_unavailable": list(self.dimensions_unavailable),
        }


# Deterministic severity assignment per (dimension, status). Missing reference
# coverage is the reliability gap (major); extra generated content is novel
# material to verify (minor); matched is informational.
_DIFF_SEVERITY: dict[str, str] = {"missing": "major", "extra": "minor", "matched": "info"}


def crosscheck_diff(
    generated: dict[str, set[str]],
    reference: dict[str, set[str]],
    label: str,
    provenance: dict | None = None,
) -> CrossCheckDiff:
    """Compare generated vs reference evidence across dimensions (DD-5).

    `generated` / `reference` map dimension name -> key set. A dimension is
    compared only when BOTH sides provide evidence; otherwise it is reported in
    `dimensions_unavailable` with a reason — never silently treated as matched
    (XCHK_DIMENSION_UNAVAILABLE is a report, not an exception).

    Keeps `crosscheck_nets` semantics for the net dimension: coverage_pct and
    the prose verdict are computed exactly as before (dual track).
    """
    for side_name, side in (("generated", generated), ("reference", reference)):
        for dim in side:
            if dim not in DIFF_DIMENSIONS:
                raise CrossCheckError(
                    f"unknown diff dimension {dim!r} in {side_name} (allowed: {', '.join(DIFF_DIMENSIONS)})"
                )
    if "reference" and all(not v for v in reference.values()):
        raise CrossCheckError(
            "XCHK_EMPTY_REFERENCE: reference evidence is empty; crosscheck cannot produce a meaningful diff"
        )

    items: list[CrossCheckDiffItem] = []
    available: list[str] = []
    unavailable: list[dict] = []
    for dim in DIFF_DIMENSIONS:
        gen_has = dim in generated
        ref_has = dim in reference
        if not gen_has and not ref_has:
            continue  # dimension not requested by either side
        if not gen_has or not ref_has:
            missing_side = "generated" if not gen_has else "reference"
            unavailable.append({"dimension": dim, "reason": f"no {dim} evidence provided by {missing_side} side"})
            continue
        if not reference[dim]:
            unavailable.append({"dimension": dim, "reason": f"reference {dim} evidence is empty"})
            continue
        available.append(dim)
        gen, ref = generated[dim], reference[dim]
        for key in sorted(gen & ref):
            items.append(CrossCheckDiffItem(dim, key, "matched", _DIFF_SEVERITY["matched"]))
        for key in sorted(ref - gen):
            items.append(CrossCheckDiffItem(dim, key, "missing", _DIFF_SEVERITY["missing"]))
        for key in sorted(gen - ref):
            items.append(CrossCheckDiffItem(dim, key, "extra", _DIFF_SEVERITY["extra"]))

    if not available:
        raise CrossCheckError(
            "XCHK_EMPTY_REFERENCE: no dimension has evidence on both sides; nothing comparable"
        )

    # Deterministic ordering: severity rank, then dimension order, then key.
    items.sort(key=lambda i: (_SEVERITY_RANK[i.severity], DIFF_DIMENSIONS.index(i.dimension), i.key))
    first_divergence = next((idx for idx, i in enumerate(items) if i.status != "matched"), None)

    # Dual track: net-dimension coverage + prose verdict identical to crosscheck_nets.
    if "net" in available:
        net_check = crosscheck_nets(generated["net"], reference["net"], label, provenance)
        coverage, verdict = net_check.coverage_pct, net_check.verdict
    else:
        matched_n = sum(1 for i in items if i.status == "matched")
        ref_total = sum(len(reference[d]) for d in available)
        coverage = round(100 * matched_n / max(ref_total, 1))
        verdict = f"{matched_n}/{ref_total} reference keys matched across {', '.join(available)} ({coverage}%)."

    return CrossCheckDiff(
        label=label, items=items, first_divergence=first_divergence,
        coverage_pct=coverage, verdict=verdict, provenance=provenance or {},
        dimensions_available=available, dimensions_unavailable=unavailable,
    )


def extract_schematic_net_labels(sch_path: str | Path, pattern: str | None = None) -> set[str]:
    text = Path(sch_path).read_text(encoding="utf-8", errors="ignore")
    nets = set(GLOBAL_LABEL_RE.findall(text))
    if pattern:
        nets = {n for n in nets if pattern.lower() in n.lower()}
    return nets


def reference_nets_from_component_knowledge(knowledge: dict, pattern: str | None = None) -> tuple[set[str], dict]:
    nets = {row["schematic_net"] for row in knowledge.get("pinout", []) if row.get("schematic_net")}
    if pattern:
        nets = {n for n in nets if pattern.lower() in n.lower()}
    return nets, knowledge.get("openmv_schematic_evidence", {})


def render_crosscheck_markdown(checks: list[ReferenceCheck], control_group: str) -> str:
    lines = [f"# Reference cross-check vs {control_group} (control group)", "",
             "Reliability is shown by comparison to a known-good shipped product, not asserted.", ""]
    for c in checks:
        lines.append(f"## {c.label} — {c.coverage_pct}% coverage")
        lines.append(f"- **Verdict:** {c.verdict}")
        if c.provenance:
            prov = c.provenance
            lines.append(f"- Reference provenance: `{prov.get('file','?')}` p.{prov.get('schematic_page','?')} "
                         f"(sha {str(prov.get('sha256',''))[:12]}…, conf {prov.get('confidence','?')})")
        if c.missing:
            lines.append(f"- ⚠️ Missing vs reference ({len(c.missing)}): {', '.join(c.missing)}")
        if c.extra:
            lines.append(f"- Extra (not in reference): {', '.join(c.extra)}")
        lines.append("")
    lines.append("_Agreement = faithful reuse of the proven design (high confidence for an OpenMV-derived V1). "
                 "Novel parts/deviations still need the analysis skills or EE review._")
    return "\n".join(lines)
