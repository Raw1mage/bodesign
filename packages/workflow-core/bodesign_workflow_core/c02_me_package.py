"""C02 mechanical enclosure package generation and readiness checks.

This module is constraint-first. It decides whether the mechanical/enclosure
inputs are ready for a draft CAD pass and can emit prototype OpenSCAD/STL
drafts. It does not generate SKP, STEP, or ME approval.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_FOR_CAD = (
    "board_outline",
    "component_heights",
)

RECOMMENDED_FOR_USEFUL_DRAFT = (
    "mounting_holes",
    "connector_openings",
    "heat_sources",
    "antenna_keepouts",
)

C02_OUTPUTS = {
    "constraints": Path("C02-ME") / "Mechanical_Constraints.json",
    "assumptions": Path("C02-ME") / "Mechanical_Assumptions.md",
    "assembly": Path("C02-ME") / "Assembly_Notes.md",
    "print_settings": Path("C02-ME") / "Print_Settings.md",
    "vendor_handoff": Path("C02-ME") / "Vendor_Handoff.md",
    "sketchup_guide": Path("C02-ME") / "SketchUp_Import_Guide.md",
    "openscad": Path("C02-ME") / "Enclosure.scad",
    "stl": Path("C02-ME") / "Enclosure.stl",
}


@dataclass(slots=True)
class C02ConstraintItem:
    key: str
    status: str
    owner: str
    message: str
    blocks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "status": self.status,
            "owner": self.owner,
            "message": self.message,
            "blocks": self.blocks,
        }


@dataclass(slots=True)
class C02ConstraintReadiness:
    readiness_level: str
    readiness_pct: int
    can_generate_cad_source: bool
    can_place_openings: bool
    can_create_printable_draft: bool
    next_step: str
    items: list[C02ConstraintItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "readiness_level": self.readiness_level,
            "readiness_pct": self.readiness_pct,
            "can_generate_cad_source": self.can_generate_cad_source,
            "can_place_openings": self.can_place_openings,
            "can_create_printable_draft": self.can_create_printable_draft,
            "next_step": self.next_step,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(slots=True)
class C02PackageResult:
    folder: str
    files: list[str]
    readiness: C02ConstraintReadiness
    status: str = "package_emitted"

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "files": self.files,
            "status": self.status,
            "readiness": self.readiness.to_dict(),
            "source_ready": False,
            "viewable_draft_ready": False,
            "printable_draft_ready": False,
            "vendor_handoff_ready": False,
            "me_approved": False,
        }


@dataclass(slots=True)
class C02OpenScadResult:
    folder: str
    source_path: str | None
    status: str
    readiness: C02ConstraintReadiness
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "source_path": self.source_path,
            "status": self.status,
            "message": self.message,
            "readiness": self.readiness.to_dict(),
            "source_ready": self.status == "source_generated",
            "viewable_draft_ready": False,
            "printable_draft_ready": False,
            "vendor_handoff_ready": False,
            "me_approved": False,
        }


@dataclass(slots=True)
class C02StlExportResult:
    folder: str
    stl_path: str | None
    status: str
    message: str
    openscad_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        exported = self.status == "stl_exported"
        return {
            "folder": self.folder,
            "stl_path": self.stl_path,
            "status": self.status,
            "message": self.message,
            "openscad_path": self.openscad_path,
            "source_ready": bool(self.openscad_path),
            "viewable_draft_ready": exported,
            "printable_draft_ready": exported,
            "vendor_handoff_ready": False,
            "me_approved": False,
        }


@dataclass(slots=True)
class C02SkpExportResult:
    folder: str
    skp_path: str | None
    status: str
    message: str
    guide_path: str
    source_path: str | None = None
    stl_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "skp_path": self.skp_path,
            "status": self.status,
            "message": self.message,
            "guide_path": self.guide_path,
            "source_path": self.source_path,
            "stl_path": self.stl_path,
            "source_ready": bool(self.source_path),
            "viewable_draft_ready": bool(self.stl_path),
            "printable_draft_ready": bool(self.stl_path),
            "vendor_handoff_ready": False,
            "me_approved": False,
        }


def emit_c02_enclosure_package(
    out_dir: str | Path,
    constraints: dict[str, Any] | None = None,
    project_summary: dict[str, Any] | str | None = None,
    prototype_intent: str | None = None,
    printer_profile: dict[str, Any] | str | None = None,
) -> C02PackageResult:
    """Emit deterministic C02 support files without generating CAD artifacts."""
    root = Path(out_dir)
    model = _build_package_model(constraints or {}, project_summary, prototype_intent, printer_profile)
    files = {
        C02_OUTPUTS["constraints"]: json.dumps(model["constraints"], ensure_ascii=False, indent=2) + "\n",
        C02_OUTPUTS["assumptions"]: _render_assumptions(model),
        C02_OUTPUTS["assembly"]: _render_assembly_notes(model),
        C02_OUTPUTS["print_settings"]: _render_print_settings(model),
        C02_OUTPUTS["vendor_handoff"]: _render_vendor_handoff(model),
        C02_OUTPUTS["sketchup_guide"]: _render_sketchup_guide(model),
    }
    written: list[str] = []
    for rel_path, content in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(rel_path))
    return C02PackageResult(str(root), written, assess_c02_constraint_readiness(folder=root))


def generate_c02_openscad(
    out_dir: str | Path,
    constraints: dict[str, Any] | None = None,
    wall_thickness_mm: float | None = None,
    clearance_mm: float | None = None,
    lid_clearance_mm: float | None = None,
) -> C02OpenScadResult:
    """Generate a simple OpenSCAD enclosure source from explicit constraints."""
    root = Path(out_dir)
    data = constraints if constraints is not None else _load_constraints(root)
    readiness = assess_c02_constraint_readiness(data)
    if not readiness.can_generate_cad_source:
        return C02OpenScadResult(
            folder=str(root),
            source_path=None,
            status="source_blocked",
            readiness=readiness,
            message=readiness.next_step,
        )
    if wall_thickness_mm is None or clearance_mm is None or lid_clearance_mm is None:
        return C02OpenScadResult(
            folder=str(root),
            source_path=None,
            status="source_blocked",
            readiness=readiness,
            message="wall_thickness_mm, clearance_mm, and lid_clearance_mm must be explicit; C02 does not guess enclosure dimensions.",
        )
    try:
        source = _render_openscad_source(data, wall_thickness_mm, clearance_mm, lid_clearance_mm)
    except ValueError as error:
        return C02OpenScadResult(
            folder=str(root),
            source_path=None,
            status="source_blocked",
            readiness=readiness,
            message=str(error),
        )
    path = root / C02_OUTPUTS["openscad"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    _update_assumptions_for_source(root, data)
    return C02OpenScadResult(
        folder=str(root),
        source_path=str(C02_OUTPUTS["openscad"]),
        status="source_generated",
        readiness=readiness,
        message="Generated OpenSCAD source only. STL/SKP/STEP export and ME approval remain separate steps.",
    )


def export_c02_stl(
    out_dir: str | Path,
    openscad_bin: str | None = None,
) -> C02StlExportResult:
    """Export STL through OpenSCAD CLI when available; otherwise fail fast."""
    root = Path(out_dir)
    source = root / C02_OUTPUTS["openscad"]
    if not source.exists():
        return C02StlExportResult(
            folder=str(root),
            stl_path=None,
            status="source_missing",
            message="C02-ME/Enclosure.scad is required before STL export.",
        )
    executable = openscad_bin or shutil.which("openscad")
    if not executable:
        return C02StlExportResult(
            folder=str(root),
            stl_path=None,
            status="export_unavailable",
            message="OpenSCAD CLI is not available; no fake STL was created.",
            openscad_path=str(C02_OUTPUTS["openscad"]),
        )
    stl = root / C02_OUTPUTS["stl"]
    stl.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [executable, "-o", str(stl), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not stl.exists():
        return C02StlExportResult(
            folder=str(root),
            stl_path=None,
            status="export_failed",
            message=(completed.stderr or completed.stdout or "OpenSCAD export failed.").strip(),
            openscad_path=str(C02_OUTPUTS["openscad"]),
        )
    _update_print_settings_for_stl(root)
    return C02StlExportResult(
        folder=str(root),
        stl_path=str(C02_OUTPUTS["stl"]),
        status="stl_exported",
        message="Generated real STL via OpenSCAD CLI. This is still a prototype draft, not ME approval.",
        openscad_path=str(C02_OUTPUTS["openscad"]),
    )


def export_c02_skp(
    out_dir: str | Path,
) -> C02SkpExportResult:
    """Report native SKP export unavailability and keep SketchUp import guidance current."""
    root = Path(out_dir)
    source = root / C02_OUTPUTS["openscad"]
    stl = root / C02_OUTPUTS["stl"]
    guide = root / C02_OUTPUTS["sketchup_guide"]
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_text(_render_sketchup_fallback_status(source.exists(), stl.exists()), encoding="utf-8")
    return C02SkpExportResult(
        folder=str(root),
        skp_path=None,
        status="skp_export_unavailable",
        message="Native SKP export requires an explicit SketchUp-capable toolchain; use the import guide with the available STL/source artifact instead.",
        guide_path=str(C02_OUTPUTS["sketchup_guide"]),
        source_path=str(C02_OUTPUTS["openscad"]) if source.exists() else None,
        stl_path=str(C02_OUTPUTS["stl"]) if stl.exists() else None,
    )


def assess_c02_constraint_readiness(
    constraints: dict[str, Any] | None = None,
    folder: str | Path | None = None,
) -> C02ConstraintReadiness:
    """Assess whether C02 has enough explicit constraints for enclosure CAD.

    If `constraints` is omitted and `folder` is provided, this reads
    `C02-ME/Mechanical_Constraints.json`. Missing data is reported as blockers;
    no dimensions are guessed.
    """
    data = constraints if constraints is not None else _load_constraints(folder)
    items = [
        _item("board_outline", data, "C04 layout / EE", "Board outline is required before any enclosure source can be generated.", ["cad_source", "stl", "skp", "step"]),
        _item("component_heights", data, "C03 EE / C04 layout", "Component height envelope is required before enclosure internal height can be set.", ["cad_source", "stl", "skp", "step"]),
        _item("mounting_holes", data, "C04 layout / ME", "Mounting holes are needed for screw posts; without them posts remain placeholders.", ["screw_posts", "assembly"]),
        _item("connector_openings", data, "C03 EE / C02 ME / C04 layout", "External connector openings define case cutouts and insertion clearance.", ["openings", "layout_constraints"]),
        _item("heat_sources", data, "C03 EE", "Heat sources are needed for thermal path, vent, material, and clearance decisions.", ["thermal_review"]),
        _item("antenna_keepouts", data, "C03 EE/RF / C04 layout", "Antenna keepouts are needed before enclosing RF areas or selecting metal/vent placement.", ["rf_review", "layout_keepout"]),
        _item("battery_envelope", data, "C03 EE / user", "Battery envelope is needed when the product is battery-powered.", ["battery_compartment"]),
        _item("environment_targets", data, "C00 user / C06 verification", "Environment targets drive waterproofing, dust, drop, material, and test assumptions.", ["compliance_review", "vendor_handoff"]),
    ]
    present = {item.key for item in items if item.status == "present"}
    can_generate = all(key in present for key in REQUIRED_FOR_CAD)
    can_place_openings = "connector_openings" in present
    useful_count = sum(1 for item in items if item.status == "present")
    readiness_pct = round(100 * useful_count / len(items))
    if can_generate and all(key in present for key in RECOMMENDED_FOR_USEFUL_DRAFT):
        level = "source_ready"
        next_step = "Generate parametric source only after the user approves this constraint set; STL/SKP/STEP export remains a later toolchain step."
    elif can_generate:
        level = "brief_ready"
        next_step = "CAD source can be drafted, but collect mounting holes, connector openings, heat, and RF constraints before a useful enclosure pass."
    else:
        level = "brief_ready"
        next_step = _first_blocker(items)
    return C02ConstraintReadiness(
        readiness_level=level,
        readiness_pct=readiness_pct,
        can_generate_cad_source=can_generate,
        can_place_openings=can_place_openings,
        can_create_printable_draft=False,
        next_step=next_step,
        items=items,
    )


def _load_constraints(folder: str | Path | None) -> dict[str, Any]:
    if folder is None:
        return {}
    path = Path(folder) / "C02-ME" / "Mechanical_Constraints.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid C02 mechanical constraints JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"C02 mechanical constraints must be a JSON object: {path}")
    return data


def _build_package_model(
    constraints: dict[str, Any],
    project_summary: dict[str, Any] | str | None,
    prototype_intent: str | None,
    printer_profile: dict[str, Any] | str | None,
) -> dict[str, Any]:
    normalized = _normalized_constraints(constraints)
    readiness = assess_c02_constraint_readiness(normalized)
    return {
        "summary": _summary_text(project_summary),
        "prototype_intent": prototype_intent or "missing — user must choose visual review, fit check, demo enclosure, or vendor RFQ intent",
        "printer_profile": _printer_profile_text(printer_profile),
        "constraints": normalized,
        "readiness": readiness,
    }


def _normalized_constraints(constraints: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(constraints)
    readiness = assess_c02_constraint_readiness(constraints)
    pending = [
        {
            "key": item.key,
            "status": "engineering_pending",
            "owner": item.owner,
            "reason": item.message,
            "blocks": item.blocks,
        }
        for item in readiness.items
        if item.status != "present"
    ]
    normalized["constraint_status"] = {
        "source": "bodesign_c02_emit_enclosure_package",
        "notes": "Package emitter preserves missing data as engineering_pending; it does not generate CAD dimensions.",
        "pending": pending,
    }
    normalized["approval_status"] = {
        "source_ready": False,
        "viewable_draft_ready": False,
        "printable_draft_ready": False,
        "vendor_handoff_ready": False,
        "me_approved": False,
    }
    return normalized


def _summary_text(summary: dict[str, Any] | str | None) -> str:
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    if isinstance(summary, dict):
        chunks = [str(summary[key]) for key in ("summary", "product", "use_case", "environment") if summary.get(key)]
        if chunks:
            return "\n".join(chunks)
    return "No C00/C01/C03/C04 summary provided; C02 package remains a mechanical constraint intake shell."


def _printer_profile_text(profile: dict[str, Any] | str | None) -> str:
    if isinstance(profile, str) and profile.strip():
        return profile.strip()
    if isinstance(profile, dict) and profile:
        return ", ".join(f"{key}: {value}" for key, value in sorted(profile.items()))
    return "missing — printer, material, nozzle, layer height, and tolerance must be confirmed before printable draft claims."


def _render_openscad_source(
    constraints: dict[str, Any],
    wall_thickness_mm: float,
    clearance_mm: float,
    lid_clearance_mm: float,
) -> str:
    board = constraints.get("board_outline")
    if not isinstance(board, dict):
        raise ValueError("board_outline must be an object with width_mm and height_mm.")
    board_width = _number(board, "width_mm", "width")
    board_height = _number(board, "height_mm", "height")
    max_component_height = _max_component_height(constraints.get("component_heights"))
    wall = _positive_float(wall_thickness_mm, "wall_thickness_mm")
    clearance = _positive_float(clearance_mm, "clearance_mm")
    lid_clearance = _positive_float(lid_clearance_mm, "lid_clearance_mm", allow_zero=True)
    inner_width = board_width + clearance * 2
    inner_height = board_height + clearance * 2
    case_width = inner_width + wall * 2
    case_height = inner_height + wall * 2
    case_depth = max_component_height + clearance + lid_clearance + wall * 2
    lines = [
        "// C02 prototype enclosure draft generated by bodesign.",
        "// Prototype source only: not production ME approval, not STEP, not SKP.",
        "// All dimensions come from explicit constraints or explicit tool parameters.",
        f"board_width = {_fmt(board_width)};",
        f"board_height = {_fmt(board_height)};",
        f"max_component_height = {_fmt(max_component_height)};",
        f"wall = {_fmt(wall)};",
        f"clearance = {_fmt(clearance)};",
        f"lid_clearance = {_fmt(lid_clearance)};",
        "inner_width = board_width + clearance * 2;",
        "inner_height = board_height + clearance * 2;",
        "case_width = inner_width + wall * 2;",
        "case_height = inner_height + wall * 2;",
        "case_depth = max_component_height + clearance + lid_clearance + wall * 2;",
        "",
        "module enclosure_shell() {",
        "  difference() {",
        "    cube([case_width, case_height, case_depth]);",
        "    translate([wall, wall, wall]) cube([inner_width, inner_height, case_depth]);",
        "  }",
        "}",
        "",
        "module board_placeholder() {",
        "  translate([wall + clearance, wall + clearance, wall])",
        "    color(\"green\", 0.35) cube([board_width, board_height, 1]);",
        "}",
        "",
        "module mounting_markers() {",
    ]
    holes = constraints.get("mounting_holes")
    if isinstance(holes, list) and holes:
        for index, hole in enumerate(holes, start=1):
            if isinstance(hole, dict) and _maybe_number(hole, "x_mm") is not None and _maybe_number(hole, "y_mm") is not None:
                x = _maybe_number(hole, "x_mm")
                y = _maybe_number(hole, "y_mm")
                diameter = _maybe_number(hole, "diameter_mm") or 2.5
                lines.append(f"  // mounting hole {index}: marker only; post/counterbore needs ME review")
                lines.append(f"  translate([wall + clearance + {_fmt(x)}, wall + clearance + {_fmt(y)}, wall]) cylinder(h=3, d={_fmt(diameter + 2)}, $fn=24);")
    else:
        lines.append("  // mounting holes not provided; screw posts intentionally omitted.")
    lines.extend([
        "}",
        "",
        "module opening_notes() {",
    ])
    openings = constraints.get("connector_openings")
    if isinstance(openings, list) and openings:
        for index, opening in enumerate(openings, start=1):
            lines.append(f"  // connector/opening {index}: {_openscad_comment(opening)}")
    else:
        lines.append("  // connector openings not provided; no case cutouts generated.")
    lines.extend([
        "}",
        "",
        "enclosure_shell();",
        "board_placeholder();",
        "mounting_markers();",
        "opening_notes();",
        "",
        f"// Computed case size preview: {_fmt(case_width)} x {_fmt(case_height)} x {_fmt(case_depth)} mm",
    ])
    return "\n".join(lines) + "\n"


def _update_assumptions_for_source(root: Path, constraints: dict[str, Any]) -> None:
    path = root / C02_OUTPUTS["assumptions"]
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text += "\n## OpenSCAD Source Status\n"
    text += "- `C02-ME/Enclosure.scad` has been generated as a prototype source.\n"
    text += "- STL/SKP/STEP export and ME approval remain separate gates.\n"
    if not _has_value(constraints.get("connector_openings")):
        text += "- Connector openings were not generated because explicit opening geometry is missing.\n"
    path.write_text(text, encoding="utf-8")


def _update_print_settings_for_stl(root: Path) -> None:
    path = root / C02_OUTPUTS["print_settings"]
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text += "\n## STL Export Status\n"
    text += "- `C02-ME/Enclosure.stl` was exported by OpenSCAD.\n"
    text += "- Treat it as a prototype print draft; fit iteration and ME review are still required.\n"
    path.write_text(text, encoding="utf-8")


def _number(data: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = _maybe_number(data, key)
        if value is not None:
            return value
    raise ValueError(f"Missing numeric value; expected one of: {', '.join(keys)}")


def _maybe_number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def _max_component_height(value: Any) -> float:
    if not isinstance(value, list) or not value:
        raise ValueError("component_heights must be a non-empty list with height_mm values.")
    heights = [_maybe_number(item, "height_mm") for item in value if isinstance(item, dict)]
    numeric = [height for height in heights if height is not None]
    if not numeric:
        raise ValueError("component_heights must include at least one positive height_mm.")
    return max(numeric)


def _positive_float(value: float, label: str, allow_zero: bool = False) -> float:
    parsed = float(value)
    if parsed > 0 or (allow_zero and parsed == 0):
        return parsed
    raise ValueError(f"{label} must be positive.")


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _openscad_comment(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _render_assumptions(model: dict[str, Any]) -> str:
    readiness: C02ConstraintReadiness = model["readiness"]
    pending = [item for item in readiness.items if item.status != "present"]
    lines = [
        "# Mechanical Assumptions",
        "",
        "## Scope",
        "This C02 package is a constraint intake and vendor handoff package. It does not include CAD source, STL, SKP, STEP, or ME approval.",
        "",
        "## Project Summary",
        str(model["summary"]),
        "",
        "## Prototype Intent",
        str(model["prototype_intent"]),
        "",
        "## Engineering Pending Items",
    ]
    if pending:
        for item in pending:
            lines.append(f"- `{item.key}` — owner: {item.owner}; reason: {item.message}")
    else:
        lines.append("- No readiness blockers detected for source intake; CAD generation still requires explicit user approval and a later tool.")
    lines.extend([
        "",
        "## Non-Approval Statement",
        "AI/tool output is not production mechanical approval, DFM approval, waterproofing approval, strength approval, or tolerance sign-off.",
        "",
    ])
    return "\n".join(lines)


def _render_assembly_notes(model: dict[str, Any]) -> str:
    return "\n".join([
        "# Assembly Notes",
        "",
        "## Current Assembly Status",
        "Assembly is not finalized. Use this file to collect constraints for PCB mounting, lid/base split, screws, battery retention, cable access, and serviceability.",
        "",
        "## Required Inputs Before CAD",
        "- PCB outline and mounting strategy from C04/layout or ME.",
        "- Component height envelope and external connector list from C03/C04.",
        "- Battery envelope, cable routing, antenna keepout, and heat-source map where applicable.",
        "",
        "## Assembly Authority",
        "Final assembly sequence and fastener/catch/adhesive decisions require ME/vendor review.",
        "",
    ])


def _render_print_settings(model: dict[str, Any]) -> str:
    return "\n".join([
        "# Print Settings",
        "",
        "## Printer Profile",
        str(model["printer_profile"]),
        "",
        "## Current Printability Status",
        "No STL has been generated by this package emitter. Printable readiness remains false until a later export tool creates a real STL and records print assumptions.",
        "",
        "## Items To Confirm",
        "- Material: PLA / PETG / ABS / resin / other.",
        "- Wall thickness, clearance, screw fit, orientation, support, and tolerance compensation.",
        "- Fit iteration responsibility belongs to the printer operator and ME/vendor.",
        "",
    ])


def _render_vendor_handoff(model: dict[str, Any]) -> str:
    readiness: C02ConstraintReadiness = model["readiness"]
    return "\n".join([
        "# Vendor Handoff",
        "",
        "## Request",
        "Use this package to estimate and refine a prototype enclosure. Vendor should return mechanical recommendations, CAD/STEP plan, assembly approach, DFM risks, and quote/timeline.",
        "",
        "## Current Readiness",
        f"- Readiness level: `{readiness.readiness_level}`",
        f"- CAD source allowed by constraints: `{readiness.can_generate_cad_source}`",
        f"- Printable draft ready: `False`",
        f"- ME approved: `False`",
        "",
        "## Vendor-Owned Outputs",
        "- Final or vendor-refined `3D File (.step)`.",
        "- Introduction of Assembly / exploded view / fastening strategy.",
        "- Tolerance, material, structural, waterproofing, thermal, and DFM sign-off.",
        "",
    ])


def _render_sketchup_guide(model: dict[str, Any]) -> str:
    return "\n".join([
        "# SketchUp Import Guide",
        "",
        "Native `Enclosure.skp` is not generated by this package emitter.",
        "",
        "## Current Status",
        "- `skp_export_unavailable`: true",
        "- Reason: no SketchUp-capable export toolchain is part of C02-T1.",
        "- Baseline future path: generate `Enclosure.stl`, then import the STL/DAE/OBJ into SketchUp for 360-degree review.",
        "",
        "Do not treat this guide as proof that an SKP, STL, or STEP artifact exists.",
        "",
    ])


def _render_sketchup_fallback_status(source_exists: bool, stl_exists: bool) -> str:
    artifact = "C02-ME/Enclosure.stl" if stl_exists else "C02-ME/Enclosure.scad" if source_exists else "no 3D artifact yet"
    return "\n".join([
        "# SketchUp Import Guide",
        "",
        "## Native SKP Status",
        "- `skp_export_unavailable`: true",
        "- Reason: no explicit SketchUp-capable exporter, Ruby automation, SDK, or vendor conversion toolchain is configured.",
        "- No `C02-ME/Enclosure.skp` file was generated.",
        "",
        "## Available Review Artifact",
        f"- Current artifact: `{artifact}`",
        "- If an STL exists, import it into SketchUp with an STL importer or convert it through a user-approved converter before saving as `.skp`.",
        "- If only OpenSCAD source exists, export a real STL first with `bodesign_c02_export_stl` after OpenSCAD is installed/configured.",
        "",
        "## Limits",
        "- SKP import/re-save is a review workflow, not ME approval.",
        "- Do not treat this guide as proof that native SKP export succeeded.",
        "",
    ])



def _item(key: str, data: dict[str, Any], owner: str, missing_message: str, blocks: list[str]) -> C02ConstraintItem:
    value = data.get(key)
    if _has_value(value):
        return C02ConstraintItem(key=key, status="present", owner=owner, message="Explicit constraint provided.")
    return C02ConstraintItem(key=key, status="missing", owner=owner, message=missing_message, blocks=blocks)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _first_blocker(items: list[C02ConstraintItem]) -> str:
    for key in REQUIRED_FOR_CAD:
        for item in items:
            if item.key == key and item.status != "present":
                return item.message
    for item in items:
        if item.status != "present":
            return item.message
    return "C02 constraint readiness has no blockers."
