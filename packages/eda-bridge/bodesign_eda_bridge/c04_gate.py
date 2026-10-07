"""C04 placement gate (GATE-C04-01..05), core side: pure python + optional kicad-cli.

Spec: plans/eda-bridge_unified-collaborative-rebuild/c04-entry-freeze-20261007.md section 4.4
(GATE-C04-01..05) and amendment-presentation-authority-20261006.md DD-C04 (d).

Naming: the python symbol / MCP tool is ``c04_placement_geometry_gate`` / ``bodesign_c04_placement_geometry_gate``.
``c04_placement_gate`` is a LANDED gate.py verb (GATE.VERBS); its former MCP name must keep returning
TOOL_LANDED, so this tool must not take that name.

GATE-C04-02 reuse: reused BY CONVENTION, not by import. ``drc_gate`` / ``placement_preflight`` are
pcbnew-bound and ``drc_gate`` has no courtyard class, so this module shells out to
``kicad-cli pcb drc --format json`` (the same CLI ``drc_gate`` uses) and counts ``courtyards_overlap``.

Honesty rules (AGENTS.md section 2):
* No silent fallback. A missing input field, a missing Edge.Cuts outline or a footprint
  without a courtyard raises ``C04GateInputError`` listing every gap; geometry is never
  defaulted.
* GATE-C04-02 needs ``kicad-cli``. When it is absent, or its report cannot be produced,
  the gate is ``unmeasured`` with a reason. It is never ``pass``.
* GATE-C04-05 (copper connectivity / Gerber parity) is ALWAYS ``unmeasured`` here: this is a
  placement-only gate and a placed, unrouted board must never convert to a copper PASS.
* ``ok`` is true only when GATE-C04-01..04 are all ``pass``. Unmeasured gates are listed in
  ``unmeasured_gates`` and never read as pass.

Geometry model (declared limits, not hidden):
* Courtyard = one axis-aligned bbox over every F.CrtYd/B.CrtYd graphic of the footprint after
  its rotation. Arcs contribute start/mid/end points only.
* Pad = axis-aligned bbox of the pad ``size`` rotated by the pad's stored (absolute) angle.
  Custom pad primitives are not expanded.
* Edge.Cuts = footprint-external ``gr_line/gr_rect/gr_poly/gr_circle/gr_arc`` (circles and arcs
  are polylines). Edge.Cuts graphics inside footprints are NOT read.
* Keepout box = ``x,y`` is the minimum corner, ``w,h`` extents (mm, board coordinates). Touching
  counts as intersecting (conservative).
* Footprint-local coordinates are used as stored; back-side footprints are not re-mirrored.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

GATE_IDS = ("GATE-C04-01", "GATE-C04-02", "GATE-C04-03", "GATE-C04-04", "GATE-C04-05",
            "GATE-C04-06", "GATE-C04-07")
DEFAULT_EDGE_MARGIN_MM = 0.40
DEFAULT_SILK_CLEARANCE_MM = 0.15
DEFAULT_COURTYARD_GAP_MM = 0.25
# GATE-C04-06 examines reference text on these layers by default. The btdongle r1 specimen keeps every
# Reference on F.Fab (none on silk), so a silk-only default would examine zero texts there.
DEFAULT_REF_TEXT_LAYERS = ("F.SilkS", "B.SilkS", "F.Fab", "B.Fab")
# KiCad 9.0.9 stroke font, MEASURED through pcbnew (FOOTPRINT.Reference().GetBoundingBox()) at size 1.0 mm:
# per-glyph advance in units of text width. Characters outside this table make that text item unmeasured.
_GLYPH_ADV = {
    'A': 0.8571, 'B': 1.0, 'C': 1.0, 'D': 1.0, 'E': 0.9048, 'F': 0.8571, 'G': 1.0, 'H': 1.0476, 'I': 0.4762,
    'J': 0.7619, 'K': 1.0, 'L': 0.8095, 'M': 1.1429, 'N': 1.0476, 'O': 1.0476, 'P': 1.0, 'Q': 1.0476, 'R': 1.0,
    'S': 0.9524, 'T': 0.7619, 'U': 1.0476, 'V': 0.8571, 'W': 1.1429, 'X': 0.9524, 'Y': 0.8571, 'Z': 0.9524,
    'a': 0.9048, 'b': 0.9048, 'c': 0.8571, 'd': 0.9048, 'e': 0.8571, 'f': 0.5714, 'g': 0.9048, 'h': 0.9048,
    'i': 0.4762, 'j': 0.4762, 'k': 0.8095, 'l': 0.5238, 'm': 1.3333, 'n': 0.9048, 'o': 0.9048, 'p': 0.9048,
    'q': 0.9048, 'r': 0.619, 's': 0.8095, 't': 0.5714, 'u': 0.9048, 'v': 0.7619, 'w': 1.0476, 'x': 0.8095,
    'y': 0.7619, 'z': 0.8095, '0': 0.9524, '1': 0.9524, '2': 0.9524, '3': 0.9524, '4': 0.9524, '5': 0.9524,
    '6': 0.9524, '7': 0.9524, '8': 0.9524, '9': 0.9524, '_': 0.7619, '-': 1.2381, '+': 1.2381, '.': 0.4762,
    '/': 1.0476, '(': 0.6667, ')': 0.6667, '#': 1.0, '*': 0.7619, ':': 0.4762, ',': 0.4762,
}
_EPS = 1e-9
_KEEPOUT_LAYERS = ("F.Cu", "B.Cu")


class C04GateInputError(ValueError):
    """Explicit, fail-fast input/geometry error (never a silent default)."""


# --------------------------------------------------------------------------- s-expression
_TOK = re.compile(r'\s+|\(|\)|"((?:[^"\\]|\\.)*)"|[^\s()"]+')


def parse_sexpr(text: str) -> list:
    """Parse KiCad s-expression text into nested lists of str. Unbalanced or stray input raises."""
    stack: list[list] = [[]]
    pos = 0
    for m in _TOK.finditer(text):
        if m.start() != pos:
            raise C04GateInputError(f"C04_GATE_SEXPR: unparseable text at offset {pos}")
        pos = m.end()
        t = m.group(0)
        if t[0].isspace():
            continue
        if t == "(":
            node: list = []
            stack[-1].append(node)
            stack.append(node)
        elif t == ")":
            if len(stack) < 2:
                raise C04GateInputError(f"C04_GATE_SEXPR: unbalanced ')' at offset {m.start()}")
            stack.pop()
        elif t[0] == '"':
            stack[-1].append(m.group(1).replace('\\"', '"').replace("\\\\", "\\"))
        else:
            stack[-1].append(t)
    if pos != len(text):
        raise C04GateInputError(f"C04_GATE_SEXPR: unparseable text at offset {pos}")
    if len(stack) != 1:
        raise C04GateInputError("C04_GATE_SEXPR: unbalanced '(' (unterminated block)")
    return stack[0]


def _kids(node: list, name: str) -> list[list]:
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def _kid(node: list, name: str) -> list | None:
    for c in node:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def _f(x: Any, what: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        raise C04GateInputError(f"C04_GATE_BOARD_FIELD: {what} is not a number: {x!r}") from None


# ------------------------------------------------------------------------------- geometry
def _rot(x: float, y: float, deg: float) -> tuple[float, float]:
    """KiCad convention (y down, positive angle = counter-clockwise on screen)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return x * c + y * s, -x * s + y * c


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _union(a: tuple, b: tuple) -> tuple:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _boxes_hit(a: tuple, b: tuple) -> bool:
    return a[0] <= b[2] + _EPS and b[0] <= a[2] + _EPS and a[1] <= b[3] + _EPS and b[1] <= a[3] + _EPS


def _pt_seg(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _seg_cross(a, b, c, d) -> bool:
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = o(a, b, c), o(a, b, d), o(c, d, a), o(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def _seg_seg(a, b, c, d) -> float:
    if _seg_cross(a, b, c, d):
        return 0.0
    return min(_pt_seg(*a, *c, *d), _pt_seg(*b, *c, *d), _pt_seg(*c, *a, *b), _pt_seg(*d, *a, *b))


def _inside(box: tuple, p: tuple[float, float]) -> bool:
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def _box_seg_distance(box: tuple, seg: tuple) -> float:
    a, b = (seg[0], seg[1]), (seg[2], seg[3])
    if _inside(box, a) or _inside(box, b):
        return 0.0
    corners = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    return min(_seg_seg(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _point_in_outline(p: tuple[float, float], segs: list[tuple]) -> bool:
    """Even-odd ray cast over every Edge.Cuts segment (handles internal cutouts)."""
    x, y = p
    hit = False
    for x1, y1, x2, y2 in segs:
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                hit = not hit
    return hit


def _arc_points(s, m, e, steps: int = 24) -> list[tuple[float, float]]:
    ax, ay = s
    bx, by = m
    cx, cy = e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [s, e]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a_s, a_m, a_e = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, m, e))
    two = 2 * math.pi
    ccw_m = (a_m - a_s) % two
    ccw_e = (a_e - a_s) % two
    sweep = ccw_e if ccw_m <= ccw_e else ccw_e - two
    return [(ux + r * math.cos(a_s + sweep * i / steps), uy + r * math.sin(a_s + sweep * i / steps))
            for i in range(steps + 1)]


# ---------------------------------------------------------------------------- board / netlist
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path: Any, arg: str, suffix: str) -> str:
    if not isinstance(path, str) or not path:
        raise C04GateInputError(f"C04_GATE_INPUT_MISSING: {arg} is required (non-empty path string)")
    if not os.path.isfile(path):
        raise C04GateInputError(f"C04_GATE_INPUT_NOT_FOUND: {arg}={path!r} does not exist or is not a file")
    if not path.endswith(suffix):
        raise C04GateInputError(f"C04_GATE_INPUT_SUFFIX: {arg}={path!r} must end with {suffix}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _xy(node: list | None, what: str) -> tuple[float, float]:
    if node is None or len(node) < 3:
        raise C04GateInputError(f"C04_GATE_BOARD_FIELD: missing coordinate {what}")
    return _f(node[1], what), _f(node[2], what)


def _net_name(node: list | None) -> str:
    if not node or len(node) < 2:
        return ""
    return node[2] if len(node) >= 3 else node[1]


def _fp_ref(fp: list) -> str:
    for p in _kids(fp, "property"):
        if len(p) >= 3 and p[1] == "Reference":
            return p[2]
    for t in _kids(fp, "fp_text"):
        if len(t) >= 3 and t[1] == "reference":
            return t[2]
    return ""


def _graphic_points(g: list) -> list[tuple[float, float]]:
    k = g[0]
    if k in ("fp_line", "fp_rect"):
        return [_xy(_kid(g, "start"), k + ".start"), _xy(_kid(g, "end"), k + ".end")]
    if k == "fp_poly":
        pts = _kid(g, "pts")
        return [_xy(c, "fp_poly.xy") for c in (pts or []) if isinstance(c, list) and c and c[0] == "xy"]
    if k == "fp_circle":
        cx, cy = _xy(_kid(g, "center"), "fp_circle.center")
        ex, ey = _xy(_kid(g, "end"), "fp_circle.end")
        r = math.hypot(ex - cx, ey - cy)
        return [(cx - r, cy - r), (cx + r, cy + r)]
    if k == "fp_arc":
        return [_xy(_kid(g, n), "fp_arc." + n) for n in ("start", "mid", "end")]
    return []


def _graphic_segments(g: list) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Footprint-local segments of one courtyard graphic. Rect/poly are closed; a circle is an
    inscribed 48-gon (max radial error r*(1-cos(pi/48)) ~ 0.2% of r); an arc is a 24-step polyline."""
    k = g[0]
    if k == "fp_line":
        return [(_xy(_kid(g, "start"), "fp_line.start"), _xy(_kid(g, "end"), "fp_line.end"))]
    if k == "fp_rect":
        (x1, y1), (x2, y2) = _xy(_kid(g, "start"), "fp_rect.start"), _xy(_kid(g, "end"), "fp_rect.end")
        c = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return [(c[i], c[(i + 1) % 4]) for i in range(4)]
    if k == "fp_poly":
        pts = _graphic_points(g)
        return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))] if len(pts) >= 3 else []
    if k == "fp_circle":
        cx, cy = _xy(_kid(g, "center"), "fp_circle.center")
        ex, ey = _xy(_kid(g, "end"), "fp_circle.end")
        r = math.hypot(ex - cx, ey - cy)
        pts = [(cx + r * math.cos(2 * math.pi * i / 48), cy + r * math.sin(2 * math.pi * i / 48)) for i in range(48)]
        return [(pts[i], pts[(i + 1) % 48]) for i in range(48)]
    if k == "fp_arc":
        pts = _arc_points(_xy(_kid(g, "start"), "fp_arc.start"), _xy(_kid(g, "mid"), "fp_arc.mid"),
                          _xy(_kid(g, "end"), "fp_arc.end"))
        return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return []


def _ref_text_record(fp: list, x: float, y: float, rot: float) -> dict | None:
    """Raw reference-designator text of one footprint (property "Reference" or fp_text reference).

    Position is footprint origin + text offset rotated by the footprint angle; the stored text angle
    is the ABSOLUTE board angle (checked against pcbnew 9.0.9 on the btdongle r1 specimen). Missing
    geometry is recorded in ``problems`` and only raises if GATE-C04-06 actually examines the text."""
    node, text = None, ""
    for p in _kids(fp, "property"):
        if len(p) >= 3 and p[1] == "Reference":
            node, text = p, p[2]
            break
    if node is None:
        for t in _kids(fp, "fp_text"):
            if len(t) >= 3 and t[1] == "reference":
                node, text = t, t[2]
                break
    if node is None:
        return None
    rec: dict = {"text": text, "layer": None, "hidden": False, "pos": None, "angle": 0.0, "size": None,
                 "thickness": None, "justify": [], "mirror": False, "problems": []}
    lay = _kid(node, "layer")
    rec["layer"] = lay[1] if lay and len(lay) > 1 else None
    hide = _kid(node, "hide")
    rec["hidden"] = ("hide" in node) or (hide is not None and (len(hide) < 2 or hide[1] == "yes"))
    at = _kid(node, "at")
    try:
        if at is None or len(at) < 3:
            raise C04GateInputError("missing (at ...)")
        ox, oy = _f(at[1], "text.at.x"), _f(at[2], "text.at.y")
        rec["angle"] = _f(at[3], "text.at.angle") if len(at) > 3 else 0.0
        rx, ry = _rot(ox, oy, rot)
        rec["pos"] = (x + rx, y + ry)
    except C04GateInputError as e:
        rec["problems"].append(f"position: {e}")
    eff = _kid(node, "effects")
    font = _kid(eff, "font") if eff else None
    sz = _kid(font, "size") if font else None
    th = _kid(font, "thickness") if font else None
    try:
        if sz is None or len(sz) < 3:
            raise C04GateInputError("missing (effects (font (size w h)))")
        rec["size"] = (_f(sz[1], "text.size.w"), _f(sz[2], "text.size.h"))
    except C04GateInputError as e:
        rec["problems"].append(f"size: {e}")
    try:
        if th is None or len(th) < 2:
            raise C04GateInputError("missing (effects (font (thickness t)))")
        rec["thickness"] = _f(th[1], "text.thickness")
    except C04GateInputError as e:
        rec["problems"].append(f"thickness: {e}")
    for flag in ("bold", "italic"):
        fl = _kid(font, flag) if font else None
        rec[flag] = bool(fl is not None and (len(fl) < 2 or fl[1] == "yes")) or (font is not None and flag in font)
    jus = _kid(eff, "justify") if eff else None
    if jus:
        rec["justify"] = [t for t in jus[1:] if isinstance(t, str)]
        rec["mirror"] = "mirror" in rec["justify"]
    return rec


def load_board(text: str) -> dict:
    """Extract footprints (ref, side, pads, courtyard bbox) and Edge.Cuts segments."""
    root = parse_sexpr(text)
    if len(root) != 1 or not root[0] or root[0][0] != "kicad_pcb":
        raise C04GateInputError("C04_GATE_BOARD_FORMAT: top-level form is not (kicad_pcb ...)")
    pcb = root[0]
    fps: list[dict] = []
    for fp in _kids(pcb, "footprint"):
        ref = _fp_ref(fp)
        if not ref:
            raise C04GateInputError(f"C04_GATE_BOARD_FIELD: footprint {fp[1] if len(fp) > 1 else '?'!r} has no Reference")
        at = _kid(fp, "at")
        x, y = _xy(at, f"{ref}.at")
        rot = _f(at[3], f"{ref}.at.angle") if len(at) > 3 else 0.0
        lay = _kid(fp, "layer")
        side = lay[1] if lay and len(lay) > 1 else ""
        pads = []
        for p in _kids(fp, "pad"):
            num = p[1] if len(p) > 1 else ""
            px, py = _xy(_kid(p, "at"), f"{ref}.pad{num}.at")
            pat = _kid(p, "at")
            pang = _f(pat[3], f"{ref}.pad{num}.angle") if len(pat) > 3 else 0.0
            sz = _kid(p, "size")
            if sz is None or len(sz) < 2:
                raise C04GateInputError(f"C04_GATE_BOARD_FIELD: {ref} pad {num!r} has no size")
            sw, sh = _f(sz[1], "pad.size.w"), _f(sz[2] if len(sz) > 2 else sz[1], "pad.size.h")
            hw, hh = sw / 2, sh / 2
            corners = [_rot(cx, cy, pang) for cx, cy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            rx, ry = _rot(px, py, rot)
            box = _bbox([(rx + cx + x, ry + cy + y) for cx, cy in corners])
            lyr = _kid(p, "layers") or []
            sides = [sd for sd, names in (("F", ("F.Cu", "*.Cu")), ("B", ("B.Cu", "*.Cu")))
                     if any(n in lyr for n in names)]
            pads.append({"number": num, "net": _net_name(_kid(p, "net")), "bbox": box, "sides": sides,
                         "through": any(isinstance(s, str) and s.startswith("*.Cu") for s in lyr)
                         or (len(p) > 2 and p[2] in ("thru_hole", "np_thru_hole"))})
        cpts: list[tuple[float, float]] = []
        csegs: dict[str, list[tuple[float, float, float, float]]] = {}
        widths: list[float] = []
        no_width = False
        for g in fp:
            if not (isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc")):
                continue
            l = _kid(g, "layer")
            if l and len(l) > 1 and l[1] in ("F.CrtYd", "B.CrtYd"):
                st = _kid(g, "stroke")
                wn = (_kid(st, "width") if st else None) or _kid(g, "width")
                if wn is None or len(wn) < 2:
                    no_width = True
                else:
                    widths.append(_f(wn[1], f"{ref}.courtyard.width"))
                cpts += [(*_rot(a, b, rot),) for a, b in _graphic_points(g)]
                for (a, b) in _graphic_segments(g):
                    p, q = _rot(a[0], a[1], rot), _rot(b[0], b[1], rot)
                    if math.hypot(q[0] - p[0], q[1] - p[1]) > 1e-9:
                        csegs.setdefault(l[1], []).append((p[0] + x, p[1] + y, q[0] + x, q[1] + y))
        allseg = [sg for v in csegs.values() for sg in v]
        if allseg:
            court = _bbox([(sg[0], sg[1]) for sg in allseg] + [(sg[2], sg[3]) for sg in allseg])
        else:
            court = _bbox([(a + x, b + y) for a, b in cpts]) if cpts else None
        # pcbnew 9.0.9 builds the courtyard polygon OUTSET from the drawn centreline: measured on the
        # btdongle r1 specimen (43/45 footprints, stroke 0.05) and on synthetic rects at stroke 0.01..0.3,
        # outset = stroke_width - 0.005 mm. The producer's 0.400 edge margin and the reviewer's 0.130 gap
        # both include it. Missing stroke width => outset 0 and the ref is listed (never a silent guess).
        outset = max(0.0, max(widths) - 0.005) if widths else 0.0
        fps.append({"ref": ref, "side": side, "pads": pads, "courtyard": court, "courtyards": csegs,
                    "court_fallback": bool(cpts) and not allseg, "ref_text": _ref_text_record(fp, x, y, rot),
                    "court_outset": outset, "court_outset_unknown": bool(cpts) and (no_width or not widths)})
    edge: list[tuple] = []
    for g in pcb:
        if not (isinstance(g, list) and g and g[0] in ("gr_line", "gr_rect", "gr_poly", "gr_circle", "gr_arc")):
            continue
        l = _kid(g, "layer")
        if not (l and len(l) > 1 and l[1] == "Edge.Cuts"):
            continue
        k = g[0]
        if k == "gr_line":
            (a, b), closed = [_xy(_kid(g, "start"), k), _xy(_kid(g, "end"), k)], False
        elif k == "gr_rect":
            (x1, y1), (x2, y2) = _xy(_kid(g, "start"), k), _xy(_kid(g, "end"), k)
            a, b, closed = None, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], True
        elif k == "gr_poly":
            b = [_xy(c, k) for c in (_kid(g, "pts") or []) if isinstance(c, list) and c and c[0] == "xy"]
            a, closed = None, True
        elif k == "gr_circle":
            cx, cy = _xy(_kid(g, "center"), k)
            ex, ey = _xy(_kid(g, "end"), k)
            r = math.hypot(ex - cx, ey - cy)
            b = [(cx + r * math.cos(2 * math.pi * i / 48), cy + r * math.sin(2 * math.pi * i / 48)) for i in range(48)]
            a, closed = None, True
        else:
            b = _arc_points(_xy(_kid(g, "start"), k), _xy(_kid(g, "mid"), k), _xy(_kid(g, "end"), k))
            a, closed = None, False
        if k == "gr_line":
            edge.append((a[0], a[1], b[0], b[1]))
        else:
            for i in range(len(b) - (0 if closed else 1)):
                p, q = b[i], b[(i + 1) % len(b)]
                edge.append((p[0], p[1], q[0], q[1]))
    return {"footprints": fps, "edge": edge}


def load_netlist(text: str) -> dict:
    """Return {"refs": {ref: footprint_id}, "pins": {ref: {pin: net}}} from a KiCad s-expr netlist."""
    root = parse_sexpr(text)
    if len(root) != 1 or not root[0] or root[0][0] != "export":
        raise C04GateInputError("C04_GATE_NETLIST_FORMAT: top-level form is not (export ...)")
    exp = root[0]
    refs: dict[str, str] = {}
    for comps in _kids(exp, "components"):
        for c in _kids(comps, "comp"):
            r = _kid(c, "ref")
            if not r or len(r) < 2:
                raise C04GateInputError("C04_GATE_NETLIST_FIELD: comp without (ref ...)")
            fpn = _kid(c, "footprint")
            refs[r[1]] = fpn[1] if fpn and len(fpn) > 1 else ""
    pins: dict[str, dict[str, str]] = {}
    for nets in _kids(exp, "nets"):
        for n in _kids(nets, "net"):
            nm = _kid(n, "name")
            if not nm or len(nm) < 2:
                raise C04GateInputError("C04_GATE_NETLIST_FIELD: net without (name ...)")
            for nd in _kids(n, "node"):
                r, p = _kid(nd, "ref"), _kid(nd, "pin")
                if not r or not p or len(r) < 2 or len(p) < 2:
                    raise C04GateInputError(f"C04_GATE_NETLIST_FIELD: node without ref/pin in net {nm[1]!r}")
                pins.setdefault(r[1], {})[p[1]] = nm[1]
    return {"refs": refs, "pins": pins}


# ----------------------------------------------------------------------------------- gates
def _gate(status: str, measured: dict, offenders: list) -> dict:
    return {"status": status, "measured": measured, "offenders": offenders}


def gate_parity(board: dict, nl: dict, expected_ref_count: int | None) -> dict:
    """GATE-C04-01: refs + per-ref connected-pad set + net assignment, board vs netlist."""
    b_refs = {}
    for fp in board["footprints"]:
        if fp["ref"] in b_refs:
            raise C04GateInputError(f"C04_GATE_BOARD_FIELD: duplicate footprint reference {fp['ref']!r}")
        b_refs[fp["ref"]] = fp
    missing = sorted(set(nl["refs"]) - set(b_refs))
    extra = sorted(set(b_refs) - set(nl["refs"]))
    mismatch: list[dict] = []
    for ref in sorted(set(nl["refs"]) & set(b_refs)):
        want = nl["pins"].get(ref, {})
        have: dict[str, set] = {}
        for p in b_refs[ref]["pads"]:
            if p["number"] and p["net"]:
                have.setdefault(p["number"], set()).add(p["net"])
        for pin in sorted(set(want) - set(have)):
            mismatch.append({"ref": ref, "pad": pin, "kind": "missing_pad_or_net", "netlist_net": want[pin], "board_net": None})
        for pin in sorted(set(have) - set(want)):
            mismatch.append({"ref": ref, "pad": pin, "kind": "extra_pad_net", "netlist_net": None, "board_net": sorted(have[pin])})
        for pin in sorted(set(have) & set(want)):
            if have[pin] != {want[pin]}:
                mismatch.append({"ref": ref, "pad": pin, "kind": "net_mismatch", "netlist_net": want[pin], "board_net": sorted(have[pin])})
    count_off: list[dict] = []
    if expected_ref_count is not None:
        if isinstance(expected_ref_count, bool) or not isinstance(expected_ref_count, int) or expected_ref_count < 0:
            raise C04GateInputError(f"C04_GATE_INPUT_FIELD: expected_ref_count must be a non-negative integer, got {expected_ref_count!r}")
        if len(b_refs) != expected_ref_count:
            count_off.append({"kind": "ref_count", "expected": expected_ref_count, "board": len(b_refs)})
    measured = {"board_refs": len(b_refs), "netlist_refs": len(nl["refs"]), "missing": missing, "extra": extra,
                "mismatch": mismatch, "expected_ref_count": expected_ref_count,
                "counts": {"missing": len(missing), "extra": len(extra), "mismatch": len(mismatch)}}
    offenders = ([{"ref": r, "kind": "missing_ref"} for r in missing] + [{"ref": r, "kind": "extra_ref"} for r in extra]
                 + mismatch + count_off)
    return _gate("pass" if not offenders else "fail", measured, offenders)


def _find_kicad_cli() -> str | None:
    return shutil.which("kicad-cli")


def gate_courtyard(board_path: str) -> dict:
    """GATE-C04-02: kicad-cli DRC courtyards_overlap. Absent/unusable CLI => unmeasured, never pass."""
    cli = _find_kicad_cli()
    if not cli:
        return _gate("unmeasured", {"reason": "kicad-cli not found on PATH; courtyard DRC was not run"}, [])
    fd, rep = tempfile.mkstemp(suffix=".json", prefix="c04gate_drc_", dir=os.environ.get("XDG_RUNTIME_DIR") or None)
    os.close(fd)
    try:
        proc = subprocess.run([cli, "pcb", "drc", "--format", "json", "--severity-all", "-o", rep, board_path],
                              capture_output=True, text=True, timeout=300)
        try:
            with open(rep, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            return _gate("unmeasured", {"reason": "kicad-cli produced no readable DRC JSON", "returncode": proc.returncode,
                                        "stderr": (proc.stderr or "")[-300:]}, [])
    except (OSError, subprocess.SubprocessError) as e:
        return _gate("unmeasured", {"reason": f"kicad-cli invocation failed: {type(e).__name__}: {e}"}, [])
    finally:
        if os.path.exists(rep):
            os.unlink(rep)
    viol = d.get("violations", [])
    over = [v for v in viol if v.get("type") == "courtyards_overlap"]
    offenders = [{"type": v.get("type"), "description": (v.get("description") or "")[:200],
                  "items": [(i.get("description") or "")[:120] for i in v.get("items", [])]} for v in over]
    other = {t: sum(1 for v in viol if v.get("type") == t) for t in ("malformed_courtyard", "missing_courtyard")}
    return _gate("pass" if not over else "fail",
                 {"courtyards_overlap": len(over), "other_courtyard_findings": other, "kicad_cli": cli}, offenders)


def _num(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise C04GateInputError(f"C04_GATE_INPUT_FIELD: {what} must be a finite number, got {v!r}")
    return float(v)


def _validate_keepouts(keepouts: Any) -> list[dict]:
    if keepouts is None:
        raise C04GateInputError("C04_GATE_INPUT_MISSING: keepouts is required (list of {name,x,y,w,h[,layer]}; [] = none declared)")
    if not isinstance(keepouts, list):
        raise C04GateInputError(f"C04_GATE_INPUT_FIELD: keepouts must be a list, got {type(keepouts).__name__}")
    out: list[dict] = []
    gaps: list[str] = []
    for i, k in enumerate(keepouts):
        if not isinstance(k, dict):
            gaps.append(f"keepouts[{i}] is not an object")
            continue
        for f in ("name", "x", "y", "w", "h"):
            if f not in k:
                gaps.append(f"keepouts[{i}] missing {f!r}")
        if any(f not in k for f in ("name", "x", "y", "w", "h")):
            continue
        if not isinstance(k["name"], str) or not k["name"]:
            gaps.append(f"keepouts[{i}].name must be a non-empty string")
            continue
        x, y = _num(k["x"], f"keepouts[{i}].x"), _num(k["y"], f"keepouts[{i}].y")
        w, h = _num(k["w"], f"keepouts[{i}].w"), _num(k["h"], f"keepouts[{i}].h")
        if w <= 0 or h <= 0:
            gaps.append(f"keepouts[{i}] ({k['name']}) w/h must be > 0")
            continue
        layer = k.get("layer")
        if layer is not None and layer not in _KEEPOUT_LAYERS:
            gaps.append(f"keepouts[{i}].layer {layer!r} not in {list(_KEEPOUT_LAYERS)}")
            continue
        out.append({"name": k["name"], "box": (x, y, x + w, y + h), "layer": layer})
    if gaps:
        raise C04GateInputError("C04_GATE_INPUT_FIELD: " + "; ".join(gaps))
    return out


def _fp_boxes(fp: dict) -> dict:
    """pads / courtyard / footprint (union of both) bboxes of one footprint."""
    boxes = [p["bbox"] for p in fp["pads"]]
    u = fp["courtyard"]
    for b in boxes:
        u = b if u is None else _union(u, b)
    return {"courtyard": fp["courtyard"], "footprint": u}


def gate_keepout(board: dict, keepouts: list[dict]) -> dict:
    """GATE-C04-03: any pad / courtyard / footprint bbox intersecting a keepout box (touch counts)."""
    if not keepouts:
        return _gate("unmeasured", {"reason": "keepouts=[] declared: nothing to intersect, a vacuous pass is not issued",
                                    "keepouts": 0}, [])
    offenders: list[dict] = []
    for ko in keepouts:
        for fp in board["footprints"]:
            if ko["layer"] and not (fp["side"] == ko["layer"] or any(p["through"] for p in fp["pads"])):
                continue
            hits: list[tuple[str, str]] = []
            for p in fp["pads"]:
                if _boxes_hit(p["bbox"], ko["box"]):
                    hits.append(("pad", p["number"]))
            fb = _fp_boxes(fp)
            if fb["courtyard"] is not None and _boxes_hit(fb["courtyard"], ko["box"]):
                hits.append(("courtyard", ""))
            if fb["footprint"] is not None and _boxes_hit(fb["footprint"], ko["box"]):
                hits.append(("footprint", ""))
            for kind, pad in hits:
                o = {"keepout": ko["name"], "ref": fp["ref"], "kind": kind}
                if pad:
                    o["pad"] = pad
                offenders.append(o)
    measured = {"keepouts": [{"name": k["name"], "box_mm": [round(v, 4) for v in k["box"]], "layer": k["layer"]}
                             for k in keepouts],
                "footprints_examined": len(board["footprints"]), "offender_count": len(offenders),
                "layer_filter_note": "layer, when given, selects footprints on that side or with through pads"}
    return _gate("pass" if not offenders else "fail", measured, offenders)


def _box_segs(b: tuple) -> list[tuple]:
    return [(b[0], b[1], b[2], b[1]), (b[2], b[1], b[2], b[3]), (b[2], b[3], b[0], b[3]), (b[0], b[3], b[0], b[1])]


def _segs_bbox(segs: list[tuple]) -> tuple:
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_gap(a: tuple, b: tuple) -> float:
    """Lower bound of the distance between two AABBs (0 when they touch or overlap)."""
    return math.hypot(max(a[0] - b[2], b[0] - a[2], 0.0), max(a[1] - b[3], b[1] - a[3], 0.0))


def _segs_distance(a: list[tuple], b: list[tuple]) -> float:
    """Minimum distance between two segment sets (0 on touch / crossing). Containment is NOT detected here."""
    best = math.inf
    for s in a:
        for t in b:
            d = _seg_seg((s[0], s[1]), (s[2], s[3]), (t[0], t[1]), (t[2], t[3]))
            if d < best:
                best = d
                if best <= 0.0:
                    return 0.0
    return best


def _fp_court_layers(fp: dict) -> tuple[dict, bool]:
    """{courtyard layer: segments} of a footprint and whether the AABB fallback was needed."""
    if fp["courtyards"]:
        return fp["courtyards"], False
    return {("B.CrtYd" if fp["side"] == "B.Cu" else "F.CrtYd"): _box_segs(fp["courtyard"])}, True


def gate_edge_margin(board: dict, edge_margin_mm: float) -> dict:
    """GATE-C04-04: courtyard POLYGON segments vs Edge.Cuts segments; margin = min distance
    (negative = outside outline). A footprint whose courtyard polygon could not be built falls back to
    its AABB and is listed in ``aabb_fallback_refs``."""
    segs = board["edge"]
    offenders: list[dict] = []
    per_ref: dict[str, float] = {}
    fallback: list[str] = []
    for fp in board["footprints"]:
        layers, fb = _fp_court_layers(fp)
        if fb:
            fallback.append(fp["ref"])
        cs = [s for v in layers.values() for s in v]
        d = max(0.0, _segs_distance(cs, segs) - fp["court_outset"])
        probe = (cs[0][0], cs[0][1])
        inside = _point_in_outline(probe, segs)
        margin = d if inside else -d
        per_ref[fp["ref"]] = round(margin, 4)
        if margin < edge_margin_mm - 1e-6:
            offenders.append({"ref": fp["ref"], "margin_mm": round(margin, 4),
                              "required_mm": edge_margin_mm,
                              "kind": "outside_outline_or_crossing" if (not inside or d == 0.0) else "margin_below_required"})
    worst = min(per_ref.items(), key=lambda kv: kv[1]) if per_ref else (None, None)
    measured = {"edge_margin_mm": edge_margin_mm, "min_margin_mm": worst[1], "min_margin_ref": worst[0],
                "edge_segments": len(segs), "footprints_examined": len(per_ref),
                "aabb_fallback_refs": fallback,
                "outset_unknown_refs": sorted(fp["ref"] for fp in board["footprints"] if fp["court_outset_unknown"]),
                "model": "courtyard polygon segments (outset by stroke_width-0.005 as pcbnew does) vs Edge.Cuts segments; a courtyard point decides inside/outside; "
                         "AABB only for footprints listed in aabb_fallback_refs"}
    return _gate("pass" if not offenders else "fail", measured, offenders)


def _in_poly(p: tuple[float, float], segs: list[tuple]) -> bool:
    return _point_in_outline(p, segs)


def _text_polygon(rec: dict) -> tuple[list[tuple[float, float]] | None, str | None, list[str]]:
    """(4-corner polygon in board mm, unmeasured_reason, notes) of one reference text.

    Model (fitted to and checked against pcbnew 9.0.9 text bounding boxes, ref text 'R','RR','R1','C10',
    'SW2' at sizes 0.5..1.5 and thickness 0.08..0.2): width = sum(glyph advance) * size_w + 3*t - 0.2*size_w,
    height = 1.17*size_h + 3.51*t, with t = min(thickness, min(size)/4). Rotation about the anchor by the
    stored absolute angle; ``mirror`` flips left/right justification. Non-centred justification places the
    anchor on the box edge and grows the box by 0.1 mm (approximation, listed in notes)."""
    text = rec["text"]
    bad = sorted({c for c in text if c not in _GLYPH_ADV})
    if not text or bad:
        return None, f"glyphs without measured advance: {bad or ['<empty text>']}", []
    if rec.get("bold") or rec.get("italic"):
        return None, "bold/italic text: stroke metrics not measured", []
    sw, sh = rec["size"]
    t = min(rec["thickness"], min(sw, sh) / 4.0)
    w = sum(_GLYPH_ADV[c] for c in text) * sw + 3.0 * t - 0.2 * sw
    h = 1.17 * sh + 3.51 * t
    hj = next((j for j in rec["justify"] if j in ("left", "right")), "center")
    vj = next((j for j in rec["justify"] if j in ("top", "bottom")), "center")
    if rec["mirror"] and hj != "center":
        hj = "right" if hj == "left" else "left"
    x0, x1 = {"left": (0.0, w), "right": (-w, 0.0), "center": (-w / 2, w / 2)}[hj]
    y0, y1 = {"top": (0.0, h), "bottom": (-h, 0.0), "center": (-h / 2, h / 2)}[vj]
    notes: list[str] = []
    if hj != "center" or vj != "center":
        x0, x1, y0, y1 = x0 - 0.1, x1 + 0.1, y0 - 0.1, y1 + 0.1
        notes.append(f"justify {rec['justify']}: anchor-on-edge approximation, box grown 0.1 mm")
    px, py = rec["pos"]
    pts = []
    for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        rx, ry = _rot(cx, cy, rec["angle"])
        pts.append((px + rx, py + ry))
    return pts, None, notes


def _poly_segs(pts: list[tuple[float, float]]) -> list[tuple]:
    return [(*pts[i], *pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _shape_distance(a_segs: list[tuple], b_segs: list[tuple], a_pt: tuple, b_pt: tuple) -> float:
    """Distance between two closed segment sets; 0 on touch, crossing or containment (probe-point test)."""
    d = _segs_distance(a_segs, b_segs)
    if d > 0.0 and (_in_poly(a_pt, b_segs) or _in_poly(b_pt, a_segs)):
        return 0.0
    return d


def gate_silk(board: dict, clearance_mm: float, layers: tuple[str, ...]) -> dict:
    """GATE-C04-06: visible reference-designator text vs pads (bbox) and courtyard polygons on the same side.

    Reference on *.Fab is not printed on the board; a fab-ready board should carry refs on *.SilkS --
    this gate measures collisions, not printability. Text fully inside its OWN courtyard is excluded
    (reported in measured.own_courtyard_contained); text over its OWN pads stays an offender.
    """
    offenders: list[dict] = []
    unmeasured_items: list[dict] = []
    examined: list[str] = []
    hidden: list[str] = []
    other_layer: list[str] = []
    fallback: list[str] = []
    own_contained: list[str] = []
    own_straddling: list[str] = []
    per_layer: dict[str, int] = {l: 0 for l in layers}
    notes: dict[str, list[str]] = {}
    for fp in board["footprints"]:
        rec = fp["ref_text"]
        if rec is None:
            raise C04GateInputError(f"C04_GATE_SILK_GEOMETRY: footprint {fp['ref']!r} has no reference text record")
        if rec["hidden"]:
            hidden.append(fp["ref"])
            continue
        if rec["layer"] not in layers:
            other_layer.append(fp["ref"])
            continue
        if rec["problems"]:
            raise C04GateInputError(f"C04_GATE_SILK_GEOMETRY: reference text of {fp['ref']!r} on {rec['layer']} "
                                    f"has incomplete geometry, refusing to estimate: {'; '.join(rec['problems'])}")
        poly, why, nts = _text_polygon(rec)
        if poly is None:
            unmeasured_items.append({"ref": fp["ref"], "layer": rec["layer"], "reason": why})
            continue
        examined.append(fp["ref"])
        per_layer[rec["layer"]] += 1
        if nts:
            notes[fp["ref"]] = nts
        side = "B" if rec["layer"].startswith("B.") else "F"
        tsegs = _poly_segs(poly)
        tbox = _segs_bbox(tsegs)
        tctr = (sum(p[0] for p in poly) / 4, sum(p[1] for p in poly) / 4)
        grown = (tbox[0] - clearance_mm, tbox[1] - clearance_mm, tbox[2] + clearance_mm, tbox[3] + clearance_mm)
        best: dict[tuple, dict] = {}
        for other in board["footprints"]:
            for p in other["pads"]:
                if side not in p["sides"] or not _boxes_hit(p["bbox"], grown):
                    continue
                pc = ((p["bbox"][0] + p["bbox"][2]) / 2, (p["bbox"][1] + p["bbox"][3]) / 2)
                d = _shape_distance(tsegs, _box_segs(p["bbox"]), tctr, pc)
                if d < clearance_mm - 1e-6:
                    k = (other["ref"], "pad")
                    if k not in best or d < best[k]["clearance_mm"]:
                        best[k] = {"ref": fp["ref"], "against_ref": other["ref"], "kind": "pad", "pad": p["number"],
                                   "clearance_mm": round(d, 4), "required_mm": clearance_mm, "text_layer": rec["layer"]}
            cl, fb = _fp_court_layers(other)
            segs = cl.get(side + ".CrtYd")
            if not segs:
                continue
            if fb and other["ref"] not in fallback:
                fallback.append(other["ref"])
            if not _boxes_hit(_segs_bbox(segs), grown):
                continue
            d = max(0.0, _shape_distance(tsegs, segs, tctr, (segs[0][0], segs[0][1])) - other["court_outset"])
            if other is fp:
                # normal KiCad convention: ref text sits in/on its own part's courtyard; recorded, not an offender
                # (own PADS are still checked above). Fully inside vs straddling the own courtyard line is kept apart.
                if d < clearance_mm - 1e-6:
                    if fp["ref"] not in own_contained:
                        own_contained.append(fp["ref"])
                    if not all(_in_poly(c, segs) for c in poly) and fp["ref"] not in own_straddling:
                        own_straddling.append(fp["ref"])
                continue
            if d < clearance_mm - 1e-6:
                k = (other["ref"], "courtyard")
                if k not in best or d < best[k]["clearance_mm"]:
                    best[k] = {"ref": fp["ref"], "against_ref": other["ref"], "kind": "courtyard",
                               "clearance_mm": round(d, 4), "required_mm": clearance_mm, "text_layer": rec["layer"]}
        offenders += sorted(best.values(), key=lambda o: (o["against_ref"], o["kind"]))
    measured = {"silk_clearance_mm": clearance_mm, "ref_text_layers": list(layers), "layers_examined": list(layers),
                "texts_per_layer": per_layer, "texts_examined": len(examined),
                "own_courtyard_contained": {"count": len(own_contained), "refs": sorted(own_contained),
                                            "straddling_own_courtyard_line_refs": sorted(own_straddling)},
                "texts_hidden_skipped": hidden, "texts_on_other_layers_skipped": other_layer,
                "unmeasured_items": unmeasured_items, "justify_notes": notes, "aabb_fallback_refs": fallback,
                "offending_refs": sorted({o["ref"] for o in offenders}),
                "model": "KiCad 9.0.9 stroke-font text box fitted to pcbnew bounding boxes (see _text_polygon); "
                         "text polygon vs pad AABB and courtyard polygon segments, same side only; rotation handled; "
                         "mirror flips justification only; back-side footprints are not re-mirrored"}
    if offenders:
        status = "fail"
    elif unmeasured_items or not examined:
        status = "unmeasured"
        if not examined:
            measured["reason"] = "no visible reference text on the examined layers; a vacuous pass is not issued"
    else:
        status = "pass"
    return _gate(status, measured, offenders)


def gate_courtyard_gap(board: dict, gap_mm: float) -> dict:
    """GATE-C04-07: pairwise courtyard POLYGON distance on the same courtyard layer >= gap_mm."""
    items: list[tuple[str, str, list[tuple], tuple, float]] = []
    fallback: list[str] = []
    for fp in board["footprints"]:
        cl, fb = _fp_court_layers(fp)
        if fb:
            fallback.append(fp["ref"])
        for layer, segs in cl.items():
            items.append((fp["ref"], layer, segs, _segs_bbox(segs), fp["court_outset"]))
    top: list[tuple[float, str, str, str]] = []
    offenders: list[dict] = []
    pairs = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a[1] != b[1] or a[0] == b[0]:
                continue
            pairs += 1
            cutoff = max(gap_mm, top[-1][0] if len(top) >= 3 else math.inf)
            if _bbox_gap(a[3], b[3]) - a[4] - b[4] >= cutoff:
                continue
            d = max(0.0, _shape_distance(a[2], b[2], (a[2][0][0], a[2][0][1]), (b[2][0][0], b[2][0][1])) - a[4] - b[4])
            top.append((d, a[0], b[0], a[1]))
            top.sort()
            del top[3:]
            if d < gap_mm - 1e-6:
                offenders.append({"ref": a[0], "against_ref": b[0], "layer": a[1], "distance_mm": round(d, 4),
                                  "required_mm": gap_mm})
    offenders.sort(key=lambda o: o["distance_mm"])
    measured = {"courtyard_gap_mm": gap_mm, "pairs_examined": pairs, "aabb_fallback_refs": fallback,
                "outset_unknown_refs": sorted(fp["ref"] for fp in board["footprints"] if fp["court_outset_unknown"]),
                "smallest_three": [{"refs": [r1, r2], "layer": ly, "distance_mm": round(d, 4)} for d, r1, r2, ly in top],
                "model": "courtyard polygon segments outset by stroke_width-0.005 (pcbnew behaviour), same courtyard layer; 0 on touch/crossing/containment; "
                         "AABB only for footprints listed in aabb_fallback_refs; circles are 48-gons, arcs 24-step polylines"}
    return _gate("pass" if not offenders else "fail", measured, offenders)


def gate_copper_gerber() -> dict:
    """GATE-C04-05: ALWAYS unmeasured here (placement-only gate)."""
    return _gate("unmeasured",
                 {"reason": "placement-only gate: no routing, filled-board DRC, copper continuity or Gerber parity is measured; "
                            "an unrouted placed board is never converted to a copper PASS (DD-C04 (d))",
                  "placement_only": True}, [])


def c04_placement_geometry_gate(board_path: str, netlist_path: str, keepouts: list | None = None, *,
                       edge_margin_mm: float | None = None, expected_ref_count: int | None = None,
                       silk_clearance_mm: float | None = None, courtyard_gap_mm: float | None = None,
                       ref_text_layers: list | None = None) -> dict:
    """Run GATE-C04-01..07 on a placed .kicad_pcb against its netlist. Never mutates inputs.

    06 = reference-text vs pad/courtyard clearance (``silk_clearance_mm``, default 0.15, text layers
    ``ref_text_layers``, default F/B.SilkS + F/B.Fab); 07 = pairwise courtyard polygon gap
    (``courtyard_gap_mm``, default 0.25)."""
    btext = _read(board_path, "board_path", ".kicad_pcb")
    ntext = _read(netlist_path, "netlist_path", ".net")
    kos = _validate_keepouts(keepouts)
    margin = DEFAULT_EDGE_MARGIN_MM if edge_margin_mm is None else _num(edge_margin_mm, "edge_margin_mm")
    if margin < 0:
        raise C04GateInputError(f"C04_GATE_INPUT_FIELD: edge_margin_mm must be >= 0, got {margin}")
    silk = DEFAULT_SILK_CLEARANCE_MM if silk_clearance_mm is None else _num(silk_clearance_mm, "silk_clearance_mm")
    cgap = DEFAULT_COURTYARD_GAP_MM if courtyard_gap_mm is None else _num(courtyard_gap_mm, "courtyard_gap_mm")
    if silk < 0 or cgap < 0:
        raise C04GateInputError(f"C04_GATE_INPUT_FIELD: silk_clearance_mm/courtyard_gap_mm must be >= 0, got {silk}/{cgap}")
    if ref_text_layers is None:
        tlayers = DEFAULT_REF_TEXT_LAYERS
    else:
        if (not isinstance(ref_text_layers, list) or not ref_text_layers
                or any(l not in DEFAULT_REF_TEXT_LAYERS for l in ref_text_layers)):
            raise C04GateInputError(f"C04_GATE_INPUT_FIELD: ref_text_layers must be a non-empty subset of {list(DEFAULT_REF_TEXT_LAYERS)}")
        tlayers = tuple(ref_text_layers)
    board = load_board(btext)
    nl = load_netlist(ntext)
    gaps: list[str] = []
    if not board["footprints"]:
        gaps.append("board has no footprints")
    no_court = sorted(fp["ref"] for fp in board["footprints"] if fp["courtyard"] is None)
    if no_court:
        gaps.append(f"footprints without F.CrtYd/B.CrtYd geometry: {no_court}")
    if len(board["edge"]) < 3:
        gaps.append(f"Edge.Cuts outline has {len(board['edge'])} segment(s); a closed outline needs >= 3")
    if gaps:
        raise C04GateInputError("C04_GATE_BOARD_GEOMETRY: " + "; ".join(gaps))
    gates = {
        "GATE-C04-01": gate_parity(board, nl, expected_ref_count),
        "GATE-C04-02": gate_courtyard(board_path),
        "GATE-C04-03": gate_keepout(board, kos),
        "GATE-C04-04": gate_edge_margin(board, margin),
        "GATE-C04-05": gate_copper_gerber(),
        "GATE-C04-06": gate_silk(board, silk, tlayers),
        "GATE-C04-07": gate_courtyard_gap(board, cgap),
    }
    return {"ok": all(gates[g]["status"] == "pass" for g in GATE_IDS if g != "GATE-C04-05"),
            "gates": gates,
            "unmeasured_gates": [g for g in GATE_IDS if gates[g]["status"] == "unmeasured"],
            "inputs": {"board_sha256": _sha256(board_path), "netlist_sha256": _sha256(netlist_path)},
            "scope": "placement-only; ok never implies copper connectivity or Gerber parity"}
