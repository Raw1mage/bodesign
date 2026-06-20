"""C03/C04 board-level partition breakout diagram emitter.

Projects a board-level partition MODEL (boards + board-to-board pin classes)
into a layered, editable breakout concept SVG (and optional PNG/PPTX). Mirrors
the ``emit_c01_id_visual_package`` emitter: deterministic, layered SVG with
named groups, non-silent placeholders, honest-boundary footer, and toolchain-
gated raster/PPTX (never fabricated).

This module is pure-python and deterministic: the same MODEL yields a
byte-stable SVG (no RNG). Data and drawing are strictly separated — a
``PartitionModel`` dict feeds ``_draw_*`` pure helpers, assembled by the
``emit_c03_partition_diagram`` entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape


# ── Honest boundary (DD-5): always-on, not parameterisable ──────────────
HONEST_BOUNDARY_NOTES = (
    "design partition, not fab pinout",
    "no RefDes.Pin→net",
    "no DRC-SI claim",
)

LAYERS = ("boards", "modules", "interconnect", "legend", "annotations")

VALID_DIRS = {"bidir", "core-to-carrier", "carrier-to-core", "in", "out"}

# ── Module glyph style library (DD-6): uncovered types → named placeholder ─
# Maps a module `type` to a fill colour. Unknown types render as a generic
# placeholder box (dashed) and are reported in result.placeholders.
_MODULE_GLYPHS = {
    "soc": "#cfe8ff",
    "memory": "#d8f0d8",
    "power": "#ffe2c2",
    "connector": "#f4d6f0",
    "phy": "#fff3b0",
    "sensor": "#d6e4f0",
    "fpga": "#e0d6ff",
    "mcu": "#cfe8ff",
    "rf": "#ffd6d6",
}
_PLACEHOLDER_FILL = "#eeeeee"

# ── Deterministic layout constants (DD-9): no RNG ────────────────────────
_CANVAS_PAD = 40
_BOARD_GAP = 70
_BOARD_TITLE_H = 54
_MODULE_W = 150
_MODULE_H = 46
_MODULE_GAP = 16
_MODULE_PAD = 18
_LEGEND_H = 30
_FOOTER_H = 70


@dataclass(slots=True)
class PartitionModel:
    """The emitter's sole data input (data/drawing separation).

    boards: list of {name, role, tier?, modules:[{name, type, note?}]}
    interconnect: list of {class, dir, signals?, from_board?, to_board?}
    title: optional diagram title.
    """

    boards: list[dict[str, Any]]
    interconnect: list[dict[str, Any]]
    title: str = "Board Partition Breakout"

    @classmethod
    def from_dict(cls, model: dict[str, Any]) -> "PartitionModel":
        boards = model.get("boards")
        interconnect = model.get("interconnect")
        return cls(
            boards=boards if isinstance(boards, list) else [],
            interconnect=interconnect if isinstance(interconnect, list) else [],
            title=str(model.get("title") or "Board Partition Breakout"),
        )


@dataclass(slots=True)
class EmitPartitionResult:
    status: str  # "ok" | "missing"
    missing_fields: list[str] = field(default_factory=list)
    svg_path: str | None = None
    png_rendered: bool = False
    pptx_status: str = "not-requested"  # not-requested | ok | unavailable
    pptx_reason: str | None = None
    layers: list[str] = field(default_factory=list)
    boards_count: int = 0
    modules_count: int = 0
    interconnect_count: int = 0
    placeholders: list[str] = field(default_factory=list)
    boundary: list[str] = field(default_factory=list)
    files: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "status": self.status,
            "missing_fields": list(self.missing_fields),
        }
        if self.status != "ok":
            return out
        out.update(
            {
                "svg_path": self.svg_path,
                "png_rendered": self.png_rendered,
                "pptx_status": self.pptx_status,
                "layers": list(self.layers),
                "boards_count": self.boards_count,
                "modules_count": self.modules_count,
                "interconnect_count": self.interconnect_count,
                "placeholders": list(self.placeholders),
                "boundary": {"notes": list(self.boundary)},
                "files": [dict(f) for f in self.files],
                "warnings": list(self.warnings),
            }
        )
        if self.pptx_reason:
            out["pptx_reason"] = self.pptx_reason
        return out


# ── A1: validation (DD-8, E-PART-001/002) ───────────────────────────────


def _validate_model(model: PartitionModel) -> list[str]:
    """Return the list of missing required fields (empty = valid).

    Required: at least one board; each board.role; each interconnect.class
    and interconnect.dir (with dir in the allowed enum). Never substitutes
    defaults (no silent fallback)."""
    missing: list[str] = []
    if not model.boards:
        missing.append("boards")
    for i, board in enumerate(model.boards):
        if not isinstance(board, dict):
            missing.append(f"boards[{i}]")
            continue
        if not board.get("name"):
            missing.append(f"boards[{i}].name")
        if not board.get("role"):
            missing.append(f"boards[{i}].role")
    for i, ic in enumerate(model.interconnect):
        if not isinstance(ic, dict):
            missing.append(f"interconnect[{i}]")
            continue
        if not ic.get("class"):
            missing.append(f"interconnect[{i}].class")
        ic_dir = ic.get("dir")
        if not ic_dir:
            missing.append(f"interconnect[{i}].dir")
        elif ic_dir not in VALID_DIRS:
            missing.append(f"interconnect[{i}].dir(invalid:{ic_dir})")
    return missing


# ── A2: glyph resolution (DD-6) ─────────────────────────────────────────


@dataclass(slots=True)
class _PlacedModule:
    board: str
    name: str
    type: str
    is_placeholder: bool
    fill: str
    x: float
    y: float
    w: float
    h: float
    group_id: str


def _resolve_fill(module_type: str) -> tuple[str, bool]:
    """Map a module type to (fill, is_placeholder). Unknown → placeholder."""
    key = str(module_type or "").strip().lower()
    if key in _MODULE_GLYPHS:
        return _MODULE_GLYPHS[key], False
    return _PLACEHOLDER_FILL, True


# ── A3: deterministic layout (DD-9) ─────────────────────────────────────


@dataclass(slots=True)
class _Layout:
    width: float
    height: float
    board_boxes: list[dict[str, Any]]  # {name, role, tier, x, y, w, h}
    modules: list[_PlacedModule]
    board_centers: dict[str, float]  # board name → centre x


def _layout(model: PartitionModel) -> _Layout:
    """Deterministic horizontal board layout; modules stacked by declaration
    order inside each board outline. No RNG — board order = declaration order."""
    board_inner_w = _MODULE_W + 2 * _MODULE_PAD
    max_modules = max((len(b.get("modules") or []) for b in model.boards), default=0)
    board_body_h = max(
        max_modules * _MODULE_H + max(max_modules - 1, 0) * _MODULE_GAP + 2 * _MODULE_PAD,
        _MODULE_H + 2 * _MODULE_PAD,
    )
    board_h = _BOARD_TITLE_H + board_body_h
    board_boxes: list[dict[str, Any]] = []
    modules: list[_PlacedModule] = []
    board_centers: dict[str, float] = {}

    x = _CANVAS_PAD
    top = _CANVAS_PAD
    for board in model.boards:
        bname = str(board.get("name"))
        bx, by = x, top
        board_boxes.append(
            {
                "name": bname,
                "role": str(board.get("role") or ""),
                "tier": str(board.get("tier") or ""),
                "x": bx,
                "y": by,
                "w": board_inner_w,
                "h": board_h,
            }
        )
        board_centers[bname] = bx + board_inner_w / 2
        mods = board.get("modules") or []
        my = by + _BOARD_TITLE_H + _MODULE_PAD
        mx = bx + _MODULE_PAD
        for n, mod in enumerate(mods, start=1):
            fill, is_ph = _resolve_fill((mod or {}).get("type", ""))
            modules.append(
                _PlacedModule(
                    board=bname,
                    name=str((mod or {}).get("name") or f"module {n}"),
                    type=str((mod or {}).get("type") or ""),
                    is_placeholder=is_ph,
                    fill=fill,
                    x=mx,
                    y=my,
                    w=_MODULE_W,
                    h=_MODULE_H,
                    group_id=f"module-{bname}-{n}",
                )
            )
            my += _MODULE_H + _MODULE_GAP
        x += board_inner_w + _BOARD_GAP

    total_w = x - _BOARD_GAP + _CANVAS_PAD
    interconnect_band = 40 + len(model.interconnect) * 22
    total_h = top + board_h + interconnect_band + _LEGEND_H + _FOOTER_H + _CANVAS_PAD
    return _Layout(total_w, total_h, board_boxes, modules, board_centers)


# ── A4: drawing pure functions (DD-4: 5 layers, named groups) ───────────


def _draw_boards(lay: _Layout) -> str:
    parts = ['  <g id="layer-boards">']
    for b in lay.board_boxes:
        title = escape(f"{b['name']}")
        sub_bits = [p for p in (b["role"], b["tier"]) if p]
        sub = escape(" · ".join(sub_bits))
        parts.append(f'    <g id="board-{escape(b["name"])}">')
        parts.append(
            f'      <rect x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" '
            f'rx="8" fill="#ffffff" stroke="#333333" stroke-width="2"/>'
        )
        parts.append(
            f'      <text x="{b["x"] + b["w"] / 2}" y="{b["y"] + 24}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="18" '
            f'font-weight="bold" fill="#111111">{title}</text>'
        )
        parts.append(
            f'      <text x="{b["x"] + b["w"] / 2}" y="{b["y"] + 44}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="#555555">{sub}</text>'
        )
        parts.append("    </g>")
    parts.append("  </g>")
    return "\n".join(parts)


def _draw_modules(lay: _Layout) -> str:
    parts = ['  <g id="layer-modules">']
    for m in lay.modules:
        dash = ' stroke-dasharray="6 4"' if m.is_placeholder else ""
        label = escape(m.name)
        type_label = escape(m.type or "?")
        if m.is_placeholder:
            type_label = escape(f"{m.type or '?'} (placeholder)")
        parts.append(f'    <g id="{escape(m.group_id)}">')
        parts.append(
            f'      <rect x="{m.x}" y="{m.y}" width="{m.w}" height="{m.h}" rx="5" '
            f'fill="{m.fill}" stroke="#444444" stroke-width="1.5"{dash}/>'
        )
        parts.append(
            f'      <text x="{m.x + m.w / 2}" y="{m.y + m.h / 2 - 2}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="13" '
            f'font-weight="bold" fill="#111111">{label}</text>'
        )
        parts.append(
            f'      <text x="{m.x + m.w / 2}" y="{m.y + m.h / 2 + 14}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="10" '
            f'fill="#666666">{type_label}</text>'
        )
        parts.append("    </g>")
    parts.append("  </g>")
    return "\n".join(parts)


def _interconnect_endpoints(
    lay: _Layout, ic: dict[str, Any]
) -> tuple[float, float]:
    """Resolve (x_from, x_to) board centres for an interconnect.

    Uses explicit from_board/to_board when present (disambiguates >2 boards),
    otherwise falls back to the first two declared board centres by order."""
    centers = lay.board_centers
    order = [b["name"] for b in lay.board_boxes]
    fb = ic.get("from_board")
    tb = ic.get("to_board")
    x_from = centers.get(fb) if fb in centers else None
    x_to = centers.get(tb) if tb in centers else None
    if x_from is None:
        x_from = centers[order[0]]
    if x_to is None:
        x_to = centers[order[1]] if len(order) > 1 else centers[order[0]]
    return x_from, x_to


def _draw_interconnect(lay: _Layout, model: PartitionModel) -> str:
    band_y = (
        _CANVAS_PAD
        + max((b["y"] + b["h"] for b in lay.board_boxes), default=_CANVAS_PAD)
        - _CANVAS_PAD
        + 32
    )
    parts = ['  <g id="layer-interconnect">']
    parts.append(
        '    <defs><marker id="arrow" markerWidth="10" markerHeight="10" '
        'refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L8,3 L0,6 Z" fill="#1b5e9b"/></marker></defs>'
    )
    for n, ic in enumerate(model.interconnect):
        cls = str(ic.get("class"))
        ic_dir = str(ic.get("dir"))
        x_from, x_to = _interconnect_endpoints(lay, ic)
        y = band_y + n * 22
        signals = ic.get("signals") or []
        sig_text = f" [{', '.join(str(s) for s in signals)}]" if signals else ""
        label = escape(f"{cls} · {ic_dir}{sig_text}")
        # Direction → marker placement.
        if ic_dir in ("bidir",):
            marker = ' marker-start="url(#arrow)" marker-end="url(#arrow)"'
        elif ic_dir in ("carrier-to-core", "out"):
            # arrow points toward the from side
            marker = ' marker-start="url(#arrow)"'
        else:  # core-to-carrier, in
            marker = ' marker-end="url(#arrow)"'
        parts.append(f'    <g id="net-{escape(cls)}">')
        parts.append(
            f'      <line x1="{x_from}" y1="{y}" x2="{x_to}" y2="{y}" '
            f'stroke="#1b5e9b" stroke-width="2"{marker}/>'
        )
        parts.append(
            f'      <text x="{(x_from + x_to) / 2}" y="{y - 6}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="11" '
            f'fill="#1b5e9b">{label}</text>'
        )
        parts.append("    </g>")
    parts.append("  </g>")
    return "\n".join(parts)


def _draw_legend(lay: _Layout, model: PartitionModel) -> str:
    classes: list[str] = []
    for ic in model.interconnect:
        cls = str(ic.get("class"))
        if cls not in classes:
            classes.append(cls)
    y = lay.height - _FOOTER_H - _LEGEND_H
    parts = ['  <g id="layer-legend">']
    label = escape("pin classes: " + (", ".join(classes) if classes else "(none)"))
    parts.append(
        f'    <text x="{_CANVAS_PAD}" y="{y}" font-family="sans-serif" '
        f'font-size="12" fill="#333333">{label}</text>'
    )
    parts.append("  </g>")
    return "\n".join(parts)


_BOUNDARY_PREFIX = "\u26a0 "


def _draw_honest_boundary(lay: _Layout) -> str:
    y0 = lay.height - _FOOTER_H + 10
    parts = ['  <g id="layer-annotations">']
    for i, note in enumerate(HONEST_BOUNDARY_NOTES):
        text = escape(_BOUNDARY_PREFIX + note)
        parts.append(
            f'    <text x="{_CANVAS_PAD}" y="{y0 + i * 18}" '
            f'font-family="sans-serif" font-size="11" fill="#a33">'
            f'{text}</text>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def _render_svg(model: PartitionModel, lay: _Layout) -> str:
    title = escape(model.title)
    body = "\n".join(
        [
            _draw_boards(lay),
            _draw_modules(lay),
            _draw_interconnect(lay, model),
            _draw_legend(lay, model),
            _draw_honest_boundary(lay),
        ]
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{lay.width}" height="{lay.height}" '
        f'viewBox="0 0 {lay.width} {lay.height}">\n'
        f'  <rect x="0" y="0" width="{lay.width}" height="{lay.height}" fill="#fafafa"/>\n'
        f'  <text x="{_CANVAS_PAD}" y="26" font-family="sans-serif" '
        f'font-size="20" font-weight="bold" fill="#111111">{title}</text>\n'
        f"{body}\n"
        f"</svg>\n"
    )


# ── A6/A7: emitter entry point + toolchain gating (DD-7) ────────────────

PARTITION_SVG_REL = Path("C03-EE") / "partition" / "Partition_Breakout.svg"
PARTITION_PNG_REL = Path("C03-EE") / "partition" / "Partition_Breakout.png"
PARTITION_PPTX_REL = Path("C03-EE") / "partition" / "Partition_Breakout.pptx"


def emit_c03_partition_diagram(
    folder: str | Path,
    model: dict[str, Any] | PartitionModel,
    emit_pptx: bool = False,
    mcp_call: Callable[[str, str, dict[str, Any]], Any] | None = None,
) -> EmitPartitionResult:
    """Emit the C03 board-level partition breakout diagram.

    folder: output project root. The SVG lands under C03-EE/partition/.
    model: PartitionModel dict (or instance). Required fields fail fast.
    emit_pptx: when True, attempt an editable PPTX via the docxmcp bridge
        (`mcp_call(server, tool, arguments)` callable). Unreachable/missing →
        pptx_status="unavailable" (never fabricates a .pptx).
    mcp_call: optional MCP delegation callable injected by the server handler.

    Returns EmitPartitionResult.to_dict()-ready dataclass. Deterministic:
    same MODEL → byte-stable SVG (no RNG)."""
    pm = model if isinstance(model, PartitionModel) else PartitionModel.from_dict(model)

    missing = _validate_model(pm)
    if missing:
        return EmitPartitionResult(status="missing", missing_fields=missing)

    lay = _layout(pm)
    svg = _render_svg(pm, lay)

    root = Path(folder)
    svg_abs = root / PARTITION_SVG_REL
    svg_abs.parent.mkdir(parents=True, exist_ok=True)
    svg_abs.write_text(svg, encoding="utf-8")

    placeholders = [m.name for m in lay.modules if m.is_placeholder]
    warnings: list[str] = []
    for m in lay.modules:
        if m.is_placeholder:
            warnings.append(
                f"module '{m.name}' type '{m.type}' not in glyph library; "
                f"rendered as generic placeholder"
            )

    files: list[dict[str, str]] = [{"rel": str(PARTITION_SVG_REL), "kind": "svg"}]

    # A6: PNG raster — toolchain-gated (cairosvg). No phantom file on absence.
    png_rendered = False
    try:
        import cairosvg  # type: ignore

        png_abs = root / PARTITION_PNG_REL
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_abs))
        png_rendered = True
        files.append({"rel": str(PARTITION_PNG_REL), "kind": "png"})
    except Exception:
        warnings.append(
            "PNG raster unavailable (cairosvg absent); SVG delivered, PNG skipped"
        )

    # A7: optional editable PPTX via docxmcp bridge — graceful unavailable.
    pptx_status = "not-requested"
    pptx_reason: str | None = None
    if emit_pptx:
        pptx_status, pptx_reason, pptx_rel = _emit_pptx(root, pm, lay, mcp_call)
        if pptx_status == "ok" and pptx_rel:
            files.append({"rel": pptx_rel, "kind": "pptx"})
        elif pptx_reason:
            warnings.append(
                f"editable PPTX unavailable: {pptx_reason}; SVG/PNG delivered"
            )

    return EmitPartitionResult(
        status="ok",
        svg_path=str(PARTITION_SVG_REL),
        png_rendered=png_rendered,
        pptx_status=pptx_status,
        pptx_reason=pptx_reason,
        layers=list(LAYERS),
        boards_count=len(pm.boards),
        modules_count=len(lay.modules),
        interconnect_count=len(pm.interconnect),
        placeholders=placeholders,
        boundary=list(HONEST_BOUNDARY_NOTES),
        files=files,
        warnings=warnings,
    )


def _emit_pptx(
    root: Path,
    model: PartitionModel,
    lay: _Layout,
    mcp_call: Callable[[str, str, dict[str, Any]], Any] | None,
) -> tuple[str, str | None, str | None]:
    """Attempt an editable PPTX via the docxmcp MCP bridge.

    Returns (pptx_status, reason, pptx_rel). Never fabricates a .pptx: if no
    mcp_call callable is injected or the delegation does not yield a usable
    result, status is "unavailable" with a reason."""
    if mcp_call is None:
        return "unavailable", "docxmcp bridge not configured (no mcp_call)", None
    try:
        shapes = _pptx_shapes(model, lay)
        result = mcp_call(
            "docxmcp",
            "pptx_edit",
            {"shapes": shapes, "title": model.title},
        )
    except Exception as exc:  # delegation failure — honest unavailable.
        return "unavailable", f"docxmcp unreachable ({exc})", None
    if isinstance(result, dict) and result.get("status") in {
        "worker_unavailable",
        "worker_starting",
        "error",
    }:
        return "unavailable", f"docxmcp {result.get('status')}", None
    pptx_rel = str(PARTITION_PPTX_REL)
    return "ok", None, pptx_rel


def _pptx_shapes(model: PartitionModel, lay: _Layout) -> list[dict[str, Any]]:
    """Project the layout into docxmcp-style native shape ops (data only)."""
    shapes: list[dict[str, Any]] = []
    for b in lay.board_boxes:
        shapes.append(
            {
                "kind": "rect",
                "id": f"board-{b['name']}",
                "x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"],
                "text": f"{b['name']} ({b['role']})",
            }
        )
    for m in lay.modules:
        shapes.append(
            {
                "kind": "rect",
                "id": m.group_id,
                "x": m.x, "y": m.y, "w": m.w, "h": m.h,
                "text": m.name,
                "placeholder": m.is_placeholder,
            }
        )
    for note in HONEST_BOUNDARY_NOTES:
        shapes.append({"kind": "annotation", "text": note})
    return shapes
