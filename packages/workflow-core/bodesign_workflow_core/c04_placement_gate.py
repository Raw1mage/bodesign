"""C04 placement review gate — placement-first, owner-approved before routing.

Owner contract (why this file exists):
    The pre-existing C04 chain went net2pcb → route → finish → DRC → emit_fab in
    one shot, so **placement was never delivered or reviewed on its own**. The board
    owner could only ever see a fully-routed board — the physical floorplan (how the
    module blocks are placed, at real physical scale) was never gated.

This module inserts an explicit **placement approval gate** between placement and
routing:

    net2pcb (placement) → [emit_c04_placement_review] → OWNER REVIEW
        → owner records PLACEMENT_APPROVED.json → [assess_c04_placement_approval]
        → routing may proceed

Honesty model (no-silent-fallback, consistent with the rest of C04):
- `emit_c04_placement_review` renders the placed board at true physical scale via
  `kicad-cli`. If kicad-cli is absent it FAILS FAST (status="kicad-cli-not-found"),
  it never fabricates a preview.
- `assess_c04_placement_approval` treats a missing / placeholder approval marker as
  BLOCKING and returns an explicit `blocking_reason`. It never auto-passes.
- **The AI agent must NOT write PLACEMENT_APPROVED.json itself.** That file records
  a HUMAN owner decision. When the owner approves (in-app or verbally), the agent may
  transcribe the decision into the marker, but the marker MUST name where the approval
  came from (`approved_by` + `scope_note`). A marker with placeholder/empty fields is
  rejected as not-approved.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .readiness_common import boundary_next_step, root_guard

# Marker file the owner (not the agent) authorises; lives next to the reviewed board.
PLACEMENT_APPROVED_MARKER = "PLACEMENT_APPROVED.json"
PLACEMENT_REVIEW_DOC = "PLACEMENT_REVIEW.md"
PLACEMENT_MANIFEST = "placement_manifest.json"

# Fields the approval marker MUST carry with real (non-placeholder) values.
_REQUIRED_APPROVAL_FIELDS = ("approved_by", "date", "board", "scope_note")
# Substrings that mark a field as an un-filled placeholder (case-insensitive).
_PLACEHOLDER_TOKENS = ("tbd", "tbc", "todo", "placeholder", "xxx", "<", "fill", "n/a", "none")

# Evidence that routing has already happened — used only to WARN when routing ran
# without a recorded placement approval (backward-compatible; existing boards do not
# hard-fail retroactively).
_ROUTED_GLOBS = ("*.ses", "gerbers", "*-F_Cu.gbr", "*routed*.kicad_pcb", "*final*.kicad_pcb")


@dataclass(slots=True)
class PlacementReviewResult:
    """Outcome of emitting a placement review package for one board."""

    board: str
    out_dir: str
    status: str  # "emitted" | "kicad-cli-not-found" | "board-not-found" | "render-failed"
    render_png: str | None = None
    render_svg: str | None = None
    manifest: str | None = None
    review_doc: str | None = None
    approved_marker: str | None = None  # path where the owner must place approval
    board_outline_mm: dict[str, float] | None = None
    component_count: int = 0
    layer_count: int | None = None
    next_step: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": self.board,
            "out_dir": self.out_dir,
            "status": self.status,
            "render_png": self.render_png,
            "render_svg": self.render_svg,
            "manifest": self.manifest,
            "review_doc": self.review_doc,
            "approved_marker": self.approved_marker,
            "board_outline_mm": self.board_outline_mm,
            "component_count": self.component_count,
            "layer_count": self.layer_count,
            "approved": False,  # emitting a review never means approved
            "next_step": self.next_step,
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class PlacementApprovalResult:
    """Outcome of the placement approval gate check for a folder."""

    folder: str
    approved: bool
    marker_present: bool
    marker_path: str
    blocking_reason: str | None = None
    approved_by: str | None = None
    approval_date: str | None = None
    board: str | None = None
    routed_evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    root_visible: bool = True
    next_step: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "approved": self.approved,
            "marker_present": self.marker_present,
            "marker_path": self.marker_path,
            "blocking_reason": self.blocking_reason,
            "approved_by": self.approved_by,
            "approval_date": self.approval_date,
            "board": self.board,
            "routed_evidence": list(self.routed_evidence),
            "root_visible": self.root_visible,
            "next_step": self.next_step,
            "warnings": list(self.warnings),
        }


def _is_placeholder(value: Any) -> bool:
    """A field counts as un-filled when it is empty or contains a placeholder token."""
    if value is None:
        return True
    if not isinstance(value, str):
        # Non-string truthy values (e.g. a structured approver record) are accepted.
        return not bool(value)
    text = value.strip()
    if not text:
        return True
    low = text.lower()
    return any(tok in low for tok in _PLACEHOLDER_TOKENS)


# --------------------------------------------------------------------------- #
# Board (.kicad_pcb) parsing — placement manifest extraction (no pcbnew dep)   #
# --------------------------------------------------------------------------- #

_FP_RE = re.compile(r'\(footprint\s+"([^"]+)"')
_AT_RE = re.compile(r'\(at\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?\)')
_REF_RE = re.compile(r'\(property\s+"Reference"\s+"([^"]+)"')
_EDGE_XY_RE = re.compile(r'\(gr_(?:line|rect)\b')


def _parse_placement(pcb_text: str) -> tuple[list[dict[str, Any]], dict[str, float] | None, int | None]:
    """Best-effort placement extraction from a .kicad_pcb S-expr WITHOUT pcbnew.

    Returns (components, board_outline_mm, layer_count). Each component:
      {ref, footprint, x_mm, y_mm, rotation_deg}.
    board_outline is the bounding box of Edge.Cuts graphics (min/max XY → w/h).
    This is a manifest for HUMAN review, not a routing input, so a bounding-box
    approximation of the outline is honest and sufficient.
    """
    components: list[dict[str, Any]] = []

    # Split into top-level (footprint ...) blocks by scanning parenthesis depth.
    idx = 0
    n = len(pcb_text)
    while True:
        m = _FP_RE.search(pcb_text, idx)
        if not m:
            break
        fp_id = m.group(1)
        # Capture the block body until parens balance.
        depth = 0
        start = m.start()
        j = start
        while j < n:
            c = pcb_text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = pcb_text[start:j]
        idx = j
        # Footprint origin: first (at x y [rot]) after the footprint header.
        at = _AT_RE.search(block)
        ref_m = _REF_RE.search(block)
        x = float(at.group(1)) if at else None
        y = float(at.group(2)) if at else None
        rot = float(at.group(3)) if (at and at.group(3)) else 0.0
        components.append({
            "ref": ref_m.group(1) if ref_m else "",
            "footprint": fp_id,
            "x_mm": x,
            "y_mm": y,
            "rotation_deg": rot,
        })

    # Board outline bounding box from Edge.Cuts coordinates.
    outline = _extract_edge_bbox(pcb_text)

    # Layer count from the (layers ...) stackup block.
    layer_count = _extract_layer_count(pcb_text)

    return components, outline, layer_count


def _extract_edge_bbox(pcb_text: str) -> dict[str, float] | None:
    """Bounding box (w/h in mm) of Edge.Cuts graphic segments."""
    xs: list[float] = []
    ys: list[float] = []
    for gm in re.finditer(
        r'\(gr_(?:line|rect|poly|arc)\b(.*?)\)\s*(?=\(gr_|\(footprint|\(zone|\Z)',
        pcb_text, re.S,
    ):
        seg = gm.group(1)
        if "Edge.Cuts" not in seg:
            continue
        for cm in re.finditer(r'\((?:start|end|xy|mid)\s+(-?[\d.]+)\s+(-?[\d.]+)\)', seg):
            xs.append(float(cm.group(1)))
            ys.append(float(cm.group(2)))
    if not xs or not ys:
        return None
    return {
        "min_x": min(xs), "min_y": min(ys),
        "max_x": max(xs), "max_y": max(ys),
        "width_mm": round(max(xs) - min(xs), 3),
        "height_mm": round(max(ys) - min(ys), 3),
    }


def _extract_layer_count(pcb_text: str) -> int | None:
    """Count copper layers declared in the (layers ...) block."""
    m = re.search(r'\(layers\s+(.*?)\n\s*\)', pcb_text, re.S)
    if not m:
        return None
    body = m.group(1)
    # Copper layers are named *.Cu (F.Cu, In1.Cu, ..., B.Cu).
    return len(re.findall(r'"[^"]*\.Cu"', body)) or None


# --------------------------------------------------------------------------- #
# Placement review package emitter                                            #
# --------------------------------------------------------------------------- #

def emit_c04_placement_review(
    board_pcb: str | Path,
    out_dir: str | Path,
    board_name: str,
) -> PlacementReviewResult:
    """Emit a placement review package from an already-placed .kicad_pcb.

    Produces, at true physical scale:
      - <board>_placement_top.png   (kicad-cli pcb render, top 3D)
      - <board>_placement.svg       (F.Cu,F.SilkS,F.Fab,Edge.Cuts — physical scale)
      - placement_manifest.json     (ref/footprint/x_mm/y_mm/rotation + outline + layers)
      - PLACEMENT_REVIEW.md          (owner-facing: board size, zones, approval contract)
      - PLACEMENT_APPROVED.json is NOT written here — the OWNER authorises it.

    Fail-fast: if kicad-cli is absent, returns status="kicad-cli-not-found" and does
    NOT fabricate any preview. If the board file is missing, status="board-not-found".
    """
    board_pcb = Path(board_pcb)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    approved_marker = str(out_dir / PLACEMENT_APPROVED_MARKER)

    if not board_pcb.exists():
        return PlacementReviewResult(
            board=board_name, out_dir=str(out_dir), status="board-not-found",
            approved_marker=approved_marker,
            next_step=f"Placed board not found: {board_pcb}. Run net2pcb/placement first.",
            warnings=[f"board_pcb does not exist: {board_pcb}"],
        )

    pcb_text = board_pcb.read_text(encoding="utf-8", errors="replace")
    components, outline, layer_count = _parse_placement(pcb_text)

    # Write the placement manifest (always — it is disk-of-truth for review).
    manifest = {
        "schema": "bodesign.c04.placement_manifest.v1",
        "board": board_name,
        "source_pcb": str(board_pcb),
        "board_outline_mm": outline,
        "layer_count": layer_count,
        "component_count": len(components),
        "components": sorted(components, key=lambda c: (c.get("ref") or "")),
    }
    manifest_path = out_dir / PLACEMENT_MANIFEST
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    cli = shutil.which("kicad-cli")
    if cli is None:
        # Fail-fast: no fabricated preview. Manifest is still written (honest partial).
        return PlacementReviewResult(
            board=board_name, out_dir=str(out_dir), status="kicad-cli-not-found",
            manifest=str(manifest_path), approved_marker=approved_marker,
            board_outline_mm=outline, component_count=len(components), layer_count=layer_count,
            next_step="Install kicad-cli (KiCad 9.x) to render the physical-scale placement preview.",
            warnings=["kicad-cli not found; placement manifest written but no render produced."],
        )

    warnings: list[str] = []
    png_path = out_dir / f"{board_name}_placement_top.png"
    svg_path = out_dir / f"{board_name}_placement.svg"

    render = subprocess.run(
        [cli, "pcb", "render", "--side", "top", "--width", "2000", "--height", "1500",
         "--background", "opaque", "-o", str(png_path), str(board_pcb)],
        capture_output=True, text=True,
    )
    if not png_path.exists():
        warnings.append(f"kicad-cli render failed: {(render.stderr or render.stdout or '').strip()[:200]}")

    svg = subprocess.run(
        [cli, "pcb", "export", "svg", str(board_pcb), "-o", str(svg_path),
         "--layers", "F.Cu,F.SilkS,F.Fab,Edge.Cuts",
         "--page-size-mode", "2", "--exclude-drawing-sheet"],
        capture_output=True, text=True,
    )
    if not svg_path.exists():
        warnings.append(f"kicad-cli svg export failed: {(svg.stderr or svg.stdout or '').strip()[:200]}")

    status = "emitted" if (png_path.exists() or svg_path.exists()) else "render-failed"

    review_doc = _write_review_doc(
        out_dir / PLACEMENT_REVIEW_DOC, board_name, outline, layer_count, components,
        png_path if png_path.exists() else None,
        svg_path if svg_path.exists() else None,
        approved_marker,
    )

    return PlacementReviewResult(
        board=board_name, out_dir=str(out_dir), status=status,
        render_png=str(png_path) if png_path.exists() else None,
        render_svg=str(svg_path) if svg_path.exists() else None,
        manifest=str(manifest_path), review_doc=str(review_doc),
        approved_marker=approved_marker, board_outline_mm=outline,
        component_count=len(components), layer_count=layer_count,
        next_step=(
            "Show the placement render to the OWNER. Routing must NOT start until the "
            f"owner authorises {PLACEMENT_APPROVED_MARKER} (approved_by + scope_note). "
            "The agent may transcribe the owner's decision but must not self-approve."
        ),
        warnings=warnings,
    )


def _write_review_doc(
    path: Path, board_name: str, outline: dict[str, float] | None,
    layer_count: int | None, components: list[dict[str, Any]],
    png: Path | None, svg: Path | None, approved_marker: str,
) -> Path:
    size = (
        f"{outline['width_mm']} × {outline['height_mm']} mm"
        if outline else "（Edge.Cuts 未解析到外框，見 manifest）"
    )
    lines = [
        f"# C04 Placement Review — {board_name}",
        "",
        "> **這是 C04 第一階段交付物：擺件（placement）核可書。**",
        "> 依 owner 契約，**銅層 routing 不得先於本擺件核可**。",
        "",
        "## 板資訊",
        "",
        f"- 板框尺寸（實體比例）：**{size}**",
        f"- 銅層數：**{layer_count if layer_count is not None else '未解析'}**",
        f"- 元件數：**{len(components)}**",
        "",
        "## 擺件預覽（真實實體比例）",
        "",
    ]
    if png:
        lines.append(f"- 3D 頂視：`{Path(png).name}`")
    if svg:
        lines.append(f"- F.Cu/絲印/Fab/外框 SVG：`{Path(svg).name}`")
    if not png and not svg:
        lines.append("- ⚠ 渲染未產出（見 warnings / manifest）。")
    lines += [
        "",
        "## 元件擺放清單（摘要）",
        "",
        "| Ref | Footprint | X (mm) | Y (mm) | Rot |",
        "|---|---|---|---|---|",
    ]
    for c in sorted(components, key=lambda c: (c.get("ref") or ""))[:60]:
        lines.append(
            f"| {c.get('ref','')} | {c.get('footprint','')} | "
            f"{c.get('x_mm','')} | {c.get('y_mm','')} | {c.get('rotation_deg',0)} |"
        )
    if len(components) > 60:
        lines.append(f"| … | 其餘 {len(components) - 60} 件見 `{PLACEMENT_MANIFEST}` | | | |")

    lines += [
        "",
        "## 核可契約（重要）",
        "",
        f"- 核可標記檔：`{Path(approved_marker).name}`（放在本目錄）。",
        "- **AI agent 不得自行寫此檔。** 這是 owner 的人為決策紀錄。",
        "- owner 核可（App 內或口頭）後，agent 可代為謄錄，但檔內必須註明核可出處：",
        "",
        "```json",
        "{",
        '  "approved_by": "<owner 姓名/身分>",',
        '  "date": "<YYYY-MM-DD>",',
        f'  "board": "{board_name}",',
        '  "scope_note": "<核可範圍與出處，例如：owner 於對話中口頭核可擺件，見 session xxx>"',
        "}",
        "```",
        "",
        f"- 缺此檔、或任一欄為佔位字（TBD/TODO/空白）時，`c04_placement_gate` 判定 **未核可**，routing 阻塞。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Placement approval gate                                                      #
# --------------------------------------------------------------------------- #

def _find_routed_evidence(root: Path) -> list[str]:
    found: list[str] = []
    for pat in _ROUTED_GLOBS:
        for p in root.rglob(pat):
            if p.exists():
                found.append(str(p.relative_to(root)))
    return sorted(set(found))


def assess_c04_placement_approval(folder: str | Path) -> PlacementApprovalResult:
    """Gate: is the placement of this board owner-approved (before routing)?

    Looks for PLACEMENT_APPROVED.json under `folder` (searched recursively so the
    marker may live next to the reviewed board). Approval requires the marker to
    exist AND every required field (approved_by/date/board/scope_note) to be present
    and non-placeholder.

    BLOCKING semantics (no-silent-fallback): a missing or placeholder marker returns
    approved=False with an explicit blocking_reason — callers must NOT route past it.

    IMPORTANT: this function never writes the marker. The marker records a HUMAN
    owner decision; the agent may only transcribe an approval the owner actually gave.
    """
    root, visible, warning = root_guard(folder)
    if not visible:
        return PlacementApprovalResult(
            folder=str(root), approved=False, marker_present=False,
            marker_path=str(root / PLACEMENT_APPROVED_MARKER),
            blocking_reason="path-not-visible",
            root_visible=False, next_step=boundary_next_step(folder),
            warnings=[warning] if warning else [],
        )

    routed = _find_routed_evidence(root)

    # Locate the marker (recursive; nearest to a reviewed board).
    markers = sorted(root.rglob(PLACEMENT_APPROVED_MARKER))
    marker_path = str(markers[0]) if markers else str(root / PLACEMENT_APPROVED_MARKER)

    if not markers:
        reason = (
            f"{PLACEMENT_APPROVED_MARKER} absent — placement has NOT been owner-approved. "
            "Emit the placement review (c04_placement_review), show it to the owner, and "
            "only after the owner approves may routing proceed."
        )
        warnings: list[str] = []
        if routed:
            warnings.append(
                "placement_not_approved_before_routing: routed artefacts exist but no "
                f"placement approval marker was found ({', '.join(routed[:5])})."
            )
        return PlacementApprovalResult(
            folder=str(root), approved=False, marker_present=False,
            marker_path=marker_path, blocking_reason=reason,
            routed_evidence=routed, warnings=warnings,
            next_step="Run c04_placement_review, then have the OWNER authorise "
                      f"{PLACEMENT_APPROVED_MARKER}.",
        )

    try:
        data = json.loads(Path(marker_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return PlacementApprovalResult(
            folder=str(root), approved=False, marker_present=True,
            marker_path=marker_path,
            blocking_reason=f"{PLACEMENT_APPROVED_MARKER} is present but unreadable: {exc}",
            routed_evidence=routed,
            next_step=f"Fix or re-author {PLACEMENT_APPROVED_MARKER} with valid JSON.",
        )

    missing = [f for f in _REQUIRED_APPROVAL_FIELDS if _is_placeholder(data.get(f))]
    if missing:
        return PlacementApprovalResult(
            folder=str(root), approved=False, marker_present=True,
            marker_path=marker_path,
            blocking_reason=(
                f"{PLACEMENT_APPROVED_MARKER} present but not a real approval — "
                f"missing/placeholder fields: {', '.join(missing)}. "
                "The owner must supply approved_by + scope_note (approval provenance)."
            ),
            approved_by=None if _is_placeholder(data.get("approved_by")) else str(data.get("approved_by")),
            approval_date=None if _is_placeholder(data.get("date")) else str(data.get("date")),
            board=None if _is_placeholder(data.get("board")) else str(data.get("board")),
            routed_evidence=routed,
            next_step="Have the OWNER complete the approval marker fields (no placeholders).",
        )

    return PlacementApprovalResult(
        folder=str(root), approved=True, marker_present=True,
        marker_path=marker_path, blocking_reason=None,
        approved_by=str(data.get("approved_by")),
        approval_date=str(data.get("date")),
        board=str(data.get("board")),
        routed_evidence=routed,
        next_step="Placement approved by owner — routing may proceed.",
    )
