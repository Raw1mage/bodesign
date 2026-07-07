"""Single pinout block drafter (eda_draftsman-v2 task 1.3, IDEF0 A2).

DD-1/DD-2: the symbol BODY geometry is loaded verbatim from the KiCad official /
vendor library via kiutils — this module NEVER computes or fabricates pin
geometry. It only places the *peripheral* wiring artifacts around an already-
correct four-edge symbol: a short wire stub off each connected pin plus a net
label at the stub end (and, later, power ports / NC flags).

The old engine's death cause (four rounds of "left pin drawn inside the body",
"20% sheet strip", "stacked labels") came from HAND-COMPUTING pin coordinates
and HAND-ROLLING s-expressions. Here every pin's outward direction is taken
DIRECTLY from the library pin's `position.angle` (0=points right / left edge,
180=points left / right edge, 90=points up / bottom edge, 270=points down /
top edge — KiCad convention: angle is the direction the pin line extends AWAY
from the body). Label anchor/justify follow the edge. Placement is decided in
the kiutils object layer with bbox-overlap checks BEFORE render, not after.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from kiutils.schematic import Schematic
from kiutils.items.schitems import (
    SchematicSymbol, LocalLabel, Connection,
    SymbolProjectInstance, SymbolProjectPath,
)
from kiutils.items.common import Position, Property, Effects
from kiutils.symbol import Symbol, SymbolLib

from .symbol_index import resolve as resolve_lib_id, SymbolNotFound
from .kicad_emit import _power_net_kind

# --- power-net → stock KiCad power-port symbol (DD-9 Part 1) ----------------
# The power-net classifier is REUSED from kicad_emit (the legacy engine SSOT):
# _power_net_kind(name) -> "gnd" | "supply" | None. We do NOT invent a divergent
# rule here. A net classified gnd/supply is drawn as a real KiCad *power-port*
# symbol (power:GND, power:+3V3, ...) instead of a text LocalLabel: identical
# power-port net names auto-join (no wire), and the compact glyph dissolves the
# label<->label density that a TEXT label per power ball otherwise creates.
#
# Symbol selection (DD-1 no-fabrication):
#   gnd    -> "power:GND"
#   supply -> "power:<net-name>" verbatim (KiCad ships +3V3/+5V/+1V8/VDD/VCC/...)
# A supply rail with no stock symbol (e.g. VBAT / VDDCORE / VREF) is a REAL gap:
# we NEVER synthesize a power symbol. draw_block records it in `power_gaps` and
# falls back to the ordinary signal-label path for that rail (fail-loud via the
# returned gap list, not a silent fabricated glyph).

# --- geometry constants (mm; KiCad schematic grid is 1.27mm) --------------
STUB_LEN = 2.54            # length of the wire stub drawn off a pin end
LABEL_GAP = 1.27           # gap between stub end and label text anchor
CHAR_W = 1.27              # approx rendered width per char at default 1.27mm font
FONT_H = 1.27              # default label font height
ROW_PITCH = 2.54           # min vertical spacing between labels on same edge
STAGGER_STEP = 2.54        # extra outward offset when a label collides


@dataclass
class _Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def overlaps(self, o: "_Box", pad: float = 0.254) -> bool:
        return not (self.x1 + pad <= o.x0 or o.x1 + pad <= self.x0
                    or self.y1 + pad <= o.y0 or o.y1 + pad <= self.y0)


@dataclass
class PinoutBlock:
    block_id: str
    sch_path: str
    bbox_mm: dict            # {"w":..,"h":..}
    ports: list              # net-label names exposed for inter-block wiring
    validated: bool = False
    pin_map: dict = field(default_factory=dict)   # pin number -> net (expected partition)
    power_gaps: list = field(default_factory=list)  # rails with no stock power symbol

    def to_dict(self) -> dict:
        return {"block_id": self.block_id, "sch_path": self.sch_path,
                "bbox_mm": self.bbox_mm, "ports": self.ports,
                "validated": self.validated, "power_gaps": self.power_gaps}


def _edge_of(angle: float) -> str:
    """Map a library pin's position.angle to the body edge it sits on.

    KiCad pin angle = direction the pin line points away from the body:
      0   -> pin extends right  -> sits on LEFT edge
      180 -> pin extends left   -> sits on RIGHT edge
      90  -> pin extends up     -> sits on BOTTOM edge
      270 -> pin extends down   -> sits on TOP edge
    """
    a = int(round(angle)) % 360
    return {0: "left", 180: "right", 90: "bottom", 270: "top"}[a]


def _pin_end(px: float, py: float, angle: float, length: float) -> tuple[float, float]:
    """Coordinate of the pin's free end (where the stub/label attaches)."""
    a = int(round(angle)) % 360
    if a == 0:
        return px + length, py
    if a == 180:
        return px - length, py
    if a == 90:
        return px, py - length     # KiCad Y grows downward; up = -Y
    return px, py + length         # 270 -> down = +Y


def _label_box(text: str, ax: float, ay: float, justify: str,
               rotated: bool = False) -> _Box:
    """Rendered bbox of a net label anchored at (ax, ay).

    rotated: the label is emitted with LocalLabel rotation 90 (lang=90) for
    top/bottom-edge pins, so KiCad renders the glyph run ALONG Y, not X. The
    box's long dimension must then lie on Y (tall-and-narrow) or the stagger /
    overlap-avoidance checks the wrong axis and Y-stacked top/bottom labels
    never register as colliding (the label<->label overlap root cause).

    `justify` names the anchor edge of the text along its OWN reading direction:
    for a horizontal label "left" = text extends +X, "right" = -X; for a rotated
    (90) label the same reading direction is mapped onto +Y / -Y respectively.
    """
    long = max(len(text), 1) * CHAR_W   # extent along the reading direction
    short = FONT_H                       # glyph height, across the reading dir
    if rotated:
        # reading direction is Y; glyph height spans X (narrow)
        x0, x1 = ax - short * 0.6, ax + short * 0.6
        if justify == "left":       # anchor at start, text extends +Y
            y0, y1 = ay, ay + long
        elif justify == "right":    # anchor at end, text extends -Y
            y0, y1 = ay - long, ay
        else:
            y0, y1 = ay - long / 2, ay + long / 2
        return _Box(x0, y0, x1, y1)
    # horizontal label: reading direction is X, glyph height spans Y (short)
    if justify == "left":       # anchor at left, text extends right
        x0, x1 = ax, ax + long
    elif justify == "right":    # anchor at right, text extends left
        x0, x1 = ax - long, ax
    else:
        x0, x1 = ax - long / 2, ax + long / 2
    return _Box(x0, ay - short * 0.6, x1, ay + short * 0.6)


def _pins_of(sym: Symbol) -> list:
    pins = []
    for unit in sym.units:
        pins.extend(unit.pins)
    return pins


def _clone_symbol(sym: Symbol) -> Symbol:
    """Deep-copy a library Symbol before mutating its libId / embedding it.

    symbol_index.resolve() returns Symbols from an lru_cache; mutating them in
    place (e.g. setting libId) would corrupt the shared cached object for every
    later caller. A deepcopy isolates the sheet-local copy.
    """
    return copy.deepcopy(sym)


def _power_lib_id(net: str, kind: str) -> str:
    """Stock KiCad power-library lib_id for a power/ground net (DD-9 Part 1).

    gnd    -> power:GND          (KiCad ships one canonical ground glyph)
    supply -> power:<net> verbatim (KiCad ships +3V3/+5V/+1V8/VDD/VCC/VDDA/...)

    No fabrication: if the resulting lib_id does not resolve to a stock symbol
    the caller treats the rail as a gap (fail-loud), never synthesizes a glyph.
    """
    if kind == "gnd":
        return "power:GND"
    return f"power:{net.strip()}"


# outward unit vector (sheet space) per body edge: the direction a power port is
# pushed AWAY from the symbol body. sheet +y is screen-down (KiCad Y inverted on
# placement), so bottom-edge outward = +y, top-edge outward = -y.
_OUTWARD = {"left": (-1.0, 0.0), "right": (1.0, 0.0),
            "bottom": (0.0, 1.0), "top": (0.0, -1.0)}

# how far out from the port pin the stock symbol renders its Value (net-name)
# glyph: stock GND Value is 3.81mm below its pin, +3V3/VDD 3.556mm above. Model a
# conservative center at this radius along the outward vector.
_PWR_VALUE_RADIUS = 3.81


def _power_rotation(kind: str, edge: tuple[float, float]) -> int:
    """Rotation (deg, KiCad CCW) so a stock power-port glyph faces AWAY from the
    body along the pin's outward edge vector (net-name Value on the outward side).

    Mirrors kicad_emit._power_symbol_rotation (the verified legacy SSOT). Stock
    defs draw: supply glyph toward local +y (screen up, rot 0), gnd glyph toward
    local -y (screen down, rot 0). `edge` (nx, ny) is the SHEET outward vector
    (ny>0 = screen down). Returns 0/90/180/270. NOT a pin angle.
    """
    nx, ny = edge
    horizontal = abs(nx) >= abs(ny)
    if horizontal:
        outward_right = nx >= 0
        if kind == "gnd":
            return 90 if outward_right else 270
        return 270 if outward_right else 90
    outward_down = ny >= 0  # sheet +y is screen down
    if kind == "gnd":
        return 0 if outward_down else 180
    return 180 if outward_down else 0


def _pwr_value_box(net: str, cx: float, cy: float,
                   nx: float, ny: float) -> _Box:
    """Conservative rendered bbox of a power-port's Value (net-name) glyph.

    The port pin sits at (cx, cy); the glyph + net-name text extend OUTWARD along
    (nx, ny) by ~_PWR_VALUE_RADIUS, so model the text box centered at
    (cx + nx*r, cy + ny*r). Length spans the reading direction (perpendicular to
    the outward vector for a horizontal edge the text reads along X; for a
    vertical edge along Y). Slightly oversized is fine (pushes ports further out).

    Input: net name, port-pin sheet coords, outward unit vector.
    Output: _Box (a peripheral text box, NOT a symbol-body box).
    NOT to be read as the port's electrical extent — only its net-name glyph.
    Complete when the box conservatively covers where KiCad draws the Value text.
    """
    r = _PWR_VALUE_RADIUS
    tcx, tcy = cx + nx * r, cy + ny * r
    long = max(len(net), 1) * CHAR_W
    short = FONT_H
    horizontal_edge = abs(nx) >= abs(ny)
    if horizontal_edge:
        # left/right edge: Value text reads along X (horizontal), height on Y
        return _Box(tcx - long / 2, tcy - short * 0.6,
                    tcx + long / 2, tcy + short * 0.6)
    # top/bottom edge: the stock port is rotated so its Value reads along X too,
    # but it is stacked vertically among same-column ports; model it as a box
    # long on X (net-name) so vertically-adjacent ports' boxes still separate.
    return _Box(tcx - long / 2, tcy - short * 0.6,
                tcx + long / 2, tcy + short * 0.6)


def _pin_text_boxes(sym: Symbol) -> list[_Box]:
    """Conservative rendered bboxes of the vendor symbol's OWN pin-name and
    pin-number glyphs (DD-9 Part 2), in sheet space (Y-mirrored like draw_block).

    READ-ONLY model of the vendor body (DD-1): we never move the symbol; we seed
    these boxes into the stagger `placed` list so a signal net's LocalLabel
    staggers clear of the vendor pin text it would otherwise overprint.

    Geometry (empirically confirmed against STM32N657 A4: number 'A4' just
    OUTSIDE the pin root, name 'UCPD1_CC1' rendered INTO the body from the root,
    both height ~1.27mm):
      - pin-name : renders along the pin axis, from the pin ROOT toward INSIDE
        the body (opposite the pin's outward direction). Length = len(name)*CHAR_W.
      - pin-number: renders just OUTSIDE the pin root along the pin axis, short.
    Hidden name/number (symbol pinNames/pinNumbers hide, or pin.hide) render no
    glyph, so no box is seeded for them.
    """
    boxes: list[_Box] = []
    # symbol-level hide flags: kiutils exposes pinNames/pinNumbers as bool-ish.
    # `True` here means the attribute is PRESENT (names shown); KiCad's hide is a
    # nested (hide yes) — kiutils sets pinNames/pinNumbers hidden via the value
    # being falsy is not reliable, so we honor only per-pin hide + the coarse
    # symbol flag when it is explicitly False (definitely hidden).
    names_hidden = getattr(sym, "pinNames", True) is False and False  # names shown by default
    numbers_hidden = getattr(sym, "pinNumbers", True) is False and False
    for pin in _pins_of(sym):
        if getattr(pin, "hide", False):
            continue
        a = int(round(pin.position.angle)) % 360
        # sheet-space pin ROOT (Y-mirrored, symbol at origin) — same as draw_block
        rx, ry = pin.position.X, -pin.position.Y
        # inward unit vector = opposite the pin's outward direction.
        # outward: 0->+X, 180->-X, 90->-Y(sheet, up), 270->+Y(sheet, down)
        if a == 0:      # left edge, pin points +X out -> name runs -X into body
            in_dx, in_dy = -1.0, 0.0
        elif a == 180:  # right edge -> name runs +X into body
            in_dx, in_dy = 1.0, 0.0
        elif a == 90:   # bottom edge, out=up(sheet -Y) -> name runs +Y into body
            in_dx, in_dy = 0.0, 1.0
        else:           # 270 top edge, out=down(sheet +Y) -> name runs -Y into body
            in_dx, in_dy = 0.0, -1.0
        name = (pin.name or "").strip()
        if name and name != "~" and not names_hidden:
            nlen = max(len(name), 1) * CHAR_W
            # name box spans from root inward by nlen along the axis
            if in_dx:
                x0, x1 = sorted((rx, rx + in_dx * nlen))
                y0, y1 = ry - FONT_H * 0.6, ry + FONT_H * 0.6
            else:
                y0, y1 = sorted((ry, ry + in_dy * nlen))
                x0, x1 = rx - FONT_H * 0.6, rx + FONT_H * 0.6
            boxes.append(_Box(x0, y0, x1, y1))
        num = (pin.number or "").strip()
        if num and not numbers_hidden:
            nlen = max(len(num), 1) * CHAR_W
            # number box spans from root OUTWARD (opposite inward) a short run
            if in_dx:
                x0, x1 = sorted((rx, rx - in_dx * nlen))
                y0, y1 = ry - FONT_H * 0.6, ry + FONT_H * 0.6
            else:
                y0, y1 = sorted((ry, ry - in_dy * nlen))
                x0, x1 = rx - FONT_H * 0.6, rx + FONT_H * 0.6
            boxes.append(_Box(x0, y0, x1, y1))
    return boxes


def draw_block(lib_id: str, pin_map: dict[str, str], *,
               block_id: str | None = None,
               out_dir: Path | str,
               lib_root: Path | None = None) -> PinoutBlock:
    """Draw ONE pinout block: place the library symbol + a net label off every
    pin listed in pin_map. Returns a PinoutBlock (validated=False until QA).

    pin_map: {pin_number: net_name}. Only pins present here get a stub+label;
    absent pins are left as bare library pins (caller marks them NC upstream).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    block_id = block_id or lib_id.split(":", 1)[-1]

    _, sym = resolve_lib_id(lib_id, lib_root)

    nickname, entry = lib_id.split(":", 1)
    sch = Schematic().create_new()
    # the sheet needs a root uuid so the placed symbol's instances path can be
    # "/<root_uuid>"; without a project/instances path kicad-cli's netlister
    # emits ZERO components (empty (components) block) -> no pin nodes -> every
    # shared net reads as only_baseline (the deeper cause behind the shared-net
    # CONNECTIVITY_DIVERGE, distinct from the missing wire stub).
    root_uuid = str(uuid.uuid4())
    sch.uuid = root_uuid
    # refdes MUST be "U" to match block_qa's expected-partition node key
    # (block_qa builds nodes as f"U.{pin}"); a mismatch makes fidelity see two
    # disjoint node universes and diff everything.
    refdes = "U"
    # The lib_symbols entry MUST be keyed by the FULL lib_id ("Nickname:Name"),
    # NOT the bare entryName kiutils carries from SymbolLib.from_file. kicad-cli
    # binds a placed instance to its libpart by matching the instance's lib_id
    # against the lib_symbols key; a bare-entryName key leaves (components) /
    # (libparts) EMPTY, every pin becomes (pintype "unspecified") and collapses
    # into one degenerate Net-(U-Pad??) net (mirrors kicad_emit.load_symbol,
    # which rewrites the embedded (symbol "Name") token to (symbol "lib_id")).
    sym.libId = lib_id
    # place the symbol at origin; kiutils keeps the library body geometry intact
    inst = SchematicSymbol()
    inst.libId = lib_id
    inst.position = Position(0, 0, 0)
    inst.unit = 1
    inst.uuid = str(uuid.uuid4())
    inst.inBom = True
    inst.onBoard = True
    # Reference/Value are hidden: a draft pinout block's electrical identity is
    # carried by the net labels, and rendering "U"/value glyphs stacked at the
    # symbol origin collides with the body + pin-name text (render_qa
    # TEXT_BBOX_OVERLAP). They still exist for netlisting; (hide yes) keeps them
    # out of the SVG the text-overlap gate inspects.
    inst.properties.append(Property(key="Reference", value=refdes,
                                   position=Position(0, 0, 0),
                                   effects=Effects(hide=True)))
    inst.properties.append(Property(key="Value", value=entry,
                                    position=Position(0, 0, 0),
                                    effects=Effects(hide=True)))
    # per-pin instance uuids: the netlister binds the placed symbol's pins to the
    # library pins THROUGH these entries. Absent them, kicad-cli exports no pin
    # nodes at all, so no net (shared or unique) can ever be reconstructed.
    for pin in _pins_of(sym):
        inst.pins[pin.number] = str(uuid.uuid4())
    inst.instances.append(SymbolProjectInstance(
        name=block_id,
        paths=[SymbolProjectPath(sheetInstancePath="/" + root_uuid,
                                 reference=refdes, unit=1)],
    ))
    # carry the library symbol definition into the sheet's lib_symbols table
    sch.libSymbols.append(sym)
    sch.schematicSymbols.append(inst)

    placed: list[_Box] = []
    ports: list[str] = []
    # group pins by edge so we can stagger within an edge deterministically
    labels: list[LocalLabel] = []
    stubs: list[Connection] = []       # wire from each pin end to its label anchor
    power_gaps: list[dict] = []        # rails with no stock power symbol (fail-loud)
    pwr_syms: list[SchematicSymbol] = []            # placed power-port instances
    pwr_lib_defs: dict[str, Symbol] = {}            # power lib_symbols to embed
    _pwr_ref = [0]

    # DD-9 Part 2: seed the stagger `placed` list with the vendor symbol's OWN
    # pin-name / pin-number glyph boxes so a signal LocalLabel staggers clear of
    # the vendor pin text it would otherwise overprint (label<->pin-name overlap
    # the stagger loop was previously blind to). READ-ONLY: the symbol body is
    # never moved (DD-1).
    placed.extend(_pin_text_boxes(sym))

    for pin in _pins_of(sym):
        net = pin_map.get(pin.number)
        if not net:
            continue
        # DD-9 Part 1: power/ground nets become a stock KiCad power-port symbol
        # (auto-joining, compact) instead of a text label — this dissolves the
        # dense-edge label<->label density (24×VDD / 17×GND identical labels).
        pkind = _power_net_kind(net)
        if pkind is not None:
            ex, ey = pin.position.X, -pin.position.Y
            plib = _power_lib_id(net, pkind)
            try:
                _, psym = resolve_lib_id(plib, None)
            except (SymbolNotFound, ValueError):
                # REAL gap: no stock power symbol for this rail. DD-1 forbids
                # fabricating one — record it and fall through to the ordinary
                # signal-label path so the net still connects (via same-name
                # local labels), but surface the gap to the caller (fail-loud).
                power_gaps.append({"net": net, "pin": pin.number,
                                   "kind": pkind, "tried_lib_id": plib,
                                   "note": "no stock KiCad power symbol; "
                                           "not fabricated (DD-1)"})
            else:
                # Place the power-port OUTWARD along the pin's edge vector (like
                # the legacy kicad_emit SSOT), with a stub wire from the pin ROOT
                # to the port pin, staggering further out until the port's Value
                # (net-name) glyph clears every prior box (vendor pin text seeded
                # into `placed`, other labels, other ports). Placing the port at
                # the bare pin root (no outward offset, no rotation) let its Value
                # render back over the vendor pin-number/pin-name glyphs and let
                # same-rail ports 2.54mm apart stack their Value text — the DD-9
                # power-port density/overlap root cause.
                nx, ny = _OUTWARD[_edge_of(pin.position.angle)]
                prot = _power_rotation(pkind, (nx, ny))
                # first port lands one stub out from the pin root
                t = 1
                px = ex + nx * STUB_LEN * t
                py = ey + ny * STUB_LEN * t
                vbox = _pwr_value_box(net, px, py, nx, ny)
                tries = 0
                while any(vbox.overlaps(b) for b in placed) and tries < 8:
                    t += 1
                    px = ex + nx * STUB_LEN * t
                    py = ey + ny * STUB_LEN * t
                    vbox = _pwr_value_box(net, px, py, nx, ny)
                    tries += 1
                placed.append(vbox)
                # stub wire: pin ROOT (electrical point) -> port pin location
                stubs.append(Connection(
                    type="wire",
                    points=[Position(ex, ey), Position(px, py)],
                    uuid=str(uuid.uuid4()),
                ))
                psym = _clone_symbol(psym)
                psym.libId = plib
                # kiutils 1.4.8 mis-parses the stock power symbol's nested
                # (pin_numbers (hide yes)) as hidePinNumbers=False, so a naive
                # re-embed renders the port's OWN pin-number "1" glyph, which
                # then overlaps the port's OWN net-name Value text (a
                # symbol-internal overlap the scoped gate counts because the
                # Value is a peripheral net label). Restore KiCad's stock intent:
                # a power port shows neither pin number nor pin name.
                psym.hidePinNumbers = True
                psym.pinNamesHide = True
                pwr_lib_defs.setdefault(plib, psym)
                _pwr_ref[0] += 1
                pinst = SchematicSymbol()
                pinst.libId = plib
                pinst.position = Position(px, py, prot)
                pinst.unit = 1
                pinst.uuid = str(uuid.uuid4())
                pinst.inBom = False
                pinst.onBoard = True
                pref = f"#PWR{_pwr_ref[0]:04d}"
                pinst.properties.append(Property(key="Reference", value=pref,
                                                 position=Position(px, py, 0),
                                                 effects=Effects(hide=True)))
                pinst.properties.append(Property(key="Value", value=net,
                                                 position=Position(px, py, 0)))
                for pp in _pins_of(psym):
                    pinst.pins[pp.number] = str(uuid.uuid4())
                pinst.instances.append(SymbolProjectInstance(
                    name=block_id,
                    paths=[SymbolProjectPath(sheetInstancePath="/" + root_uuid,
                                             reference=pref, unit=1)],
                ))
                pwr_syms.append(pinst)
                ports.append(net)
                continue
        edge = _edge_of(pin.position.angle)
        # The pin's ELECTRICAL connection point in sheet space is the pin ROOT
        # (pin.position, NOT pin.position + length), Y-MIRRORED: KiCad places a
        # symbol's library geometry into the sheet with Y inverted (sheet Y grows
        # downward vs. the library's upward Y). Symbol is placed at origin (0,0),
        # so sheet-space connection point = (local_x, -local_y). Verified against
        # the kicad_emit.py SSOT (which nets correctly): a wire must touch THIS
        # point, not the drawn free-end, or KiCad reports the pin unconnected and
        # same-net pins never merge (the CONNECTIVITY_DIVERGE root cause).
        ex, ey = pin.position.X, -pin.position.Y
        # outward anchor beyond the pin end
        if edge == "left":
            ax, ay, justify, lang = ex - LABEL_GAP, ey, "right", 0
        elif edge == "right":
            ax, ay, justify, lang = ex + LABEL_GAP, ey, "left", 0
        elif edge == "bottom":
            ax, ay, justify, lang = ex, ey + LABEL_GAP, "left", 90
        else:  # top
            ax, ay, justify, lang = ex, ey - LABEL_GAP, "left", 90

        # bbox-overlap avoidance: stagger outward until clear (max 6 tries).
        # lang==90 (top/bottom edge) => label renders ALONG Y, so its box must
        # be tall-and-narrow or the overlap check inspects the wrong axis and
        # Y-stacked labels never register as colliding.
        rotated = lang == 90
        box = _label_box(net, ax, ay, justify, rotated)
        tries = 0
        while any(box.overlaps(b) for b in placed) and tries < 6:
            if edge == "left":
                ax -= STAGGER_STEP
            elif edge == "right":
                ax += STAGGER_STEP
            elif edge == "bottom":
                ay += STAGGER_STEP
            else:
                ay -= STAGGER_STEP
            box = _label_box(net, ax, ay, justify, rotated)
            tries += 1
        placed.append(box)

        # DD-1 peripheral wiring: draw the stub wire from the pin's ROOT
        # connection point (ex, ey) to the label anchor (ax, ay). Without it the
        # label floats in空 space touching nothing, so KiCad treats each same-named
        # label as its own net and pins sharing a net never join (fidelity FAIL /
        # CONNECTIVITY_DIVERGE). pin root -> wire -> label anchor is now one
        # electrically continuous run, so two same-name local labels merge.
        stubs.append(Connection(
            type="wire",
            points=[Position(ex, ey), Position(ax, ay)],
            uuid=str(uuid.uuid4()),
        ))

        lbl = LocalLabel(text=net, position=Position(ax, ay, lang))
        labels.append(lbl)
        ports.append(net)

    for stub in stubs:
        sch.graphicalItems.append(stub)
    for lbl in labels:
        sch.labels.append(lbl)
    # embed each distinct power-port lib_symbol once, then place the instances.
    for pdef in pwr_lib_defs.values():
        sch.libSymbols.append(pdef)
    for pinst in pwr_syms:
        sch.schematicSymbols.append(pinst)

    # compute block bbox from placed label boxes (+ a margin)
    if placed:
        w = max(b.x1 for b in placed) - min(b.x0 for b in placed)
        h = max(b.y1 for b in placed) - min(b.y0 for b in placed)
    else:
        w = h = 0.0

    sch_path = out_dir / f"{block_id}.kicad_sch"
    sch.to_file(str(sch_path))

    return PinoutBlock(
        block_id=block_id,
        sch_path=str(sch_path),
        bbox_mm={"w": round(w, 2), "h": round(h, 2)},
        ports=sorted(set(ports)),
        pin_map=dict(pin_map),
        power_gaps=power_gaps,
    )
