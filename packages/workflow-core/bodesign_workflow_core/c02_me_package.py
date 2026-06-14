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
    "step": Path("C02-ME") / "Enclosure.step",
    "step_handoff": Path("C02-ME") / "STEP_Draft_Handoff.md",
    "projection_scad": Path("C02-ME") / "Enclosure_projection.scad",
    "projection_svg": Path("C02-ME") / "Enclosure.svg",
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


@dataclass(slots=True)
class C02StepExportResult:
    folder: str
    step_path: str | None
    status: str
    message: str
    handoff_path: str
    source_path: str | None = None
    stl_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        exported = self.status == "step_exported"
        return {
            "folder": self.folder,
            "step_path": self.step_path,
            "status": self.status,
            "message": self.message,
            "handoff_path": self.handoff_path,
            "source_path": self.source_path,
            "stl_path": self.stl_path,
            "source_ready": bool(self.source_path),
            "viewable_draft_ready": bool(self.stl_path) or exported,
            "printable_draft_ready": bool(self.stl_path),
            "vendor_handoff_ready": exported,
            "draft_unapproved": exported,
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
    corner_radius_mm: float | None = None,
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
        source = _render_openscad_source(data, wall_thickness_mm, clearance_mm, lid_clearance_mm, corner_radius_mm)
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


@dataclass(slots=True)
class C02ProjectionSvgResult:
    folder: str
    svg_path: str | None
    status: str
    message: str
    wrapper_path: str | None = None
    source_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "svg_path": self.svg_path,
            "status": self.status,
            "message": self.message,
            "wrapper_path": self.wrapper_path,
            "source_path": self.source_path,
            "vector_ready": self.status == "svg_exported",
        }


def export_c02_projection_svg(
    out_dir: str | Path,
    openscad_bin: str | None = None,
    cut: bool = False,
) -> C02ProjectionSvgResult:
    """Project the 3D enclosure to a clean 2D vector SVG via OpenSCAD projection().

    This derives the 2D drawing FROM the 3D model (same source, no drift) instead
    of tracing a raster — the SVG is exact geometric paths, not messy trace
    fragments. Requires the exported STL (Enclosure.stl) and the OpenSCAD CLI;
    writes a wrapper .scad that does `projection(cut=<cut>) import("Enclosure.stl")`
    then runs `openscad -o Enclosure.svg <wrapper>`. Fails fast (no fake SVG) when
    the STL or the CLI is absent.

    cut=False -> outline projection (silhouette of all geometry, the design view).
    cut=True  -> a planar cross-section at z=0.
    """
    root = Path(out_dir)
    stl = root / C02_OUTPUTS["stl"]
    if not stl.exists():
        return C02ProjectionSvgResult(
            folder=str(root),
            svg_path=None,
            status="source_missing",
            message="C02-ME/Enclosure.stl is required before SVG projection; run c02_export_stl first.",
            source_path=str(C02_OUTPUTS["openscad"]) if (root / C02_OUTPUTS["openscad"]).exists() else None,
        )
    executable = openscad_bin or shutil.which("openscad")
    if not executable:
        return C02ProjectionSvgResult(
            folder=str(root),
            svg_path=None,
            status="export_unavailable",
            message="OpenSCAD CLI is not available; no fake SVG was created.",
            source_path=str(C02_OUTPUTS["stl"]),
        )
    wrapper = root / C02_OUTPUTS["projection_scad"]
    svg = root / C02_OUTPUTS["projection_svg"]
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    # The wrapper sits beside Enclosure.stl in C02-ME/, so import() uses a bare name.
    cut_flag = "true" if cut else "false"
    wrapper.write_text(
        "// Auto-generated 2D projection of the 3D enclosure (exact geometry, not traced).\n"
        f"projection(cut = {cut_flag}) import(\"Enclosure.stl\");\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [executable, "-o", str(svg), str(wrapper)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not svg.exists():
        return C02ProjectionSvgResult(
            folder=str(root),
            svg_path=None,
            status="export_failed",
            message=(completed.stderr or completed.stdout or "OpenSCAD SVG projection failed.").strip(),
            wrapper_path=str(C02_OUTPUTS["projection_scad"]),
            source_path=str(C02_OUTPUTS["stl"]),
        )
    return C02ProjectionSvgResult(
        folder=str(root),
        svg_path=str(C02_OUTPUTS["projection_svg"]),
        status="svg_exported",
        message="Projected a clean 2D vector SVG from the 3D enclosure (exact geometric paths, not a raster trace).",
        wrapper_path=str(C02_OUTPUTS["projection_scad"]),
        source_path=str(C02_OUTPUTS["stl"]),
    )


def _build123d_available() -> bool:
    """True when the build123d/OCP CAD kernel can be imported. Patchable in tests."""
    try:
        import build123d  # noqa: F401
        return True
    except Exception:
        return False


def _build_enclosure_part(
    constraints: dict[str, Any],
    wall_thickness_mm: float,
    clearance_mm: float,
    lid_clearance_mm: float,
    corner_radius_mm: float | None = None,
):
    """Build a real enclosure solid from the SAME constraints the OpenSCAD path uses.

    Mirrors `_render_openscad_source` geometry: an open-top shell with a wall-thick
    floor plus solid mounting bosses (with pilot holes) at the given mounting holes.
    When corner_radius_mm > 0 the four vertical (Z-axis) edges are filleted to match
    the OpenSCAD hull rounding; the flat top/bottom edges stay square.
    Raises ValueError on missing/invalid board outline — C02 never guesses dimensions.
    """
    from build123d import Align, Axis, Box, BuildPart, Cylinder, Locations, Mode, fillet

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
    standoff_h = max(3.0, min(max_component_height or 4.0, case_depth - wall * 2))
    radius = _validate_corner_radius(corner_radius_mm, case_width, case_height)

    corner = (Align.MIN, Align.MIN, Align.MIN)
    center3 = (Align.CENTER, Align.CENTER, Align.CENTER)
    with BuildPart() as part:
        Box(case_width, case_height, case_depth, align=corner)
        if radius > 0.0:
            # Round only the four vertical edges (parallel to Z), matching the
            # OpenSCAD hull; the flat top/bottom edges are left square.
            vertical_edges = part.edges().filter_by(Axis.Z)
            fillet(vertical_edges, radius=radius)
        with Locations((wall, wall, wall)):  # hollow: open top + wall-thick floor
            Box(inner_width, inner_height, case_depth + 1, align=corner, mode=Mode.SUBTRACT)
        holes = constraints.get("mounting_holes")
        if isinstance(holes, list) and standoff_h > 0:
            for hole in holes:
                if not isinstance(hole, dict):
                    continue
                hx, hy = _maybe_number(hole, "x_mm"), _maybe_number(hole, "y_mm")
                if hx is None or hy is None:
                    continue
                dia = _maybe_number(hole, "diameter_mm") or 2.5
                cx, cy = wall + clearance + hx, wall + clearance + hy
                with Locations((cx, cy, wall)):
                    Cylinder((dia + 3) / 2, standoff_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((cx, cy, wall)):
                    Cylinder(dia / 2, standoff_h + 1, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # Connector cutouts — same shared geometry as the OpenSCAD path so the two
        # routes do not drift. Openings lacking complete geometry are skipped.
        openings = constraints.get("connector_openings")
        if isinstance(openings, list):
            for opening in openings:
                cut = _connector_cut_geometry(opening, wall, clearance, case_width, case_height)
                if cut is None:
                    continue
                with Locations((cut["center_x"], cut["center_y"], cut["center_z"])):
                    Box(cut["size_x"], cut["size_y"], cut["size_z"], align=center3, mode=Mode.SUBTRACT)
    return part.part


def export_c02_step(
    out_dir: str | Path,
    constraints: dict[str, Any] | None = None,
    wall_thickness_mm: float | None = None,
    clearance_mm: float | None = None,
    lid_clearance_mm: float | None = None,
    corner_radius_mm: float | None = None,
) -> C02StepExportResult:
    """Export a real STEP via build123d when the kernel and explicit dimensions exist.

    Toolchain-gated, same shape as the STL/SKP exporters: with the build123d/OCP
    kernel present AND explicit wall/clearance/lid_clearance, write a real
    `Enclosure.step`; otherwise report `step_export_unavailable` and write the handoff
    note — never a fabricated STEP. C02 never guesses dimensions, so omitting the
    dimension params also yields `step_export_unavailable`.
    """
    root = Path(out_dir)
    data = constraints if constraints is not None else _load_constraints(root)
    source = root / C02_OUTPUTS["openscad"]
    stl = root / C02_OUTPUTS["stl"]
    handoff = root / C02_OUTPUTS["step_handoff"]
    handoff.parent.mkdir(parents=True, exist_ok=True)
    dims_given = None not in (wall_thickness_mm, clearance_mm, lid_clearance_mm)

    if _build123d_available() and dims_given:
        try:
            part = _build_enclosure_part(data, wall_thickness_mm, clearance_mm, lid_clearance_mm)
            from build123d import export_step as _export_step
            step_path = root / C02_OUTPUTS["step"]
            _export_step(part, str(step_path))
        except Exception as error:  # bad constraints / kernel failure — no fake STEP
            handoff.write_text(_render_step_handoff_status(source.exists(), stl.exists()), encoding="utf-8")
            return C02StepExportResult(
                folder=str(root), step_path=None, status="step_export_blocked",
                message=f"STEP geometry could not be built from the given constraints: {error}",
                handoff_path=str(C02_OUTPUTS["step_handoff"]),
                source_path=str(C02_OUTPUTS["openscad"]) if source.exists() else None,
                stl_path=str(C02_OUTPUTS["stl"]) if stl.exists() else None,
            )
        if not step_path.exists() or step_path.stat().st_size == 0:
            handoff.write_text(_render_step_handoff_status(source.exists(), stl.exists()), encoding="utf-8")
            return C02StepExportResult(
                folder=str(root), step_path=None, status="step_export_failed",
                message="build123d export_step produced no STEP file.",
                handoff_path=str(C02_OUTPUTS["step_handoff"]),
                source_path=str(C02_OUTPUTS["openscad"]) if source.exists() else None,
                stl_path=str(C02_OUTPUTS["stl"]) if stl.exists() else None,
            )
        handoff.write_text(_render_step_exported_handoff(), encoding="utf-8")
        return C02StepExportResult(
            folder=str(root), step_path=str(C02_OUTPUTS["step"]), status="step_exported",
            message="Generated a real STEP via build123d/OCP from explicit constraints. Draft for ME/vendor handoff — marked draft_unapproved, not ME approval.",
            handoff_path=str(C02_OUTPUTS["step_handoff"]),
            source_path=str(C02_OUTPUTS["openscad"]) if source.exists() else None,
            stl_path=str(C02_OUTPUTS["stl"]) if stl.exists() else None,
        )

    handoff.write_text(_render_step_handoff_status(source.exists(), stl.exists()), encoding="utf-8")
    return C02StepExportResult(
        folder=str(root),
        step_path=None,
        status="step_export_unavailable",
        message="STEP draft export requires a configured CAD kernel (build123d/OCP, FreeCAD, or CadQuery) and explicit wall/clearance/lid_clearance; no fake STEP was created.",
        handoff_path=str(C02_OUTPUTS["step_handoff"]),
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


def _validate_corner_radius(
    corner_radius_mm: float | None, case_width: float, case_height: float
) -> float:
    """Validate an optional vertical-edge corner radius. Returns 0.0 for None/0.

    DD-2: a None/0 radius means "no rounding" (an explicit absence of the feature),
    NOT a guessed value. A positive radius larger than half the smaller case side
    is geometrically impossible for four corner cylinders, so it fails fast rather
    than being silently clamped.
    """
    if corner_radius_mm is None:
        return 0.0
    radius = float(corner_radius_mm)
    if radius == 0.0:
        return 0.0
    if radius < 0.0:
        raise ValueError("corner_radius_mm must be >= 0.")
    limit = min(case_width, case_height) / 2.0
    if radius > limit:
        raise ValueError(
            f"corner_radius_mm ({_fmt(radius)}) exceeds half the smaller case side "
            f"({_fmt(limit)}); reduce the radius or enlarge the case."
        )
    return radius


def _outer_shell_scad(radius: float) -> str:
    """Return the OpenSCAD statement for the outer case body (square or rounded).

    radius == 0 -> a plain cube([case_width, case_height, case_depth]).
    radius > 0  -> hull() of four vertical cylinders (one per Z edge), centred
    `radius` in from each corner, giving rounded vertical edges only. The flat top
    and bottom edges stay square. Indented to sit inside the difference() block.
    """
    if radius <= 0.0:
        return "    cube([case_width, case_height, case_depth]);"
    r = _fmt(radius)
    cyl = f"cylinder(h=case_depth, r={r}, $fn=48)"
    return (
        "    hull() {\n"
        f"      translate([{r}, {r}, 0]) {cyl};\n"
        f"      translate([case_width - {r}, {r}, 0]) {cyl};\n"
        f"      translate([{r}, case_height - {r}, 0]) {cyl};\n"
        f"      translate([case_width - {r}, case_height - {r}, 0]) {cyl};\n"
        "    }"
    )


def _render_openscad_source(
    constraints: dict[str, Any],
    wall_thickness_mm: float,
    clearance_mm: float,
    lid_clearance_mm: float,
    corner_radius_mm: float | None = None,
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
    standoff_h = max(3.0, min(max_component_height or 4.0, case_depth - wall * 2))
    radius = _validate_corner_radius(corner_radius_mm, case_width, case_height)
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
        f"standoff_h = {_fmt(standoff_h)};",
        "inner_width = board_width + clearance * 2;",
        "inner_height = board_height + clearance * 2;",
        "case_width = inner_width + wall * 2;",
        "case_height = inner_height + wall * 2;",
        "case_depth = max_component_height + clearance + lid_clearance + wall * 2;",
        "",
        "module enclosure_shell() {",
        "  difference() {",
        _outer_shell_scad(radius),
        "    translate([wall, wall, wall]) cube([inner_width, inner_height, case_depth]);",
        "    connector_cuts();",
        "  }",
        "}",
        "",
        "module board_placeholder() {",
        "  translate([wall + clearance, wall + clearance, wall])",
        "    color(\"green\", 0.35) cube([board_width, board_height, 1]);",
        "}",
        "",
        "// Real screw standoffs: a solid boss (dia+3) minus a pilot hole (dia),",
        "// matching the build123d STEP path so the two geometry routes do not drift.",
        "module mounting_posts() {",
    ]
    holes = constraints.get("mounting_holes")
    if isinstance(holes, list) and holes and standoff_h > 0:
        any_post = False
        for index, hole in enumerate(holes, start=1):
            if isinstance(hole, dict) and _maybe_number(hole, "x_mm") is not None and _maybe_number(hole, "y_mm") is not None:
                x = _maybe_number(hole, "x_mm")
                y = _maybe_number(hole, "y_mm")
                diameter = _maybe_number(hole, "diameter_mm") or 2.5
                any_post = True
                lines.append(f"  // mounting hole {index}: standoff boss + pilot hole")
                lines.append(f"  translate([wall + clearance + {_fmt(x)}, wall + clearance + {_fmt(y)}, wall]) difference() {{")
                lines.append(f"    cylinder(h=standoff_h, d={_fmt(diameter + 3)}, $fn=32);")
                lines.append(f"    translate([0, 0, -0.5]) cylinder(h=standoff_h + 1, d={_fmt(diameter)}, $fn=32);")
                lines.append("  }")
        if not any_post:
            lines.append("  // mounting holes provided but lacked x_mm/y_mm; no posts generated.")
    else:
        lines.append("  // mounting holes not provided; screw posts intentionally omitted.")
    lines.extend([
        "}",
        "",
        "// Real connector cutouts: each opening with complete geometry",
        "// (face/width_mm/height_mm/z_mm) is differenced through its wall.",
        "module connector_cuts() {",
    ])
    openings = constraints.get("connector_openings")
    if isinstance(openings, list) and openings:
        any_cut = False
        for index, opening in enumerate(openings, start=1):
            cut = _connector_cut_geometry(opening, wall, clearance, case_width, case_height)
            if cut is None:
                lines.append(f"  // connector/opening {index}: skipped — incomplete cut geometry (need face/width_mm/height_mm/z_mm): {_openscad_comment(opening)}")
                continue
            any_cut = True
            ox = cut["center_x"] - cut["size_x"] / 2.0
            oy = cut["center_y"] - cut["size_y"] / 2.0
            oz = cut["center_z"] - cut["size_z"] / 2.0
            lines.append(f"  // connector/opening {index}: {cut['face']} face, {_fmt(cut['width_mm'])}x{_fmt(cut['height_mm'])} @ z={_fmt(cut['z_mm'])}")
            lines.append(f"  translate([{_fmt(ox)}, {_fmt(oy)}, {_fmt(oz)}]) cube([{_fmt(cut['size_x'])}, {_fmt(cut['size_y'])}, {_fmt(cut['size_z'])}]);")
        if not any_cut and not any(_connector_cut_geometry(o, wall, clearance, case_width, case_height) for o in openings):
            lines.append("  // no openings had complete cut geometry; no case cutouts generated.")
    else:
        lines.append("  // connector openings not provided; no case cutouts generated.")
    lines.extend([
        "}",
        "",
        "enclosure_shell();",
        "board_placeholder();",
        "mounting_posts();",
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


# Connector opening cut geometry — shared by the OpenSCAD and build123d paths so
# the two geometry routes never drift. DD-2: no dimension is ever guessed; an
# opening that lacks face/width_mm/height_mm/z_mm is reported, not cut.
_FACE_ALIASES = {
    "east": "east", "東": "east", "右": "east", "right": "east", "+x": "east",
    "west": "west", "西": "west", "左": "west", "left": "west", "-x": "west",
    "north": "north", "北": "north", "後": "north", "back": "north", "rear": "north", "+y": "north",
    "south": "south", "南": "south", "前": "south", "front": "south", "-y": "south",
}


def _normalize_face(raw: Any) -> str | None:
    """Normalize a connector face label to east/west/north/south, or None.

    Accepts EN/中文 aliases (東/east/右/right → east, etc.). Any unknown or
    non-string value yields None — never a guessed face (DD-2).
    """
    if not isinstance(raw, str):
        return None
    return _FACE_ALIASES.get(raw.strip().lower())


def _connector_cut_geometry(
    opening: Any,
    wall: float,
    clearance: float,
    case_width: float,
    case_height: float,
) -> dict[str, Any] | None:
    """Resolve a connector opening into an explicit cut box, or None when the
    opening lacks complete cut geometry.

    Required (DD-2, no guessing): face (normalizable), width_mm, height_mm, z_mm.
    Optional: offset_mm — center position along the wall measured from the wall's
    lower-coordinate end; when absent the cut is centered on that wall.

    Returns a dict with the resolved cut box in the shared corner-origin frame
    (Align.MIN at the case corner; case_width→+X, case_height→+Y, depth→+Z;
    floor top at z=wall):
      {face, width_mm, height_mm, z_mm, center_x, center_y, center_z,
       size_x, size_y, size_z}
    where size_* spans the cut box (the wall-normal axis is wall + 2 to punch
    fully through the wall). Returns None for incomplete/invalid geometry so the
    caller can keep it as a skipped note.
    """
    if not isinstance(opening, dict):
        return None
    face = _normalize_face(opening.get("face"))
    if face is None:
        return None
    width = _maybe_number(opening, "width_mm")
    height = _maybe_number(opening, "height_mm")
    z = _maybe_number(opening, "z_mm")
    if width is None or height is None or z is None:
        return None
    offset = _maybe_number(opening, "offset_mm")
    through = wall + 2.0  # punch fully through the wall in the normal direction
    center_z = wall + z

    if face in ("east", "west"):
        # wall normal is X; the opening width runs along Y, height along Z.
        along = offset if offset is not None else case_height / 2.0
        center_y = along
        center_x = case_width - wall / 2.0 if face == "east" else wall / 2.0
        size_x, size_y, size_z = through, width, height
    else:  # north / south — wall normal is Y; width runs along X, height along Z.
        along = offset if offset is not None else case_width / 2.0
        center_x = along
        center_y = case_height - wall / 2.0 if face == "north" else wall / 2.0
        size_x, size_y, size_z = width, through, height

    return {
        "face": face,
        "width_mm": width,
        "height_mm": height,
        "z_mm": z,
        "center_x": center_x,
        "center_y": center_y,
        "center_z": center_z,
        "size_x": size_x,
        "size_y": size_y,
        "size_z": size_z,
    }


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


def _render_step_handoff_status(source_exists: bool, stl_exists: bool) -> str:
    artifact = "C02-ME/Enclosure.stl" if stl_exists else "C02-ME/Enclosure.scad" if source_exists else "no 3D artifact yet"
    return "\n".join([
        "# STEP Draft Handoff",
        "",
        "## Native STEP Status",
        "- `step_export_unavailable`: true",
        "- Reason: no explicit FreeCAD, CadQuery, OCP, or equivalent CAD-kernel exporter is configured.",
        "- No `C02-ME/Enclosure.step` file was generated.",
        "",
        "## Available Source Artifact",
        f"- Current artifact: `{artifact}`",
        "- A vendor or ME engineer may use the source/STL as a reference to rebuild or refine a proper STEP model.",
        "- Any future STEP output must be marked `draft_unapproved` until reviewed by ME/vendor.",
        "",
        "## Limits",
        "- This handoff is not DFM, tolerance, strength, waterproofing, thermal, or production approval.",
        "- Do not treat this note as proof that STEP export succeeded.",
        "",
    ])



def _render_step_exported_handoff() -> str:
    return "\n".join([
        "# STEP Draft Handoff",
        "",
        "## Native STEP Status",
        "- `step_exported`: true",
        "- Toolchain: build123d / OCP (OpenCASCADE) CAD kernel.",
        "- Output: `C02-ME/Enclosure.step` — a real ISO-10303 STEP solid built from explicit constraints.",
        "- Marked `draft_unapproved`: this is a prototype handoff model, NOT ME/vendor approval.",
        "",
        "## For the ME / vendor",
        "- Open `Enclosure.step` in FreeCAD/SolidWorks/Fusion as a starting point.",
        "- Verify and own: wall/tolerance/draft/undercut, fit, strength, waterproofing, thermal, and DFM.",
        "",
        "## Limits",
        "- Not DFM, tolerance, strength, waterproofing, thermal, or production approval.",
        "- bodesign generated the geometry from constraints; it does not certify manufacturability.",
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


# ── Voice-to-design: spoken intent extraction + clarifying loop (DD-1/DD-2) ──
# Mirrors requirement_planning.plan_design_intent's deterministic keyword-binding
# skeleton, but binds the C02 mechanical fields (aligned with
# assess_c02_constraint_readiness's 8 items) instead of the C03 electrical ones.
# It NEVER guesses dimensions: unparseable/missing constraints become clarifying
# questions, not silent defaults (DD-2). gen_params (wall/clearance/lid) likewise
# come only from the spoken text or answers — never assumed.

import re as _re


@dataclass(frozen=True, slots=True)
class C02FieldBinding:
    """A C02 constraint field bound to natural-language keywords + a clarifying question.

    key: the constraint key (must match assess_c02_constraint_readiness items).
    label: human label for the field.
    keywords: EN+zh trigger words that mark the field as `stated` when matched.
    question: the clarifying question asked when the field is `missing`.
    blocks_source: True when a missing value blocks CAD source generation
        (board_outline / component_heights — the REQUIRED_FOR_CAD pair).
    extractor: optional callable(text) -> structured value | None; when present and
        it returns a value, the field is recorded with that structured value.
    """

    key: str
    label: str
    keywords: tuple[str, ...]
    question: str
    blocks_source: bool = False
    extractor: Any = None


def _extract_wxh(text: str) -> dict[str, float] | None:
    """Extract a width×height board outline from free text.

    Matches 50×30 / 50x30 / 60 x 40 / 50*30, optional 'mm'. Returns
    {width_mm, height_mm} or None when no W×H pair is present. Never guesses.
    """
    match = _re.search(
        r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×\*]\s*(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)?",
        text,
    )
    if not match:
        return None
    return {"width_mm": float(match.group(1)), "height_mm": float(match.group(2))}


def _extract_heights(text: str) -> list[dict[str, float]] | None:
    """Extract a component height envelope from free text.

    Matches '元件高 12mm' / '最高的元件大概 15 公釐' / 'tallest component 12 mm'.
    Requires a height-context keyword nearby so a bare board dimension is not
    mistaken for a component height. Returns [{height_mm}] or None.
    """
    height_ctx = ("元件", "component", "高", "tall", "height")
    if not any(token in text.lower() for token in height_ctx):
        return None
    # Avoid matching the W×H pair; search numbers followed by a mm/公釐 unit that
    # are NOT part of an x-separated pair.
    for match in _re.finditer(r"(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)", text):
        start = match.start()
        # skip if this number is the second half of a W×H (preceded by x/×/* )
        prefix = text[max(0, start - 3):start]
        if _re.search(r"[x×\*]\s*$", prefix):
            continue
        return [{"height_mm": float(match.group(1))}]
    return None


def _extract_connector_opening(text: str) -> dict[str, float | str] | None:
    """Extract ONE connector opening's cut geometry from free text, or None.

    Looks for a face (面/方位 alias) AND width×height AND a離地高 (z) — all three
    are required before an opening is treated as cuttable (DD-2: never guess a
    hole's face, size, or height). Returns a dict with the raw fields
    {face, width_mm, height_mm, z_mm[, offset_mm]} suitable for
    _connector_cut_geometry, or None when geometry is incomplete.

    Examples it resolves:
      "側面(east)開 USB-C，孔 9x3.5，離底 4mm"
      "open a 9 x 3.5 mm port on the east face, 4 mm from the floor"
    """
    face = None
    lowered = text.lower()
    # Find any face alias token present in the text.
    for alias, canonical in _FACE_ALIASES.items():
        if alias in ("+x", "-x", "+y", "-y"):
            continue
        if alias in lowered or alias in text:
            face = canonical
            break
    if face is None:
        return None
    # Find the W×H pair that is the connector hole — NOT the board outline. The
    # board pair is preceded by a board keyword (盒子/box/board/外殼), the hole
    # pair by a connector/opening keyword (開孔/孔/port/opening). Pick the first
    # pair NOT immediately preceded by a board-context word; never guess a size.
    _BOARD_CTX = ("盒子", "板框", "板子", "外殼", "box", "board", "enclosure", "outline")
    wh = None
    for m in _re.finditer(r"(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)?\s*[x×\*]\s*(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)?", text):
        # look at the words after this pair (board pairs read "60×40 的盒子")
        tail = text[m.end():m.end() + 8].lower()
        if any(ctx in tail for ctx in _BOARD_CTX):
            continue
        wh = m
        break
    if wh is None:
        return None
    width = float(wh.group(1))
    height = float(wh.group(2))
    z = None
    z_match = _re.search(r"(?:離底|離地|離地高|高度|from the floor|z)\s*(?:約|大概|為|=|:|of)?\s*(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)?", text, _re.IGNORECASE)
    if z_match:
        z = float(z_match.group(1))
    else:
        # also accept a trailing "4mm 離底" ordering
        z_match2 = _re.search(r"(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)\s*(?:離底|離地|from the floor)", text)
        if z_match2:
            z = float(z_match2.group(1))
    if z is None:
        return None
    out: dict[str, float | str] = {"face": face, "width_mm": width, "height_mm": height, "z_mm": z}
    off = _re.search(r"(?:offset|沿牆|位置)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)?", text, _re.IGNORECASE)
    if off:
        out["offset_mm"] = float(off.group(1))
    return out


def _parse_connector_answer(raw: str) -> list[dict[str, Any]] | None:
    """Parse a direct answer to the connector clarifying question.

    Accepts either a key=value form ("face=east, width_mm=9, height_mm=3.5,
    z_mm=4[, offset_mm=20]") or the same free-text the spoken extractor handles.
    Returns [opening] when complete cut geometry is present, else None (DD-2:
    incomplete answers do not invent a hole).
    """
    text = raw.strip()
    if not text:
        return None
    kv = dict(_re.findall(r"([a-zA-Z_]+)\s*=\s*([^,;\s]+)", text))
    if kv:
        face = _normalize_face(kv.get("face"))
        width = kv.get("width_mm")
        height = kv.get("height_mm")
        z = kv.get("z_mm")
        if face and width and height and z:
            try:
                opening: dict[str, Any] = {
                    "face": face,
                    "width_mm": float(width),
                    "height_mm": float(height),
                    "z_mm": float(z),
                }
            except ValueError:
                return None
            if kv.get("offset_mm"):
                try:
                    opening["offset_mm"] = float(kv["offset_mm"])
                except ValueError:
                    pass
            return [opening]
    extracted = _extract_connector_opening(text)
    return [extracted] if extracted else None


def _parse_answer_value(key: str, raw: str, binding: "C02FieldBinding") -> Any:
    """Parse a direct answer to a clarifying question for field `key`.

    The answer's target field is already established by `key`, so structured
    parsing here does NOT require the in-text context keywords that the
    spoken-text extractor (`binding.extractor`) needs. board_outline parses a
    W×H pair; component_heights parses the first mm number into [{height_mm}];
    connector_openings parses cut geometry (face/width/height/z); fields without
    a structured extractor keep the trimmed answer string. Returns the structured
    value, or None when nothing parseable is present.
    """
    text = raw.strip()
    if not text:
        return None
    if key == "board_outline":
        return _extract_wxh(text)
    if key == "component_heights":
        match = _re.search(r"(\d+(?:\.\d+)?)", text)
        return [{"height_mm": float(match.group(1))}] if match else None
    if key == "connector_openings":
        return _parse_connector_answer(text)
    if binding.extractor:
        return binding.extractor(text)
    return text


def _extract_gen_param(text: str, labels: tuple[str, ...]) -> float | None:
    """Extract a single mm dimension following one of `labels` (e.g. 壁厚/間隙/蓋間隙).

    Returns the float mm value or None. Never assumes a default (DD-2).
    """
    for label in labels:
        match = _re.search(
            _re.escape(label) + r"\s*(?:約|大概|為|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:mm|公釐|毫米)?",
            text,
        )
        if match:
            return float(match.group(1))
    return None


def _extract_gen_params(text: str, answers: dict[str, str]) -> dict[str, float]:
    """Collect wall/clearance/lid_clearance from spoken text or answers.

    Answers take precedence (an explicit clarifying answer). Values absent from
    both are simply omitted — the orchestrator must ask, never guess (DD-2).
    """
    params: dict[str, float] = {}
    sources = [text]
    spec_map = {
        "wall_thickness_mm": ("壁厚", "牆厚", "wall thickness", "wall"),
        "clearance_mm": ("間隙", "間距", "clearance", "gap"),
        "lid_clearance_mm": ("蓋間隙", "蓋子間隙", "lid clearance", "lid"),
        "corner_radius_mm": ("圓角", "倒角", "圓弧角", "corner radius", "rounded", "fillet", "chamfer", "radius"),
    }
    for param_key, labels in spec_map.items():
        ans = answers.get(param_key, "").strip() if answers.get(param_key) else ""
        if ans:
            num = _re.search(r"\d+(?:\.\d+)?", ans)
            if num:
                params[param_key] = float(num.group(0))
                continue
        for src in sources:
            value = _extract_gen_param(src, labels)
            if value is not None:
                params[param_key] = value
                break
    return params


# Rounding keywords that signal the user WANTS rounded vertical edges. If any is
# present but no radius number was extracted, plan_c02_intent must ask for the
# radius (DD-2: never guess a corner radius).
_CORNER_RADIUS_KEYWORDS = ("圓角", "倒角", "圓弧角", "rounded", "fillet", "chamfer")


# CMF single-colour keywords (EN + 中文) -> canonical name forwarded to the
# renderer's _resolve_cmf_color. Colour is a cosmetic render choice, NOT a
# dimension, so absence is fine (neutral grey) — we never ask for it (unlike
# DD-2 dimensions). Longer/more-specific keys are checked first so "深藍" beats "藍".
_CMF_COLOR_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("深藍", "navy"), ("navy", "navy"),
    ("白色", "white"), ("白", "white"), ("white", "white"),
    ("黑色", "black"), ("黑", "black"), ("black", "black"),
    ("銀色", "silver"), ("銀", "silver"), ("silver", "silver"),
    ("灰色", "grey"), ("灰", "grey"), ("grey", "grey"), ("gray", "grey"),
    ("紅色", "red"), ("紅", "red"), ("red", "red"),
    ("綠色", "green"), ("綠", "green"), ("green", "green"),
    ("藍色", "blue"), ("藍", "blue"), ("blue", "blue"),
    ("橘色", "orange"), ("橘", "orange"), ("橙", "orange"), ("orange", "orange"),
    ("黃色", "yellow"), ("黃", "yellow"), ("yellow", "yellow"),
)


def _extract_cmf_color(text: str, answers: dict[str, str]) -> str | None:
    """Extract a single CMF colour from spoken text or answers.

    Returns a hex string ("#RRGGBB[AA]") or a canonical colour name, or None when
    no colour is mentioned. Answers take precedence. A hex code anywhere in the
    text wins over a named colour. Unlike dimensions, a missing colour is NOT a
    clarifying question — the renderer simply keeps neutral grey.
    """
    ans = answers.get("cmf_color", "") if answers else ""
    if isinstance(ans, str) and ans.strip():
        return ans.strip()
    hex_match = _re.search(r"#([0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?)\b", text)
    if hex_match:
        return "#" + hex_match.group(1)
    lowered = text.lower()
    for keyword, canonical in _CMF_COLOR_KEYWORDS:
        # CJK keywords are matched against the raw text; ASCII against lowered.
        haystack = lowered if keyword.isascii() else text
        if keyword in haystack:
            return canonical
    return None


# C02 field bindings aligned 1:1 with assess_c02_constraint_readiness's 8 items.
# board_outline + component_heights block source (REQUIRED_FOR_CAD); the rest do not.
C02_FIELD_BINDINGS: tuple[C02FieldBinding, ...] = (
    C02FieldBinding(
        "board_outline", "Board outline (W×H mm)",
        ("板框", "板子", "盒子", "外殼", "box", "enclosure", "board", "outline", "尺寸", "size"),
        "板框尺寸是多少？（寬 × 高，mm，例如 50×30）", blocks_source=True, extractor=_extract_wxh,
    ),
    C02FieldBinding(
        "component_heights", "Component height envelope (mm)",
        ("元件高", "最高元件", "component height", "tallest", "高度"),
        "最高的元件大約多高？（mm，決定外殼內部淨高）", blocks_source=True, extractor=_extract_heights,
    ),
    C02FieldBinding(
        "mounting_holes", "Mounting holes",
        ("安裝孔", "螺絲孔", "鎖點", "mounting hole", "screw", "standoff"),
        "有哪些安裝孔/螺絲柱？（座標與孔徑）",
    ),
    C02FieldBinding(
        "connector_openings", "Connector openings",
        ("usb-c", "usb c", "type-c", "typec", "開孔", "接口", "連接器", "connector", "opening", "port", "插孔"),
        "外殼需要開哪些連接器孔？（類型、位置、尺寸）",
    ),
    C02FieldBinding(
        "heat_sources", "Heat sources",
        ("發熱", "散熱", "熱源", "heat", "thermal", "晶片功耗", "瓦"),
        "有發熱元件需要散熱考量嗎？（位置、功率）",
    ),
    C02FieldBinding(
        "antenna_keepouts", "Antenna keepouts",
        ("天線", "antenna", "rf", "ble", "wifi", "wi-fi", "射頻", "keepout"),
        "有天線/RF 區需要 keepout 嗎？（位置、範圍）",
    ),
    C02FieldBinding(
        "battery_envelope", "Battery envelope",
        ("電池", "鋰電", "battery", "li-ion", "lipo", "cell"),
        "有電池嗎？電池尺寸/容量為何？",
    ),
    C02FieldBinding(
        "environment_targets", "Environment targets",
        ("室內", "戶外", "防水", "防塵", "indoor", "outdoor", "ip40", "ip54", "ip67", "waterproof", "環境"),
        "使用環境是什麼？（室內/戶外、防水防塵等級）",
    ),
)

_GEN_PARAM_QUESTION = (
    "壁厚與間隙要設多少？（壁厚 wall / 間隙 clearance / 蓋間隙 lid_clearance，mm；系統不猜尺寸）"
)


def plan_c02_intent(spec_text: str, answers: dict[str, str] | None = None) -> dict[str, Any]:
    """Extract C02 enclosure constraints from spoken natural language (DD-1/DD-2).

    Three-state per field (mirrors plan_design_intent): a value present in
    `answers` -> "answered"; a keyword/extractor hit in spec_text -> "stated";
    neither -> "missing". Returns an IntentPlanResult dict (see data-schema.json):
    {status, draft (+field_status), gen_params, readiness_pct,
     can_generate_cad_source, next_question, missing}.

    Never guesses dimensions (DD-2): when board/heights or wall/clearance cannot be
    extracted, they surface as clarifying questions, not defaults. `answers` keys
    are constraint field keys (e.g. board_outline="50x30") or gen-param keys
    (wall_thickness_mm="2mm").
    """
    if not spec_text or not spec_text.strip():
        return {
            "status": "needs-clarification",
            "error": "C02_VTD_EMPTY_SPEC",
            "message": "請描述你要的產品結構（板尺寸、裝什麼、開哪些孔、什麼環境）。",
            "draft": {"field_status": {}},
            "gen_params": {},
            "readiness_pct": 0,
            "can_generate_cad_source": False,
            "next_question": None,
            "missing": [b.key for b in C02_FIELD_BINDINGS],
        }

    answers = {key: value for key, value in (answers or {}).items()}
    lowered = spec_text.lower()

    draft: dict[str, Any] = {}
    field_status: dict[str, str] = {}
    missing: list[str] = []
    open_questions: list[dict[str, Any]] = []

    for binding in C02_FIELD_BINDINGS:
        key = binding.key
        # answered: an explicit answer to a prior clarifying question. The answer's
        # field is already established by its key, so structured parsing here does
        # NOT require the in-text context keywords the spoken-text extractor needs.
        raw_answer = answers.get(key, "")
        if isinstance(raw_answer, str) and raw_answer.strip():
            value = _parse_answer_value(key, raw_answer, binding)
            if value:
                draft[key] = value
                field_status[key] = "answered"
                continue
        # stated: an extractor hit or a keyword hit in the spoken text
        extracted = binding.extractor(spec_text) if binding.extractor else None
        if extracted:
            draft[key] = extracted
            field_status[key] = "stated"
            continue
        # connector_openings: a keyword-only field, but we now try to extract real
        # cut geometry (face/width/height/z). When the geometry is complete the
        # opening becomes "stated" with a real, cuttable item; when the connector
        # is only mentioned (keyword hit, no geometry) we keep a marker AND ask a
        # geometry-detail follow-up — never guess the hole's face/size (DD-2).
        if key == "connector_openings":
            geo = _extract_connector_opening(spec_text)
            keyword_hit = any(kw in lowered for kw in binding.keywords)
            if geo:
                draft[key] = [geo]
                field_status[key] = "stated"
                continue
            if keyword_hit:
                draft[key] = [{"note": "mentioned in spoken intent; needs detail"}]
                field_status[key] = "stated"
                open_questions.append({
                    "key": key,
                    "label": binding.label,
                    "question": "連接器孔要切在哪一面？孔多大、離底多高？（面 east/west/north/south、寬×高 mm、離底高 z mm；系統不猜尺寸）",
                    "blocks_source": False,
                    "needs_geometry": True,
                })
                continue
        if any(kw in lowered for kw in binding.keywords) and not binding.extractor:
            # keyword-only field (no structured extractor): mark stated with a
            # lightweight non-empty marker so readiness sees it as present.
            draft[key] = [{"note": "mentioned in spoken intent; needs detail"}]
            field_status[key] = "stated"
            continue
        # missing
        field_status[key] = "missing"
        missing.append(key)
        open_questions.append({
            "key": key,
            "label": binding.label,
            "question": binding.question,
            "blocks_source": binding.blocks_source,
        })

    draft["field_status"] = field_status
    gen_params = _extract_gen_params(spec_text, answers)

    # CMF colour: cosmetic single-colour render choice (NOT a dimension). Absence
    # is fine — neutral grey — so we never raise a clarifying question for it.
    cmf_color = _extract_cmf_color(spec_text, answers)
    if cmf_color is not None:
        gen_params["cmf_color"] = cmf_color

    # Corner-radius ask (DD-2): if the user mentioned rounded/chamfered edges but
    # no radius number was extracted, ask for it instead of guessing. No rounding
    # keyword at all -> stay square (corner_radius_mm simply absent).
    wants_rounding = any(kw in lowered for kw in _CORNER_RADIUS_KEYWORDS)
    if wants_rounding and "corner_radius_mm" not in gen_params:
        open_questions.append({
            "key": "corner_radius_mm",
            "label": "Corner radius",
            "question": "圓角半徑要幾 mm？（corner_radius_mm，系統不猜尺寸）",
            "blocks_source": False,
            "needs_geometry": True,
        })

    readiness = assess_c02_constraint_readiness({k: v for k, v in draft.items() if k != "field_status"})
    can_generate = readiness.can_generate_cad_source

    # next_question priority: a blocks_source missing field first, then gen_params
    # (wall/clearance) if constraints are ready but dimensions are absent, then any
    # remaining missing field.
    next_question: dict[str, Any] | None = None
    blocking = [q for q in open_questions if q["blocks_source"]]
    if blocking:
        next_question = blocking[0]
    elif can_generate and not ("wall_thickness_mm" in gen_params and "clearance_mm" in gen_params):
        next_question = {
            "key": "gen_params", "label": "Wall/clearance dimensions",
            "question": _GEN_PARAM_QUESTION, "blocks_source": True,
        }
    elif open_questions:
        next_question = open_questions[0]

    # status:
    #  - needs-clarification: a blocking field or required gen_param is missing
    #  - ready-for-approval: constraints + wall/clearance present (lid may be 0)
    if blocking or (can_generate and not ("wall_thickness_mm" in gen_params and "clearance_mm" in gen_params)):
        status = "needs-clarification"
    elif can_generate:
        status = "ready-for-approval"
    else:
        status = "needs-clarification"

    return {
        "status": status,
        "draft": draft,
        "gen_params": gen_params,
        "readiness_pct": readiness.readiness_pct,
        "can_generate_cad_source": can_generate,
        "next_question": next_question,
        "missing": missing,
    }


def voice_to_design(
    out_dir: str | Path,
    spec_text: str,
    answers: dict[str, str] | None = None,
    approve: bool = False,
) -> dict[str, Any]:
    """Orchestrate spoken intent -> clarify -> approval gate -> source -> STL (DD-4).

    Pure-workflow portion (does NOT render — rendering is the eda-bridge layer's
    job and is wired in the MCP handler). Returns:
      - needs-clarification: the plan result (carries next_question), no CAD.
      - ready-for-approval (approve=False): the plan result + constraint set, no CAD.
      - approved (approve=True & ready): runs generate_c02_openscad + export_c02_stl,
        returns {status:"approved", pipeline:[...], plan, source, stl}.

    Never auto-generates without approve=True (DD-4); never guesses dimensions: a
    missing wall/clearance keeps status at needs-clarification (DD-2).
    """
    plan = plan_c02_intent(spec_text, answers)
    if plan["status"] != "ready-for-approval":
        return plan
    if not approve:
        return {**plan, "generated_source": False,
                "message": "約束齊備，請確認這組約束後帶 approve=true 重新呼叫以生成 CAD。"}

    draft = {k: v for k, v in plan["draft"].items() if k != "field_status"}
    gp = plan["gen_params"]
    source_result = generate_c02_openscad(
        out_dir, draft,
        wall_thickness_mm=gp.get("wall_thickness_mm"),
        clearance_mm=gp.get("clearance_mm"),
        lid_clearance_mm=gp.get("lid_clearance_mm", 0.0),
        corner_radius_mm=gp.get("corner_radius_mm"),
    )
    pipeline = [source_result.status]
    if source_result.status != "source_generated":
        return {"status": "blocked", "stage": "generate_openscad",
                "pipeline": pipeline, "plan": plan, "source": source_result.to_dict()}

    stl_result = export_c02_stl(out_dir)
    pipeline.append(stl_result.status)
    return {
        "status": "approved" if stl_result.status == "stl_exported" else "blocked",
        "stage": "export_stl" if stl_result.status != "stl_exported" else "stl_exported",
        "pipeline": pipeline,
        "plan": plan,
        "source": source_result.to_dict(),
        "stl": stl_result.to_dict(),
    }
