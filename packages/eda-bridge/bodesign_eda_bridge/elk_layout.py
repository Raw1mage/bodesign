"""ELK layered presentation engine bridge (DD-15, governed by DD-9 clearance).

Scope: the ENGINE path of the multi-sheet emitter. Given the seam's declared
topology (components + nets), the final rendered symbol geometry (pin tips,
body extents, after the same scale stacking `emit_kicad_schematic` applies) and
the page, this module

  1. builds an ELK JSON graph: one node per symbol with FIXED_POS ports at the
     exact pin tips, one edge per (root pin -> other pin) of every drawn net;
  2. runs ONE bounded Node child (`packages/eda-bridge/elk/runner.cjs`,
     elkjs 0.12.0 pinned by lock integrity, no web-worker);
  3. quantizes the solution onto the KiCad 1.27 mm grid;
  4. VERIFIES it: every route endpoint is a pin tip of its own net, junction
     semantics are explicit (dot iff >= 3 incident branches, same net), and the
     drawn connectivity reproduces the declared nets exactly (0 fused / 0
     missing / 0 misrouted) under KiCad's wire-contact semantics.

Anything the engine cannot do is a typed refusal (`ElkLayoutError` with a
code and a named gap). There is NO fallback to the legacy router: DD-13 forbids
it, and a fallback would hide engine failure instead of raising it.

Coordinates: sheet mm, KiCad y-down. ELK is unit-less, so mm are passed
through unchanged; node (x, y) is the node's TOP-LEFT in ELK, pin tips are
converted from symbol-local (y-up) to node-local (y-down) when building ports.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .kicad_emit import (
    EmitComponent,
    EmitNet,
    ORIENTATIONS,
    _graphics_bbox,
    _label_bbox,
    _prop_text_box,
    _PROP_TEXT_CW_MM,
    _r3_enabled,
    _native_pitch_and_count,
    _page_pitch_floor,
    _snap_grid,
    _vendor_sym_scale,
    load_symbol,
    orient_pins,
    orient_rect,
    _LABEL_CW_MM,
    _LABEL_GLYPH_MM,
    _LABEL_HMARGIN_MM,
    _LABEL_CH_MM,
    _LABEL_VMARGIN_MM,
)

GRID_MM = 1.27
ELK_DIR = Path(__file__).resolve().parents[1] / "elk"
RUNNER = ELK_DIR / "runner.cjs"
ELKJS_PINNED_VERSION = "0.12.0"
DEFAULT_TIMEOUT_S = 60.0
#: Page margin the engine candidate is placed against (== hierarchical._PAGE_MARGIN_MM,
#: 20 grid units) so `fit_page` finds the candidate already in place and does not
#: translate a validated solution.
PAGE_ORIGIN_MM = 25.4
EPS = 1e-6

#: Layout options handed to ELK. Spacings are >= 2 grid units so that grid
#: quantization (max displacement 0.635 mm per coordinate) can never make two
#: distinct parallel routes collinear.
DEFAULT_LAYOUT_OPTIONS: dict[str, str] = {
    "elk.algorithm": "layered",
    "elk.direction": "RIGHT",
    "elk.edgeRouting": "ORTHOGONAL",
    "elk.layered.mergeEdges": "true",
    # Every spacing and the root padding is a grid multiple and the node
    # placer is BRANDES_KOEPF: measured on the usbc graph, that combination
    # returns every node origin and every edge point ON the 1.27 mm grid, so
    # quantization is an identity check. NETWORK_SIMPLEX balances y to
    # non-grid values (J1 landed at 30.7 grid units) and each node then snapped
    # by a different delta, which is what tore hyperedge junctions apart.
    "elk.padding": "[top=12.7,left=12.7,bottom=12.7,right=12.7]",
    # Compaction is by spacing only (never geometric scaling). Text ink is
    # reserved per node through `elk.margins` (see `plan_node_ink`), so these
    # spacings no longer stand in for text clearance.
    "elk.spacing.nodeNode": "5.08",
    "elk.layered.spacing.nodeNodeBetweenLayers": "10.16",
    "elk.spacing.edgeEdge": "2.54",
    "elk.layered.spacing.edgeEdgeBetweenLayers": "2.54",
    "elk.spacing.edgeNode": "2.54",
    "elk.layered.spacing.edgeNodeBetweenLayers": "3.81",
    "elk.spacing.portPort": "2.54",
    "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
    "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
    "elk.layered.thoroughness": "10",
    "elk.hierarchyHandling": "INCLUDE_CHILDREN",
}

#: Round 5: the only ELK options a caller may override as a spacing setting.
SPACING_OPTION_KEYS: tuple[str, ...] = (
    "elk.spacing.nodeNode", "elk.layered.spacing.nodeNodeBetweenLayers",
    "elk.spacing.edgeEdge", "elk.layered.spacing.edgeEdgeBetweenLayers",
    "elk.spacing.edgeNode", "elk.layered.spacing.edgeNodeBetweenLayers",
    "elk.spacing.portPort")

#: Clearance (mm) an ink box must keep from foreign ink / wires. A strict
#: overlap test with this inflation; KiCad text has no hard edge.
INK_CLEAR_MM = 0.25

#: Bounded ELK option variants tried per sheet (ruling: bounded attempt, no
#: endless sweep). Each is a delta over DEFAULT_LAYOUT_OPTIONS plus an edge-root
#: policy ("first" = first node of the net is the edge source, "last" = last).
LAYOUT_VARIANTS: tuple[dict, ...] = (
    {"name": "default", "root": "first", "options": {}},
    {"name": "no-merge", "root": "first",
     "options": {"elk.layered.mergeEdges": "false"}},
    {"name": "root-last", "root": "last", "options": {}},
    {"name": "model-order", "root": "first",
     "options": {"elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES"}},
    {"name": "model-order-root-last", "root": "last",
     "options": {"elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES"}},
    {"name": "linear-segments", "root": "first",
     "options": {"elk.layered.nodePlacement.strategy": "LINEAR_SEGMENTS"}},
    {"name": "longest-path", "root": "first",
     "options": {"elk.layered.layering.strategy": "LONGEST_PATH"}},
    {"name": "no-merge-root-last", "root": "last",
     "options": {"elk.layered.mergeEdges": "false"}},
    # Ordering-constraint variants: node/edge model order follows the anchor's pin order.
    {"name": "rank-default", "root": "first", "order": "anchor-rank", "options": {}},
    {"name": "rank-model-order", "root": "first", "order": "anchor-rank",
     "options": {"elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES"}},
    {"name": "rank-force-order", "root": "first", "order": "anchor-rank",
     "options": {"elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
                 "elk.layered.crossingMinimization.forceNodeModelOrder": "true"}},
    {"name": "rank-linear", "root": "first", "order": "anchor-rank",
     "options": {"elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
                 "elk.layered.nodePlacement.strategy": "LINEAR_SEGMENTS"}},
)


class ElkLayoutError(ValueError):
    """Typed refusal. `code` is machine-readable; `details` names the gap."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


Point = tuple[float, float]
Segment = tuple[Point, Point]


# --------------------------------------------------------------------------- geometry


@dataclass(slots=True)
class SymbolGeometry:
    """Final RENDERED geometry of one placed symbol (symbol-local, KiCad y-up).

    `pins`: pin number -> (x, y, rotation) at the SAME scale `emit_kicad_schematic`
    will embed, so a port position computed here is exactly where the emitter
    will put the pin tip. `bbox`: union of drawn graphics (body + pin stubs
    included via `pins` below)."""
    ref: str
    lib_id: str
    scale: float
    pins: dict[str, tuple[float, float, float]]
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 symbol-local y-up
    #: native orientation id (kicad_emit.ORIENTATIONS) already applied to pins/bbox
    orientation: str = "R0"
    #: union bbox of the drawn graphics ONLY (pins excluded), symbol-local y-up,
    #: orientation applied; None when the symbol draws no graphic (round 5)
    gfx: tuple[float, float, float, float] | None = None


def resolve_symbol_geometry(components: list[EmitComponent], symbol_dir,
                            page_scale: float = 1.0,
                            orientations: dict[str, str] | None = None
                            ) -> dict[str, SymbolGeometry]:
    """Resolve each component's final drawn geometry with the SAME scale stacking
    as `emit_kicad_schematic` (`_page_pitch_floor` + `_vendor_sym_scale`), so
    later scaling cannot move a port. Missing symbol => refusal (no guess).

    `orientations` (ref -> id in `kicad_emit.ORIENTATIONS`): the SAME native
    transform the emitter serializes as `(at x y rot) (mirror ..)`. Pin tips,
    pin angles and the hull are mapped by the emitter's own functions, so the
    port the engine fixes is the tip the emitter and KiCad place. Unknown ref,
    unknown id, or one library symbol placed with two orientations => refusal."""
    orientations = dict(orientations or {})
    refs = {c.ref for c in components}
    bad = sorted(set(orientations) - refs)
    if bad:
        raise ElkLayoutError("E_ELK_ORIENT_UNRESOLVED",
                             f"orientation declared for refs not on this sheet: {bad}", refs=bad)
    unknown = sorted({o for o in orientations.values() if o not in ORIENTATIONS})
    if unknown:
        raise ElkLayoutError("E_ELK_ORIENT_UNKNOWN",
                             f"unknown orientation id(s) {unknown}; supported "
                             f"{sorted(ORIENTATIONS)}", ids=unknown)
    for ref, o in orientations.items():
        lib = next(c.lib_id for c in components if c.ref == ref)
        clash = [c.ref for c in components if c.lib_id == lib and c.ref != ref
                 and orientations.get(c.ref, "R0") != o]
        if clash:
            raise ElkLayoutError(
                "E_ELK_ORIENT_SHARED_LIB",
                f"{ref} and {clash} share library symbol {lib} with different "
                f"orientations; the emitter's pin map is per library symbol", refs=[ref] + clash)
    page_floor = _page_pitch_floor(components, symbol_dir)
    cache: dict[str, tuple[float, int]] = {}
    out: dict[str, SymbolGeometry] = {}
    missing: list[str] = []
    for c in components:
        is_u1 = c.lib_id.partition(":")[0].startswith("u1_")
        if is_u1:
            scale = 1.0
        else:
            npitch, ncount = _native_pitch_and_count(c.lib_id, symbol_dir, cache)
            scale = _vendor_sym_scale(page_scale, npitch, page_floor, ncount)
        try:
            definition, pins = load_symbol(c.lib_id, symbol_dir, page_scale=scale)
        except (FileNotFoundError, KeyError) as error:
            missing.append(f"{c.ref} ({c.lib_id}): {error}")
            continue
        if not pins:
            missing.append(f"{c.ref} ({c.lib_id}): symbol has no pins")
            continue
        orient = orientations.get(c.ref, "R0")
        if orient != "R0":
            pins = orient_pins(orient, pins)
        gb = _graphics_bbox(definition)
        if gb is not None and orient != "R0":
            gb = orient_rect(orient, gb)
        xs = [p[0] for p in pins.values()]
        ys = [p[1] for p in pins.values()]
        if gb is None:
            bbox = (min(xs), min(ys), max(xs), max(ys))
        else:
            bbox = (min(gb[0], *xs), min(gb[1], *ys), max(gb[2], *xs), max(gb[3], *ys))
        out[c.ref] = SymbolGeometry(ref=c.ref, lib_id=c.lib_id, scale=scale,
                                    pins={k: (float(v[0]), float(v[1]),
                                              float(v[2]) if len(v) > 2 else 0.0)
                                          for k, v in pins.items()},
                                    bbox=bbox, orientation=orient,
                                    gfx=(tuple(float(v) for v in gb) if gb is not None else None))
    if missing:
        raise ElkLayoutError(
            "E_ELK_SYMBOL_UNRESOLVED",
            "engine layout needs the final geometry of every symbol; these could not "
            "be resolved and are not guessed",
            missing=missing)
    return out


def _grid_up(v: float) -> float:
    """Smallest grid multiple >= v."""
    import math
    return round(math.ceil(v / GRID_MM - EPS) * GRID_MM, 4)


def _node_box(g: SymbolGeometry) -> tuple[float, float, float, float]:
    """Node-local box (ELK y-down) enclosing graphics + pin tips + text margin,
    with the node origin chosen so every pin tip is a grid multiple away from it.
    Returns (width, height, ox, oy) where (ox, oy) is the symbol origin inside
    the node (node-local, y-down)."""
    x0, y0, x1, y1 = g.bbox
    # symbol-local y-up -> node-local y-down: y_node = -y_sym. The node box is the
    # HULL of pin tips + graphics so that every pin tip sits ON the node border
    # (ELK routes orthogonally out of border ports; a port inside the box yields
    # a diagonal lead-in, measured on the usbc trial). Text clearance is passed
    # to ELK as `elk.margins`, not folded into the box.
    ox = _grid_up(-x0)
    oy = _grid_up(y1)
    width = _grid_up(ox + x1)
    height = _grid_up(oy - y0)
    return width, height, ox, oy


def _port_side(rot: float) -> str:
    """KiCad pin rotation -> ELK side the wire LEAVES from (see kicad_emit._pin_edge)."""
    r = int(round(rot)) % 360
    return {0: "WEST", 180: "EAST", 90: "SOUTH", 270: "NORTH"}.get(r, "EAST")


# --------------------------------------------------------------------------- ink model
#
# "Ink" = everything the native render draws that is not a wire: the symbol
# hull (graphics + pin tips), Reference/Value text, net-label text and the
# global-flag glyph+text of every label-continued pin. The boxes use the SAME
# text model the emitter uses (`_prop_text_box`, `_label_bbox`), so what the
# engine reserves is what the emitter draws. Boxes are (x0, y0, x1, y1), sheet
# orientation (y down). Node-relative boxes are relative to the symbol origin.

Box = tuple[float, float, float, float]
EXIT_LEN_MM = 2.54
EXIT_HALF_W_MM = 0.635
DOT_HALF_MM = 0.4


def _rect(b) -> Box:
    """`_label_bbox` / `_prop_text_box` return (x0, x1, y0, y1)."""
    return (b[0], b[2], b[1], b[3])


def _shift(b: Box, dx: float, dy: float) -> Box:
    return (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)


def _inflate(b: Box, m: float) -> Box:
    return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)


def _boxes_overlap(a: Box, b: Box, inflate: float = 0.0) -> bool:
    """Strict overlap of `a` inflated by `inflate` with `b` (touching is no overlap)."""
    a = _inflate(a, inflate)
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _seg_hits_box(a: Point, b: Point, box: Box, inflate: float = 0.0) -> bool:
    x0, y0, x1, y1 = _inflate(box, inflate)
    sx0, sx1 = sorted((a[0], b[0]))
    sy0, sy1 = sorted((a[1], b[1]))
    return not (sx1 <= x0 or x1 <= sx0 or sy1 <= y0 or y1 <= sy0)


def _pin_out_vec(rot: float) -> tuple[float, float]:
    """Outward direction of a pin (sheet y-down); same table as the emitter's `_pin_edge`."""
    r = int(round(rot)) % 360
    return {0: (-1.0, 0.0), 180: (1.0, 0.0), 90: (0.0, 1.0), 270: (0.0, -1.0)}.get(r, (1.0, 0.0))


@dataclass(slots=True)
class PropChoice:
    name: str
    ref_at: Point
    val_at: Point
    ref_box: Box
    val_box: Box | None


@dataclass(slots=True)
class NodeInk:
    ref: str
    hull: Box
    #: (net, pin, box) of the flag the emitter draws at each label-continued pin
    flags: list[tuple[str, str, Box]]
    #: wire-exit corridors of the remaining pins (a short strip outward of the tip)
    exits: list[Box]
    candidates: list[PropChoice]
    natural: int
    #: ELK margins (top, left, bottom, right), grid multiples
    margins: tuple[float, float, float, float]
    #: round 5: non-electrical package outline box (symbol-relative, y-down) or None
    outline: Box | None = None


def _prop_candidates(c: EmitComponent, hull: Box, page_scale: float) -> list[PropChoice]:
    hx0, hy0, hx1, hy1 = hull
    mid = (hy0 + hy1) / 2
    ref, val = c.ref, c.value or ""
    rw = (_prop_text_box(ref, 0.0, 0.0, page_scale)[1])
    vw = (_prop_text_box(val, 0.0, 0.0, page_scale)[1]) if val else 0.0
    out: list[PropChoice] = []

    def mk(name: str, rx: float, ry: float, vx: float, vy: float) -> None:
        rb = _rect(_prop_text_box(ref, rx, ry, page_scale))
        vb = _rect(_prop_text_box(val, vx, vy, page_scale)) if val else None
        out.append(PropChoice(name, (round(rx, 4), round(ry, 4)),
                              (round(vx, 4), round(vy, 4)), rb, vb))

    x = hx1 + 1.27
    mk("right", x, mid - 1.27, x, mid + 1.27)
    vy = hy0 - 1.905
    mk("above", hx0, vy - 2.54, hx0, vy)
    ry = hy1 + 1.905
    mk("below", hx0, ry, hx0, ry + 2.54)
    xl = hx0 - 1.27
    mk("left", xl - rw, mid - 1.27, xl - vw, mid + 1.27)
    x = hx1 + 6.35
    mk("far-right", x, mid - 1.27, x, mid + 1.27)
    vy = hy0 - 4.445
    mk("far-above", hx0, vy - 2.54, hx0, vy)
    ry = hy1 + 4.445
    mk("far-below", hx0, ry, hx0, ry + 2.54)
    return out


#: Round 5: clearance (mm) between the drawn graphics and the package outline.
OUTLINE_MARGIN_MM = 0.254


def _flagged_pin_outward_box(name: str, tx: float, ty: float,
                             ux: float, uy: float, page_scale: float) -> Box:
    flag_len = len(name) * (_LABEL_CW_MM * page_scale) + (_LABEL_GLYPH_MM * page_scale) + _LABEL_HMARGIN_MM
    reach = math.ceil((GRID_MM + flag_len) / GRID_MM) * GRID_MM
    h = _LABEL_CH_MM * page_scale + _LABEL_VMARGIN_MM
    if abs(ux) >= abs(uy):
        if ux >= 0:
            return (round(tx, 4), round(ty - h / 2, 4), round(tx + reach, 4), round(ty + h / 2, 4))
        return (round(tx - reach, 4), round(ty - h / 2, 4), round(tx, 4), round(ty + h / 2, 4))
    if uy >= 0:
        return (round(tx - h / 2, 4), round(ty, 4), round(tx + h / 2, 4), round(ty + reach, 4))
    return (round(tx - h / 2, 4), round(ty - reach, 4), round(tx + h / 2, 4), round(ty, 4))


def plan_node_ink(c: EmitComponent, g: SymbolGeometry, flag_pins: dict[str, str],
                  node_box: tuple[float, float, float, float], page_scale: float,
                  outline: bool = False) -> NodeInk:
    """Reserve one node's ACTUAL ink. `flag_pins`: pin -> net name for every pin
    whose net is label-continued (the emitter draws a flag there). `node_box` =
    (width, height, ox, oy) from `_node_box`."""
    x0, y0, x1, y1 = g.bbox
    hull: Box = (x0, -y1, x1, -y0)
    outline_box: Box | None = None
    if outline:
        if g.gfx is None:
            raise ElkLayoutError(
                "E_ELK_OUTLINE_NO_GRAPHICS",
                f"{c.ref}: a package outline was requested but the symbol draws no "
                f"graphic to enclose; refused rather than inventing a box", ref=c.ref)
        gx0, gy0, gx1, gy1 = g.gfx
        m = OUTLINE_MARGIN_MM
        outline_box = (round(gx0 - m, 4), round(-gy1 - m, 4), round(gx1 + m, 4), round(-gy0 + m, 4))
        hull = (min(hull[0], outline_box[0]), min(hull[1], outline_box[1]),
                max(hull[2], outline_box[2]), max(hull[3], outline_box[3]))
    flags: list[tuple[str, str, Box]] = []
    exits: list[Box] = []
    for pin, (px, py, rot) in sorted(g.pins.items()):
        tx, ty = px, -py
        ux, uy = _pin_out_vec(rot)
        if pin in flag_pins:
            name = flag_pins[pin]
            if _r3_enabled("C"):
                box = _flagged_pin_outward_box(name, tx, ty, ux, uy, page_scale)
            else:
                box = _rect(_label_bbox(name, tx, ty, True, (ux, uy), page_scale))
            flags.append((name, pin, box))
        elif abs(ux) > 0:
            ex = tx + ux * EXIT_LEN_MM
            exits.append((min(tx, ex), ty - EXIT_HALF_W_MM, max(tx, ex), ty + EXIT_HALF_W_MM))
        else:
            ey = ty + uy * EXIT_LEN_MM
            exits.append((tx - EXIT_HALF_W_MM, min(ty, ey), tx + EXIT_HALF_W_MM, max(ty, ey)))
    cands = _prop_candidates(c, hull, page_scale)
    natural = None
    for i, cand in enumerate(cands):
        boxes = [cand.ref_box] + ([cand.val_box] if cand.val_box else [])
        if any(_boxes_overlap(b, hull, INK_CLEAR_MM) for b in boxes):
            continue
        if any(_boxes_overlap(b, f[2], INK_CLEAR_MM) for b in boxes for f in flags):
            continue
        if any(_boxes_overlap(b, e) for b in boxes for e in exits):
            continue
        natural = i
        break
    if natural is None:
        raise ElkLayoutError(
            "E_ELK_PROP_NO_POSITION",
            f"{c.ref}: no Reference/Value text position clears the symbol hull, its "
            f"label flags and its pin corridors; refused rather than overlapping ink",
            ref=c.ref)
    width, height, ox, oy = node_box
    nb: Box = (-ox, -oy, width - ox, height - oy)
    chosen = cands[natural]
    # Hard gate (Round 3 ruling D): Reference/Value box ∩ expanded hull (INK_CLEAR_MM) must be empty
    if _r3_enabled("D"):
        _chosen_boxes = [chosen.ref_box] + ([chosen.val_box] if chosen.val_box else [])
        assert not any(_boxes_overlap(b, hull, INK_CLEAR_MM) for b in _chosen_boxes), \
            f"{c.ref}: chosen prop box intersects symbol hull inflated by INK_CLEAR_MM"
    ink_boxes = [f[2] for f in flags] + [chosen.ref_box] + ([chosen.val_box] if chosen.val_box else [])
    if outline_box is not None:
        ink_boxes.append(outline_box)
    left = max([0.0] + [nb[0] - b[0] for b in ink_boxes])
    top = max([0.0] + [nb[1] - b[1] for b in ink_boxes])
    right = max([0.0] + [b[2] - nb[2] for b in ink_boxes])
    bottom = max([0.0] + [b[3] - nb[3] for b in ink_boxes])
    margins = tuple(_grid_up(v) if v > EPS else 0.0 for v in (top, left, bottom, right))
    return NodeInk(ref=c.ref, hull=hull, flags=flags, exits=exits, candidates=cands,
                   natural=natural, margins=margins,  # type: ignore[arg-type]
                   outline=outline_box)



# --------------------------------------------------------------------------- graph build


@dataclass(slots=True)
class ElkGraphBuild:
    graph: dict
    #: port id -> (ref, pin)
    ports: dict[str, tuple[str, str]]
    #: edge id -> net name
    edge_nets: dict[str, str]
    #: ref -> (ox, oy) symbol origin inside its node (node-local y-down)
    origins: dict[str, tuple[float, float]]
    #: nets handed to the engine (drawn), in declaration order
    drawn_nets: list[str]
    #: nets NOT drawn (label/power continuation), with the stated reason
    undrawn: dict[str, str]
    #: (ref, pin) -> net for every node of every net on this sheet (declared)
    declared_pin_nets: dict[tuple[str, str], str]
    #: ref -> reserved ink plan (hull, flag boxes, prop candidates, margins)
    inks: dict[str, "NodeInk"] = field(default_factory=dict)
    #: ref -> node width/height (mm), for diagnostics
    node_sizes: dict[str, tuple[float, float]] = field(default_factory=dict)
    #: net -> pins of that net on this sheet (declaration order), for flag anchoring
    net_pins: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    #: variant that produced this graph
    variant: str = "default"
    #: (ref, pin) -> pin rotation (KiCad), for outward direction of flags
    pin_rot: dict[tuple[str, str], float] = field(default_factory=dict)


def _anchor_rank_order(components, nets, geometry):
    """Deterministic MODEL ORDER: the anchor is the symbol with the most pins;
    every other node (and net) is ranked by the top-to-bottom position, on the
    anchor, of the lowest-placed anchor pin of the nets it touches. This feeds
    ELK's model-order strategy so layer order follows the anchor's pin order
    (an ordering constraint, not geometry). Ties keep declaration order."""
    anchor = max(components, key=lambda c: len(geometry[c.ref].pins))
    g = geometry[anchor.ref]
    pin_rank: dict[str, int] = {}
    for i, (pin, (_x, y, _r)) in enumerate(sorted(g.pins.items(), key=lambda kv: (-kv[1][1], kv[0]))):
        pin_rank[pin] = i
    net_rank: dict[str, int] = {}
    for n in nets:
        rs = [pin_rank[p] for r, p in n.nodes if r == anchor.ref and p in pin_rank]
        net_rank[n.name] = min(rs) if rs else 10 ** 6
    comp_rank: dict[str, int] = {anchor.ref: -1}
    for n in nets:
        for r, _p in n.nodes:
            comp_rank[r] = min(comp_rank.get(r, 10 ** 6), net_rank[n.name])
    comps = sorted(components, key=lambda c: (comp_rank.get(c.ref, 10 ** 6),))
    nts = sorted(nets, key=lambda n: (net_rank[n.name],))
    return comps, nts


def build_elk_graph(components: list[EmitComponent], nets: list[EmitNet],
                    geometry: dict[str, SymbolGeometry], *,
                    drawn_filter=None,
                    layout_options: dict[str, str] | None = None,
                    root: str = "first", page_scale: float = 1.0,
                    variant: str = "default", order: str = "declared",
                    partitions: dict[str, int] | None = None,
                    outline_refs: frozenset[str] | set[str] | None = None,
                    cross_sheet_nets: set[str] | frozenset | None = None) -> ElkGraphBuild:
    """One ELK node per component with FIXED_POS ports at the pin tips; one edge
    per (first node -> other node) of every drawn net. `drawn_filter(net) ->
    (bool, reason)` decides which nets the engine routes; the rest are reported
    in `undrawn` and are the caller's label/power business.

    Pin tips of ONE node that share a coordinate (stock library convention:
    PESD5V0L4UF pins 2 and 5 both at (2.54, 0)) share ONE port, because two ports
    at one point would be two ELK endpoints at one wire end.

    Hierarchy (motifs as compound nodes) is NOT built here: the usbc leaf carries
    no motif geometry. A caller passing `motif_geometries` is refused by the
    adapter so the gap is named rather than silently flattened."""
    if order == "anchor-rank":
        components, nets = _anchor_rank_order(components, nets, geometry)
    ports: dict[str, tuple[str, str]] = {}
    port_of_node: dict[tuple[str, str], str] = {}
    origins: dict[str, tuple[float, float]] = {}
    children: list[dict] = []
    for c in components:
        g = geometry.get(c.ref)
        if g is None:
            raise ElkLayoutError("E_ELK_SYMBOL_UNRESOLVED",
                                 f"{c.ref} has no resolved geometry", ref=c.ref)
        width, height, ox, oy = _node_box(g)
        origins[c.ref] = (ox, oy)
        node_ports: list[dict] = []
        seen_pt: dict[tuple[float, float], str] = {}
        for pin, (px, py, rot) in sorted(g.pins.items()):
            # symbol-local y-up -> node-local y-down
            nx, ny = round(ox + px, 4), round(oy - py, 4)
            key = (nx, ny)
            if key in seen_pt:
                port_of_node[(c.ref, pin)] = seen_pt[key]
                continue
            pid = f"{c.ref}.{pin}"
            seen_pt[key] = pid
            ports[pid] = (c.ref, pin)
            port_of_node[(c.ref, pin)] = pid
            node_ports.append({
                "id": pid, "x": nx, "y": ny, "width": 0.0, "height": 0.0,
                "properties": {"elk.port.side": _port_side(rot)},
            })
        children.append({
            "id": c.ref, "width": width, "height": height,
            "properties": {"elk.portConstraints": "FIXED_POS"},
            "ports": node_ports,
        })

    edges: list[dict] = []
    edge_nets: dict[str, str] = {}
    drawn: list[str] = []
    undrawn: dict[str, str] = {}
    declared_pin_nets: dict[tuple[str, str], str] = {}
    for net in nets:
        for ref, pin in net.nodes:
            declared_pin_nets[(ref, pin)] = net.name
        if drawn_filter is not None:
            ok, reason = drawn_filter(net)
            if not ok:
                undrawn[net.name] = reason
                continue
        pids: list[str] = []
        for ref, pin in net.nodes:
            pid = port_of_node.get((ref, pin))
            if pid is None:
                raise ElkLayoutError(
                    "E_ELK_PIN_UNRESOLVED",
                    f"net {net.name!r} names {ref}.{pin}, which is not a pin of a "
                    f"placed symbol on this sheet", net=net.name, node=f"{ref}.{pin}")
            if pid not in pids:
                pids.append(pid)
        if len(pids) < 2:
            undrawn[net.name] = "single resolvable endpoint on this sheet"
            continue
        drawn.append(net.name)
        ordered = pids if root == "first" else list(reversed(pids))
        src = ordered[0]
        for i, pid in enumerate(ordered[1:]):
            eid = f"e:{net.name}:{i}"
            edge_nets[eid] = net.name
            edges.append({"id": eid, "sources": [src], "targets": [pid]})

    graph = {
        "id": "sheet",
        "layoutOptions": dict(layout_options or DEFAULT_LAYOUT_OPTIONS),
        "children": children,
        "edges": edges,
    }
    if partitions:
        # Round 4 placement constraint (ELK partitioning): a node with a lower
        # partition id is placed in an earlier layer. Requested layers only; no
        # coordinate is written, and unconstrained nodes carry no partition.
        unknown = sorted(set(partitions) - {c.ref for c in components})
        if unknown:
            raise ElkLayoutError("E_ELK_PARTITION_UNRESOLVED",
                                 f"partition declared for refs not on this sheet: {unknown}",
                                 refs=unknown)
        graph["layoutOptions"]["elk.partitioning.activate"] = "true"
        for child in children:
            if child["id"] in partitions:
                child["properties"]["elk.partitioning.partition"] = str(int(partitions[child["id"]]))
    # Reserve each node's ACTUAL ink (symbol hull, flags of label-continued pins,
    # Reference/Value text) as ELK node margins, replacing the old fixed margin.
    flag_pins_of: dict[str, dict[str, str]] = {}
    comps_on_sheet = {c.ref for c in components}
    for net in nets:
        if net.name in drawn:
            if _r3_enabled("C") and cross_sheet_nets and net.name in cross_sheet_nets:
                for ref, pin in net.nodes:
                    if ref in comps_on_sheet:
                        flag_pins_of.setdefault(ref, {})[pin] = net.name
                        break
            continue
        for ref, pin in net.nodes:
            flag_pins_of.setdefault(ref, {})[pin] = net.name
    inks: dict[str, NodeInk] = {}
    sizes: dict[str, tuple[float, float]] = {}
    for c, child in zip(components, children):
        g = geometry[c.ref]
        box = _node_box(g)
        ink = plan_node_ink(c, g, flag_pins_of.get(c.ref, {}), box, page_scale,
                            outline=c.ref in (outline_refs or ()))
        inks[c.ref] = ink
        sizes[c.ref] = (box[0], box[1])
        # ELK layered IGNORES an input `elk.margins` (measured: node positions are
        # identical with margins absent or 20 mm). OUTSIDE node labels ARE honoured
        # (measured: the same graph re-spaces), so each reserved ink side is
        # carried by one empty label of exactly that extent. No text is drawn.
        t, l, b, r = ink.margins
        child["properties"]["elk.spacing.labelNode"] = "0"
        placement = {"top": "[H_CENTER, V_TOP, OUTSIDE]",
                     "bottom": "[H_CENTER, V_BOTTOM, OUTSIDE]",
                     "left": "[H_LEFT, V_CENTER, OUTSIDE]",
                     "right": "[H_RIGHT, V_CENTER, OUTSIDE]"}
        labels = []
        for side, v in (("top", t), ("bottom", b), ("left", l), ("right", r)):
            if v > 0:
                horiz = side in ("top", "bottom")
                labels.append({
                    "id": f"{c.ref}.ink.{side}", "text": ".",
                    "width": box[0] if horiz else v, "height": v if horiz else box[1],
                    "layoutOptions": {"elk.nodeLabels.placement": placement[side]}})
        child["labels"] = labels
    net_pins = {net.name: [(r, p) for r, p in net.nodes] for net in nets}
    pin_rot = {(c.ref, pin): rot for c in components
               for pin, (_x, _y, rot) in geometry[c.ref].pins.items()}
    return ElkGraphBuild(graph=graph, ports=ports, edge_nets=edge_nets, origins=origins,
                         drawn_nets=drawn, undrawn=undrawn,
                         declared_pin_nets=declared_pin_nets, inks=inks,
                         node_sizes=sizes, net_pins=net_pins, variant=variant,
                         pin_rot=pin_rot)


# --------------------------------------------------------------------------- runner


def _node_binary() -> str:
    """`BODESIGN_NODE_BIN` or `node` on PATH. Absent => refusal, no download."""
    env = os.environ.get("BODESIGN_NODE_BIN")
    if env:
        if not Path(env).is_file():
            raise ElkLayoutError("E_ELK_NODE_MISSING",
                                 f"BODESIGN_NODE_BIN={env!r} is not a file", path=env)
        return env
    found = shutil.which("node")
    if not found:
        raise ElkLayoutError("E_ELK_NODE_MISSING",
                             "no `node` on PATH and BODESIGN_NODE_BIN unset; the engine "
                             "is unavailable here (Dockerfile.ee ships a pinned Node 22)")
    return found


@dataclass(slots=True)
class RunnerReceipt:
    node_bin: str
    node_version: str
    elkjs_version: str
    runner_sha256: str
    wall_s: float
    max_rss_kb: int | None
    graph_sha256: str
    solution_sha256: str


def run_elk(graph: dict, *, timeout_s: float = DEFAULT_TIMEOUT_S,
            runner: Path = RUNNER) -> tuple[dict, RunnerReceipt]:
    """Run ONE bounded Node child. Timeout / nonzero exit / malformed stdout =>
    typed refusal. Never falls back."""
    if not runner.is_file():
        raise ElkLayoutError("E_ELK_RUNNER_MISSING", f"runner not found at {runner}",
                             path=str(runner))
    if not (runner.parent / "node_modules" / "elkjs" / "package.json").is_file():
        raise ElkLayoutError(
            "E_ELK_NOT_INSTALLED",
            f"elkjs is not installed beside {runner.name}; run `npm ci --omit=dev "
            f"--ignore-scripts` in {runner.parent} (no runtime download is performed)",
            path=str(runner.parent))
    node = _node_binary()
    payload = json.dumps({"graph": graph, "timeout_ms": int(timeout_s * 1000)},
                         separators=(",", ":"))
    graph_sha = hashlib.sha256(payload.encode()).hexdigest()
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [node, str(runner)], input=payload, capture_output=True, text=True,
            timeout=timeout_s + 5.0, cwd=str(runner.parent))
    except subprocess.TimeoutExpired as error:
        raise ElkLayoutError("E_ELK_TIMEOUT",
                             f"elk runner exceeded {timeout_s + 5.0:.0f}s and was killed",
                             timeout_s=timeout_s) from error
    wall = time.monotonic() - t0
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else None
    except (json.JSONDecodeError, IndexError):
        result = None
    if proc.returncode != 0 or not isinstance(result, dict):
        raise ElkLayoutError(
            "E_ELK_RUNNER_FAILED",
            f"elk runner exit={proc.returncode}; stdout is "
            f"{'not JSON' if result is None else 'an error object'}",
            exit=proc.returncode, stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:],
            runner_error=(result or {}).get("code"))
    if not result.get("ok") or not isinstance(result.get("solution"), dict):
        raise ElkLayoutError("E_ELK_RUNNER_FAILED", "elk runner reported failure",
                             runner_error=result.get("code"), message=result.get("message"))
    if result.get("elkjs") != ELKJS_PINNED_VERSION:
        raise ElkLayoutError("E_ELK_VERSION_DRIFT",
                             f"runner loaded elkjs {result.get('elkjs')!r}, pinned "
                             f"{ELKJS_PINNED_VERSION}", loaded=result.get("elkjs"))
    rss = None
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    except Exception:  # pragma: no cover - platform without resource
        rss = None
    nv = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    receipt = RunnerReceipt(
        node_bin=node, node_version=nv, elkjs_version=result["elkjs"],
        runner_sha256=hashlib.sha256(runner.read_bytes()).hexdigest(),
        wall_s=round(wall, 3), max_rss_kb=rss, graph_sha256=graph_sha,
        solution_sha256=hashlib.sha256(
            json.dumps(result["solution"], sort_keys=True).encode()).hexdigest())
    return result["solution"], receipt


# --------------------------------------------------------------------------- quantize


@dataclass(slots=True)
class PresentationSolution:
    """One validated presentation solution for a sheet (sheet mm, y-down, on-grid)."""
    #: ref -> symbol origin (x, y) on the sheet
    poses: dict[str, tuple[float, float]]
    #: net -> list of wire segments ((x1,y1),(x2,y2)), axis-aligned, on-grid
    segments: dict[str, list[Segment]]
    #: net -> junction dots (x, y): degree >= 3 meet points of that net
    junctions: dict[str, list[Point]]
    #: net -> label anchor (x, y) = midpoint of the net's longest segment
    label_anchors: dict[str, Point]
    #: nets handed to the engine
    drawn_nets: list[str]
    #: nets NOT drawn and why
    undrawn: dict[str, str]
    #: (ref, pin) -> sheet pin tip, for every pin of every placed symbol
    pin_tips: dict[tuple[str, str], Point]
    receipt: RunnerReceipt | None = None
    verification: dict = field(default_factory=dict)
    #: ref -> Reference/Value placement chosen on the solved layout
    props: dict = field(default_factory=dict)
    #: cross-sheet drawn net -> continuation flag placement
    flags: dict = field(default_factory=dict)
    #: drawn non-cross-sheet net -> local label placement
    local_labels: dict = field(default_factory=dict)
    #: ink boxes of the pin-tip flags the emitter draws for undrawn nets
    fixed_flag_boxes: list = field(default_factory=list)
    #: foreign-net interior crossings of the chosen solution (disclosed, if any)
    foreign_crossings: list = field(default_factory=list)
    variant: str = "default"
    variant_log: list = field(default_factory=list)
    #: ref -> native orientation id for every NON-identity transform (the emitter
    #: serializes `(at x y rot) (mirror ..)` from this; absent ref = R0)
    orientations: dict = field(default_factory=dict)
    #: the predeclared transform set that was evaluated, and the chosen id
    orientation_sweep: dict = field(default_factory=dict)
    #: round 4: name of the placement model that produced this solution
    placement_model: str = "R0"
    #: round 5: ref -> package outline + caption boxes (sheet coords, x0,y0,x1,y1)
    outlines: dict = field(default_factory=dict)
    #: round 5: ELK spacing overrides applied on top of the defaults (empty = R4 baseline)
    spacing_overrides: dict = field(default_factory=dict)


def _q(v: float) -> float:
    return _snap_grid(float(v))


def _split_at_contacts(segs: list[Segment]) -> list[Segment]:
    """Split runs at every same-net endpoint that lies strictly inside them."""
    ends: set[Point] = set()
    for a, b in segs:
        ends.add(a); ends.add(b)
    out: list[Segment] = []
    for a, b in segs:
        cuts = [p for p in ends if p not in (a, b) and _on_segment(p, a, b)]
        if not cuts:
            out.append((a, b))
            continue
        axis = 1 if abs(a[0] - b[0]) < EPS else 0
        pts = sorted([a, b] + cuts, key=lambda p: p[axis])
        if a[axis] > b[axis]:
            pts.reverse()
        for p, q in zip(pts, pts[1:]):
            out.append((p, q))
    return out


def _merge_collinear(segs: list[Segment]) -> list[Segment]:
    """Merge same-net collinear segments that overlap or touch end-to-end into
    maximal runs. Junction semantics are unchanged: a branch meeting a merged
    run's interior still counts as a T."""
    out: list[Segment] = []
    groups: dict[tuple[str, float], list[tuple[float, float]]] = {}
    for a, b in segs:
        if abs(a[0] - b[0]) < EPS:
            groups.setdefault(("V", a[0]), []).append((min(a[1], b[1]), max(a[1], b[1])))
        else:
            groups.setdefault(("H", a[1]), []).append((min(a[0], b[0]), max(a[0], b[0])))
    for (orient, k), spans in groups.items():
        spans.sort()
        cur_lo, cur_hi = spans[0]
        merged: list[tuple[float, float]] = []
        for lo, hi in spans[1:]:
            if lo <= cur_hi + EPS:
                cur_hi = max(cur_hi, hi)
            else:
                merged.append((cur_lo, cur_hi))
                cur_lo, cur_hi = lo, hi
        merged.append((cur_lo, cur_hi))
        for lo, hi in merged:
            if orient == "V":
                out.append(((k, lo), (k, hi)))
            else:
                out.append(((lo, k), (hi, k)))
    return out


def _quantize_polyline(raw: list[Point], src_tip: Point | None, dst_tip: Point | None,
                       net: str) -> list[Point]:
    """Snap an ELK orthogonal polyline onto the grid WITHOUT bending it.

    Each run owns one shared coordinate (y for a horizontal run, x for a
    vertical one). A run touching a pin tip takes that coordinate from the tip;
    a free run snaps its ELK value once. Bend points are then rebuilt from their
    two adjacent runs, so no run can become diagonal through independent
    rounding. A tip-to-tip single run whose two tips disagree, or an ELK run
    that is itself diagonal, is a refusal -- not a local reroute."""
    pts = [raw[0]]
    for p in raw[1:]:
        if abs(p[0] - pts[-1][0]) > 1e-6 or abs(p[1] - pts[-1][1]) > 1e-6:
            pts.append(p)
    if len(pts) == 1:
        tip = src_tip or dst_tip
        return [tip] if tip else [(_q(pts[0][0]), _q(pts[0][1]))]
    n = len(pts) - 1
    orient: list[str] = []
    for a, b in zip(pts, pts[1:]):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        if dx > 1e-6 and dy > 1e-6:
            raise ElkLayoutError("E_ELK_ROUTE_NOT_ORTHOGONAL",
                                 f"net {net!r}: engine run {a}->{b} is diagonal",
                                 net=net, run=[a, b])
        orient.append("H" if dy <= 1e-6 else "V")
    # shared coordinate per run
    shared: list[float] = []
    for i, o in enumerate(orient):
        axis = 1 if o == "H" else 0
        vals: list[float] = []
        if i == 0 and src_tip is not None:
            vals.append(src_tip[axis])
        if i == n - 1 and dst_tip is not None:
            vals.append(dst_tip[axis])
        if not vals:
            vals.append(_q(pts[i][axis]))
        if len(vals) == 2 and abs(vals[0] - vals[1]) > 1e-6:
            # A single straight tip-to-tip run whose two nodes snapped to different
            # grid rows/columns. Independent node snapping can shift the tips apart
            # by at most one grid step; the deterministic quantization of such a
            # run is a mid-point dogleg (H-V-H or V-H-V), recorded as a dogleg.
            # This is the grid's consequence, not a reroute around an obstacle;
            # any contact the dogleg creates is still caught by verify_solution.
            if abs(vals[0] - vals[1]) > GRID_MM + 1e-6:
                raise ElkLayoutError("E_ELK_ROUTE_TIPS_MISALIGNED",
                                     f"net {net!r}: straight run between two pin tips whose "
                                     f"{'y' if axis else 'x'} differ by more than one grid",
                                     net=net, tips=[src_tip, dst_tip])
            other = 0 if axis == 1 else 1
            lo, hi = sorted((src_tip[other], dst_tip[other]))
            mid = _q((lo + hi) / 2)
            if not (lo + GRID_MM - 1e-6 <= mid <= hi - GRID_MM + 1e-6):
                raise ElkLayoutError("E_ELK_ROUTE_TOO_SHORT_FOR_DOGLEG",
                                     f"net {net!r}: misaligned tip-to-tip run too short to "
                                     f"dogleg on the grid", net=net, tips=[src_tip, dst_tip])
            if axis == 1:   # horizontal run: H-V-H
                return [src_tip, (mid, src_tip[1]), (mid, dst_tip[1]), dst_tip]
            return [src_tip, (src_tip[0], mid), (dst_tip[0], mid), dst_tip]
        shared.append(vals[0])
    out: list[Point] = []
    for i in range(n + 1):
        if i == 0 and src_tip is not None:
            out.append(src_tip); continue
        if i == n and dst_tip is not None:
            out.append(dst_tip); continue
        prev_o = orient[i - 1] if i > 0 else None
        next_o = orient[i] if i < n else None
        x = y = None
        for o, j in ((prev_o, i - 1), (next_o, i)):
            if o == "H":
                y = shared[j]
            elif o == "V":
                x = shared[j]
        if x is None:
            x = _q(pts[i][0])
        if y is None:
            y = _q(pts[i][1])
        out.append((round(x, 4), round(y, 4)))
    clean: list[Point] = [out[0]]
    for p in out[1:]:
        if p != clean[-1]:
            clean.append(p)
    for a, b in zip(clean, clean[1:]):
        if abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS:
            raise ElkLayoutError("E_ELK_ROUTE_NOT_ORTHOGONAL",
                                 f"net {net!r}: quantized run {a}->{b} is diagonal; refused "
                                 f"rather than locally rerouted", net=net, run=[a, b])
    return clean


def quantize_solution(solution: dict, build: ElkGraphBuild,
                      geometry: dict[str, SymbolGeometry],
                      origin: Point = (PAGE_ORIGIN_MM, PAGE_ORIGIN_MM)) -> PresentationSolution:
    """Map the ELK solution onto the sheet and the 1.27 mm grid.

    Node positions are snapped; because every port is a grid multiple away from
    its node origin (see `_node_box`), snapping the node keeps every pin tip on
    grid without moving it relative to its symbol. Edge bend points are snapped
    independently; the FIRST and LAST point of every section are REPLACED by the
    exact pin tips they are attached to (the ELK port is a zero-size box on the
    tip; its reported point is the tip itself, but after snapping the two must be
    identical by construction, not by rounding luck). A section whose snapped
    polyline is no longer axis-aligned is a refusal, not a local reroute."""
    nodes = {n["id"]: n for n in solution.get("children", [])}
    poses: dict[str, tuple[float, float]] = {}
    pin_tips: dict[tuple[str, str], Point] = {}
    port_tip: dict[str, Point] = {}
    for ref, g in geometry.items():
        n = nodes.get(ref)
        if n is None or "x" not in n or "y" not in n:
            raise ElkLayoutError("E_ELK_SOLUTION_INCOMPLETE",
                                 f"solution carries no position for node {ref}", ref=ref)
        ox, oy = build.origins[ref]
        sx = _q(origin[0] + float(n["x"]) + ox)
        sy = _q(origin[1] + float(n["y"]) + oy)
        poses[ref] = (sx, sy)
        for pin, (px, py, _rot) in g.pins.items():
            tip = (round(sx + px, 4), round(sy - py, 4))
            pin_tips[(ref, pin)] = tip
            if abs(tip[0] - _q(tip[0])) > 1e-3 or abs(tip[1] - _q(tip[1])) > 1e-3:
                raise ElkLayoutError("E_ELK_PIN_OFF_GRID",
                                     f"{ref}.{pin} tip {tip} is not on the 1.27 mm grid; "
                                     f"the symbol's pin offsets are not grid multiples",
                                     ref=ref, pin=pin, tip=tip)
    for pid, (ref, pin) in build.ports.items():
        port_tip[pid] = pin_tips[(ref, pin)]

    segments: dict[str, list[Segment]] = {}
    for edge in solution.get("edges", []):
        net = build.edge_nets.get(edge["id"])
        if net is None:
            raise ElkLayoutError("E_ELK_SOLUTION_INCOMPLETE",
                                 f"solution edge {edge['id']!r} was not in the request",
                                 edge=edge["id"])
        sections = edge.get("sections") or []
        if not sections:
            raise ElkLayoutError("E_ELK_EDGE_UNROUTED",
                                 f"net {net!r}: edge {edge['id']} has no route sections",
                                 net=net, edge=edge["id"])
        src = edge["sources"][0]
        dst = edge["targets"][0]
        for sec in sections:
            pts = [sec["startPoint"]] + list(sec.get("bendPoints") or []) + [sec["endPoint"]]
            raw = [(origin[0] + float(p["x"]), origin[1] + float(p["y"])) for p in pts]
            # Only a section end that IS a port is replaced by the exact pin tip; a
            # hyperedge section may start/end at a junction instead.
            src_tip = port_tip[src] if sec.get("incomingShape", src) == src else None
            dst_tip = port_tip[dst] if sec.get("outgoingShape", dst) == dst else None
            clean = _quantize_polyline(raw, src_tip, dst_tip, net)
            for a, b in zip(clean, clean[1:]):
                segments.setdefault(net, []).append((a, b))
    for net in build.drawn_nets:
        if not segments.get(net):
            raise ElkLayoutError("E_ELK_EDGE_UNROUTED", f"net {net!r} received no wire",
                                 net=net)
    # A merged hyperedge reports its shared prefix once per member edge, so the
    # same net carries overlapping collinear runs. Merge them into maximal runs:
    # otherwise the shared pin tip counts two wire ends + pin = 3 branches and
    # verification would (correctly, for the geometry as written) demand a dot
    # on the pin tip -- the class (a) defect the reviewers rejected.
    segments = {net: _merge_collinear(segs) for net, segs in segments.items()}
    # Then split every run at each same-net endpoint lying on its interior. KiCad
    # breaks wires at junction dots on load and was measured (S1 receipt §7, and
    # this spike's first usbc export: F1.1 / D1.3 / R2.1 unconnected) to DROP the
    # part of the run beyond the dot. A T must therefore be three wire ENDS
    # meeting at one point, never an end on an interior.
    segments = {net: _split_at_contacts(segs) for net, segs in segments.items()}
    return PresentationSolution(
        poses=poses, segments=segments, junctions={}, label_anchors={},
        drawn_nets=list(build.drawn_nets), undrawn=dict(build.undrawn),
        pin_tips=pin_tips)


# --------------------------------------------------------------------------- verify


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    """p lies on the closed axis-aligned segment a-b (inclusive of ends)."""
    if abs(a[0] - b[0]) < EPS:
        return abs(p[0] - a[0]) < EPS and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS
    if abs(a[1] - b[1]) < EPS:
        return abs(p[1] - a[1]) < EPS and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS
    return False


def _collinear_overlap(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Two axis-aligned segments share a positive-length collinear run."""
    if abs(a[0] - b[0]) < EPS and abs(c[0] - d[0]) < EPS and abs(a[0] - c[0]) < EPS:
        lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
        return hi - lo > EPS
    if abs(a[1] - b[1]) < EPS and abs(c[1] - d[1]) < EPS and abs(a[1] - c[1]) < EPS:
        lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
        return hi - lo > EPS
    return False


def _proper_cross(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    """Interior crossing point of a horizontal and a vertical segment, else None."""
    if abs(a[0] - b[0]) < EPS and abs(c[1] - d[1]) < EPS:   # a-b vertical, c-d horizontal
        x, y = a[0], c[1]
        if (min(c[0], d[0]) + EPS < x < max(c[0], d[0]) - EPS
                and min(a[1], b[1]) + EPS < y < max(a[1], b[1]) - EPS):
            return (x, y)
        return None
    if abs(a[1] - b[1]) < EPS and abs(c[0] - d[0]) < EPS:
        return _proper_cross(c, d, a, b)
    return None


def _foreign_crossings_segs(segments: dict[str, list[Segment]]) -> list[dict]:
    out: list[dict] = []
    items = [(n, s) for n, ss in segments.items() for s in ss]
    for i, (ni, (a, b)) in enumerate(items):
        for nj, (c, d) in items[i + 1:]:
            if ni == nj:
                continue
            x = _proper_cross(a, b, c, d)
            if x is not None:
                out.append({"nets": sorted([ni, nj]), "at": list(x)})
    return out


def _resolve_foreign_collinear_channels(sol: PresentationSolution, build: ElkGraphBuild) -> None:
    """Invariant: two wire segments of DIFFERENT nets that are collinear (same x
    for verticals / same y for horizontals) must be separated along the shared axis
    by >= 2.54 mm; otherwise one of them moves to an adjacent track.
    Offsets the shorter segment by whole grid steps (+/-1.27, +/-2.54) and re-stitches
    its orthogonal connectors.
    Raises E_COLLINEAR_FOREIGN_NO_TRACK if no legal track exists."""
    hull_boxes = []
    for ref, ink in build.inks.items():
        pos = sol.poses.get(ref, (0.0, 0.0))
        hull_boxes.append(_shift(ink.hull, pos[0], pos[1]))

    gap_threshold = 3.81 if _r3_enabled("E") else 2.54

    for _pass in range(20):
        all_segs = [(net, s) for net, ss in sol.segments.items() for s in ss]
        violation = None
        for i, (ni, (a, b)) in enumerate(all_segs):
            for nj, (c, d) in all_segs[i + 1:]:
                if ni == nj:
                    continue
                # Vertical collinear
                if abs(a[0] - b[0]) < EPS and abs(c[0] - d[0]) < EPS and abs(a[0] - c[0]) < EPS:
                    s1_y = (min(a[1], b[1]), max(a[1], b[1]))
                    s2_y = (min(c[1], d[1]), max(c[1], d[1]))
                    gap = s2_y[0] - s1_y[1] if s1_y[1] <= s2_y[0] else (s1_y[0] - s2_y[1] if s2_y[1] <= s1_y[0] else 0.0)
                    if gap < gap_threshold - EPS:
                        violation = ("V", a[0], (ni, (a, b)), (nj, (c, d)), gap)
                        break
                # Horizontal collinear
                elif abs(a[1] - b[1]) < EPS and abs(c[1] - d[1]) < EPS and abs(a[1] - c[1]) < EPS:
                    s1_x = (min(a[0], b[0]), max(a[0], b[0]))
                    s2_x = (min(c[0], d[0]), max(c[0], d[0]))
                    gap = s2_x[0] - s1_x[1] if s1_x[1] <= s2_x[0] else (s1_x[0] - s2_x[1] if s2_x[1] <= s1_x[0] else 0.0)
                    if gap < gap_threshold - EPS:
                        violation = ("H", a[1], (ni, (a, b)), (nj, (c, d)), gap)
                        break
            if violation:
                break
        if not violation:
            return  # Invariant satisfied for all foreign segments!

        orient, coord, (n1, seg1), (n2, seg2), gap = violation
        len1 = abs(seg1[1][1] - seg1[0][1]) if orient == "V" else abs(seg1[1][0] - seg1[0][0])
        len2 = abs(seg2[1][1] - seg2[0][1]) if orient == "V" else abs(seg2[1][0] - seg2[0][0])
        candidates = [(n1, seg1), (n2, seg2)] if len1 <= len2 else [(n2, seg2), (n1, seg1)]
        orig_crossings = len(_foreign_crossings_segs(sol.segments))

        resolved = False
        for move_net, move_seg in candidates:
            for offset in (GRID_MM, -GRID_MM, 2 * GRID_MM, -2 * GRID_MM):
                if orient == "V":
                    min_y, max_y = min(move_seg[0][1], move_seg[1][1]), max(move_seg[0][1], move_seg[1][1])
                    new_coord = round(coord + offset, 4)
                    new_seg = ((new_coord, min_y), (new_coord, max_y))
                    ep_a, ep_b = (coord, min_y), (coord, max_y)
                    tgt_a, tgt_b = (new_coord, min_y), (new_coord, max_y)
                else:
                    min_x, max_x = min(move_seg[0][0], move_seg[1][0]), max(move_seg[0][0], move_seg[1][0])
                    new_coord = round(coord + offset, 4)
                    new_seg = ((min_x, new_coord), (max_x, new_coord))
                    ep_a, ep_b = (min_x, coord), (max_x, coord)
                    tgt_a, tgt_b = (min_x, new_coord), (max_x, new_coord)

                # Constraint (1a): hull collision
                if any(_seg_hits_box(new_seg[0], new_seg[1], h, 0.0) for h in hull_boxes):
                    continue

                # Constraint (1b): foreign pin tips
                foreign_tips = [tip for (r, p), tip in sol.pin_tips.items() if build.declared_pin_nets.get((r, p)) != move_net]
                if any(_on_segment(tip, new_seg[0], new_seg[1]) for tip in foreign_tips):
                    continue

                # Re-stitch connectors in move_net
                trial_segs = [s for s in sol.segments[move_net] if s != move_seg and s != (move_seg[1], move_seg[0])]
                stitching_ok = True
                new_connectors = []
                for ep, tgt in ((ep_a, tgt_a), (ep_b, tgt_b)):
                    conn_indices = [idx for idx, s in enumerate(trial_segs) if ep in s]
                    if conn_indices:
                        for idx in conn_indices:
                            s = trial_segs[idx]
                            is_perp = (abs(s[0][1] - s[1][1]) < EPS) if orient == "V" else (abs(s[0][0] - s[1][0]) < EPS)
                            if is_perp:
                                new_s = (tgt, s[1]) if s[0] == ep else (s[0], tgt)
                                if any(_seg_hits_box(new_s[0], new_s[1], h, 0.0) for h in hull_boxes):
                                    stitching_ok = False; break
                                trial_segs[idx] = new_s
                            else:
                                jog = (ep, tgt)
                                if any(_seg_hits_box(jog[0], jog[1], h, 0.0) for h in hull_boxes):
                                    stitching_ok = False; break
                                new_connectors.append(jog)
                    else:
                        if ep in sol.pin_tips.values():
                            jog = (ep, tgt)
                            if any(_seg_hits_box(jog[0], jog[1], h, 0.0) for h in hull_boxes):
                                stitching_ok = False; break
                            new_connectors.append(jog)
                    if not stitching_ok:
                        break
                if not stitching_ok:
                    continue

                trial_segs.append(new_seg)
                trial_segs.extend(new_connectors)
                trial_segs = _split_at_contacts(_merge_collinear(trial_segs))

                # Constraint (1c): wire contacts with foreign nets
                foreign_segs = [s for net, ss in sol.segments.items() if net != move_net for s in ss]
                hit_foreign = False
                for s in trial_segs:
                    for fs in foreign_segs:
                        if _collinear_overlap(s[0], s[1], fs[0], fs[1]):
                            hit_foreign = True; break
                        if any(_on_segment(p, fs[0], fs[1]) for p in (s[0], s[1])):
                            hit_foreign = True; break
                        if any(_on_segment(p, s[0], s[1]) for p in (fs[0], fs[1])):
                            hit_foreign = True; break
                    if hit_foreign: break
                if hit_foreign:
                    continue

                # Constraint (1d): collinear gap with any foreign segment on new_coord >= 2.54 mm
                new_gap_bad = False
                for fs in foreign_segs:
                    if orient == "V":
                        if abs(fs[0][0] - fs[1][0]) < EPS and abs(fs[0][0] - new_coord) < EPS:
                            fy = (min(fs[0][1], fs[1][1]), max(fs[0][1], fs[1][1]))
                            for s in trial_segs:
                                if abs(s[0][0] - s[1][0]) < EPS and abs(s[0][0] - new_coord) < EPS:
                                    sy = (min(s[0][1], s[1][1]), max(s[0][1], s[1][1]))
                                    gap_f = sy[0] - fy[1] if fy[1] <= sy[0] else (fy[0] - sy[1] if sy[1] <= fy[0] else 0.0)
                                    if gap_f < 2.54 - EPS:
                                        new_gap_bad = True; break
                    else:
                        if abs(fs[0][1] - fs[1][1]) < EPS and abs(fs[0][1] - new_coord) < EPS:
                            fx = (min(fs[0][0], fs[1][0]), max(fs[0][0], fs[1][0]))
                            for s in trial_segs:
                                if abs(s[0][1] - s[1][1]) < EPS and abs(s[0][1] - new_coord) < EPS:
                                    sx = (min(s[0][0], s[1][0]), max(s[0][0], s[1][0]))
                                    gap_f = sx[0] - fx[1] if fx[1] <= sx[0] else (fx[0] - sx[1] if sx[1] <= fx[0] else 0.0)
                                    if gap_f < 2.54 - EPS:
                                        new_gap_bad = True; break
                    if new_gap_bad: break
                if new_gap_bad:
                    continue

                # Constraint (2): foreign crossing count per sheet must not increase
                trial_dict = {k: (trial_segs if k == move_net else v) for k, v in sol.segments.items()}
                if len(_foreign_crossings_segs(trial_dict)) > orig_crossings:
                    continue

                sol.segments[move_net] = trial_segs
                resolved = True
                break
            if resolved:
                break
        if not resolved:
            raise ElkLayoutError("E_COLLINEAR_FOREIGN_NO_TRACK",
                                 f"no free channel track exists to separate foreign collinear nets {n1} and {n2} by >= 2.54 mm",
                                 net1=n1, net2=n2, gap=gap)


class _DSU:
    def __init__(self):
        self.p: dict = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def verify_solution(sol: PresentationSolution, build: ElkGraphBuild) -> dict:
    """KiCad wire-contact semantics applied to the quantized geometry:

      * two wires are joined where an ENDPOINT of one lies on the other (or ends
        coincide); a pin is joined where a wire endpoint equals its tip;
      * a crossing of two interiors is NOT a contact (no junction there);
      * every wire endpoint that is not a pin tip must be on another wire of the
        SAME net (no dangling run);
      * junction dot iff >= 3 incident branches at a point (same net).

    Then the drawn pin partition is compared with the declared nets restricted
    to the drawn ones: fused / missing / misrouted must all be zero. Sets
    `sol.junctions`, `sol.label_anchors`, `sol.verification`; raises on any gap."""
    problems: list[dict] = []
    tip_owner: dict[Point, set[tuple[str, str]]] = {}
    for key, tip in sol.pin_tips.items():
        tip_owner.setdefault(tip, set()).add(key)
    declared = build.declared_pin_nets
    drawn_set = set(sol.drawn_nets)

    all_segs: list[tuple[str, Segment]] = [(n, s) for n, ss in sol.segments.items() for s in ss]
    # 1. endpoint discipline + 2. contact graph
    dsu = _DSU()
    for i, (net, (a, b)) in enumerate(all_segs):
        dsu.find(("seg", i))
        for p in (a, b):
            owners = tip_owner.get(p)
            if owners:
                for ref, pin in owners:
                    dn = declared.get((ref, pin))
                    if dn != net:
                        problems.append({"code": "E_ELK_ENDPOINT_FOREIGN_PIN", "net": net,
                                         "pin": f"{ref}.{pin}", "pin_net": dn, "at": p})
                    dsu.union(("seg", i), ("pin", ref, pin))
    # wire-wire contacts: endpoint of one on the other (any net -- that is how
    # KiCad reads it, and a foreign contact is exactly the fusion we must catch)
    for i, (ni, (a, b)) in enumerate(all_segs):
        for j, (nj, (c, d)) in enumerate(all_segs):
            if j <= i:
                continue
            touch = any(_on_segment(p, c, d) for p in (a, b)) or any(_on_segment(p, a, b) for p in (c, d))
            if touch:
                dsu.union(("seg", i), ("seg", j))
                if ni != nj:
                    problems.append({"code": "E_ELK_FOREIGN_CONTACT", "nets": [ni, nj],
                                     "segs": [[a, b], [c, d]]})
            elif _collinear_overlap(a, b, c, d):
                dsu.union(("seg", i), ("seg", j))
                if ni != nj:
                    problems.append({"code": "E_ELK_FOREIGN_COLLINEAR", "nets": [ni, nj],
                                     "segs": [[a, b], [c, d]]})
            elif ni != nj and _r3_enabled("A"):
                # Invariant: two wire segments of DIFFERENT nets that are collinear
                # must be separated along the shared axis by >= 2.54 mm.
                if abs(a[0] - b[0]) < EPS and abs(c[0] - d[0]) < EPS and abs(a[0] - c[0]) < EPS:
                    s1_y = (min(a[1], b[1]), max(a[1], b[1]))
                    s2_y = (min(c[1], d[1]), max(c[1], d[1]))
                    gap = s2_y[0] - s1_y[1] if s1_y[1] <= s2_y[0] else (s1_y[0] - s2_y[1] if s2_y[1] <= s1_y[0] else 0.0)
                    if gap < 2.54 - EPS:
                        problems.append({"code": "E_ELK_FOREIGN_COLLINEAR_GAP", "nets": [ni, nj],
                                         "axis": "x", "val": a[0], "gap": round(gap, 4),
                                         "segs": [[a, b], [c, d]]})
                elif abs(a[1] - b[1]) < EPS and abs(c[1] - d[1]) < EPS and abs(a[1] - c[1]) < EPS:
                    s1_x = (min(a[0], b[0]), max(a[0], b[0]))
                    s2_x = (min(c[0], d[0]), max(c[0], d[0]))
                    gap = s2_x[0] - s1_x[1] if s1_x[1] <= s2_x[0] else (s1_x[0] - s2_x[1] if s2_x[1] <= s1_x[0] else 0.0)
                    if gap < 2.54 - EPS:
                        problems.append({"code": "E_ELK_FOREIGN_COLLINEAR_GAP", "nets": [ni, nj],
                                         "axis": "y", "val": a[1], "gap": round(gap, 4),
                                         "segs": [[a, b], [c, d]]})
    # a wire endpoint that is neither a pin tip nor on another segment is dangling
    for i, (net, (a, b)) in enumerate(all_segs):
        for p in (a, b):
            if p in tip_owner:
                continue
            if not any(_on_segment(p, c, d) for j, (_n, (c, d)) in enumerate(all_segs) if j != i):
                problems.append({"code": "E_ELK_DANGLING_END", "net": net, "at": p})
    # a wire interior passing over a FOREIGN pin tip is a contact in KiCad
    for net, (a, b) in all_segs:
        for tip, owners in tip_owner.items():
            if tip in (a, b):
                continue
            if _on_segment(tip, a, b):
                for ref, pin in owners:
                    dsu.union(("pin", ref, pin), ("seg", all_segs.index((net, (a, b)))))
                    if declared.get((ref, pin)) != net:
                        problems.append({"code": "E_ELK_WIRE_OVER_FOREIGN_PIN", "net": net,
                                         "pin": f"{ref}.{pin}", "at": tip})

    # 3. junction semantics: count incident branches at every candidate point
    junctions: dict[str, list[Point]] = {}
    pts: set[Point] = set()
    for _n, (a, b) in all_segs:
        pts.add(a); pts.add(b)
    for p in pts:
        incident: list[str] = []
        for net, (a, b) in all_segs:
            if p == a or p == b:
                incident.append(net)
            elif _on_segment(p, a, b):
                incident.extend([net, net])  # a T onto an interior splits it: 2 branches
        if p in tip_owner:
            incident.append("pin")
        if len(incident) >= 3:
            nets_here = {n for n in incident if n != "pin"}
            if len(nets_here) != 1:
                problems.append({"code": "E_ELK_JUNCTION_MULTI_NET", "at": p, "nets": sorted(nets_here)})
                continue
            junctions.setdefault(next(iter(nets_here)), []).append(p)
    # crossing interiors must NOT host a junction (they would be a short)
    for i, (ni, (a, b)) in enumerate(all_segs):
        for j, (nj, (c, d)) in enumerate(all_segs):
            if j <= i:
                continue
            x = _proper_cross(a, b, c, d)
            if x is not None and any(x in js for js in junctions.values()):
                problems.append({"code": "E_ELK_JUNCTION_ON_CROSSING", "at": x, "nets": [ni, nj]})

    # 4. connectivity: drawn partition of pins vs declared, restricted to drawn nets
    drawn_pins = {k for k, n in declared.items() if n in drawn_set}
    comp_of: dict[tuple[str, str], object] = {k: dsu.find(("pin",) + k) for k in drawn_pins}
    fused: list[dict] = []
    missing: list[dict] = []
    by_net: dict[str, set] = {}
    for k, n in declared.items():
        if n in drawn_set:
            by_net.setdefault(n, set()).add(comp_of[k])
    for n, comps in by_net.items():
        if len(comps) > 1:
            missing.append({"net": n, "fragments": len(comps)})
    root_net: dict[object, set[str]] = {}
    for k, n in declared.items():
        if n in drawn_set:
            root_net.setdefault(comp_of[k], set()).add(n)
    for root, ns in root_net.items():
        if len(ns) > 1:
            fused.append({"nets": sorted(ns)})
    misrouted = [p for p in problems if p["code"] in
                 ("E_ELK_ENDPOINT_FOREIGN_PIN", "E_ELK_WIRE_OVER_FOREIGN_PIN")]

    # Label anchors are NOT chosen here: `place_ink` picks them on the verified
    # geometry from each label's own net (replaces the longest-segment midpoint).
    anchors: dict[str, Point] = {}

    report = {
        "fused": fused, "missing": missing, "misrouted": misrouted,
        "problems": problems,
        "drawn_nets": sorted(drawn_set), "undrawn": dict(sol.undrawn),
        "segments": sum(len(s) for s in sol.segments.values()),
        "junctions": sum(len(j) for j in junctions.values()),
        "pins_examined": len(drawn_pins),
    }
    sol.junctions = junctions
    sol.label_anchors = anchors
    sol.verification = report
    if fused or missing or problems:
        raise ElkLayoutError(
            "E_ELK_SOLUTION_INVALID",
            f"engine solution refused: fused={len(fused)} missing={len(missing)} "
            f"problems={len(problems)}", **report)
    return report


# --------------------------------------------------------------------------- ink placement
#
# After routing, props / label flags / local net labels are placed
# deterministically against the ACTUAL solved geometry. Every choice is checked
# against foreign wires, other symbols' hulls, junction dots and every ink box
# already placed. No legal position => typed refusal (never reroute / relabel).


@dataclass(slots=True)
class PropPlacement:
    ref: str
    ref_at: Point
    val_at: Point
    ref_box: Box
    val_box: Box | None
    candidate: str


@dataclass(slots=True)
class LabelPlacement:
    net: str
    kind: str                    # "local" | "flag"
    at: Point
    edge: tuple[float, float]    # outward text direction (flags only)
    box: Box
    pin: str | None = None       # "REF.PIN" the flag is attached to


_LABEL_UP_MM = 0.8   # a KiCad local label draws its text above the anchor line
_FLAG_DIRS = ((1.0, 0.0), (-1.0, 0.0))


def _box_hits_wires(box: Box, wires, *, own_net: str | None,
                    own_strict: bool = False,
                    anchor_seg: Segment | None = None) -> bool:
    """Foreign wires (and, with own_net=None, every wire) hit within INK_CLEAR_MM.
    `own_strict`: the owning net's wires count only when they run THROUGH the box
    (touching its edge, as at the flag anchor, is the attachment itself).
    `anchor_seg`: optional carrier segment on which a label is anchored; exempt."""
    for net, a, b in wires:
        if anchor_seg is not None and ((a == anchor_seg[0] and b == anchor_seg[1]) or (a == anchor_seg[1] and b == anchor_seg[0])):
            continue
        if own_net is not None and net == own_net:
            if own_strict and _seg_hits_box(a, b, box, 0.0):
                return True
            continue
        if _seg_hits_box(a, b, box, INK_CLEAR_MM):
            return True
    return False


def place_ink(sol: "PresentationSolution", build: ElkGraphBuild,
              components: list[EmitComponent], *, cross_sheet_nets: set[str],
              page_scale: float = 1.0) -> dict:
    """Choose Reference/Value positions, continuation flags and local labels.
    Returns an ink report; raises `ElkLayoutError` when any item has no legal
    position or when a fixed pin flag collides with routed geometry."""
    wires = [(n, a, b) for n, ss in sol.segments.items() for a, b in ss]
    dots = [_inflate((p[0], p[1], p[0], p[1]), DOT_HALF_MM)
            for js in sol.junctions.values() for p in js]
    hulls: dict[str, Box] = {}
    for c in components:
        x, y = sol.poses[c.ref]
        hulls[c.ref] = _shift(build.inks[c.ref].hull, x, y)

    placed: list[tuple[str, Box]] = []          # (owner, box)

    def _free(box: Box, *, owner: str | None, own_hull_ok: str | None = None,
              own_net: str | None = None, hull_clear: float = INK_CLEAR_MM,
              own_strict: bool = False,
              anchor_seg: Segment | None = None) -> bool:
        if _box_hits_wires(box, wires, own_net=own_net, own_strict=own_strict, anchor_seg=anchor_seg):
            return False
        for ref, h in hulls.items():
            if ref == own_hull_ok:
                continue
            if _boxes_overlap(box, h, hull_clear):
                return False
        if any(_boxes_overlap(box, d) for d in dots):
            return False
        for who, pb in placed:
            if _boxes_overlap(box, pb, 0.1):
                return False
        return True

    # 1. fixed flags of label-continued pins: the emitter draws these at the pin tips
    conflicts: list[dict] = []
    fixed: list[tuple[str, str, str, Box]] = []
    seen_flag: set[tuple[str, Box]] = set()
    for c in components:
        x, y = sol.poses[c.ref]
        for name, pin, rb in build.inks[c.ref].flags:
            if name in build.drawn_nets:
                continue
            box = _shift(rb, x, y)
            key = (name, tuple(round(v, 3) for v in box))
            if key in seen_flag:
                continue
            seen_flag.add(key)
            fixed.append((c.ref, pin, name, box))
            if _box_hits_wires(box, wires, own_net=None):
                conflicts.append({"flag": f"{c.ref}.{pin}:{name}", "against": "wire"})
            for ref, h in hulls.items():
                if ref != c.ref and _boxes_overlap(box, h, INK_CLEAR_MM):
                    conflicts.append({"flag": f"{c.ref}.{pin}:{name}", "against": f"hull {ref}"})
            if any(_boxes_overlap(box, d) for d in dots):
                conflicts.append({"flag": f"{c.ref}.{pin}:{name}", "against": "junction"})
    for ref, pin, name, box in fixed:
        placed.append((f"flag:{ref}.{pin}", box))
    for i, (r1, p1, n1, b1) in enumerate(fixed):
        for (r2, p2, n2, b2) in fixed[i + 1:]:
            if _boxes_overlap(b1, b2, 0.1):
                conflicts.append({"flag": f"{r1}.{p1}:{n1}", "against": f"flag {r2}.{p2}:{n2}"})
    if conflicts:
        raise ElkLayoutError("E_ELK_INK_CONFLICT",
                             "a label flag drawn at a pin tip collides with routed geometry",
                             conflicts=conflicts[:12], variant=build.variant)

    # 2. Reference / Value text
    props: dict[str, PropPlacement] = {}
    for c in components:
        ink = build.inks[c.ref]
        x, y = sol.poses[c.ref]
        chosen = None
        for cand in ink.candidates[ink.natural:]:
            rb = _shift(cand.ref_box, x, y)
            vb = _shift(cand.val_box, x, y) if cand.val_box else None
            boxes = [rb] + ([vb] if vb else [])
            if _boxes_overlap(rb, vb, 0.1) if vb else False:
                continue
            if all(_free(b, owner=c.ref) for b in boxes):
                chosen = (cand, rb, vb)
                break
        if chosen is None:
            raise ElkLayoutError(
                "E_ELK_PROP_NO_POSITION",
                f"{c.ref}: no Reference/Value text position is clear of wires, foreign "
                f"symbols, flags and junction dots on the solved layout",
                ref=c.ref, variant=build.variant)
        cand, rb, vb = chosen
        props[c.ref] = PropPlacement(
            ref=c.ref, ref_at=(round(x + cand.ref_at[0], 4), round(y + cand.ref_at[1], 4)),
            val_at=(round(x + cand.val_at[0], 4), round(y + cand.val_at[1], 4)),
            ref_box=rb, val_box=vb, candidate=cand.name)
        placed.append((f"ref:{c.ref}", rb))
        if vb:
            placed.append((f"val:{c.ref}", vb))

    # 3. continuation flags of DRAWN cross-sheet nets. The flag attaches to the
    # OWNING net: first at one of its pin tips, then at any on-grid point of its own
    # wires; direction = the four axis directions, outward-of-pin first.
    flags: dict[str, LabelPlacement] = {}
    for net in build.drawn_nets:
        if net not in cross_sheet_nets:
            continue
        pick = None
        anchors: list[tuple[Point, str | None, tuple[float, float] | None]] = []
        for ref, pin in build.net_pins[net]:
            tip = sol.pin_tips.get((ref, pin))
            if tip is not None:
                anchors.append((tip, ref, _pin_out_vec(build_rot(build, ref, pin))))
        seen_pt = {a[0] for a in anchors}
        for a, b in sol.segments.get(net, []):
            nstep = int(round((abs(a[0] - b[0]) + abs(a[1] - b[1])) / GRID_MM))
            for k in range(0, nstep + 1):
                t = k / nstep if nstep else 0.0
                pt = (round(a[0] + (b[0] - a[0]) * t, 4), round(a[1] + (b[1] - a[1]) * t, 4))
                if pt not in seen_pt:
                    seen_pt.add(pt)
                    anchors.append((pt, None, None))
        for pt, ref, first in anchors:
            if ref is not None:
                if _r3_enabled("C"):
                    # Pin-anchored flag: dedicated stub wire of exactly 1.27 mm along first
                    stub_vec = first if first is not None else (1.0, 0.0)
                    stub_far = (round(pt[0] + stub_vec[0] * GRID_MM, 4), round(pt[1] + stub_vec[1] * GRID_MM, 4))
                    stub_seg = (pt, stub_far)
                    # Stub must clear other component hulls
                    if any(_seg_hits_box(stub_seg[0], stub_seg[1], h, 0.0) for r, h in hulls.items() if r != ref):
                        continue
                    # Check if an existing carrier segment leaves pt along stub_vec:
                    collinear_seg = None
                    tail_seg = None
                    for s in sol.segments.get(net, []):
                        if s[0] == pt:
                            other = s[1]
                        elif s[1] == pt:
                            other = s[0]
                        else:
                            continue
                        vec = (other[0] - pt[0], other[1] - pt[1])
                        if abs(stub_vec[0]) > 0:
                            if abs(vec[1]) < EPS and vec[0] * stub_vec[0] > 0 and abs(vec[0]) >= GRID_MM - EPS:
                                collinear_seg = s
                                if abs(vec[0]) > GRID_MM + EPS:
                                    tail_seg = (stub_far, other)
                                break
                        elif abs(stub_vec[1]) > 0:
                            if abs(vec[0]) < EPS and vec[1] * stub_vec[1] > 0 and abs(vec[1]) >= GRID_MM - EPS:
                                collinear_seg = s
                                if abs(vec[1]) > GRID_MM + EPS:
                                    tail_seg = (stub_far, other)
                                break
                    # Flag box at stub_far pointing outward along stub_vec (collinear)
                    box = _rect(_label_bbox(net, stub_far[0], stub_far[1], True, stub_vec, page_scale))
                    # Closed-interval test: flag box must not intersect any wire except its own stub (and carrier tail if collinear)
                    hits_wire = False
                    for wnet, wa, wb in wires:
                        if (wa == stub_seg[0] and wb == stub_seg[1]) or (wa == stub_seg[1] and wb == stub_seg[0]):
                            continue
                        if collinear_seg is not None and ((wa == collinear_seg[0] and wb == collinear_seg[1]) or (wa == collinear_seg[1] and wb == collinear_seg[0])):
                            continue
                        if tail_seg is not None and ((wa == tail_seg[0] and wb == tail_seg[1]) or (wa == tail_seg[1] and wb == tail_seg[0])):
                            continue
                        sx0, sx1 = sorted((wa[0], wb[0]))
                        sy0, sy1 = sorted((wa[1], wb[1]))
                        if not (sx1 < box[0] or box[2] < sx0 or sy1 < box[1] or box[3] < sy0):
                            hits_wire = True
                            break
                        if wnet != net and _seg_hits_box(wa, wb, box, INK_CLEAR_MM):
                            hits_wire = True
                            break
                    if hits_wire:
                        continue
                    if any(_boxes_overlap(box, h, 0.0) for r, h in hulls.items() if r != ref):
                        continue
                    if any(_boxes_overlap(box, d) for d in dots):
                        continue
                    if any(_boxes_overlap(box, pb, 0.1) for who, pb in placed):
                        continue
                    pick = LabelPlacement(net, "flag", stub_far, stub_vec, box, ref and f"{ref}")
                    if collinear_seg is not None:
                        segs = sol.segments.get(net, [])
                        idx = segs.index(collinear_seg)
                        segs.pop(idx)
                        segs.append(stub_seg)
                        if tail_seg:
                            segs.append(tail_seg)
                        for i, w in enumerate(wires):
                            if w[0] == net and ((w[1] == collinear_seg[0] and w[2] == collinear_seg[1]) or (w[1] == collinear_seg[1] and w[2] == collinear_seg[0])):
                                wires.pop(i)
                                break
                        wires.append((net, stub_seg[0], stub_seg[1]))
                        if tail_seg:
                            wires.append((net, tail_seg[0], tail_seg[1]))
                    else:
                        sol.segments.setdefault(net, []).append(stub_seg)
                        wires.append((net, stub_seg[0], stub_seg[1]))
                    break
                else:
                    inward = (-first[0], -first[1]) if first else None
                    dirs = [d for d in ([first] if first else []) + [d for d in _FLAG_DIRS if d != first]
                            if inward is None or d != inward]
                    for d in dirs:
                        box = _rect(_label_bbox(net, pt[0], pt[1], True, d, page_scale))
                        if _free(box, owner=net, own_hull_ok=ref, own_net=net, hull_clear=0.0, own_strict=True):
                            pick = LabelPlacement(net, "flag", pt, d, box, ref and f"{ref}")
                            break
                    if pick:
                        break
            else:
                if _r3_enabled("C"):
                    continue
                # Wire-anchored flag
                dirs = list(_FLAG_DIRS)
                for d in dirs:
                    box = _rect(_label_bbox(net, pt[0], pt[1], True, d, page_scale))
                    hits_wire = False
                    for wnet, wa, wb in wires:
                        if _on_segment(pt, wa, wb):
                            if _seg_hits_box(wa, wb, box, 0.0):
                                hits_wire = True
                                break
                            continue
                        sx0, sx1 = sorted((wa[0], wb[0]))
                        sy0, sy1 = sorted((wa[1], wb[1]))
                        if not (sx1 < box[0] or box[2] < sx0 or sy1 < box[1] or box[3] < sy0):
                            hits_wire = True
                            break
                        if wnet != net and _seg_hits_box(wa, wb, box, INK_CLEAR_MM):
                            hits_wire = True
                            break
                    if hits_wire:
                        continue
                    if any(_boxes_overlap(box, h, INK_CLEAR_MM) for r, h in hulls.items()):
                        continue
                    if any(_boxes_overlap(box, d) for d in dots):
                        continue
                    if any(_boxes_overlap(box, pb, 0.1) for who, pb in placed):
                        continue
                    pick = LabelPlacement(net, "flag", pt, d, box, None)
                    break
                if pick:
                    break
        if pick is None:
            raise ElkLayoutError(
                "E_FLAG_NO_OUTWARD",
                f"net {net!r} is cross-sheet and drawn locally; no anchor on its own "
                f"pins/wires admits a clear outward continuation flag on the solved layout",
                net=net, variant=build.variant)
        flags[net] = pick
        placed.append((f"flag:{net}", pick.box))

    # 4. local net labels (every drawn net that is not cross-sheet)
    labels: dict[str, LabelPlacement] = {}
    tipset = set(sol.pin_tips.values())
    for net in build.drawn_nets:
        if net in cross_sheet_nets:
            continue
        segs = sol.segments.get(net, [])
        jset = set(sol.junctions.get(net, []))
        if not _r3_enabled("B"):
            cands_v3: list[tuple[tuple, Point]] = []
            for a, b in segs:
                horiz = abs(a[1] - b[1]) < EPS
                length = abs(a[0] - b[0]) + abs(a[1] - b[1])
                n = int(round(length / GRID_MM))
                for k in range(0, n + 1):
                    t = k / n if n else 0.0
                    p = (round(a[0] + (b[0] - a[0]) * t, 4), round(a[1] + (b[1] - a[1]) * t, 4))
                    if p in jset or p in tipset:
                        continue
                    cands_v3.append(((0 if horiz else 1, -length, p[1], p[0]), p))
            cands_v3.sort(key=lambda t: t[0])
            pick_v3 = None
            for _k, p in cands_v3:
                box = _rect(_label_bbox(net, p[0], p[1], False, (1.0, 0.0), page_scale))
                if _free(box, owner=net, own_net=net, own_strict=True):
                    pick_v3 = LabelPlacement(net, "local", p, (1.0, 0.0), box)
                    break
            if pick_v3 is None:
                raise ElkLayoutError(
                    "E_ELK_LABEL_NO_POSITION",
                    f"net {net!r}: no on-wire anchor admits a clear local label on the solved "
                    f"layout (refused rather than relabelled or rerouted)",
                    net=net, variant=build.variant)
            labels[net] = pick_v3
            placed.append((f"label:{net}", pick_v3.box))
            continue

        # Rule B-1: local-label anchor stays a wire TERMINAL (dead-end).
        # When the only available terminal is a 90° corner vertex, grow a dedicated
        # 1.27 mm dead-end stub from that vertex along the straight run's own direction,
        # same net, on grid, and anchor the label at the stub's far end.
        term_cands: list[tuple[Point, Segment]] = []
        for a, b in segs:
            for p, other in ((a, b), (b, a)):
                if p in jset or p in tipset:
                    continue
                deg = sum(1 for sa, sb in segs if p in (sa, sb))
                if deg == 1 and other[0] < p[0] - EPS:
                    term_cands.append((p, (other, p)))
        pick = None
        for p, seg in term_cands:
            box = _rect(_label_bbox(net, p[0], p[1], False, (1.0, 0.0), page_scale))
            # Text box must clear its OWN other wires by >= 1.27 mm
            clear_wires = True
            for oa, ob in segs:
                if (oa == seg[0] and ob == seg[1]) or (oa == seg[1] and ob == seg[0]):
                    continue
                sx0, sx1 = sorted((oa[0], ob[0]))
                sy0, sy1 = sorted((oa[1], ob[1]))
                if not (sx1 <= box[0] - GRID_MM + EPS or box[2] + GRID_MM - EPS <= sx0 or
                        sy1 <= box[1] - GRID_MM + EPS or box[3] + GRID_MM - EPS <= sy0):
                    clear_wires = False
                    break
            if not clear_wires:
                continue
            if _free(box, owner=net, own_net=net, own_strict=True, anchor_seg=seg):
                pick = LabelPlacement(net, "local", p, (1.0, 0.0), box)
                break

        if pick is None:
            corners: list[tuple[Point, Point, tuple[float, float]]] = []
            for i, s1 in enumerate(segs):
                h1 = abs(s1[0][1] - s1[1][1]) < EPS
                for j, s2 in enumerate(segs):
                    if j <= i:
                        continue
                    h2 = abs(s2[0][1] - s2[1][1]) < EPS
                    if h1 != h2:
                        for p in (s1[0], s1[1]):
                            if p in (s2[0], s2[1]) and p not in jset and p not in tipset:
                                H = s1 if h1 else s2
                                V = s2 if h1 else s1
                                h_other = H[1] if H[0] == p else H[0]
                                v_other = V[1] if V[0] == p else V[0]
                                if h_other[0] < p[0] - EPS:
                                    corners.append((p, (round(p[0] + GRID_MM, 4), p[1]), (1.0, 0.0)))
                                elif h_other[0] > p[0] + EPS:
                                    corners.append((p, (round(p[0] - GRID_MM, 4), p[1]), (-1.0, 0.0)))
                                if v_other[1] < p[1] - EPS:
                                    stub_p = (p[0], round(p[1] + GRID_MM, 4))
                                    if h_other[0] > p[0] + EPS:
                                        corners.append((p, stub_p, (1.0, 0.0)))
                                    elif h_other[0] < p[0] - EPS:
                                        corners.append((p, stub_p, (-1.0, 0.0)))
                                elif v_other[1] > p[1] + EPS:
                                    stub_p = (p[0], round(p[1] - GRID_MM, 4))
                                    if h_other[0] > p[0] + EPS:
                                        corners.append((p, stub_p, (1.0, 0.0)))
                                    elif h_other[0] < p[0] - EPS:
                                        corners.append((p, stub_p, (-1.0, 0.0)))
            for p, stub_far, edge in corners:
                stub_seg = (p, stub_far)
                box = _rect(_label_bbox(net, stub_far[0], stub_far[1], False, edge, page_scale))
                hits_wire = False
                for wnet, wa, wb in wires:
                    if (wa == stub_seg[0] and wb == stub_seg[1]) or (wa == stub_seg[1] and wb == stub_seg[0]):
                        continue
                    sx0, sx1 = sorted((wa[0], wb[0]))
                    sy0, sy1 = sorted((wa[1], wb[1]))
                    if not (sx1 < box[0] or box[2] < sx0 or sy1 < box[1] or box[3] < sy0):
                        hits_wire = True
                        break
                    if _seg_hits_box(wa, wb, box, INK_CLEAR_MM - 1e-4):
                        hits_wire = True
                        break
                if hits_wire:
                    continue
                if any(_boxes_overlap(box, h, INK_CLEAR_MM) for r, h in hulls.items()):
                    continue
                if any(_boxes_overlap(box, d) for d in dots):
                    continue
                if any(_boxes_overlap(box, pb, 0.1) for who, pb in placed):
                    continue
                pick = LabelPlacement(net, "local", stub_far, edge, box)
                sol.segments.setdefault(net, []).append(stub_seg)
                wires.append((net, stub_seg[0], stub_seg[1]))
                sol.junctions.setdefault(net, []).append(p)
                break
        if pick is None:
            raise ElkLayoutError(
                "E_ELK_LABEL_NO_POSITION",
                f"net {net!r}: no on-wire anchor admits a clear local label on the solved "
                f"layout (refused rather than relabelled or rerouted)",
                net=net, variant=build.variant)
        labels[net] = pick
        placed.append((f"label:{net}", pick.box))

    # 5. Round 5 package outlines: the box is NON-ELECTRICAL presentation ink. No wire
    # (any net), junction dot, flag, label or foreign text may lie inside it, and the
    # caption (Reference/Value) must not overlap it. Typed refusal, never a reroute.
    outlines: dict[str, dict] = {}
    for c in components:
        ob = build.inks[c.ref].outline
        if ob is None:
            continue
        x, y = sol.poses[c.ref]
        box = _shift(ob, x, y)
        bad: list[dict] = []
        for net, a, b in wires:
            if _seg_hits_box(a, b, box, 0.0):
                bad.append({"kind": "wire", "net": net, "seg": [list(a), list(b)]})
        for d in dots:
            if _boxes_overlap(d, box):
                bad.append({"kind": "junction"})
        for who, pb in placed:
            if who in (f"ref:{c.ref}", f"val:{c.ref}"):
                continue
            if _boxes_overlap(pb, box):
                bad.append({"kind": "ink", "owner": who})
        if bad:
            raise ElkLayoutError(
                "E_ELK_OUTLINE_INK_INSIDE",
                f"{c.ref}: ink lies inside the package outline {list(box)}; refused rather "
                f"than drawing a box that would read as wiring or enclosing foreign items",
                ref=c.ref, conflicts=bad[:8], variant=build.variant)
        pr = props[c.ref]
        cap = [pr.ref_box] + ([pr.val_box] if pr.val_box else [])
        for cb in cap:
            if _boxes_overlap(cb, box):
                raise ElkLayoutError(
                    "E_ELK_OUTLINE_CAPTION_OVERLAP",
                    f"{c.ref}: caption box {list(cb)} overlaps the package outline",
                    ref=c.ref, variant=build.variant)
        outlines[c.ref] = {
            "outline": [round(v, 4) for v in box],
            "caption": [round(min(b[0] for b in cap), 4), round(min(b[1] for b in cap), 4),
                        round(max(b[2] for b in cap), 4), round(max(b[3] for b in cap), 4)],
            "ref_at": list(pr.ref_at), "val_at": list(pr.val_at)}
    sol.outlines = outlines
    sol.props = props
    sol.flags = flags
    sol.local_labels = labels
    sol.label_anchors = {n: lp.at for n, lp in labels.items()}
    sol.fixed_flag_boxes = [{"ref": r, "pin": p, "net": n, "box": [round(v, 3) for v in b]}
                            for r, p, n, b in fixed]
    return {
        "props": {r: {"candidate": p.candidate, "ref_at": list(p.ref_at),
                      "val_at": list(p.val_at)} for r, p in props.items()},
        "flags": {n: {"at": list(f.at), "edge": list(f.edge), "pin": f.pin}
                  for n, f in flags.items()},
        "local_labels": {n: {"at": list(f.at)} for n, f in labels.items()},
        "fixed_flags": len(fixed),
    }


def build_rot(build: ElkGraphBuild, ref: str, pin: str) -> float:
    return build.pin_rot.get((ref, pin), 0.0)


def _foreign_crossings(sol: "PresentationSolution") -> list[dict]:
    return _foreign_crossings_segs(sol.segments)



# --------------------------------------------------------------------------- entry


def _layout_area(sol: "PresentationSolution", build: ElkGraphBuild) -> float:
    xs: list[float] = []
    ys: list[float] = []
    for ss in sol.segments.values():
        for a, b in ss:
            xs += [a[0], b[0]]; ys += [a[1], b[1]]
    for ref, h in ((r, _shift(build.inks[r].hull, *sol.poses[r])) for r in sol.poses):
        xs += [h[0], h[2]]; ys += [h[1], h[3]]
    return round((max(xs) - min(xs)) * (max(ys) - min(ys)), 2) if xs else 0.0


#: Round 4 predeclared placement models (receipt R4.1). "R0" is the comparison
#: baseline (no constraint). `partitions`: ref -> requested layer rank (ELK
#: partitioning); `above`: (upper, lower) within-layer relations to realize.
PLACEMENT_MODELS: tuple[dict, ...] = (
    {"name": "R0", "partitions": {}, "above": ()},
    {"name": "M1-D1-mid", "partitions": {"J1": 0, "D1": 1, "R1": 2, "R2": 2},
     "above": (("R1", "R2"),)},
    {"name": "M2-R1|D1|R2", "partitions": {"J1": 0, "R1": 1, "D1": 2, "R2": 3},
     "above": ()},
)


def realized_placement(sol: "PresentationSolution", build: ElkGraphBuild,
                       model: dict) -> dict:
    """Requested vs realized relationships of one placement model, read back from
    the SOLVED hull boxes (not from the request). `executed` is False when a
    requested layer order is contradicted (the option was ignored)."""
    hulls = {r: _shift(build.inks[r].hull, *sol.poses[r]) for r in sol.poses}
    parts = model.get("partitions") or {}
    rel: list[dict] = []
    ok = True
    refs = sorted(parts, key=lambda r: (parts[r], r))
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            if parts[a] < parts[b]:
                realized = hulls[a][2] <= hulls[b][0] + EPS
                rel.append({"requested": f"{a} layer before {b}", "realized": realized,
                            "hull_x1_a": round(hulls[a][2], 3), "hull_x0_b": round(hulls[b][0], 3)})
                ok = ok and realized
            elif parts[a] == parts[b]:
                same = abs(hulls[a][0] - hulls[b][0]) < GRID_MM * 4 or not (
                    hulls[a][2] <= hulls[b][0] or hulls[b][2] <= hulls[a][0])
                rel.append({"requested": f"{a} and {b} share a layer", "realized": same})
    for up, lo in model.get("above") or ():
        realized = hulls[up][1] < hulls[lo][1]
        rel.append({"requested": f"{up} above {lo}", "realized": realized,
                    "y0_up": round(hulls[up][1], 3), "y0_lo": round(hulls[lo][1], 3)})
        ok = ok and realized
    return {"model": model["name"], "requested_partitions": dict(parts),
            "relations": rel, "executed": ok}


def _pin_order_report(components, geometry, osets) -> dict:
    """Resolved pin order (top to bottom, sheet y-down) of the transformed ref."""
    if not osets:
        return {}
    ref = next(iter(osets))
    g = geometry[ref]
    rows = sorted(g.pins.items(), key=lambda kv: (-kv[1][1], kv[0]))
    return {"ref": ref, "orientation": g.orientation,
            "top_to_bottom": [[pin, round(x, 4), round(y, 4), round(a, 1)]
                              for pin, (x, y, a) in rows]}


def solve_sheet(components: list[EmitComponent], nets: list[EmitNet], *,
                symbol_dir, page_scale: float = 1.0,
                drawn_filter=None, motif_geometries=None,
                timeout_s: float = DEFAULT_TIMEOUT_S,
                layout_options: dict[str, str] | None = None,
                cross_sheet_nets: set[str] | frozenset | None = None,
                variants: tuple[dict, ...] = LAYOUT_VARIANTS,
                orientation_sets: dict[str, tuple[str, ...]] | None = None,
                placement_models: tuple[dict, ...] | None = None,
                outline_refs: frozenset[str] | set[str] | None = None,
                spacing_overrides: dict[str, str] | None = None
                ) -> PresentationSolution:
    """The seam entry: declared topology + symbol library -> ONE validated
    presentation solution (poses, per-net segments, junctions, props, flags,
    local labels).

    A BOUNDED set of ELK option variants (`LAYOUT_VARIANTS`, deterministic order)
    is tried; each is fully verified (connectivity + ink placement). The chosen
    solution has the fewest foreign crossings, then the smallest layout area;
    every variant's outcome is persisted in `variant_log`. A residual foreign
    crossing is DISCLOSED in `foreign_crossings`, never hidden.

    `drawn_filter(net) -> (bool, reason)` is the caller's policy for which nets
    the engine draws (the rest stay label/power continuation). Motif compound
    nodes are a NAMED GAP for this spike: a sheet carrying motif geometry is
    refused rather than flattened.

    `orientation_sets` (round 3): ONE ref -> a predeclared finite tuple of native
    orientation ids (<= 4, identity first, no repeats). Each id is evaluated with the
    caller's `variants`; selection is by (foreign crossings, area, declaration
    order). No other component is transformed and no combination is formed.
    Outcomes of every orientation are persisted in `orientation_sweep`."""
    spacing = dict(spacing_overrides or {})
    bad_sp = sorted(set(spacing) - set(SPACING_OPTION_KEYS))
    if bad_sp:
        raise ElkLayoutError("E_ELK_SPACING_UNKNOWN",
                             f"spacing overrides limited to {sorted(SPACING_OPTION_KEYS)}; got {bad_sp}",
                             keys=bad_sp)
    for k, v in spacing.items():
        q = float(v) / GRID_MM
        if float(v) <= 0 or abs(q - round(q)) > 1e-6:
            raise ElkLayoutError("E_ELK_SPACING_OFF_GRID",
                                 f"spacing {k}={v} must be a positive multiple of {GRID_MM} mm "
                                 f"(grid quantization must stay an identity check)", key=k)
    osets = {r: tuple(ids) for r, ids in (orientation_sets or {}).items()}
    if len(osets) > 1:
        raise ElkLayoutError("E_ELK_ORIENT_SET_INVALID",
                             "orientation sets are bounded to ONE component (no combinations)",
                             refs=sorted(osets))
    for r, ids in osets.items():
        if not ids or ids[0] != "R0" or len(set(ids)) != len(ids) or len(ids) > 4 \
                or any(i not in ORIENTATIONS for i in ids):
            raise ElkLayoutError(
                "E_ELK_ORIENT_SET_INVALID",
                f"{r}: the predeclared set must start with R0, have no repeats, hold at "
                f"most 4 ids and use only {sorted(ORIENTATIONS)}", ref=r, ids=list(ids))
    if motif_geometries:
        raise ElkLayoutError(
            "E_ELK_UNSUPPORTED_MOTIF",
            "rigid motif compound nodes are not implemented in the engine adapter; "
            "the sheet is refused rather than drawn without its motifs",
            motifs=[getattr(g, 'net', '?') for _h, g in motif_geometries])
    if not components:
        raise ElkLayoutError("E_ELK_EMPTY_SHEET", "no components to lay out")
    cross = set(cross_sheet_nets or ())
    use = variants if layout_options is None else (
        {"name": "caller-options", "root": "first", "options": {}},)
    log: list[dict] = []
    ok: list[tuple[tuple, PresentationSolution]] = []
    if osets:
        _ref, _ids = next(iter(osets.items()))
        orient_plan: list[dict[str, str]] = [({_ref: i} if i != "R0" else {}) for i in _ids]
        orient_names = list(_ids)
    else:
        orient_plan, orient_names = [{}], ["R0"]
    pmodels = tuple(placement_models) if placement_models else ({"name": "R0", "partitions": {}, "above": ()},)
    if len(pmodels) > 3:
        raise ElkLayoutError("E_ELK_PLACEMENT_SET_INVALID",
                             "placement models are bounded to a baseline + at most 2", n=len(pmodels))
    plan = [(oi, orients, oname, pm) for oi, (orients, oname) in enumerate(zip(orient_plan, orient_names))
            for pm in pmodels]
    for oi, orients, oname, pm in plan:
      geometry = resolve_symbol_geometry(components, symbol_dir, page_scale, orients)
      for var in use:
        opts = dict(layout_options or DEFAULT_LAYOUT_OPTIONS)
        opts.update(var["options"])
        opts.update(spacing)
        entry = {"orientation": oname, "placement": pm["name"], "variant": var["name"],
                 "options": dict(var["options"]), "root": var["root"]}
        try:
            build = build_elk_graph(components, nets, geometry, drawn_filter=drawn_filter,
                                    layout_options=opts, root=var["root"],
                                    page_scale=page_scale, variant=var["name"],
                                    order=var.get("order", "declared"),
                                    partitions=pm.get("partitions") or None,
                                    outline_refs=frozenset(outline_refs or ()),
                                    cross_sheet_nets=cross)
            solution, receipt = run_elk(build.graph, timeout_s=timeout_s)
            sol = quantize_solution(solution, build, geometry)
            sol.receipt = receipt
            if _r3_enabled("A"):
                _resolve_foreign_collinear_channels(sol, build)
            verify_solution(sol, build)
            entry["realized_placement"] = realized_placement(sol, build, pm)
            if pm.get("partitions") and not entry["realized_placement"]["executed"]:
                entry["status"] = "NOT_EXECUTED:option_ignored"
                log.append(entry)
                continue
            sol.foreign_crossings = _foreign_crossings(sol)
            entry["foreign_crossings"] = list(sol.foreign_crossings)
            entry["area_mm2"] = _layout_area(sol, build)
            entry["wire_length_mm"] = round(sum(abs(a[0] - b[0]) + abs(a[1] - b[1])
                                                for ss in sol.segments.values() for a, b in ss), 2)
            entry["ink"] = place_ink(sol, build, components, cross_sheet_nets=cross,
                                     page_scale=page_scale)
            sol.variant = var["name"]
            sol.placement_model = pm["name"]
            sol.spacing_overrides = dict(spacing)
            sol.orientations = dict(orients)
            entry["orientation_pins"] = _pin_order_report(components, geometry, osets)
            entry["status"] = "ok"
            entry["graph_sha256"] = receipt.graph_sha256
            ok.append(((len(sol.foreign_crossings), entry["area_mm2"], entry["wire_length_mm"], oi, len(log)), sol))
            entry["_sol_id"] = id(sol)
        except ElkLayoutError as error:
            entry["status"] = f"refused:{error.code}"
            entry["detail"] = {k: v for k, v in error.details.items()
                               if k in ("conflicts", "ref", "net", "missing")}
        log.append(entry)
    if not ok:
        raise ElkLayoutError(
            "E_ELK_NO_VALID_VARIANT",
            "every bounded layout variant was refused (connectivity or ink placement); "
            "no legacy fallback", variant_log=log)
    ok.sort(key=lambda t: t[0])
    sol = ok[0][1]
    chosen_o = next(iter(sol.orientations.values()), "R0") if osets else "R0"
    for e in log:
        e["chosen"] = (e.get("_sol_id") == id(sol))
        e.pop("_sol_id", None)
    sol.variant_log = log
    if osets:
        sol.orientation_sweep = {
            "ref": next(iter(osets)), "declared_set": list(next(iter(osets.values()))),
            "chosen": chosen_o,
            "per_orientation": {e["orientation"] + "/" + e["variant"]: {
                "status": e["status"],
                "foreign_crossings": len(e.get("foreign_crossings", [])),
                "area_mm2": e.get("area_mm2"),
                "detail": e.get("detail")} for e in log},
        }
    return sol


__all__ = [
    "DEFAULT_LAYOUT_OPTIONS",
    "ELKJS_PINNED_VERSION",
    "ElkGraphBuild",
    "ElkLayoutError",
    "PresentationSolution",
    "RunnerReceipt",
    "SymbolGeometry",
    "build_elk_graph",
    "LAYOUT_VARIANTS",
    "PLACEMENT_MODELS",
    "SPACING_OPTION_KEYS",
    "realized_placement",
    "place_ink",
    "plan_node_ink",
    "quantize_solution",
    "resolve_symbol_geometry",
    "run_elk",
    "solve_sheet",
    "verify_solution",
    "_resolve_foreign_collinear_channels",
]
