"""bodesign_c04_gerber_gate: GATE-C04-05 made measurable -- Gerber-level copper connectivity and export parity.

Core-side, pure python (no numpy / shapely / pcbnew). The board (.kicad_pcb) is read through ``c04_gate``'s
s-expression loader (``parse_sexpr`` / ``load_board``) and ``c04_manifest``'s outline chaining / hashing --
reused, not forked. ``bodesign_gerber_core`` was READ and NOT reused: ``parse_gerber_file`` keeps only sampled
draws/flashes, ignores G36 regions, arcs and aperture macros, and ``parse_drill_file`` hard-codes inch/5-decimal
coordinates, so neither can carry a connectivity decision. The RS-274X and Excellon readers below are new.

G-01 export parity   board pads / vias / drills / Edge.Cuts vs the gerber + drill bytes (missing / extra per layer).
G-02 copper connectivity from gerber bytes alone: every copper item (flash / draw / region) is a shape
                     (core polyline-or-polygon + radius); two items on one layer are connected when their exact
                     analytic distance is <= ``CONNECT_TOL_MM`` (1 um); a PLATED drill hit unions every item it
                     touches on every copper layer inside the drill file's layer span. Connected components are
                     then mapped to board pad -> net: a net whose pads fall in >1 component is OPEN, a component
                     holding pads of >1 net is a SHORT. Method: exact geometry, no raster, so no pixel resolution;
                     arcs are flattened to chords with sagitta <= ``ARC_SAGITTA_MM`` (0.005 mm).
G-03 keepout         copper items (any layer, optional per-keepout layer) vs declared keepout boxes.
G-04 render binding  ``NN.c04-<layer>-vN.png`` must carry a sidecar / caption naming a gerber file whose sha256
                     matches a file in gerber_dir. Binding only; image content is NOT judged.

Status rules: pass | fail | unmeasured. Anything not computable is ``unmeasured`` with a reason, never pass.
``ok`` is true only when G-01..G-03 all pass (G-04 is reported, not part of ``ok``).

Declared limits (also emitted in ``method.limits``): clear polarity (%LPC), step-and-repeat, blocks, negative
layers, rect-aperture strokes, single-quadrant arcs, incremental coordinates and trailing-zero formats make the
layer ``unsupported`` -> G-01..G-03 unmeasured; aperture holes are ignored; macro primitives 6/7 and clear
exposure are unsupported; pad centre = centre of the board loader's pad bbox; custom-pad primitives, oval drills
and drill offsets are not modelled (listed in ``measured.unmodeled``); G-01 does not compare track / zone-fill
geometry (G-02 consumes it); net attributes in the gerber (%TO.N) are not used; layers above two copper layers
treat through-pad/via flashes on inner layers as explained, not required.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Any

from .c04_gate import (C04GateInputError, _boxes_hit, _f, _fp_ref, _gate, _kid, _kids, _net_name, _num, _pt_seg, _read,
                       _rot, _seg_seg, _sha256, _validate_keepouts, _xy, load_board, parse_sexpr)
from .c04_manifest import _canon_loop, _chain, c04_board_hashes

SCHEMA = "c04_gerber_gate/1"
GATE_IDS = ("G-01", "G-02", "G-03", "G-04")
ARC_SAGITTA_MM = 0.005
CONNECT_TOL_MM = 0.001
DEFAULT_PAD_TOL_MM = 0.01
DEFAULT_EDGE_TOL_MM = 0.02
DEFAULT_DRILL_TOL_MM = 0.01
DRILL_DIA_TOL_MM = 0.01
_INF = float("inf")
LIMITS = ("clear polarity / step-repeat / blocks / negative layers / rect strokes / single-quadrant arcs / "
          "incremental or trailing-zero coordinates => layer unsupported => G-01..G-03 unmeasured",
          "aperture holes ignored; macro primitives 6/7 and clear exposure unsupported",
          "pad centre = centre of the board loader pad bbox; custom pad primitives, oval drills, drill offsets unmodelled",
          "G-01 does not compare track / zone-fill geometry; gerber %TO.N net attributes are not used",
          "inner layers: through-pad / via flashes are explained, not required")


# ------------------------------------------------------------------------------------------ shapes
# shape = (pts, closed, radius): a polyline (open) or polygon (closed) core thickened by ``radius``.
def _item(kind: str, shapes: list, at: tuple, layer: str = "") -> dict:
    xs = [p[0] for s in shapes for p in s[0]]
    ys = [p[1] for s in shapes for p in s[0]]
    r = max((s[2] for s in shapes), default=0.0)
    return {"kind": kind, "shapes": shapes, "at": at, "layer": layer,
            "bbox": (min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r)}


def _segs(pts: list, closed: bool) -> list:
    if len(pts) == 1:
        return [(pts[0], pts[0])]
    s = list(zip(pts[:-1], pts[1:]))
    if closed and len(pts) > 2:
        s.append((pts[-1], pts[0]))
    return s


def _pt_in_poly(p: tuple, pts: list) -> bool:
    x, y = p
    hit = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def shape_distance(a: tuple, b: tuple, limit: float = 0.0) -> float:
    """Exact edge-to-edge distance between two shapes (0 when overlapping). Exact only when the true distance is
    <= ``limit`` (+ nothing): pairs farther apart than ``limit`` are culled and return inf. Callers only compare against limit."""
    ap, ac, ar = a
    bp, bc, br = b
    if ac and len(ap) >= 3 and _pt_in_poly(bp[0], ap):
        return 0.0
    if bc and len(bp) >= 3 and _pt_in_poly(ap[0], bp):
        return 0.0
    m = limit + ar + br
    bx0, bx1 = min(p[0] for p in bp) - m, max(p[0] for p in bp) + m
    by0, by1 = min(p[1] for p in bp) - m, max(p[1] for p in bp) + m
    sb = _segs(bp, bc)
    best = _INF
    for p, q in _segs(ap, ac):
        if max(p[0], q[0]) < bx0 or min(p[0], q[0]) > bx1 or max(p[1], q[1]) < by0 or min(p[1], q[1]) > by1:
            continue
        for r, s in sb:
            d = _seg_seg(p, q, r, s)
            if d < best:
                best = d
                if best - ar - br <= limit:
                    return max(0.0, best - ar - br)
    return max(0.0, best - ar - br) if best < _INF else _INF


def item_distance(a: dict, b: dict, limit: float = 0.0) -> float:
    ab, bb = a["bbox"], b["bbox"]
    if (ab[0] > bb[2] + limit or bb[0] > ab[2] + limit or ab[1] > bb[3] + limit or bb[1] > ab[3] + limit):
        return _INF
    best = _INF
    for sa in a["shapes"]:
        for sb in b["shapes"]:
            d = shape_distance(sa, sb, limit)
            if d < best:
                best = d
                if best <= limit:
                    return best
    return best


def _flatten_arc(p0: tuple, p1: tuple, c: tuple, cw: bool) -> list:
    r = math.hypot(p0[0] - c[0], p0[1] - c[1])
    if r < 1e-9:
        return [p0, p1]
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    full = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 1e-9
    two = 2 * math.pi
    sweep = (-(((a0 - a1) % two) or (two if full else 0.0))) if cw else (((a1 - a0) % two) or (two if full else 0.0))
    step = 2 * math.acos(max(-1.0, 1 - ARC_SAGITTA_MM / r)) if r > ARC_SAGITTA_MM else math.pi / 2
    n = max(2, int(math.ceil(abs(sweep) / step)))
    pts = [(c[0] + r * math.cos(a0 + sweep * i / n), c[1] + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = p0, p1
    return pts


# ---------------------------------------------------------------------------------- aperture macros
def _eval(expr: str, var: dict) -> float:
    toks = re.findall(r"\$\d+|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+|[-+()x/]", expr.replace(" ", ""))
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def factor():
        t = take()
        if t == "-":
            return -factor()
        if t == "+":
            return factor()
        if t == "(":
            v = add()
            take()
            return v
        if t is None:
            raise ValueError(f"bad macro expression {expr!r}")
        if t.startswith("$"):
            return float(var.get(int(t[1:]), 0.0))
        return float(t)

    def mul():
        v = factor()
        while peek() in ("x", "/"):
            v = v * factor() if take() == "x" else v / factor()
        return v

    def add():
        v = mul()
        while peek() in ("+", "-"):
            v = v + mul() if take() == "+" else v - mul()
        return v

    v = add()
    if pos[0] != len(toks):
        raise ValueError(f"bad macro expression {expr!r}")
    return v


def _rotp(x: float, y: float, deg: float) -> tuple:
    a = math.radians(deg)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def _macro_shapes(stmts: list, params: list, scale: float, notes: set) -> list:
    var = {i + 1: p for i, p in enumerate(params)}
    out: list = []
    for s in stmts:
        if re.match(r"^\$\d+=", s):
            k, v = s.split("=", 1)
            var[int(k[1:])] = _eval(v, var)
            continue
        if s == "0" or s.startswith("0 ") or s.startswith("0\t"):
            continue
        parts = s.split(",")
        try:
            code = int(parts[0])
            v = [_eval(p, var) for p in parts[1:]]
        except ValueError:
            notes.add(f"macro statement {s[:24]!r}")
            continue
        if not v or v[0] == 0:
            notes.add("macro clear exposure")
            continue
        if code == 1:
            cx, cy = _rotp(v[2], v[3], v[4] if len(v) > 4 else 0.0)
            out.append(([(cx * scale, cy * scale)], False, v[1] * scale / 2))
        elif code in (20, 21, 22):
            if code == 20:
                x1, y1, x2, y2, rot = v[2], v[3], v[4], v[5], v[6] if len(v) > 6 else 0.0
                l = math.hypot(x2 - x1, y2 - y1) or 1.0
                nx, ny = -(y2 - y1) / l * v[1] / 2, (x2 - x1) / l * v[1] / 2
                cs = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
            else:
                w, h = v[1], v[2]
                cx, cy = (v[3], v[4]) if code == 21 else (v[3] + w / 2, v[4] + h / 2)
                rot = v[5] if len(v) > 5 else 0.0
                cs = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
            out.append(([(_rotp(x, y, rot)[0] * scale, _rotp(x, y, rot)[1] * scale) for x, y in cs], True, 0.0))
        elif code == 4:
            n = int(v[1])
            co = v[2:2 + 2 * (n + 1)]
            rot = v[2 + 2 * (n + 1)] if len(v) > 2 + 2 * (n + 1) else 0.0
            pts = [_rotp(co[2 * i], co[2 * i + 1], rot) for i in range(n + 1)]
            out.append(([(x * scale, y * scale) for x, y in pts], True, 0.0))
        elif code == 5:
            n, cx, cy, d = int(v[1]), v[2], v[3], v[4]
            rot = v[5] if len(v) > 5 else 0.0
            pts = [_rotp(cx + d / 2 * math.cos(2 * math.pi * i / n), cy + d / 2 * math.sin(2 * math.pi * i / n), rot) for i in range(n)]
            out.append(([(x * scale, y * scale) for x, y in pts], True, 0.0))
        else:
            notes.add(f"macro primitive {code}")
    return out


# ------------------------------------------------------------------------------------ RS-274X reader
class _Unsupported(Exception):
    pass


def _blocks(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \r\n\t":
            i += 1
        elif c == "%":
            j = text.find("%", i + 1)
            if j < 0:
                raise _Unsupported("unterminated %..% extended command")
            yield True, [s.strip() for s in text[i + 1:j].split("*") if s.strip()]
            i = j + 1
        else:
            j = text.find("*", i)
            if j < 0:
                break
            yield False, [text[i:j].strip()]
            i = j + 1


def _flip(pts: list) -> list:
    return [(x, -y) for x, y in pts]


def _aperture_shapes(ap: tuple, scale: float, macros: dict, notes: set) -> list:
    """Shapes of one aperture flashed at the origin (gerber frame, y up, mm)."""
    name, prm = ap
    if name == "C":
        return [([(0.0, 0.0)], False, prm[0] * scale / 2)]
    if name == "R":
        w, h = prm[0] * scale / 2, prm[1] * scale / 2
        return [([(-w, -h), (w, -h), (w, h), (-w, h)], True, 0.0)]
    if name == "O":
        w, h = prm[0] * scale, prm[1] * scale
        d = abs(w - h) / 2
        return [([(-d, 0.0), (d, 0.0)] if w >= h else [(0.0, -d), (0.0, d)], False, min(w, h) / 2)]
    if name == "P":
        dia, n = prm[0] * scale, int(prm[1])
        rot = prm[2] if len(prm) > 2 else 0.0
        return [([_rotp(dia / 2 * math.cos(2 * math.pi * k / n), dia / 2 * math.sin(2 * math.pi * k / n), rot)
                  for k in range(n)], True, 0.0)]
    if name in macros:
        return _macro_shapes(macros[name], prm, scale, notes)
    raise _Unsupported(f"aperture type {name!r}")


def parse_rs274x(text: str) -> dict:
    """RS-274X -> {"items", "function", "unsupported": [...], "notes": [...]}; coordinates in mm, board frame (y flipped)."""
    dec = scale = None
    apt: dict = {}
    macros: dict = {}
    items: list = []
    unsup: list = []
    notes: set = set()
    function = None
    cur = (0.0, 0.0)
    sel = None
    interp = None
    region = None
    contour = None
    last_op = None
    try:
        for ext, cmds in _blocks(text):
            if ext:
                if cmds and cmds[0].startswith("AM"):
                    macros[cmds[0][2:]] = cmds[1:]
                    continue
                for c in cmds:
                    if c.startswith("FS"):
                        m = re.match(r"FS([LT])([AI])X(\d)(\d)Y(\d)(\d)$", c)
                        if not m or m.group(1) != "L" or m.group(2) != "A":
                            unsup.append(f"coordinate format {c!r} (only absolute, leading-zero-omitted)")
                        else:
                            dec = int(m.group(4))
                    elif c.startswith("MO"):
                        scale = 25.4 if "IN" in c else 1.0
                    elif c.startswith("TF.FileFunction"):
                        function = c.split(",", 1)[1] if "," in c else ""
                    elif c.startswith("AD"):
                        m = re.match(r"ADD(\d+)([A-Za-z_][\w.$]*),?(.*)$", c)
                        if not m:
                            unsup.append(f"aperture definition {c!r}")
                            continue
                        apt[m.group(1)] = (m.group(2), [float(v) for v in m.group(3).split("X") if v != ""])
                    elif c.startswith("LP") and c != "LPD":
                        unsup.append("clear polarity (%LPC)")
                    elif c.startswith("SR") and c != "SR":
                        unsup.append("step-and-repeat")
                    elif c.startswith("AB"):
                        unsup.append("aperture blocks")
                    elif c in ("LMN", "LR0", "LS1") or c.startswith(("LM", "LR", "LS")):
                        if c not in ("LMN", "LR0", "LS1"):
                            unsup.append(f"aperture transform {c!r}")
                continue
            b = cmds[0]
            if not b or b.startswith("G04"):
                continue
            toks = re.findall(r"G\d+|[XYIJ][+-]?\d+|D\d+|M\d+", b)
            xyij: dict = {}
            op = None
            for t in toks:
                if t[0] == "G":
                    g = int(t[1:])
                    if g in (1, 2, 3):
                        interp = g
                    elif g == 36:
                        region, contour = [], None
                    elif g == 37:
                        if contour and len(contour) >= 3:
                            region.append(contour)
                        shapes = [(_flip(c), True, 0.0) for c in (region or [])]
                        if shapes:
                            items.append(_item("region", shapes, shapes[0][0][0]))
                        region = contour = None
                    elif g == 74:
                        unsup.append("single-quadrant arcs (G74)")
                    elif g in (54, 55, 75):
                        pass
                    elif g in (70, 71, 90):
                        if g == 70:
                            scale = 25.4
                        elif g == 71:
                            scale = 1.0
                    elif g == 91:
                        unsup.append("incremental coordinates (G91)")
                    else:
                        unsup.append(f"G{g:02d}")
                elif t[0] in "XYIJ":
                    xyij[t[0]] = int(t[1:])
                elif t[0] == "D":
                    v = int(t[1:])
                    if v in (1, 2, 3):
                        op = v
                    else:
                        sel = str(v)
                elif t[0] == "M":
                    if int(t[1:]) in (0, 2):
                        raise StopIteration
            if not xyij and op is None:
                continue
            if dec is None or scale is None:
                raise _Unsupported("coordinate format / unit statement missing before geometry")
            f = 10.0 ** dec
            nx = xyij["X"] / f * scale if "X" in xyij else cur[0]
            ny = xyij["Y"] / f * scale if "Y" in xyij else cur[1]
            if op is None:
                if last_op is None:
                    raise _Unsupported("coordinate without D-code")
                op = last_op
            last_op = op
            new = (nx, ny)
            if op == 2:
                if region is not None:
                    if contour and len(contour) >= 3:
                        region.append(contour)
                    contour = [new]
                cur = new
                continue
            if op == 1:
                if interp is None:
                    raise _Unsupported("D01 before any G01/G02/G03")
                if interp == 1:
                    pts = [cur, new]
                else:
                    ctr = (cur[0] + xyij.get("I", 0) / f * scale, cur[1] + xyij.get("J", 0) / f * scale)
                    pts = _flatten_arc(cur, new, ctr, interp == 2)
                if region is not None:
                    if contour is None:
                        contour = [cur]
                    contour.extend(pts[1:])
                else:
                    ap = apt.get(sel or "")
                    if ap is None:
                        raise _Unsupported(f"draw with undefined aperture D{sel}")
                    if ap[0] != "C":
                        raise _Unsupported(f"stroke with non-circular aperture {ap[0]!r}")
                    items.append(_item("draw", [(_flip(pts), False, ap[1][0] * scale / 2)], _flip([pts[0]])[0]))
                cur = new
                continue
            ap = apt.get(sel or "")
            if ap is None:
                raise _Unsupported(f"flash with undefined aperture D{sel}")
            sh = [([(px + nx, py + ny) for px, py in s[0]], s[1], s[2]) for s in _aperture_shapes(ap, scale, macros, notes)]
            if not sh:
                raise _Unsupported(f"aperture {ap[0]!r} produced no shape")
            items.append(_item("flash", [(_flip(s[0]), s[1], s[2]) for s in sh], (nx, -ny)))
            cur = new
    except StopIteration:
        pass
    except (_Unsupported, ValueError, KeyError, IndexError, ZeroDivisionError) as e:
        unsup.append(f"{type(e).__name__}: {e}")
    if notes:
        unsup.extend(f"unsupported {n}" for n in sorted(notes))
    return {"items": items, "function": function, "unsupported": sorted(set(unsup)), "scale": scale}


# -------------------------------------------------------------------------------------- Excellon reader
def parse_excellon(text: str) -> dict:
    """Excellon -> hits (round drills and SLOTS). A slot hit is a stadium: ``slot=(p1, p2)`` endpoints + ``dia``;
    ``x, y`` is always the centre (midpoint for a slot). Slots come from ``X..Y..G85X..Y..`` and from routed
    ``G00 X Y`` / ``M15`` / ``G01 X Y`` / ``M16`` sequences; routed arcs (G02/G03) make the file unsupported."""
    unit = 1.0
    tools: dict = {}
    hits: list = []
    unsup: list = []
    notes: set = set()
    func = None
    span = None
    pend = None
    cur = None
    route_from = None
    tool_down = False

    def add(t: dict, x1: float, y1: float, x2: float | None = None, y2: float | None = None) -> None:
        plated = (True if func == "Plated" else False if func == "NonPlated"
                  else (None if t["plating"] is None else t["plating"] == "Plated"))
        y1n = -y1
        if x2 is None:
            hits.append({"x": x1, "y": y1n, "dia": t["dia"], "plated": plated, "slot": None})
        else:
            y2n = -y2
            hits.append({"x": (x1 + x2) / 2, "y": (y1n + y2n) / 2, "dia": t["dia"], "plated": plated,
                         "slot": ((x1, y1n), (x2, y2n))})

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith(";"):
            m = re.match(r";\s*#@!\s*TF\.FileFunction,(\w+)(?:,(\d+),(\d+))?", s)
            if m:
                func = m.group(1)
                span = (int(m.group(2)), int(m.group(3))) if m.group(2) else None
            m = re.match(r";\s*#@!\s*TA\.AperFunction,(Plated|NonPlated)", s)
            if m:
                pend = m.group(1)
            continue
        if s.startswith("INCH"):
            unit = 25.4
            continue
        if s.startswith("METRIC"):
            unit = 1.0
            continue
        m = re.match(r"^T(\d+)C([\d.]+)", s)
        if m:
            tools[m.group(1)] = {"dia": float(m.group(2)) * unit, "plating": pend}
            pend = None
            continue
        m = re.match(r"^T(\d+)$", s)
        if m:
            cur = m.group(1)
            continue
        if s == "M30":
            break
        if s == "M15":
            tool_down = True
            continue
        if s == "M16":
            tool_down = False
            continue
        if s in ("G05", "G90", "G91") or s.startswith(("FMAT", "%", "M48", "VER")):
            if s == "G91":
                unsup.append("incremental Excellon coordinates (G91)")
            continue
        if re.match(r"^G0[23]", s):
            unsup.append("routed arc slot (G02/G03)")
            continue
        num = r"[+-]?[\d.]+"
        m = re.match(rf"^X({num})Y({num})G85X({num})Y({num})$", s)
        if m:
            if not all("." in g for g in m.groups()):
                unsup.append("non-decimal Excellon coordinates")
                continue
            t = tools.get(cur or "")
            if t is None:
                unsup.append(f"slot before a defined tool (T{cur})")
                continue
            a, b, c, d = (float(g) * unit for g in m.groups())
            add(t, a, b, c, d)
            continue
        m = re.match(rf"^(?:G00)?X({num})Y({num})$", s) if s.startswith("G00") else None
        if m:
            route_from = (float(m.group(1)) * unit, float(m.group(2)) * unit)
            continue
        m = re.match(rf"^G01X({num})Y({num})$", s)
        if m:
            if not tool_down or route_from is None:
                unsup.append("G01 route without M15 / G00 start")
                continue
            t = tools.get(cur or "")
            if t is None:
                unsup.append(f"route before a defined tool (T{cur})")
                continue
            to = (float(m.group(1)) * unit, float(m.group(2)) * unit)
            add(t, route_from[0], route_from[1], to[0], to[1])
            route_from = to
            continue
        m = re.match(rf"^X({num})Y({num})$", s)
        if m:
            if "." not in m.group(1) or "." not in m.group(2):
                unsup.append("non-decimal Excellon coordinates")
                continue
            t = tools.get(cur or "")
            if t is None:
                unsup.append(f"hit before a defined tool (T{cur})")
                continue
            add(t, float(m.group(1)) * unit, float(m.group(2)) * unit)
    return {"hits": hits, "function": func, "span": span, "unsupported": sorted(set(unsup)), "notes": sorted(notes)}


# ------------------------------------------------------------------------------------------ inputs
_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
_PNG = re.compile(r"^(\d+)\.c04-(.+)-v(\d+)\.png$")


def _scan_gerber_dir(path: Any) -> dict:
    if not isinstance(path, str) or not path:
        raise C04GateInputError("C04_GERBER_INPUT_MISSING: gerber_dir is required (non-empty path string)")
    if not os.path.isdir(path):
        raise C04GateInputError(f"C04_GERBER_INPUT_NOT_FOUND: gerber_dir={path!r} is not a directory")
    files = sorted(f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
    if not files:
        raise C04GateInputError(f"C04_GERBER_INPUT_EMPTY: gerber_dir={path!r} has no files")
    out: dict = {"copper": {}, "copper_n": {}, "profile": [], "drill": [], "other": [], "sha": {}}
    for f in files:
        p = os.path.join(path, f)
        out["sha"][f] = _sha256(p)
        with open(p, "rb") as fh:
            raw = fh.read()
        if b"\x00" in raw[:4096]:
            out["other"].append(f)
            continue
        text = raw.decode("utf-8", "ignore")
        head = text[:4000]
        if head.lstrip().startswith("M48"):
            d = parse_excellon(text)
            d["file"] = f
            out["drill"].append(d)
        elif "%FS" in head:
            g = parse_rs274x(text)
            g["file"] = f
            fn = (g["function"] or "").split(",")
            if fn[0] == "Copper":
                m = re.match(r"^L(\d+)$", fn[1]) if len(fn) > 1 else None
                if not m or len(fn) < 3:
                    out["other"].append(f)
                    continue
                n = int(m.group(1))
                name = {"Top": "F.Cu", "Bot": "B.Cu"}.get(fn[2]) or (f"In{n - 1}.Cu" if fn[2] == "Inr" else None)
                if name is None:
                    out["other"].append(f)
                elif name in out["copper"]:
                    raise C04GateInputError(f"C04_GERBER_INPUT_DUPLICATE_LAYER: {name} appears in {out['copper'][name]['file']} and {f}")
                else:
                    out["copper"][name] = g
                    out["copper_n"][name] = n
            elif fn[0] == "Profile":
                out["profile"].append(g)
            else:
                out["other"].append(f)
        else:
            out["other"].append(f)
    return out


def _board_objects(text: str) -> dict:
    """Pads (centre, copper layers, net, drill), vias and board copper layer names, straight from the s-expression."""
    root = parse_sexpr(text)
    if len(root) != 1 or not root[0] or root[0][0] != "kicad_pcb":
        raise C04GateInputError("C04_GATE_BOARD_FORMAT: top-level form is not (kicad_pcb ...)")
    pcb = root[0]
    layers = [l[1] for l in (_kid(pcb, "layers") or [])[1:]
              if isinstance(l, list) and len(l) > 1 and isinstance(l[1], str) and l[1].endswith(".Cu")]
    if not layers:
        raise C04GateInputError("C04_GERBER_BOARD_FIELD: board declares no copper layers")
    nets = {n[1]: (n[2] if len(n) > 2 else "") for n in _kids(pcb, "net")}

    def cu(names: list) -> list:
        out: list = []
        for s in names:
            for l in (layers if s == "*.Cu" else [s] if s in layers else []):
                if l not in out:
                    out.append(l)
        return out

    pads: list = []
    unmodeled: list = []
    for fp in _kids(pcb, "footprint"):
        ref = _fp_ref(fp)
        at = _kid(fp, "at")
        x, y = _xy(at, f"{ref}.at")
        rot = _f(at[3], f"{ref}.at.angle") if len(at) > 3 else 0.0
        for p in _kids(fp, "pad"):
            num = p[1] if len(p) > 1 else ""
            kind = p[2] if len(p) > 2 else ""
            px, py = _xy(_kid(p, "at"), f"{ref}.pad{num}.at")
            rx, ry = _rot(px, py, rot)
            d = _kid(p, "drill")
            drill = None
            slot = None
            dmax = None
            pat = _kid(p, "at")
            pang = _f(pat[3], f"{ref}.pad{num}.angle") if len(pat) > 3 else 0.0
            sz = _kid(p, "size")
            sw = _f(sz[1], f"{ref}.pad{num}.size") if sz and len(sz) > 1 else 0.0
            sh = _f(sz[2], f"{ref}.pad{num}.size") if sz and len(sz) > 2 else sw
            cx, cy = x + rx, y + ry
            if d is not None:
                nums = [t for t in d[1:] if isinstance(t, str) and t != "oval"]
                if "oval" in d:
                    if len(nums) < 2:
                        unmodeled.append(f"{ref}.{num}: oval drill without two sizes")
                    else:
                        a, b = _f(nums[0], f"{ref}.pad{num}.drill"), _f(nums[1], f"{ref}.pad{num}.drill")
                        drill, dmax = min(a, b), max(a, b)
                        half = (dmax - drill) / 2
                        if half > 1e-9:
                            off = (half, 0.0) if a >= b else (0.0, half)
                            u = _rot(off[0], off[1], pang)
                            slot = ((cx + u[0], cy + u[1]), (cx - u[0], cy - u[1]))
                elif nums:
                    drill = dmax = _f(nums[0], f"{ref}.pad{num}.drill")
            cl = cu([s for s in (_kid(p, "layers") or [])[1:] if isinstance(s, str)])
            # KiCad plots no copper for an NPTH pad that has no annulus (size <= drill) or no copper layer.
            drill_only = kind == "np_thru_hole" and (not cl or (dmax is not None and sw <= dmax + 1e-6 and sh <= dmax + 1e-6))
            pads.append({"ref": ref, "number": num, "kind": kind, "c": (cx, cy), "cu": cl, "slot": slot,
                         "net": _net_name(_kid(p, "net")), "drill": drill, "drill_only": drill_only})
    vias: list = []
    for v in _kids(pcb, "via"):
        vx, vy = _xy(_kid(v, "at"), "via.at")
        names = [s for s in (_kid(v, "layers") or [])[1:] if isinstance(s, str) and s in layers]
        if len(names) != 2:
            raise C04GateInputError(f"C04_GERBER_BOARD_FIELD: via at ({vx}, {vy}) has no 2-layer (layers ..) pair")
        i0, i1 = sorted(layers.index(n) for n in names)
        dn = _kid(v, "drill")
        if dn is None or len(dn) < 2:
            raise C04GateInputError(f"C04_GERBER_BOARD_FIELD: via at ({vx}, {vy}) has no drill")
        nn = _kid(v, "net")
        vias.append({"c": (vx, vy), "cu": layers[i0:i1 + 1], "drill": _f(dn[1], "via.drill"),
                     "net": nets.get(nn[1], "") if nn and len(nn) > 1 else ""})
    graphics = {g[0] for g in pcb if isinstance(g, list) and g and g[0] in ("gr_arc", "gr_circle")
                and (_kid(g, "layer") or [None, None])[1] == "Edge.Cuts"}
    return {"layers": layers, "pads": pads, "vias": vias, "unmodeled": unmodeled, "edge_has_arcs": bool(graphics)}


# ------------------------------------------------------------------------------------ G-01 parity
def _pt(c: tuple) -> dict:
    return _item("point", [([c], False, 0.0)], c)


def _covering(items: list, c: tuple, tol: float) -> list:
    p = _pt(c)
    return [it for it in items if item_distance(it, p, tol) <= tol]


def _required(p: dict, layers: list) -> list:
    """Copper layers on which a pad MUST have a flash/region: outer layers only (inner flashes are explained, not required)."""
    if p.get("drill_only"):
        return []
    outer = (layers[0], layers[-1])
    r = [l for l in p["cu"] if l in outer]
    return r or list(p["cu"])


def _vname(v: dict) -> str:
    return f"via@{v['c'][0]:.4f},{v['c'][1]:.4f}"


def _slot_match(want: Any, got: Any, tol: float) -> bool:
    """Round vs round, or slot vs slot with the same two endpoints (either order) within tol."""
    if want is None or got is None:
        return want is None and got is None
    (a, b), (c, d) = want, got
    def near(p: tuple, q: tuple) -> bool:
        return math.hypot(p[0] - q[0], p[1] - q[1]) <= tol
    return (near(a, c) and near(b, d)) or (near(a, d) and near(b, c))


def _poly_dev(a: list, b_segs: list) -> float:
    return max((min(_pt_seg(p[0], p[1], *s) for s in b_segs) for p in a), default=0.0)


def _gerber_loops(prof: list) -> tuple:
    segs = []
    for g in prof:
        for it in g["items"]:
            if it["kind"] != "draw":
                return None, "profile contains a non-draw item (region/flash)"
            for pts, _c, _r in it["shapes"]:
                segs += [(a[0], a[1], b[0], b[1]) for a, b in zip(pts[:-1], pts[1:])]
    if not segs:
        return None, "profile gerber has no draws"
    try:
        return _chain(segs), ""
    except C04GateInputError as e:
        return None, str(e)


def gate_export_parity(obj: dict, scan: dict, board_edge: list, pad_tol: float, edge_tol: float, drill_tol: float) -> dict:
    off: list = []
    unmeas: list = []
    layers = obj["layers"]
    per_layer: dict = {}
    for L in layers:
        want = [(f"{p['ref']}.{p['number']}", p["c"], "pad") for p in obj["pads"] if L in _required(p, layers)]
        outer = (layers[0], layers[-1])
        want += [(_vname(v), v["c"], "via") for v in obj["vias"] if L in v["cu"] and L in outer]
        g = scan["copper"].get(L)
        if g is None:
            if want:
                off.append({"kind": "layer_file_missing", "layer": L, "needed_by": len(want)})
            continue
        if g["unsupported"]:
            unmeas.append({"layer": L, "file": g["file"], "reasons": g["unsupported"]})
            continue
        fl = [it for it in g["items"] if it["kind"] in ("flash", "region")]
        miss = [w for w in want if not _covering(fl, w[1], pad_tol)]
        known = [p["c"] for p in obj["pads"] if L in p["cu"] and not p["drill_only"]] + [v["c"] for v in obj["vias"] if L in v["cu"]]
        extra = [it for it in g["items"] if it["kind"] == "flash"
                 and not any(math.hypot(it["at"][0] - c[0], it["at"][1] - c[1]) <= pad_tol for c in known)]
        for w in miss:
            off.append({"kind": "missing_flash", "layer": L, "what": w[0], "type": w[2], "at": [round(w[1][0], 4), round(w[1][1], 4)]})
        for it in extra:
            off.append({"kind": "extra_flash", "layer": L, "at": [round(it["at"][0], 4), round(it["at"][1], 4)]})
        per_layer[L] = {"file": g["file"], "required": len(want), "missing": len(miss), "flashes": sum(1 for it in g["items"] if it["kind"] == "flash"),
                        "extra": len(extra), "items": len(g["items"])}
    # drills: board drills vs drill-file hits (each hit consumed once)
    hits = [dict(h, file=d["file"]) for d in scan["drill"] for h in d["hits"]]
    for d in scan["drill"]:
        if d["unsupported"]:
            unmeas.append({"layer": "drill", "file": d["file"], "reasons": d["unsupported"]})
    want_d = [(f"{p['ref']}.{p['number']}", p["c"], p["drill"], p["kind"] != "np_thru_hole", p["slot"]) for p in obj["pads"] if p["drill"]]
    want_d += [(_vname(v), v["c"], v["drill"], True, None) for v in obj["vias"]]
    used: set = set()
    dmiss = []
    for name, c, dia, plated, slot in want_d:
        best = None
        for i, h in enumerate(hits):
            if i in used:
                continue
            dd = math.hypot(h["x"] - c[0], h["y"] - c[1])
            if (dd <= drill_tol and abs(h["dia"] - dia) <= DRILL_DIA_TOL_MM and _slot_match(slot, h.get("slot"), drill_tol)
                    and (best is None or dd < best[0])):
                best = (dd, i)
        if best is None:
            dmiss.append(name)
            off.append({"kind": "missing_drill", "what": name, "dia_mm": dia, "slot": slot is not None,
                        "at": [round(c[0], 4), round(c[1], 4)]})
            continue
        used.add(best[1])
        h = hits[best[1]]
        if h["plated"] is not None and h["plated"] != plated:
            off.append({"kind": "drill_plating_mismatch", "what": name, "board_plated": plated, "file_plated": h["plated"]})
    extra_d = [h for i, h in enumerate(hits) if i not in used]
    for h in extra_d:
        off.append({"kind": "extra_drill", "at": [round(h["x"], 4), round(h["y"], 4)], "dia_mm": h["dia"], "file": h["file"]})
    # Edge.Cuts
    edge: dict = {}
    if not scan["profile"]:
        off.append({"kind": "profile_missing", "detail": "no Profile (Edge.Cuts) gerber found in gerber_dir"})
    elif any(g["unsupported"] for g in scan["profile"]):
        unmeas.append({"layer": "Edge.Cuts", "reasons": sorted({r for g in scan["profile"] for r in g["unsupported"]})})
    else:
        gl, why = _gerber_loops(scan["profile"])
        if gl is None:
            off.append({"kind": "profile_unusable", "detail": why})
        else:
            try:
                bl = _chain(board_edge)
            except C04GateInputError as e:
                raise C04GateInputError(str(e))
            gs = [(*l[i], *l[(i + 1) % len(l)]) for l in gl for i in range(len(l))]
            bs = [(*l[i], *l[(i + 1) % len(l)]) for l in bl for i in range(len(l))]
            dev = max(_poly_dev([p for l in bl for p in l], gs), _poly_dev([p for l in gl for p in l], bs))
            edge = {"board_loops": len(bl), "gerber_loops": len(gl), "max_vertex_deviation_mm": round(dev, 6), "tol_mm": edge_tol}
            if len(bl) != len(gl) or dev > edge_tol:
                off.append({"kind": "outline_mismatch", **edge})
    drill_only = [f"{p['ref']}.{p['number'] or '-'}" for p in obj["pads"] if p["drill_only"]]
    measured = {"per_layer": per_layer, "drills": {"board": len(want_d), "hits": len(hits), "missing": len(dmiss), "extra": len(extra_d),
                                                   "slots_board": sum(1 for w in want_d if w[4]), "slots_file": sum(1 for h in hits if h.get("slot"))},
                "drill_only_pads": drill_only,
                "edge_cuts": edge, "tolerances_mm": {"pad": pad_tol, "edge": edge_tol, "drill": drill_tol, "drill_dia": DRILL_DIA_TOL_MM},
                "unmeasured_parts": unmeas, "unmodeled": obj["unmodeled"],
                "outline_comparison": "symmetric vertex-to-polyline distance (arc chords differ between the board loader and the gerber), not a hash equality"}
    return _gate("fail" if off else ("unmeasured" if unmeas else "pass"), measured, off)


# ------------------------------------------------------------------------------ G-02 connectivity
class _DSU:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, a: int) -> int:
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _span_layers(span: Any, scan: dict) -> list:
    """Copper layer names a drill file's TF.FileFunction span (from, to) covers; no span => every copper layer."""
    if not span:
        return list(scan["copper_n"])
    lo, hi = min(span), max(span)
    return [n for n, k in scan["copper_n"].items() if lo <= k <= hi]


def gate_connectivity(obj: dict, scan: dict) -> dict:
    layers = obj["layers"]
    usable = {L: g for L, g in scan["copper"].items() if not g["unsupported"] and L in layers}
    gaps = [{"layer": L, "reason": ("gerber file missing" if L not in scan["copper"] else "unsupported: "
                                    + "; ".join(scan["copper"][L]["unsupported"]))}
            for L in layers if L not in usable]
    for d in scan["drill"]:
        if d["unsupported"]:
            gaps.append({"layer": "drill", "file": d["file"], "reason": "unsupported: " + "; ".join(d["unsupported"])})
    if not usable:
        return _gate("unmeasured", {"reason": "no supported copper gerber layer", "unmeasured_parts": gaps}, [])
    base: dict = {}
    nodes: list = []
    for L, g in usable.items():
        base[L] = len(nodes)
        nodes.extend((L, i) for i in range(len(g["items"])))
    dsu = _DSU(len(nodes))
    # same-layer touching / overlapping copper (exact analytic distance <= CONNECT_TOL_MM)
    for L, g in usable.items():
        its = g["items"]
        order = sorted(range(len(its)), key=lambda i: its[i]["bbox"][0])
        for a, i in enumerate(order):
            xmax = its[i]["bbox"][2] + CONNECT_TOL_MM
            for j in order[a + 1:]:
                if its[j]["bbox"][0] > xmax:
                    break
                if dsu.find(base[L] + i) != dsu.find(base[L] + j) and item_distance(its[i], its[j], CONNECT_TOL_MM) <= CONNECT_TOL_MM:
                    dsu.union(base[L] + i, base[L] + j)
    # plated drill hits join every copper item they touch inside the drill file's layer span
    unplated_or_unknown = 0
    plated_hits = 0
    npth_hits: list = []
    unexplained_unplated: list = []
    for d in scan["drill"]:
        if d["unsupported"]:
            continue
        span = [L for L in _span_layers(d["span"], scan) if L in usable]
        for h in d["hits"]:
            if h["plated"] is not True:
                unplated_or_unknown += 1
                hit = {"at": [round(h["x"], 4), round(h["y"], 4)], "dia_mm": h["dia"], "plated": h["plated"], "slot": bool(h.get("slot"))}
                if any(q["kind"] == "np_thru_hole" and q["drill"] and math.hypot(q["c"][0] - h["x"], q["c"][1] - h["y"]) <= DEFAULT_DRILL_TOL_MM
                       and abs(q["drill"] - h["dia"]) <= DRILL_DIA_TOL_MM for q in obj["pads"]):
                    npth_hits.append(hit)
                else:
                    unexplained_unplated.append(hit)
                continue
            plated_hits += 1
            if h.get("slot"):
                p = _item("slot", [(list(h["slot"]), False, h["dia"] / 2)], (h["x"], h["y"]))
            else:
                p = _pt((h["x"], h["y"]))
            touched = [base[L] + i for L in span for i, it in enumerate(usable[L]["items"])
                       if item_distance(it, p, CONNECT_TOL_MM) <= CONNECT_TOL_MM]
            for t in touched[1:]:
                dsu.union(touched[0], t)
    # terminals: pads + vias carrying a net
    terms: list = []
    for p in obj["pads"]:
        if p["net"] and p["cu"]:
            terms.append({"name": f"{p['ref']}.{p['number']}", "net": p["net"], "c": p["c"], "cu": p["cu"]})
    for v in obj["vias"]:
        if v["net"]:
            terms.append({"name": _vname(v), "net": v["net"], "c": v["c"], "cu": v["cu"]})
    off: list = []
    for t in terms:
        pt = _pt(t["c"])
        roots: set = set()
        for L in t["cu"]:
            if L not in usable:
                continue
            for i, it in enumerate(usable[L]["items"]):
                if item_distance(it, pt, CONNECT_TOL_MM) <= CONNECT_TOL_MM:
                    roots.add(dsu.find(base[L] + i))
        t["roots"] = roots
        if not roots:
            if any(L in usable for L in t["cu"]):
                off.append({"kind": "terminal_without_copper", "net": t["net"], "terminal": t["name"]})
        elif len(roots) > 1:
            off.append({"kind": "barrel_open", "net": t["net"], "terminal": t["name"], "components": len(roots),
                        "detail": "copper of this pad/via on its layers is not joined (no plated drill hit connects them)"})
    by_net: dict = {}
    for t in terms:
        by_net.setdefault(t["net"], []).append(t)
    single: list = []
    open_nets: set = {o["net"] for o in off}
    for net, ts in sorted(by_net.items()):
        if len(ts) < 2:
            single.append({"net": net, "terminal": ts[0]["name"]})
            continue
        groups: dict = {}
        for t in ts:
            if len(t["roots"]) == 1:
                groups.setdefault(next(iter(t["roots"])), []).append(t["name"])
        if len(groups) > 1:
            open_nets.add(net)
            off.append({"kind": "open", "net": net, "components": sorted(sorted(g) for g in groups.values())})
    comp_nets: dict = {}
    for t in terms:
        for r in t["roots"]:
            comp_nets.setdefault(r, {}).setdefault(t["net"], []).append(t["name"])
    for r, nm in sorted(comp_nets.items()):
        if len(nm) > 1:
            off.append({"kind": "short", "nets": sorted(nm), "terminals": {n: sorted(v) for n, v in sorted(nm.items())}})
    for h in unexplained_unplated:
        off.append({"kind": "unplated_hit_not_npth", **h,
                    "detail": "drill hit is not plated and matches no np_thru_hole board pad; plated barrels cannot join layers through it"})
    comps = len({dsu.find(i) for i in range(len(nodes))})
    measured = {"layers_measured": sorted(usable), "copper_items": len(nodes), "components": comps,
                "plated_hits": plated_hits, "unplated_or_unknown_hits": unplated_or_unknown,
                "unplated_hits": {"count": unplated_or_unknown, "matched_board_npth_pads": len(npth_hits), "unexplained": unexplained_unplated,
                                  "matched": npth_hits},
                "nets_with_terminals": len(by_net), "terminals": len(terms),
                "open_nets": sorted(open_nets), "short_count": sum(1 for o in off if o["kind"] == "short"),
                "single_terminal_nets": single, "unmeasured_parts": gaps,
                "method": f"exact analytic shape distance <= {CONNECT_TOL_MM} mm (no raster); plated hits join items by "
                          f"point containment inside the drill file layer span; arc chords sagitta <= {ARC_SAGITTA_MM} mm"}
    return _gate("fail" if off else ("unmeasured" if gaps else "pass"), measured, off)


# ------------------------------------------------------------------------------------ G-03 keepout
def gate_keepout_copper(scan: dict, kos: list, layers: list) -> dict:
    if not kos:
        return _gate("unmeasured", {"reason": "no keepouts declared (None or []): nothing to intersect, a vacuous pass is not issued"}, [])
    usable = {L: g for L, g in scan["copper"].items() if not g["unsupported"] and L in layers}
    gaps = [{"layer": L, "reason": "gerber file missing" if L not in scan["copper"] else "unsupported"} for L in layers if L not in usable]
    off: list = []
    for ko in kos:
        b = ko["box"]
        boxshape = ([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], True, 0.0)
        for L, g in usable.items():
            if ko["layer"] and ko["layer"] != L:
                continue
            for it in g["items"]:
                if not _boxes_hit(it["bbox"], b):
                    continue
                if any(shape_distance(s, boxshape, 0.0) <= 0.0 for s in it["shapes"]):
                    off.append({"keepout": ko["name"], "layer": L, "kind": it["kind"],
                                "at": [round(it["at"][0], 4), round(it["at"][1], 4)]})
    if not usable:
        return _gate("unmeasured", {"reason": "no supported copper gerber layer", "unmeasured_parts": gaps}, [])
    measured = {"keepouts": [{"name": k["name"], "box_mm": [round(v, 4) for v in k["box"]], "layer": k["layer"]} for k in kos],
                "layers_examined": sorted(usable), "offender_count": len(off), "unmeasured_parts": gaps,
                "frame": "gerber coordinates read as board-file frame (y flipped); assumes no aux/drill origin offset (G-01 would expose one)"}
    return _gate("fail" if off else ("unmeasured" if gaps else "pass"), measured, off)


# ------------------------------------------------------------------------------ G-04 render binding
DEFAULT_RENDER_VIEWS = ("F.Cu", "B.Cu", "copper-composite")
_INNER_VIEW = re.compile(r"^In\d+\.Cu$")


def gate_render_binding(human_dir: Any, scan: dict, render_views: Any = None) -> dict:
    """Only gerber-derived layer renders are bound: view in ``render_views`` (default F.Cu, B.Cu, In<n>.Cu,
    copper-composite). Other NN.c04-*.png (placement, routed, ...) are listed in measured.out_of_scope."""
    if human_dir is None:
        return _gate("unmeasured", {"reason": "human_dir not supplied"}, [])
    if not isinstance(human_dir, str) or not os.path.isdir(human_dir):
        raise C04GateInputError(f"C04_GERBER_INPUT_NOT_FOUND: human_dir={human_dir!r} is not a directory")
    if render_views is None:
        rviews = DEFAULT_RENDER_VIEWS
    else:
        if (not isinstance(render_views, list) or not render_views
                or any(not isinstance(v, str) or not v for v in render_views)):
            raise C04GateInputError("C04_GERBER_INPUT_FIELD: render_views must be a non-empty list of strings")
        rviews = tuple(render_views)
    allpngs = sorted(f for f in os.listdir(human_dir) if _PNG.match(f))
    pngs = []
    out_of_scope = []
    for f in allpngs:
        view = _PNG.match(f).group(2)
        if view in rviews or (render_views is None and _INNER_VIEW.match(view)):
            pngs.append(f)
        else:
            out_of_scope.append(f)
    if not pngs:
        return _gate("unmeasured", {"reason": "no gerber-derived layer render (views %s or In<n>.Cu) in human_dir" % list(rviews),
                                    "human_dir": human_dir, "out_of_scope": out_of_scope}, [])
    by_sha = {}
    for n, s in scan["sha"].items():
        by_sha.setdefault(s, []).append(n)
    off: list = []
    bound: list = []
    for f in pngs:
        stem = f[:-4]
        side = [os.path.join(human_dir, c) for c in (f + ".json", stem + ".json", stem + ".caption.txt", stem + ".txt", stem + ".md")
                if os.path.isfile(os.path.join(human_dir, c))]
        if not side:
            off.append({"png": f, "kind": "no_sidecar"})
            continue
        txt = ""
        for sp in side:
            with open(sp, encoding="utf-8", errors="ignore") as fh:
                txt += fh.read() + "\n"
        hashes = sorted(set(_HEX64.findall(txt.lower())))
        if not hashes:
            off.append({"png": f, "kind": "no_sha256_in_sidecar", "sidecar": [os.path.basename(s) for s in side]})
            continue
        hits = [(h, by_sha[h]) for h in hashes if h in by_sha]
        if not hits:
            off.append({"png": f, "kind": "sha_not_in_gerber_dir", "sha256": hashes})
            continue
        named = [n for n in scan["sha"] if n in txt]
        wrong = [n for n in named if scan["sha"][n] not in [h for h, _ in hits] and not any(scan["sha"][n] == h for h in hashes)]
        if wrong:
            off.append({"png": f, "kind": "named_file_sha_differs", "files": wrong})
            continue
        bound.append({"png": f, "gerber_files": sorted({n for _, ns in hits for n in ns})})
    measured = {"pngs": len(pngs), "bound": len(bound), "bindings": bound, "render_views": list(rviews),
                "out_of_scope": out_of_scope,
                "scope": "presence + sha binding only; image content is NOT judged"}
    return _gate("fail" if off else "pass", measured, off)


# --------------------------------------------------------------------------------------- entrypoint
def c04_gerber_gate(board_path: str, gerber_dir: str, keepouts: list | None = None, *, human_dir: str | None = None,
                    pad_tol_mm: float | None = None, edge_tol_mm: float | None = None,
                    drill_tol_mm: float | None = None, render_views: list | None = None) -> dict:
    """GATE-C04-05 made measurable: G-01 export parity, G-02 copper connectivity from gerber bytes, G-03 keepout on
    copper, G-04 render binding. ``ok`` = G-01..G-03 pass. Never mutates inputs."""
    btext = _read(board_path, "board_path", ".kicad_pcb")
    tol = {}
    for nm, v, d in (("pad_tol_mm", pad_tol_mm, DEFAULT_PAD_TOL_MM), ("edge_tol_mm", edge_tol_mm, DEFAULT_EDGE_TOL_MM),
                     ("drill_tol_mm", drill_tol_mm, DEFAULT_DRILL_TOL_MM)):
        tol[nm] = d if v is None else _num(v, nm)
        if tol[nm] < 0:
            raise C04GateInputError(f"C04_GERBER_INPUT_FIELD: {nm} must be >= 0, got {tol[nm]}")
    kos = _validate_keepouts(keepouts) if keepouts is not None else []
    scan = _scan_gerber_dir(gerber_dir)
    obj = _board_objects(btext)
    board = load_board(btext)
    if len(board["edge"]) < 3:
        raise C04GateInputError(f"C04_GATE_BOARD_GEOMETRY: Edge.Cuts outline has {len(board['edge'])} segment(s); a closed outline needs >= 3")
    if not obj["pads"] and not obj["vias"]:
        raise C04GateInputError("C04_GATE_BOARD_GEOMETRY: board has no pads or vias to compare")
    gates = {
        "G-01": gate_export_parity(obj, scan, board["edge"], tol["pad_tol_mm"], tol["edge_tol_mm"], tol["drill_tol_mm"]),
        "G-02": gate_connectivity(obj, scan),
        "G-03": gate_keepout_copper(scan, kos, obj["layers"]),
        "G-04": gate_render_binding(human_dir, scan, render_views),
    }
    if keepouts is None:
        gates["G-03"]["measured"]["reason"] = "keepouts not supplied (None): " + gates["G-03"]["measured"].get("reason", "")
    return {"ok": all(gates[g]["status"] == "pass" for g in ("G-01", "G-02", "G-03")),
            "gates": gates,
            "unmeasured_gates": [g for g in GATE_IDS if gates[g]["status"] == "unmeasured"],
            "inputs": {"board_sha256": _sha256(board_path), "gerber_files_sha256": dict(scan["sha"]),
                       "board_hashes": c04_board_hashes(board_path)},
            "method": {"schema": SCHEMA, "connectivity": "exact analytic geometry, no raster", "connect_tol_mm": CONNECT_TOL_MM,
                       "arc_sagitta_mm": ARC_SAGITTA_MM, "tolerances_mm": tol, "limits": list(LIMITS)},
            "scope": "gerber-level copper connectivity + export parity; says nothing about clearance, DRC or electrical function"}

