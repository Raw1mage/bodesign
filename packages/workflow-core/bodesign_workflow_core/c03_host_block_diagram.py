"""C03 host/MCU-centric functional block diagram emitter.

Projects a host-centric MODEL (a center SoC/MCU + peripherals radiating to the
four sides) into a layered, editable functional block diagram SVG (and optional
PNG/PPTX). Sibling of ``emit_c03_partition_diagram``: deterministic, layered SVG
with named groups, non-silent placeholders, honest-boundary footer, and
toolchain-gated raster/PPTX (never fabricated).

This module is pure-python and deterministic: the same MODEL yields a
byte-stable SVG (no RNG). Data and drawing are strictly separated — a
``HostBlockModel`` dict feeds ``_draw_*`` pure helpers, assembled by the
``emit_c03_host_block_diagram`` entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape


# ── Honest boundary: always-on, not parameterisable ─────────────────────
HONEST_BOUNDARY_NOTES = (
    "functional block diagram, not a netlist",
    "no RefDes.Pin→net",
    "no DRC-SI claim",
)

LAYERS = ("center", "peripherals", "buses", "legend", "annotations")

VALID_SIDES = ("top", "bottom", "left", "right")

# ── Glyph style library: uncovered types → named placeholder ─────────────
# Maps a part `type` to a fill colour. Unknown types render as a generic
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
_CENTER_FILL = "#1b5e9b"  # solid blue center, white text
_PLACEHOLDER_FILL = "#eeeeee"

# ── Deterministic layout constants: no RNG ───────────────────────────────
_CANVAS_PAD = 40
_TITLE_H = 36
_CENTER_W = 200
_CENTER_H = 110
_PERIPH_W = 170
_PERIPH_H = 56
_PERIPH_GAP_V = 22   # vertical gap between stacked blocks (left/right columns)
_PERIPH_GAP_H = 28   # horizontal gap between stacked blocks (top/bottom rows)
_BUS_LEN = 90        # orthogonal bus length between center edge and peripheral
_LEGEND_H = 30
_FOOTER_H = 70


@dataclass(slots=True)
class HostBlockModel:
    """The emitter's sole data input (data/drawing separation).

    center_part: {name, mpn?, type?}
    peripherals: list of {name, side, mpn?, bus?, type?}
    reference_baseline: optional {name, diffs:[str], sourcing_gates:[str]}
    title: optional diagram title.
    """

    center_part: dict[str, Any]
    peripherals: list[dict[str, Any]]
    reference_baseline: dict[str, Any] | None = None
    title: str = "Host Block Diagram"

    @classmethod
    def from_dict(cls, model: dict[str, Any]) -> "HostBlockModel":
        center = model.get("center_part")
        peripherals = model.get("peripherals")
        ref = model.get("reference_baseline")
        return cls(
            center_part=center if isinstance(center, dict) else {},
            peripherals=peripherals if isinstance(peripherals, list) else [],
            reference_baseline=ref if isinstance(ref, dict) else None,
            title=str(model.get("title") or "Host Block Diagram"),
        )


@dataclass(slots=True)
class EmitHostBlockResult:
    status: str  # "ok" | "missing"
    missing_fields: list[str] = field(default_factory=list)
    svg_path: str | None = None
    png_rendered: bool = False
    pptx_status: str = "not-requested"  # not-requested | ok | unavailable
    pptx_reason: str | None = None
    layers: list[str] = field(default_factory=list)
    peripherals_count: int = 0
    placeholders: list[str] = field(default_factory=list)
    boundary: list[str] = field(default_factory=list)
    reference_baseline: dict[str, Any] | None = None
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
                "peripherals_count": self.peripherals_count,
                "placeholders": list(self.placeholders),
                "boundary": {"notes": list(self.boundary)},
                "files": [dict(f) for f in self.files],
                "warnings": list(self.warnings),
            }
        )
        if self.reference_baseline is not None:
            out["reference_baseline"] = dict(self.reference_baseline)
        if self.pptx_reason:
            out["pptx_reason"] = self.pptx_reason
        return out


# ── A1: validation (no silent fallback) ─────────────────────────────────


def _validate_model(model: HostBlockModel) -> list[str]:
    """Return the list of missing required fields (empty = valid).

    Required: center_part.name; at least one peripheral; each peripheral.name
    and peripheral.side (with side in the allowed enum). Never substitutes
    defaults (no silent fallback)."""
    missing: list[str] = []
    if not model.center_part.get("name"):
        missing.append("center_part.name")
    if not model.peripherals:
        missing.append("peripherals")
    for i, p in enumerate(model.peripherals):
        if not isinstance(p, dict):
            missing.append(f"peripherals[{i}]")
            continue
        if not p.get("name"):
            missing.append(f"peripherals[{i}].name")
        side = p.get("side")
        if not side:
            missing.append(f"peripherals[{i}].side")
        elif side not in VALID_SIDES:
            missing.append(f"peripherals[{i}].side(invalid:{side})")
    return missing


# ── A2: glyph resolution ─────────────────────────────────────────────────


def _resolve_fill(part_type: str) -> tuple[str, bool]:
    """Map a part type to (fill, is_placeholder). Unknown → placeholder."""
    key = str(part_type or "").strip().lower()
    if key in _MODULE_GLYPHS:
        return _MODULE_GLYPHS[key], False
    return _PLACEHOLDER_FILL, True


# ── A3: deterministic radial layout (no RNG) ─────────────────────────────


@dataclass(slots=True)
class _PlacedPeripheral:
    name: str
    side: str
    type: str
    bus: str
    is_placeholder: bool
    fill: str
    x: float
    y: float
    w: float
    h: float
    group_id: str
    bus_id: str
    # bus endpoints: from center edge (cx1,cy1) to peripheral edge (px2,py2)
    bx1: float
    by1: float
    bx2: float
    by2: float


@dataclass(slots=True)
class _Layout:
    width: float
    height: float
    center: dict[str, Any]  # {name, mpn, type, fill, is_placeholder, x, y, w, h}
    peripherals: list[_PlacedPeripheral]


def _group_by_side(
    peripherals: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group peripherals by side, preserving declaration order within a side.

    Deterministic: dict insertion order is VALID_SIDES order; per-side order is
    the order peripherals were declared in the MODEL."""
    grouped: dict[str, list[dict[str, Any]]] = {s: [] for s in VALID_SIDES}
    for p in peripherals:
        grouped[str(p.get("side"))].append(p)
    return grouped


def _layout(model: HostBlockModel) -> _Layout:
    """Deterministic radial layout. Center fixed in canvas middle; peripherals
    grouped by side, left/right stacked vertically, top/bottom stacked
    horizontally. No RNG — per-side order = declaration order."""
    grouped = _group_by_side(model.peripherals)
    n_left = len(grouped["left"])
    n_right = len(grouped["right"])
    n_top = len(grouped["top"])
    n_bottom = len(grouped["bottom"])

    # Vertical extent of a column of N peripheral boxes.
    def col_h(n: int) -> float:
        if n <= 0:
            return 0.0
        return n * _PERIPH_H + (n - 1) * _PERIPH_GAP_V

    # Horizontal extent of a row of N peripheral boxes.
    def row_w(n: int) -> float:
        if n <= 0:
            return 0.0
        return n * _PERIPH_W + (n - 1) * _PERIPH_GAP_H

    # Inner band height: the center row must clear the tallest side column.
    side_col_h = max(col_h(n_left), col_h(n_right), _CENTER_H)
    # Inner band width: the center plus left/right columns and their buses.
    left_band = (_PERIPH_W + _BUS_LEN) if n_left else 0.0
    right_band = (_PERIPH_W + _BUS_LEN) if n_right else 0.0
    # The top/bottom rows may be wider than the center+side bands.
    top_row_w = row_w(n_top)
    bottom_row_w = row_w(n_bottom)
    center_band_w = left_band + _CENTER_W + right_band
    inner_w = max(center_band_w, top_row_w, bottom_row_w)

    top_band = (_PERIPH_H + _BUS_LEN) if n_top else 0.0
    bottom_band = (_PERIPH_H + _BUS_LEN) if n_bottom else 0.0
    inner_h = top_band + side_col_h + bottom_band

    width = _CANVAS_PAD * 2 + inner_w
    height = (
        _CANVAS_PAD + _TITLE_H + inner_h + _LEGEND_H + _FOOTER_H + _CANVAS_PAD
    )

    # Center box centered horizontally; vertically centered in the side band.
    cx = (width - _CENTER_W) / 2
    band_top = _CANVAS_PAD + _TITLE_H + top_band
    cy = band_top + (side_col_h - _CENTER_H) / 2

    c_fill, c_ph = _resolve_fill(model.center_part.get("type") or "soc")
    center = {
        "name": str(model.center_part.get("name")),
        "mpn": str(model.center_part.get("mpn") or ""),
        "type": str(model.center_part.get("type") or ""),
        "fill": _CENTER_FILL,
        "is_placeholder": False,
        "x": cx,
        "y": cy,
        "w": _CENTER_W,
        "h": _CENTER_H,
    }
    center_mid_x = cx + _CENTER_W / 2
    center_mid_y = cy + _CENTER_H / 2

    placed: list[_PlacedPeripheral] = []

    # Left column: stacked vertically, right edge at (cx - _BUS_LEN).
    left_x = cx - _BUS_LEN - _PERIPH_W
    _place_column(
        placed, grouped["left"], "left", left_x, band_top, side_col_h,
        center_edge_x=cx, center_edge_dir=-1,
    )
    # Right column: stacked vertically, left edge at (cx + _CENTER_W + _BUS_LEN).
    right_x = cx + _CENTER_W + _BUS_LEN
    _place_column(
        placed, grouped["right"], "right", right_x, band_top, side_col_h,
        center_edge_x=cx + _CENTER_W, center_edge_dir=1,
    )
    # Top row: stacked horizontally, bottom edge at (band_top - _BUS_LEN).
    top_y = _CANVAS_PAD + _TITLE_H + (top_band - _PERIPH_H - _BUS_LEN) \
        if top_band else 0.0
    _place_row(
        placed, grouped["top"], "top", width, top_y,
        center_edge_y=cy, center_edge_dir=-1, center_mid_x=center_mid_x,
    )
    # Bottom row: stacked horizontally, top edge below the side band.
    bottom_y = band_top + side_col_h + _BUS_LEN
    _place_row(
        placed, grouped["bottom"], "bottom", width, bottom_y,
        center_edge_y=cy + _CENTER_H, center_edge_dir=1, center_mid_x=center_mid_x,
    )

    # Resolve bus endpoints toward the center for vertical (top/bottom) blocks
    # now that center geometry is known (left/right done in _place_column).
    for pp in placed:
        if pp.side in ("top", "bottom"):
            pp.bx1 = pp.x + pp.w / 2
            pp.bx2 = pp.x + pp.w / 2
            if pp.side == "top":
                pp.by1 = pp.y + pp.h
                pp.by2 = cy
            else:
                pp.by1 = pp.y
                pp.by2 = cy + _CENTER_H

    return _Layout(width, height, center, placed)


def _place_column(
    out: list[_PlacedPeripheral],
    items: list[dict[str, Any]],
    side: str,
    x: float,
    band_top: float,
    side_col_h: float,
    center_edge_x: float,
    center_edge_dir: int,
) -> None:
    """Place a vertical column of peripherals (left/right), centered in the
    side band. center_edge_dir: -1 left of center, +1 right of center."""
    n = len(items)
    if n == 0:
        return
    col_h = n * _PERIPH_H + (n - 1) * _PERIPH_GAP_V
    y = band_top + (side_col_h - col_h) / 2
    for idx, p in enumerate(items, start=1):
        fill, is_ph = _resolve_fill((p or {}).get("type", ""))
        name = str((p or {}).get("name") or f"peripheral {idx}")
        py = y
        # bus from center edge to peripheral edge (horizontal).
        if center_edge_dir < 0:  # left: peripheral right edge → center left edge
            bx1 = x + _PERIPH_W
            bx2 = center_edge_x
        else:  # right: peripheral left edge → center right edge
            bx1 = x
            bx2 = center_edge_x
        by = py + _PERIPH_H / 2
        out.append(
            _PlacedPeripheral(
                name=name,
                side=side,
                type=str((p or {}).get("type") or ""),
                bus=str((p or {}).get("bus") or ""),
                is_placeholder=is_ph,
                fill=fill,
                x=x,
                y=py,
                w=_PERIPH_W,
                h=_PERIPH_H,
                group_id=f"peripheral-{name}",
                bus_id=f"bus-{name}",
                bx1=bx1,
                by1=by,
                bx2=bx2,
                by2=by,
            )
        )
        y += _PERIPH_H + _PERIPH_GAP_V


def _place_row(
    out: list[_PlacedPeripheral],
    items: list[dict[str, Any]],
    side: str,
    canvas_w: float,
    y: float,
    center_edge_y: float,
    center_edge_dir: int,
    center_mid_x: float,
) -> None:
    """Place a horizontal row of peripherals (top/bottom), centered
    horizontally on the canvas. Bus endpoints (vertical) resolved by caller."""
    n = len(items)
    if n == 0:
        return
    row_w = n * _PERIPH_W + (n - 1) * _PERIPH_GAP_H
    x = (canvas_w - row_w) / 2
    for idx, p in enumerate(items, start=1):
        fill, is_ph = _resolve_fill((p or {}).get("type", ""))
        name = str((p or {}).get("name") or f"peripheral {idx}")
        out.append(
            _PlacedPeripheral(
                name=name,
                side=side,
                type=str((p or {}).get("type") or ""),
                bus=str((p or {}).get("bus") or ""),
                is_placeholder=is_ph,
                fill=fill,
                x=x,
                y=y,
                w=_PERIPH_W,
                h=_PERIPH_H,
                group_id=f"peripheral-{name}",
                bus_id=f"bus-{name}",
                bx1=0.0,
                by1=0.0,
                bx2=0.0,
                by2=0.0,
            )
        )
        x += _PERIPH_W + _PERIPH_GAP_H


# ── A4: drawing pure functions (5 layers, named groups) ─────────────────


def _draw_center(lay: _Layout) -> str:
    c = lay.center
    title = escape(str(c["name"]))
    sub = escape(str(c["mpn"]))
    parts = ['  <g id="layer-center">']
    parts.append(f'    <g id="center-{escape(str(c["name"]))}">')
    parts.append(
        f'      <rect x="{c["x"]}" y="{c["y"]}" width="{c["w"]}" height="{c["h"]}" '
        f'rx="10" fill="{c["fill"]}" stroke="#0d3a63" stroke-width="2.5"/>'
    )
    parts.append(
        f'      <text x="{c["x"] + c["w"] / 2}" y="{c["y"] + c["h"] / 2 - 4}" '
        f'text-anchor="middle" font-family="sans-serif" font-size="18" '
        f'font-weight="bold" fill="#ffffff">{title}</text>'
    )
    if sub:
        parts.append(
            f'      <text x="{c["x"] + c["w"] / 2}" y="{c["y"] + c["h"] / 2 + 18}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="#dce8f5">{sub}</text>'
        )
    parts.append("    </g>")
    parts.append("  </g>")
    return "\n".join(parts)


def _draw_peripherals(lay: _Layout) -> str:
    parts = ['  <g id="layer-peripherals">']
    for p in lay.peripherals:
        dash = ' stroke-dasharray="6 4"' if p.is_placeholder else ""
        label = escape(p.name)
        type_label = escape(p.type or "?")
        if p.is_placeholder:
            type_label = escape(f"{p.type or '?'} (placeholder)")
        parts.append(f'    <g id="{escape(p.group_id)}">')
        parts.append(
            f'      <rect x="{p.x}" y="{p.y}" width="{p.w}" height="{p.h}" rx="6" '
            f'fill="{p.fill}" stroke="#1b5e9b" stroke-width="1.5"{dash}/>'
        )
        parts.append(
            f'      <text x="{p.x + p.w / 2}" y="{p.y + p.h / 2 - 2}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="13" '
            f'font-weight="bold" fill="#111111">{label}</text>'
        )
        parts.append(
            f'      <text x="{p.x + p.w / 2}" y="{p.y + p.h / 2 + 14}" '
            f'text-anchor="middle" font-family="sans-serif" font-size="10" '
            f'fill="#666666">{type_label}</text>'
        )
        parts.append("    </g>")
    parts.append("  </g>")
    return "\n".join(parts)


def _draw_buses(lay: _Layout) -> str:
    parts = ['  <g id="layer-buses">']
    for p in lay.peripherals:
        bus_label = escape(p.bus) if p.bus else ""
        parts.append(f'    <g id="{escape(p.bus_id)}">')
        parts.append(
            f'      <line x1="{p.bx1}" y1="{p.by1}" x2="{p.bx2}" y2="{p.by2}" '
            f'stroke="#1b5e9b" stroke-width="2"/>'
        )
        if bus_label:
            mid_x = (p.bx1 + p.bx2) / 2
            mid_y = (p.by1 + p.by2) / 2
            parts.append(
                f'      <text x="{mid_x}" y="{mid_y - 4}" '
                f'text-anchor="middle" font-family="sans-serif" font-size="10" '
                f'fill="#1b5e9b">{bus_label}</text>'
            )
        parts.append("    </g>")
    parts.append("  </g>")
    return "\n".join(parts)


def _draw_legend(lay: _Layout) -> str:
    buses: list[str] = []
    for p in lay.peripherals:
        if p.bus and p.bus not in buses:
            buses.append(p.bus)
    y = lay.height - _FOOTER_H - _LEGEND_H
    parts = ['  <g id="layer-legend">']
    label = escape("buses: " + (", ".join(buses) if buses else "(none)"))
    parts.append(
        f'    <text x="{_CANVAS_PAD}" y="{y}" font-family="sans-serif" '
        f'font-size="12" fill="#333333">{label}</text>'
    )
    parts.append("  </g>")
    return "\n".join(parts)


_BOUNDARY_PREFIX = "\u26a0 "
_DERIVED_PREFIX = "\u2295 "  # circled plus


def _draw_annotations(lay: _Layout, model: HostBlockModel) -> str:
    """Annotations layer: optional reference-baseline diff block (when present)
    followed by the always-on honest-boundary footer."""
    parts = ['  <g id="layer-annotations">']

    # Optional reference-baseline block (above the footer). Absent → not drawn.
    ref = model.reference_baseline
    y = lay.height - _FOOTER_H - _LEGEND_H - 16
    if ref and ref.get("name"):
        # Render bottom-up: gates, diffs, then the "derived from" header on top.
        lines: list[tuple[str, str]] = []
        lines.append(("header", f"derived from {ref['name']}"))
        for d in ref.get("diffs") or []:
            lines.append(("diff", str(d)))
        for g in ref.get("sourcing_gates") or []:
            lines.append(("gate", str(g)))
        # Stack upward from y; topmost line is the header.
        n = len(lines)
        y0 = y - (n - 1) * 14
        for i, (kind, txt) in enumerate(lines):
            ly = y0 + i * 14
            if kind == "header":
                text = escape(_DERIVED_PREFIX + txt)
                colour = "#1b5e9b"
                weight = ' font-weight="bold"'
            elif kind == "gate":
                text = escape("gate: " + txt)
                colour = "#a36b00"
                weight = ""
            else:
                text = escape("• " + txt)
                colour = "#555555"
                weight = ""
            parts.append(
                f'    <text x="{lay.width / 2}" y="{ly}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="11"{weight} '
                f'fill="{colour}">{text}</text>'
            )

    # Always-on honest-boundary footer.
    y0 = lay.height - _FOOTER_H + 10
    for i, note in enumerate(HONEST_BOUNDARY_NOTES):
        text = escape(_BOUNDARY_PREFIX + note)
        parts.append(
            f'    <text x="{_CANVAS_PAD}" y="{y0 + i * 18}" '
            f'font-family="sans-serif" font-size="11" fill="#a33">'
            f'{text}</text>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def _render_svg(model: HostBlockModel, lay: _Layout) -> str:
    title = escape(model.title)
    body = "\n".join(
        [
            _draw_buses(lay),
            _draw_center(lay),
            _draw_peripherals(lay),
            _draw_legend(lay),
            _draw_annotations(lay, model),
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


# ── A6/A7: emitter entry point + toolchain gating ───────────────────────

HOSTBLOCK_SVG_REL = Path("C03-EE") / "block" / "Host_Block_Diagram.svg"
HOSTBLOCK_PNG_REL = Path("C03-EE") / "block" / "Host_Block_Diagram.png"
HOSTBLOCK_PPTX_REL = Path("C03-EE") / "block" / "Host_Block_Diagram.pptx"


def emit_c03_host_block_diagram(
    folder: str | Path,
    model: dict[str, Any] | HostBlockModel,
    emit_pptx: bool = False,
    mcp_call: Callable[[str, str, dict[str, Any]], Any] | None = None,
) -> EmitHostBlockResult:
    """Emit the C03 host/MCU-centric functional block diagram.

    folder: output project root. The SVG lands under C03-EE/block/.
    model: HostBlockModel dict (or instance). Required fields fail fast.
    emit_pptx: when True, attempt an editable PPTX via the docxmcp bridge
        (`mcp_call(server, tool, arguments)` callable). Unreachable/missing →
        pptx_status="unavailable" (never fabricates a .pptx).
    mcp_call: optional MCP delegation callable injected by the server handler.

    Returns EmitHostBlockResult.to_dict()-ready dataclass. Deterministic:
    same MODEL → byte-stable SVG (no RNG)."""
    hm = model if isinstance(model, HostBlockModel) else HostBlockModel.from_dict(model)

    missing = _validate_model(hm)
    if missing:
        return EmitHostBlockResult(status="missing", missing_fields=missing)

    lay = _layout(hm)
    svg = _render_svg(hm, lay)

    root = Path(folder)
    svg_abs = root / HOSTBLOCK_SVG_REL
    svg_abs.parent.mkdir(parents=True, exist_ok=True)
    svg_abs.write_text(svg, encoding="utf-8")

    placeholders = [p.name for p in lay.peripherals if p.is_placeholder]
    warnings: list[str] = []
    for p in lay.peripherals:
        if p.is_placeholder:
            warnings.append(
                f"peripheral '{p.name}' type '{p.type}' not in glyph library; "
                f"rendered as generic placeholder"
            )

    files: list[dict[str, str]] = [{"rel": str(HOSTBLOCK_SVG_REL), "kind": "svg"}]

    # PNG raster — toolchain-gated (cairosvg). No phantom file on absence.
    png_rendered = False
    try:
        import cairosvg  # type: ignore

        png_abs = root / HOSTBLOCK_PNG_REL
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_abs))
        png_rendered = True
        files.append({"rel": str(HOSTBLOCK_PNG_REL), "kind": "png"})
    except Exception:
        warnings.append(
            "PNG raster unavailable (cairosvg absent); SVG delivered, PNG skipped"
        )

    # Optional editable PPTX via docxmcp bridge — graceful unavailable.
    pptx_status = "not-requested"
    pptx_reason: str | None = None
    if emit_pptx:
        pptx_status, pptx_reason, pptx_rel = _emit_pptx(root, hm, lay, mcp_call)
        if pptx_status == "ok" and pptx_rel:
            files.append({"rel": pptx_rel, "kind": "pptx"})
        elif pptx_reason:
            warnings.append(
                f"editable PPTX unavailable: {pptx_reason}; SVG/PNG delivered"
            )

    ref_echo: dict[str, Any] | None = None
    if hm.reference_baseline and hm.reference_baseline.get("name"):
        ref_echo = {
            "name": str(hm.reference_baseline["name"]),
            "diffs_count": len(hm.reference_baseline.get("diffs") or []),
            "sourcing_gates_count": len(
                hm.reference_baseline.get("sourcing_gates") or []
            ),
        }

    return EmitHostBlockResult(
        status="ok",
        svg_path=str(HOSTBLOCK_SVG_REL),
        png_rendered=png_rendered,
        pptx_status=pptx_status,
        pptx_reason=pptx_reason,
        layers=list(LAYERS),
        peripherals_count=len(lay.peripherals),
        placeholders=placeholders,
        boundary=list(HONEST_BOUNDARY_NOTES),
        reference_baseline=ref_echo,
        files=files,
        warnings=warnings,
    )


def _emit_pptx(
    root: Path,
    model: HostBlockModel,
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
    pptx_rel = str(HOSTBLOCK_PPTX_REL)
    return "ok", None, pptx_rel


def _pptx_shapes(model: HostBlockModel, lay: _Layout) -> list[dict[str, Any]]:
    """Project the layout into docxmcp-style native shape ops (data only)."""
    shapes: list[dict[str, Any]] = []
    c = lay.center
    shapes.append(
        {
            "kind": "rect",
            "id": f"center-{c['name']}",
            "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"],
            "text": f"{c['name']} ({c['mpn']})" if c["mpn"] else str(c["name"]),
        }
    )
    for p in lay.peripherals:
        shapes.append(
            {
                "kind": "rect",
                "id": p.group_id,
                "x": p.x, "y": p.y, "w": p.w, "h": p.h,
                "text": p.name,
                "placeholder": p.is_placeholder,
            }
        )
    ref = model.reference_baseline
    if ref and ref.get("name"):
        shapes.append({"kind": "annotation", "text": f"derived from {ref['name']}"})
        for d in ref.get("diffs") or []:
            shapes.append({"kind": "annotation", "text": str(d)})
        for g in ref.get("sourcing_gates") or []:
            shapes.append({"kind": "annotation", "text": f"gate: {g}"})
    for note in HONEST_BOUNDARY_NOTES:
        shapes.append({"kind": "annotation", "text": note})
    return shapes
