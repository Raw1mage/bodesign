"""Reference cross-check (G7) — the trust layer for a non-EE user.

The circuit design is a black box to a non-EE owner, so reliability must be
*demonstrated*, not asserted. The strongest available anchor is a known-good
dev-board product (OpenMV / Rockbox): treat it as a **control group** and
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
