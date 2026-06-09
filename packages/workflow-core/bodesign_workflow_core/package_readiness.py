"""Package readiness index (G2 / N28-N29) — the state/compass of the document system.

Scans a product document folder and scores it against a milestone deliverable
checklist, producing a per-section status (present / partial / missing /
external) with the single next step. This is the file-based "state" that the
prompt-driven loop (agent-as-wizard) reads each turn to decide what to do next
and what input to ask the user for — plan-builder-shaped, but for the product
document package rather than the dev spec.

Deterministic and read-only: it never mutates the folder. bodesign-owned
deliverables get an actionable next step; external (ID/ME/FW) deliverables are
marked so they are not counted as bodesign gaps.
"""

from dataclasses import dataclass, field
from pathlib import Path

from bodesign_reverse_core import ingest_project_folder

# POC deliverable checklist (electronics-core scope). Each entry:
#   key, name, section_keywords (match a C0* folder), match_roles / match_name (match files),
#   producer, required (counts toward readiness%), next_action (when not present).
POC_CHECKLIST = [
    {"key": "prd", "name": "Product requirements (PRD)", "sections": ["prd", "c00", "c07"],
     "roles": ["document", "table"], "names": ["requirement", "prd", "proposal"],
     "producer": "bodesign+you", "required": True,
     "next": "Fill the PRD open questions (memory/camera/mic/battery/USB), then bodesign finalizes it."},
    {"key": "schematic", "name": "Schematic (C03)", "sections": ["電路", "電路設計", "c03", "schematic"],
     "roles": ["schematic", "orcad-schematic"], "names": ["schematic", ".kicad_sch", ".dsn"],
     "producer": "bodesign", "required": True,
     "next": "bodesign: run the C03 circuit-design lifecycle (compose subsystems → emit schematic, kicad-cli-validated)."},
    {"key": "bom", "name": "Key-part BOM (C03)", "sections": ["電路", "c03"],
     "roles": ["bom", "table", "spreadsheet"], "names": ["bom", "key_part", "key-part"],
     "producer": "bodesign", "required": True,
     "next": "bodesign: generate the key-part BOM from the schematic/netlist."},
    {"key": "pinmap", "name": "Pin/GPIO allocation (C03↔FW)", "sections": ["電路", "c03"],
     "roles": ["table", "spreadsheet"], "names": ["gpio", "pin", "allocation"],
     "producer": "bodesign", "required": False,
     "next": "bodesign: emit the pin/GPIO allocation table (interface doc to FW)."},
    {"key": "layout", "name": "Layout constraints / stackup (C04)", "sections": ["layout", "c04"],
     "roles": ["pcb-layout", "spreadsheet", "document"], "names": ["stackup", "layout", "gerber", ".kicad_pcb"],
     "producer": "bodesign+engineer", "required": False,
     "next": "bodesign: emit stackup + layout/routing constraints; layout engineer produces the board + Gerber."},
    {"key": "verification", "name": "Verification / bring-up plan (C06)", "sections": ["驗證", "c06", "verification"],
     "roles": ["document"], "names": ["verification", "bring", "test", "驗證"],
     "producer": "bodesign+labs", "required": False,
     "next": "bodesign: draft the verification/bring-up plan; outsourced labs run EVT/DVT."},
    {"key": "readiness", "name": "Gap / readiness report", "sections": [],
     "roles": ["document"], "names": ["gap", "readiness", "evidence"],
     "producer": "bodesign", "required": False,
     "next": "bodesign: generate the gap/evidence + readiness report."},
]
# External-owned sections (not bodesign deliverables; not counted as gaps).
EXTERNAL_SECTIONS = {"c01": "ID", "id": "ID", "c02": "ME", "me": "ME", "c05": "FW", "fw": "FW"}


@dataclass(slots=True)
class DeliverableStatus:
    key: str
    name: str
    producer: str
    required: bool
    status: str  # present | partial | missing | external
    files: list[str] = field(default_factory=list)
    next_action: str = ""


@dataclass(slots=True)
class PackageReadiness:
    folder: str
    milestone: str
    deliverables: list[DeliverableStatus] = field(default_factory=list)
    external_sections: list[str] = field(default_factory=list)
    readiness_pct: int = 0
    next_step: str = ""
    summary: str = ""
    # Unresolved cross-stage reconciliation records (BlockerReturn) that name a stage as
    # recommended_owner. An open blocker blocks the milestone's all-clear even when every
    # deliverable is present — see references/cross-stage-reconciliation.md.
    open_blockers: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder, "milestone": self.milestone,
            "readiness_pct": self.readiness_pct, "next_step": self.next_step, "summary": self.summary,
            "external_sections": self.external_sections,
            "open_blockers": self.open_blockers,
            "deliverables": [
                {"key": d.key, "name": d.name, "producer": d.producer, "required": d.required,
                 "status": d.status, "files": d.files, "next_action": d.next_action}
                for d in self.deliverables
            ],
        }


def _matches(rel_path: str, item: dict) -> bool:
    # Name-based within an optional section scope. Role alone is too coarse when
    # several deliverables share a section + role (e.g. BOM vs pin-map are both
    # tables in C03); the filename keyword is the disambiguator.
    lower = rel_path.lower()
    sections = [k for k in item["sections"] if k]
    section_ok = (not sections) or any(k in lower for k in sections)
    name_ok = any(n in lower for n in item.get("names", []))
    return section_ok and name_ok


def assess_package_readiness(folder: str | Path, milestone: str = "POC") -> PackageReadiness:
    index = ingest_project_folder(folder)
    files = [(f.rel_path, f.role) for f in index.files]
    readiness = PackageReadiness(folder=str(folder), milestone=milestone)

    for item in POC_CHECKLIST:
        matched = sorted({rel for rel, _role in files if _matches(rel, item)})
        if matched:
            # "present" if a primary artifact matches; the schematic deliverable is only
            # "partial" when just supporting docs (design definition) exist, no real schematic.
            has_primary = any(
                rel.lower().endswith((".kicad_sch", ".dsn")) or "schematic" in rel.lower()
                for rel in matched
            )
            status = "present" if (item["key"] != "schematic" or has_primary) else "partial"
        else:
            status = "missing"
        readiness.deliverables.append(DeliverableStatus(
            key=item["key"], name=item["name"], producer=item["producer"], required=item["required"],
            status=status, files=matched, next_action="" if status == "present" else item["next"],
        ))

    readiness.external_sections = sorted({
        label for section in index.sections
        for prefix, label in EXTERNAL_SECTIONS.items() if section.lower().startswith(prefix)
    })

    # Feed C00 field-level PRD readiness into the prd deliverable instead of treating
    # the PRD as merely present/missing: when a C00 answer-state exists, the prd status
    # reflects how complete the PRD actually is (100% answered -> present, else partial),
    # and its next action becomes the C00 next-best question.
    prd_state = Path(folder) / "C00-PRD" / "answer_state.json"
    if prd_state.exists():
        try:
            from .c00_prd_template import assess_c00_prd_readiness
            c00 = assess_c00_prd_readiness(folder)
        except Exception:
            c00 = None
        if c00 is not None:
            for d in readiness.deliverables:
                if d.key == "prd":
                    d.status = "present" if c00.readiness_pct >= 100 else "partial"
                    d.next_action = "" if d.status == "present" else (
                        c00.next_question or f"Complete the C00 PRD ({c00.readiness_pct}% answered).")

    required = [d for d in readiness.deliverables if d.required]
    present_required = [d for d in required if d.status == "present"]
    readiness.readiness_pct = round(100 * len(present_required) / max(len(required), 1))
    pending = [d for d in readiness.deliverables if d.status != "present" and d.required] or \
              [d for d in readiness.deliverables if d.status != "present"]
    # Cross-stage reconciliation: an unresolved BlockerReturn (area/thermal/height overflow or a
    # C06 verdict-fail routed back) blocks the all-clear even when every deliverable is present.
    # The orchestration store may be absent (no blockers ever filed) — that is the normal case.
    try:
        from .orchestration import list_blockers
        open_blockers = list_blockers(folder, unresolved_only=True)
    except Exception:
        open_blockers = []
    readiness.open_blockers = [b.to_dict() for b in open_blockers]

    if open_blockers:
        routed = ", ".join(
            f"{b.blocker_id}→{','.join(b.affected_downstream_layers) or b.recommended_owner or '?'}"
            for b in open_blockers
        )
        readiness.next_step = (
            f"Resolve/route {len(open_blockers)} open reconciliation blocker(s) before this "
            f"milestone is done: {routed}."
        )
    else:
        readiness.next_step = pending[0].next_action if pending else "All tracked deliverables present for this milestone."
    blocker_note = f" {len(open_blockers)} open reconciliation blocker(s)." if open_blockers else ""
    readiness.summary = (
        f"{milestone}: {len(present_required)}/{len(required)} required deliverables present "
        f"({readiness.readiness_pct}%).{blocker_note} "
        f"External (not bodesign): {', '.join(readiness.external_sections) or 'none'}."
    )
    return readiness


def render_readiness_markdown(r: PackageReadiness) -> str:
    lines = [f"# Package readiness — {r.milestone}", "", f"- Folder: `{r.folder}`",
             f"- Readiness: **{r.readiness_pct}%** ({r.summary})", f"- **Next step:** {r.next_step}", "",
             "| Deliverable | Producer | Required | Status | Files / next action |", "|---|---|---|---|---|"]
    icon = {"present": "✅", "partial": "🟡", "missing": "⬜", "external": "↗"}
    for d in r.deliverables:
        detail = ", ".join(f"`{f}`" for f in d.files[:3]) if d.files else d.next_action
        lines.append(f"| {d.name} | {d.producer} | {'yes' if d.required else 'opt'} | {icon.get(d.status,'')} {d.status} | {detail} |")
    if r.external_sections:
        lines.append("")
        lines.append(f"_External-owned (not bodesign): {', '.join(r.external_sections)}._")
    return "\n".join(lines)
