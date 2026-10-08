"""bodesign_c04_routing_gate: routing-class gate (R-01..R-06) over a routed .kicad_pcb.

R-01 track width per net class (class min width; declared QFN escape necks listed, not failed)
R-02 via count per rail layer transition (class ``min_vias_per_transition``)
R-03 pad entry angle / acid trap (track vs pad edge, flag < ``min_entry_angle_deg``, default 45: 45-degree entries are standard)
R-04 copper-pour islands (filled-polygon outer loops touching no same-net pad / via / track)
R-05 paired net length / skew (declared ``pairs`` only; absent => unmeasured)
R-06 copper-to-keepout margin on tracks / vias / fills (``keepout_margin_mm`` required with keepouts)
R-07 minimum pour neck width (narrowest copper between two boundary stretches of one filled polygon; threshold = the
     net's class min track width, same source as R-01)
R-08 escape feasibility, pre-route (class min width W + clearance C must fit between a pad and its neighbours on at least one
     exit side; counts toward ok only on a board with no tracks/vias, informational on a routed board)

Everything is read from the .kicad_pcb s-expression (loader reused from c04_gate). Net classes come from an explicit
``classes`` argument, else the sibling .kicad_pro ``net_settings``, else board ``(net_class ...)`` blocks; if none
names the nets the gate raises. Anything not computable is ``unmeasured`` with a reason, never pass.
``ok`` = R-01..R-04, R-06 and R-07 pass, and R-05 passes when pairs are declared.
"""
from __future__ import annotations

import fnmatch
import json
import math
import os
from typing import Any

from .c04_gate import (C04GateInputError, _arc_points, _box_seg_distance, _f, _fp_ref, _kid, _kids, _net_name,
                       _pt_seg, _rot, _seg_seg, _sha256, _validate_keepouts, _xy, _read, parse_sexpr)

SCHEMA = "c04_routing_gate/1"
GATE_IDS = ("R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07", "R-08")
EPS = 1e-6
DEFAULT_ENTRY_ANGLE_DEG = 45.0
NECK_CLUSTER_MM = 1.0
NECK_MIN_BOUNDARY_FACTOR = 3.0
LIMITS = (
    "back-side footprint mirroring is not modelled (pad world position assumes an unflipped footprint); "
    "R-01 exemption is per segment (endpoint on a declared ref's pad AND segment length <= max_length_mm), not per chain; "
    "R-02 counts vias only (through-hole pads are listed, not counted) and uses the net's own copper layers; "
    "R-03 supports rect/roundrect/circle/oval pads and custom pads built from anchor rect|circle plus filled gr_poly/gr_rect/gr_circle "
    "primitives (union outline; stroke primitives, unfilled primitives or other anchors are listed unmeasured); corner rounding is ignored; "
    "R-03 detects teardrop zones only, track fans are not detected; "
    "R-04 islands are filled-polygon outer loops, evaluated on the stored fill (a stale fill is judged as stored); "
    "R-05 length is the sum of all track segments of the net (vias, stubs and branches included as copper length); "
    "R-06 distance is edge-to-edge (track half-width / via radius subtracted) to the keepout box, fills by polygon edge; "
    "R-07 measures the stored fill: narrowness is found as pairs of non-adjacent boundary edges closer than the class min width "
    "whose midpoint lies inside the copper and whose boundary-path separation exceeds 3x the threshold (same loop) or that lie on "
    "different loops (outer vs hole); a dead-end narrow spike is reported alongside true necks (kind neck_or_spike), "
    "touching (distance < 1e-6) edges are not examined, widths are polygon-edge distances (no medial-axis / raster), and "
    "offenders are clustered per 1 mm cell keeping the narrowest."
)
_ZERO = 1e-9


# ------------------------------------------------------------------------------------------- geometry
def _poly_area_centroid(pts: list) -> tuple:
    a = cx = cy = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    a /= 2.0
    if abs(a) < _ZERO:
        return 0.0, (pts[0][0], pts[0][1]) if pts else (0.0, 0.0)
    return a, (cx / (6 * a), cy / (6 * a))


def _pip(p: tuple, pts: list) -> bool:
    """Even-odd point in polygon (works on KiCad fractured chains: bridge edges are traversed twice)."""
    x, y = p
    hit = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def _split_loops(chain: list) -> list:
    """Split a KiCad fractured polygon chain into simple loops at repeated vertices; zero-area loops are dropped."""
    loops: list = []
    stack: list = []
    index: dict = {}
    for pt in chain:
        key = (round(pt[0], 6), round(pt[1], 6))
        if key in index:
            i = index[key]
            loop = stack[i:]
            for q in loop[1:]:
                index.pop((round(q[0], 6), round(q[1], 6)), None)
            stack = stack[:i + 1]
            if len(loop) >= 3 and abs(_poly_area_centroid(loop)[0]) > 1e-9:
                loops.append(loop)
        else:
            index[key] = len(stack)
            stack.append(pt)
    if len(stack) >= 3 and abs(_poly_area_centroid(stack)[0]) > 1e-9:
        loops.append(stack)
    return loops


def _components(chain: list) -> list:
    """Outer loops of a fill polygon with their hole loops: [{loop, area, centroid, holes}]."""
    loops = _split_loops(chain)
    if not loops:
        return []
    items = []
    for lp in loops:
        a, c = _poly_area_centroid(lp)
        items.append({"loop": lp, "signed": a, "centroid": c})
    items.sort(key=lambda d: -abs(d["signed"]))
    outer_sign = 1 if items[0]["signed"] > 0 else -1
    outers = [d for d in items if (d["signed"] > 0) == (outer_sign > 0)]
    for d in outers:
        d["holes"] = []
    for d in items:
        if (d["signed"] > 0) != (outer_sign > 0):
            for o in outers:
                if o is not d and _pip(d["loop"][0], o["loop"]):
                    o["holes"].append(d)
                    break
    out = []
    for o in outers:
        area = abs(o["signed"]) - sum(abs(h["signed"]) for h in o["holes"])
        out.append({"loop": o["loop"], "area": area, "centroid": o["centroid"],
                    "holes": [h["loop"] for h in o["holes"]]})
    return out


def _in_component(p: tuple, comp: dict) -> bool:
    return _pip(p, comp["loop"]) and not any(_pip(p, h) for h in comp["holes"])


def _loop_dist(p: tuple, loop: list) -> float:
    n = len(loop)
    return min(_pt_seg(p[0], p[1], *loop[i], *loop[(i + 1) % n]) for i in range(n))


def _seg_len(a: tuple, b: tuple) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _near_component(p: tuple, comp: dict, reach: float) -> bool:
    if _in_component(p, comp):
        return True
    if reach <= 0:
        return False
    return min([_loop_dist(p, comp["loop"])] + [_loop_dist(p, h) for h in comp["holes"]]) <= reach


def _seg_hits_loop(a: tuple, b: tuple, loop: list) -> bool:
    n = len(loop)
    return any(_seg_seg(a, b, loop[i], loop[(i + 1) % n]) <= 0.0 for i in range(n))


def _box_polygon_distance(box: tuple, comp: dict) -> float:
    """Distance from an axis box to the filled region of a component (0 on overlap)."""
    loops = [comp["loop"]] + comp["holes"]
    corners = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    if any(_in_component(c, comp) for c in corners):
        return 0.0
    for lp in comp["loop"], :
        if any(box[0] <= q[0] <= box[2] and box[1] <= q[1] <= box[3] and _in_component(q, comp) for q in lp):
            return 0.0
    best = math.inf
    for lp in loops:
        n = len(lp)
        for i in range(n):
            d = _box_seg_distance(box, (*lp[i], *lp[(i + 1) % n]))
            if d < best:
                best = d
                if best <= 0.0:
                    return 0.0
    return best


# ------------------------------------------------------------------------------- pad outline parts
# A pad outline is a list of parts in the pad-local frame: ("poly", [pts]) or ("circ", (cx, cy), r). Custom pads are the union of
# the anchor shape and every filled primitive; strokes (gr_line / gr_arc / gr_curve) and unfilled shapes are NOT modelled.
def _custom_parts(p: list, w: float, h: float) -> tuple:
    """(parts, None) or (None, reason) for a ``custom`` pad node."""
    opt = _kid(p, "options")
    anc = _kid(opt, "anchor") if opt else None
    kind = anc[1] if anc and len(anc) > 1 else None
    if kind == "rect":
        parts: list = [("poly", [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])]
    elif kind == "circle":
        parts = [("circ", (0.0, 0.0), w / 2)]
    else:
        return None, f"custom pad anchor {kind!r} not declared as rect/circle"
    prim = _kid(p, "primitives")
    for g in (prim or [])[1:]:
        if not isinstance(g, list) or not g:
            continue
        fill = _kid(g, "fill")
        filled = bool(fill and len(fill) > 1 and fill[1] in ("yes", "solid", "true"))
        if g[0] not in ("gr_poly", "gr_rect", "gr_circle"):
            return None, f"custom pad primitive {g[0]!r} (stroke) not modelled"
        if not filled:
            return None, f"custom pad primitive {g[0]!r} is not filled; outline-only primitives are not modelled"
        if g[0] == "gr_poly":
            pts = [(_f(c[1], "gr_poly.xy"), _f(c[2], "gr_poly.xy")) for c in (_kid(g, "pts") or [])[1:]
                   if isinstance(c, list) and len(c) >= 3 and c[0] == "xy"]
            if len(pts) < 3:
                return None, "custom pad gr_poly with fewer than 3 points"
            parts.append(("poly", pts))
        elif g[0] == "gr_rect":
            a, b = _xy(_kid(g, "start"), "gr_rect.start"), _xy(_kid(g, "end"), "gr_rect.end")
            parts.append(("poly", [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (a[0], b[1])]))
        else:
            c, e = _xy(_kid(g, "center"), "gr_circle.center"), _xy(_kid(g, "end"), "gr_circle.end")
            parts.append(("circ", c, math.hypot(e[0] - c[0], e[1] - c[1])))
    return parts, None


def _in_parts(pt: tuple, parts: list) -> bool:
    for q in parts:
        if q[0] == "poly":
            if _pip(pt, q[1]):
                return True
        elif math.hypot(pt[0] - q[1][0], pt[1] - q[1][1]) <= q[2]:
            return True
    return False


def _parts_dist(pt: tuple, parts: list) -> float:
    best = math.inf
    for q in parts:
        if q[0] == "poly":
            if _pip(pt, q[1]):
                return 0.0
            n = len(q[1])
            best = min([best] + [_pt_seg(pt[0], pt[1], *q[1][i], *q[1][(i + 1) % n]) for i in range(n)])
        else:
            best = min(best, max(0.0, math.hypot(pt[0] - q[1][0], pt[1] - q[1][1]) - q[2]))
    return best


def _tangent_at(parts: list, pt: tuple):
    """Unit tangent of the union outline at a boundary point (nearest boundary edge that has copper on exactly one side)."""
    cands: list = []
    for q in parts:
        if q[0] == "poly":
            n = len(q[1])
            for i in range(n):
                a, b = q[1][i], q[1][(i + 1) % n]
                d = _pt_seg(pt[0], pt[1], *a, *b)
                ln = math.hypot(b[0] - a[0], b[1] - a[1])
                if d < 0.03 and ln > _ZERO:
                    cands.append((d, ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)))
        else:
            rx, ry = pt[0] - q[1][0], pt[1] - q[1][1]
            rr = math.hypot(rx, ry)
            if abs(rr - q[2]) < 0.03 and rr > _ZERO:
                cands.append((abs(rr - q[2]), (-ry / rr, rx / rr)))
    good = []
    for d, t in cands:
        nx, ny = -t[1], t[0]
        if _in_parts((pt[0] + 0.03 * nx, pt[1] + 0.03 * ny), parts) != _in_parts((pt[0] - 0.03 * nx, pt[1] - 0.03 * ny), parts):
            good.append((d, t))
    pool = good or cands
    return min(pool, key=lambda a: a[0])[1] if pool else None


# ------------------------------------------------------------------------------------------- loader
def _chain(fp: list) -> list:
    pts = _kid(fp, "pts")
    return [(_f(c[1], "xy"), _f(c[2], "xy")) for c in (pts or [])[1:] if isinstance(c, list) and len(c) >= 3 and c[0] == "xy"]


def load_routing(text: str) -> dict:
    """Segments (arcs flattened), vias, pads, zones (+ filled polygons) of a .kicad_pcb, straight from the s-expression."""
    root = parse_sexpr(text)
    if len(root) != 1 or not root[0] or root[0][0] != "kicad_pcb":
        raise C04GateInputError("C04_GATE_BOARD_FORMAT: top-level form is not (kicad_pcb ...)")
    pcb = root[0]
    layers = [l[1] for l in (_kid(pcb, "layers") or [])[1:]
              if isinstance(l, list) and len(l) > 1 and isinstance(l[1], str) and l[1].endswith(".Cu")]
    if not layers:
        raise C04GateInputError("C04_ROUTING_BOARD_FIELD: board declares no copper layers")
    nets = {n[1]: (n[2] if len(n) > 2 else "") for n in _kids(pcb, "net")}

    def netname(node: list, what: str) -> str:
        n = _kid(node, "net")
        if n is None or len(n) < 2:
            raise C04GateInputError(f"C04_ROUTING_BOARD_FIELD: {what} has no (net ...)")
        if n[1] not in nets:
            raise C04GateInputError(f"C04_ROUTING_BOARD_FIELD: {what} references undeclared net code {n[1]!r}")
        return nets[n[1]]

    segs: list = []
    for s in _kids(pcb, "segment"):
        w = _kid(s, "width")
        ly = _kid(s, "layer")
        if w is None or ly is None:
            raise C04GateInputError("C04_ROUTING_BOARD_FIELD: segment without width/layer")
        a, b = _xy(_kid(s, "start"), "segment.start"), _xy(_kid(s, "end"), "segment.end")
        segs.append({"a": a, "b": b, "w": _f(w[1], "segment.width"), "layer": ly[1], "net": netname(s, "segment"), "arc": False})
    for s in _kids(pcb, "arc"):
        w = _kid(s, "width")
        ly = _kid(s, "layer")
        if w is None or ly is None:
            raise C04GateInputError("C04_ROUTING_BOARD_FIELD: arc without width/layer")
        pts = _arc_points(_xy(_kid(s, "start"), "arc.start"), _xy(_kid(s, "mid"), "arc.mid"), _xy(_kid(s, "end"), "arc.end"))
        nm = netname(s, "arc")
        for i in range(len(pts) - 1):
            segs.append({"a": pts[i], "b": pts[i + 1], "w": _f(w[1], "arc.width"), "layer": ly[1], "net": nm, "arc": True,
                         "arc_end": i in (0, len(pts) - 2)})
    vias: list = []
    for v in _kids(pcb, "via"):
        names = [x for x in (_kid(v, "layers") or [])[1:] if isinstance(x, str) and x in layers]
        sz = _kid(v, "size")
        if len(names) != 2 or sz is None or len(sz) < 2:
            raise C04GateInputError("C04_ROUTING_BOARD_FIELD: via without a 2-layer (layers ..) pair or (size ..)")
        i0, i1 = sorted(layers.index(n) for n in names)
        vias.append({"c": _xy(_kid(v, "at"), "via.at"), "size": _f(sz[1], "via.size"), "span": layers[i0:i1 + 1],
                     "net": netname(v, "via")})
    pads: list = []
    for fp in _kids(pcb, "footprint"):
        ref = _fp_ref(fp)
        at = _kid(fp, "at")
        x, y = _xy(at, f"{ref}.at")
        rot = _f(at[3], f"{ref}.at.angle") if len(at) > 3 else 0.0
        flipped = (_kid(fp, "layer") or [None, ""])[1] == "B.Cu"
        for p in _kids(fp, "pad"):
            num = p[1] if len(p) > 1 else ""
            pat = _kid(p, "at")
            px, py = _xy(pat, f"{ref}.pad{num}.at")
            pang = _f(pat[3], f"{ref}.pad{num}.angle") if len(pat) > 3 else 0.0
            sz = _kid(p, "size")
            sw = _f(sz[1], f"{ref}.pad{num}.size") if sz and len(sz) > 1 else 0.0
            sh = _f(sz[2], f"{ref}.pad{num}.size") if sz and len(sz) > 2 else sw
            rx, ry = _rot(px, py, rot)
            cl: list = []
            for s in (_kid(p, "layers") or [])[1:]:
                for l in (layers if s == "*.Cu" else [s] if s in layers else []):
                    if l not in cl:
                        cl.append(l)
            nn = _kid(p, "net")
            cparts, cwhy = _custom_parts(p, sw, sh) if (p[3] if len(p) > 3 else "") == "custom" else (None, None)
            pads.append({"ref": ref, "number": num, "kind": p[2] if len(p) > 2 else "", "shape": p[3] if len(p) > 3 else "",
                         "parts": cparts, "unmodelled": cwhy,
                         "c": (x + rx, y + ry), "w": sw, "h": sh, "ang": pang, "cu": cl, "flipped": flipped,
                         "net": nets.get(nn[1], "") if nn and len(nn) > 1 else ""})
    zones: list = []
    for z in _kids(pcb, "zone"):
        nm = _kid(z, "name")
        nn = _kid(z, "net")
        lyr = _kid(z, "layers") or _kid(z, "layer") or []
        fills = [{"layer": (_kid(fpoly, "layer") or [None, ""])[1], "chain": _chain(fpoly)} for fpoly in _kids(z, "filled_polygon")]
        zones.append({"name": nm[1] if nm and len(nm) > 1 else "", "net": nets.get(nn[1], "") if nn and len(nn) > 1 else "",
                      "layers": [s for s in lyr[1:] if isinstance(s, str)], "keepout": _kid(z, "keepout") is not None,
                      "teardrop": _kid(z, "teardrop") is not None, "fills": fills})
    return {"layers": layers, "nets": nets, "segs": segs, "vias": vias, "pads": pads, "zones": zones}


# ------------------------------------------------------------------------------- class resolution
def _gate(status: str, measured: dict, offenders: list) -> dict:
    return {"status": status, "measured": measured, "offenders": offenders}


def _num(v: Any, what: str, lo: float | None = None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: {what} must be a finite number, got {v!r}")
    if lo is not None and v < lo:
        raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: {what} must be >= {lo}, got {v!r}")
    return float(v)


def _classes_from_arg(classes: Any) -> dict:
    if not isinstance(classes, dict) or not classes:
        raise C04GateInputError("C04_ROUTING_INPUT_FIELD: classes must be a non-empty object {name: {nets: [...], min_track_width_mm, ...}}")
    out: dict = {}
    for name, c in classes.items():
        if not isinstance(c, dict) or not isinstance(c.get("nets"), list) or not c["nets"] \
                or any(not isinstance(n, str) or not n for n in c["nets"]):
            raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: classes[{name!r}].nets must be a non-empty list of net names / fnmatch patterns")
        out[name] = {"patterns": list(c["nets"]),
                     "min_track_width_mm": _num(c["min_track_width_mm"], f"classes[{name!r}].min_track_width_mm", 0.0)
                     if "min_track_width_mm" in c else None,
                     "min_vias_per_transition": int(_num(c["min_vias_per_transition"], f"classes[{name!r}].min_vias_per_transition", 0.0))
                     if "min_vias_per_transition" in c else None,
                     "clearance_mm": _num(c["clearance_mm"], f"classes[{name!r}].clearance_mm", 0.0) if "clearance_mm" in c else None}
    return out


def _classes_from_pro(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        raise C04GateInputError(f"C04_ROUTING_PROJECT_READ: {path!r}: {type(e).__name__}: {e}") from None
    ns = d.get("net_settings") if isinstance(d, dict) else None
    if not isinstance(ns, dict) or not isinstance(ns.get("classes"), list):
        raise C04GateInputError(f"C04_ROUTING_PROJECT_FIELD: {path!r} has no net_settings.classes")
    out: dict = {}
    for c in ns["classes"]:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str):
            raise C04GateInputError(f"C04_ROUTING_PROJECT_FIELD: {path!r} net class without a name")
        out[c["name"]] = {"patterns": [], "min_track_width_mm": _num(c["track_width"], f"{c['name']}.track_width", 0.0)
                          if "track_width" in c else None, "min_vias_per_transition": None,
                          "clearance_mm": _num(c["clearance"], f"{c['name']}.clearance", 0.0) if "clearance" in c else None,
                          "priority": c["priority"] if isinstance(c.get("priority"), int) and not isinstance(c.get("priority"), bool) else 1 << 30}
    for a in ns.get("netclass_patterns") or []:
        if not isinstance(a, dict) or a.get("netclass") not in out or not isinstance(a.get("pattern"), str):
            raise C04GateInputError(f"C04_ROUTING_PROJECT_FIELD: {path!r} netclass_patterns entry {a!r} names no known class")
        out[a["netclass"]]["patterns"].append(a["pattern"])
    for a in (ns.get("netclass_assignments") or {}).items() if isinstance(ns.get("netclass_assignments"), dict) else []:
        cl = a[1] if isinstance(a[1], str) else None
        if cl in out:
            out[cl]["patterns"].append(a[0])
    if "Default" in out and not out["Default"]["patterns"]:
        out["Default"]["patterns"] = ["*"]
    return out


def _classes_from_board(pcb: list) -> dict:
    out: dict = {}
    for nc in _kids(pcb, "net_class"):
        if len(nc) < 2 or not isinstance(nc[1], str):
            continue
        tw = _kid(nc, "trace_width")
        out[nc[1]] = {"patterns": [n[1] for n in _kids(nc, "add_net") if len(n) > 1],
                      "min_track_width_mm": _f(tw[1], f"{nc[1]}.trace_width") if tw and len(tw) > 1 else None,
                      "min_vias_per_transition": None,
                      "clearance_mm": _f(_kid(nc, "clearance")[1], f"{nc[1]}.clearance") if _kid(nc, "clearance") and len(_kid(nc, "clearance")) > 1 else None}
    return out


def resolve_classes(board_text: str, board_path: str, classes: Any, class_rules: Any, project_path: Any, nets: dict) -> tuple:
    """(class table, net->class map, source label). Raises when no source names the board's nets."""
    if classes is not None:
        table, src = _classes_from_arg(classes), "classes argument"
    else:
        pp = project_path
        if pp is None:
            cand = board_path[:-len(".kicad_pcb")] + ".kicad_pro"
            pp = cand if os.path.isfile(cand) else None
        if pp is not None:
            if not isinstance(pp, str) or not os.path.isfile(pp):
                raise C04GateInputError(f"C04_ROUTING_INPUT_NOT_FOUND: project_path={pp!r} does not exist")
            table, src = _classes_from_pro(pp), f"project file {os.path.basename(pp)} net_settings"
        else:
            table, src = _classes_from_board(parse_sexpr(board_text)[0]), "board (net_class ...) blocks"
        if not table or not any(c["patterns"] for c in table.values()):
            raise C04GateInputError("C04_ROUTING_CLASSES_MISSING: neither a project net_settings, board (net_class ...) blocks nor a "
                                    "classes argument names the nets; pass classes={name: {nets: [...], min_track_width_mm: ...}}")
    if class_rules is not None:
        if not isinstance(class_rules, dict):
            raise C04GateInputError("C04_ROUTING_INPUT_FIELD: class_rules must be an object {class: {min_track_width_mm?, min_vias_per_transition?}}")
        for name, r in class_rules.items():
            if name not in table:
                raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: class_rules names unknown class {name!r}; known: {sorted(table)}")
            if not isinstance(r, dict):
                raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: class_rules[{name!r}] must be an object")
            if "min_track_width_mm" in r:
                table[name]["min_track_width_mm"] = _num(r["min_track_width_mm"], f"class_rules[{name!r}].min_track_width_mm", 0.0)
            if "min_vias_per_transition" in r:
                table[name]["min_vias_per_transition"] = int(_num(r["min_vias_per_transition"], f"class_rules[{name!r}].min_vias_per_transition", 0.0))
            if "clearance_mm" in r:
                table[name]["clearance_mm"] = _num(r["clearance_mm"], f"class_rules[{name!r}].clearance_mm", 0.0)
    used = sorted({n for n in nets.values() if n})
    cmap: dict = {}
    # Most specific first: explicit priority (project file, lower number wins), then the catch-all Default last.
    ordered = sorted(table.items(), key=lambda kv: (kv[0] == "Default", kv[1].get("priority", 1 << 30)))
    for n in used:
        for name, c in ordered:
            if any(fnmatch.fnmatchcase(n, p) for p in c["patterns"]):
                cmap[n] = name
                break
    return table, cmap, src


# ------------------------------------------------------------------------------------------- R-01
def _on_pad(p: tuple, pad: dict, slack: float) -> bool:
    lx, ly = _rot(p[0] - pad["c"][0], p[1] - pad["c"][1], -pad["ang"])
    if pad.get("parts"):
        return _parts_dist((lx, ly), pad["parts"]) <= slack
    if pad["shape"] == "circle":
        return math.hypot(lx, ly) <= pad["w"] / 2 + slack
    return abs(lx) <= pad["w"] / 2 + slack and abs(ly) <= pad["h"] / 2 + slack


def gate_width(brd: dict, table: dict, cmap: dict, exemptions: list) -> dict:
    ex_refs = {e["ref"]: e["max_length_mm"] for e in exemptions}
    unknown_ex = sorted(r for r in ex_refs if not any(p["ref"] == r for p in brd["pads"]))
    if unknown_ex:
        raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: escape_exemptions names refs not on the board: {unknown_ex}")
    off: list = []
    necks: list = []
    unclassed: dict = {}
    examined = 0
    for s in brd["segs"]:
        net = s["net"]
        if not net:
            unclassed[""] = unclassed.get("", 0) + 1
            continue
        cl = cmap.get(net)
        if cl is None:
            unclassed[net] = unclassed.get(net, 0) + 1
            continue
        want = table[cl]["min_track_width_mm"]
        if want is None:
            unclassed[net] = unclassed.get(net, 0) + 1
            continue
        examined += 1
        if s["w"] + EPS >= want:
            continue
        length = _seg_len(s["a"], s["b"])
        rec = {"net": net, "class": cl, "layer": s["layer"], "width": round(s["w"], 4), "min_width": want,
               "at": [round(s["a"][0], 4), round(s["a"][1], 4)], "length": round(length, 4)}
        exempt_ref = None
        for pad in brd["pads"]:
            lim = ex_refs.get(pad["ref"])
            if lim is None or length > lim + EPS or s["layer"] not in pad["cu"] or pad["net"] != net:
                continue
            if _on_pad(s["a"], pad, s["w"] / 2) or _on_pad(s["b"], pad, s["w"] / 2):
                exempt_ref = pad["ref"]
                break
        if exempt_ref:
            necks.append({**rec, "ref": exempt_ref, "max_length_mm": ex_refs[exempt_ref]})
        else:
            off.append(rec)
    summary: dict = {}
    for o in off:
        k = (o["net"], o["class"], o["layer"], o["width"])
        summary[k] = summary.get(k, 0) + 1
    measured = {"segments_examined": examined, "segments_below_min": len(off),
                "by_net_layer_width": [{"net": k[0], "class": k[1], "layer": k[2], "width": k[3], "segments": v}
                                       for k, v in sorted(summary.items())],
                "exempt_necks": necks, "escape_exemptions": exemptions,
                "segments_without_class_or_min": {k: v for k, v in sorted(unclassed.items())},
                "min_width_source": "class min = the class track_width (project) / classes argument / class_rules override"}
    return _gate("fail" if off else "pass", measured, off)


# ------------------------------------------------------------------------------------------- R-02
def gate_vias(brd: dict, table: dict, cmap: dict) -> dict:
    order = {l: i for i, l in enumerate(brd["layers"])}
    off: list = []
    examined: list = []
    unmeasured: list = []
    nets_ruled = {n for n, c in cmap.items() if table[c]["min_vias_per_transition"]}
    if not nets_ruled:
        return _gate("unmeasured", {"reason": "no class declares min_vias_per_transition (pass class_rules={class: {min_vias_per_transition: N}})"}, [])
    for net in sorted(nets_ruled):
        cl = cmap[net]
        need = table[cl]["min_vias_per_transition"]
        used: set = {s["layer"] for s in brd["segs"] if s["net"] == net}
        used |= {l for p in brd["pads"] if p["net"] == net and p["kind"] == "smd" for l in p["cu"]}
        for z in brd["zones"]:
            if z["net"] == net and not z["keepout"]:
                if z["fills"]:
                    used |= {f["layer"] for f in z["fills"]}
                else:
                    unmeasured.append({"net": net, "zone": z["name"], "reason": "zone has no stored fill; its layer is not counted"})
        th = sorted({f"{p['ref']}.{p['number']}" for p in brd["pads"] if p["net"] == net and p["kind"] in ("thru_hole", "np_thru_hole")})
        layers = sorted((l for l in used if l in order), key=order.get)
        vias = [v for v in brd["vias"] if v["net"] == net]
        pairs: list = []
        for a, b in zip(layers, layers[1:]):
            n = sum(1 for v in vias if a in v["span"] and b in v["span"])
            pairs.append({"from": a, "to": b, "vias": n})
            if n < need:
                off.append({"net": net, "class": cl, "from": a, "to": b, "vias": n, "required": need,
                            "through_hole_pads_listed_not_counted": th})
        examined.append({"net": net, "class": cl, "layers_with_copper": layers, "vias_total": len(vias), "transitions": pairs})
    return _gate("fail" if off else ("unmeasured" if unmeasured else "pass"),
                 {"nets_examined": examined, "unmeasured_items": unmeasured,
                  "rule": "per net, each pair of consecutive copper layers (tracks, SMD pads, filled zones of the net) must be spanned by >= N vias of that net"}, off)


# ------------------------------------------------------------------------------------------- R-03
def _local(p: tuple, pad: dict) -> tuple:
    return _rot(p[0] - pad["c"][0], p[1] - pad["c"][1], -pad["ang"])


def _exit_edge_angle(p: tuple, q: tuple, pad: dict):
    """Angle (deg, 0..90, 90 = perpendicular) between the track leaving ``pad`` from p toward q and the pad edge it
    crosses; returns (angle, exit_point_local) or a str reason when not computable / not a pad exit."""
    x0, y0 = _local(p, pad)
    x1, y1 = _local(q, pad)
    dx, dy = x1 - x0, y1 - y0
    seg = math.hypot(dx, dy)
    if seg < EPS:
        return "zero-length segment"
    dx, dy = dx / seg, dy / seg
    shape = pad["shape"]
    if shape in ("rect", "roundrect"):
        hw, hh = pad["w"] / 2, pad["h"] / 2
        if abs(x0) > hw + 1e-6 or abs(y0) > hh + 1e-6:
            return "endpoint outside the pad rectangle (slack match)"
        ts = []
        if abs(dx) > 1e-12:
            ts.append(((hw * (1 if dx > 0 else -1) - x0) / dx, "x"))
        if abs(dy) > 1e-12:
            ts.append(((hh * (1 if dy > 0 else -1) - y0) / dy, "y"))
        t, edge = min(ts, key=lambda a: a[0])
        if t >= seg - 1e-6:
            return "segment ends inside the pad (no edge crossing)"
        return math.degrees(math.acos(min(1.0, abs(dy if edge == "x" else dx)))), (x0 + t * dx, y0 + t * dy)
    if shape in ("circle", "oval"):
        w, h = pad["w"], pad["h"]
        r = min(w, h) / 2
        half = (max(w, h) - min(w, h)) / 2
        ax, ay = (half, 0.0) if w >= h else (0.0, half)

        def core(x: float, y: float) -> tuple:
            if half <= 0:
                return 0.0, 0.0
            u = ((x * ax + y * ay) / (half * half))
            u = max(-1.0, min(1.0, u))
            return u * ax, u * ay

        def out(t: float) -> float:
            cx, cy = core(x0 + t * dx, y0 + t * dy)
            return math.hypot(x0 + t * dx - cx, y0 + t * dy - cy) - r
        if out(0.0) > 1e-6:
            # track end within slack OUTSIDE the outline, track running back toward the pad: the edge crossing is where it enters
            if out(seg) > 0:
                return "endpoint outside the pad outline (slack match)"
            lo, hi = 0.0, seg
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if out(mid) > 0 else (mid, hi)
            hi = lo
        else:
            if out(seg) <= 0:
                return "segment ends inside the pad (no edge crossing)"
            lo, hi = 0.0, seg
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if out(mid) <= 0 else (lo, mid)
        ex, ey = x0 + hi * dx, y0 + hi * dy
        cx, cy = core(ex, ey)
        nx, ny = ex - cx, ey - cy
        nn = math.hypot(nx, ny)
        if nn < EPS:
            return "degenerate exit normal"
        tx, ty = -ny / nn, nx / nn
        return math.degrees(math.acos(min(1.0, abs(dx * tx + dy * ty)))), (ex, ey)
    if shape == "custom":
        parts = pad.get("parts")
        if not parts:
            return f"custom pad not modelled: {pad.get('unmodelled')}"
        if not _in_parts((x0, y0), parts):
            return "endpoint outside the pad outline (slack match)"
        reach = 0.5
        for q in parts:
            if q[0] == "poly":
                reach = max(reach, 2.0 * max(math.hypot(*v) for v in q[1]) + 0.5)
            else:
                reach = max(reach, 2.0 * (math.hypot(*q[1]) + q[2]) + 0.5)
        lim = min(seg, reach)
        step = 0.01
        prev = 0.0
        hi = None
        for i in range(1, int(lim / step) + 1):
            t = i * step
            if not _in_parts((x0 + t * dx, y0 + t * dy), parts):
                hi = t
                break
            prev = t
        if hi is None and not _in_parts((x0 + lim * dx, y0 + lim * dy), parts):
            hi = lim
        if hi is None:
            return "segment ends inside the pad (no edge crossing)" if seg <= reach else \
                "segment does not leave the custom pad outline within modelled reach"
        lo = prev
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if _in_parts((x0 + mid * dx, y0 + mid * dy), parts) else (lo, mid)
        ex = (x0 + lo * dx, y0 + lo * dy)
        tg = _tangent_at(parts, ex)
        if tg is None:
            return "no outline tangent at the exit point"
        return math.degrees(math.acos(min(1.0, abs(dx * tg[0] + dy * tg[1])))), ex
    return f"pad shape {shape!r} not modelled"


def gate_entry_angle(brd: dict, min_deg: float) -> dict:
    td: dict = {}
    for z in brd["zones"]:
        if z["teardrop"] and z["net"]:
            for f in z["fills"]:
                td.setdefault((z["net"], f["layer"]), []).extend(_components(f["chain"]))
    off: list = []
    unmeasured: list = []
    fixed: list = []
    examined = 0
    for s in brd["segs"]:
        if not s["net"] or (s["arc"] and not s.get("arc_end")):
            continue
        for p, q in ((s["a"], s["b"]), (s["b"], s["a"])):
            for pad in brd["pads"]:
                if pad["net"] != s["net"] or s["layer"] not in pad["cu"] or not _on_pad(p, pad, 0.02):
                    continue
                key = {"ref": pad["ref"], "pad": pad["number"], "net": s["net"], "layer": s["layer"],
                       "at": [round(p[0], 4), round(p[1], 4)]}
                if pad["flipped"]:
                    unmeasured.append({**key, "reason": "back-side footprint pad frame not modelled"})
                    break
                r = _exit_edge_angle(p, q, pad)
                if isinstance(r, str):
                    if r.startswith("segment ends inside"):
                        break
                    unmeasured.append({**key, "reason": r})
                    break
                ang, ex = r
                examined += 1
                if ang + EPS >= min_deg:
                    break
                wp = (pad["c"][0] + _rot(ex[0], ex[1], pad["ang"])[0], pad["c"][1] + _rot(ex[0], ex[1], pad["ang"])[1])
                if any(_near_component(wp, c, 0.05) for c in td.get((s["net"], s["layer"]), [])):
                    fixed.append({**key, "angle": round(ang, 2), "teardrop_zone_fill_at_exit": True})
                else:
                    off.append({**key, "angle": round(ang, 2), "track_width": round(s["w"], 4), "min_angle": min_deg,
                                "arc_chord_approx": bool(s["arc"])})
                break
    measured = {"endpoints_examined": examined, "min_entry_angle_deg": min_deg, "unmeasured_endpoints": unmeasured,
                "teardrop_fixed": fixed, "teardrop_zones": sum(1 for z in brd["zones"] if z["teardrop"]),
                "convention": "angle between the track leaving the pad and the pad edge it crosses (90 = perpendicular); "
                              "flagged when < min_entry_angle_deg; fixed only when a same-net teardrop-zone fill covers the exit point"}
    if off:
        return _gate("fail", measured, off)
    return _gate("unmeasured" if unmeasured else "pass", measured, off)


# ------------------------------------------------------------------------------------------- R-04
def _touch_reach(kind: str, item: dict) -> float:
    """Distance from a same-net item's centre/endpoint to a fill component that still counts as connected.
    Pads / vias sit in a thermal-relief hole, so the reach is the item's radius plus a fixed 0.3 mm gap allowance."""
    if kind == "pad":
        return math.hypot(item["w"], item["h"]) / 2 + 0.3
    if kind == "via":
        return item["size"] / 2 + 0.3
    return item["w"] / 2 + 0.02


def gate_islands(brd: dict, max_area: float) -> dict:
    off: list = []
    unmeasured: list = []
    examined: list = []
    for z in brd["zones"]:
        if z["keepout"]:
            continue
        if not z["net"]:
            unmeasured.append({"zone": z["name"], "reason": "zone has no net; island connectivity needs a net"})
            continue
        if not z["fills"]:
            unmeasured.append({"zone": z["name"], "net": z["net"], "reason": "zone has no stored filled_polygon (not filled)"})
            continue
        for f in z["fills"]:
            comps = _components(f["chain"])
            layer = f["layer"]
            n_ok = 0
            for c in comps:
                touched = None
                for pad in brd["pads"]:
                    if pad["net"] == z["net"] and layer in pad["cu"] and _near_component(pad["c"], c, _touch_reach("pad", pad)):
                        touched = f"pad {pad['ref']}.{pad['number']}"
                        break
                if touched is None:
                    for v in brd["vias"]:
                        if v["net"] == z["net"] and layer in v["span"] and _near_component(v["c"], c, _touch_reach("via", v)):
                            touched = "via"
                            break
                if touched is None:
                    for s in brd["segs"]:
                        if s["net"] == z["net"] and s["layer"] == layer and (
                                _near_component(s["a"], c, _touch_reach("seg", s)) or _near_component(s["b"], c, _touch_reach("seg", s))
                                or _seg_hits_loop(s["a"], s["b"], c["loop"])):
                            touched = "track"
                            break
                if touched is not None:
                    n_ok += 1
                    continue
                if c["area"] > max_area + EPS:
                    off.append({"zone": z["name"], "net": z["net"], "layer": layer, "area_mm2": round(c["area"], 4),
                                "centroid": [round(c["centroid"][0], 4), round(c["centroid"][1], 4)]})
            examined.append({"zone": z["name"], "net": z["net"], "layer": layer, "components": len(comps), "connected": n_ok,
                             "islands": len(comps) - n_ok})
    measured = {"zones_examined": examined, "max_island_area_mm2": max_area, "unmeasured_items": unmeasured,
                "rule": "a fill component (outer loop minus holes) with no same-net pad / via / track within its reach is an island; "
                        "pad reach = half diagonal + 0.3 mm, via reach = radius + 0.3 mm (thermal-relief allowance)"}
    if off:
        return _gate("fail", measured, off)
    if not examined:
        measured["reason"] = "no filled non-keepout zone with a net on this board; a vacuous pass is not issued"
        return _gate("unmeasured", measured, off)
    return _gate("unmeasured" if unmeasured else "pass", measured, off)


# ------------------------------------------------------------------------------------------- R-07
def _closest_pair(a: tuple, b: tuple, c: tuple, d: tuple) -> tuple:
    """(distance, point_on_ab, point_on_cd) between two segments by endpoint projections (0 when they cross)."""
    if _seg_seg(a, b, c, d) <= 0.0:
        return 0.0, a, c

    def proj(p: tuple, s: tuple, e: tuple) -> tuple:
        dx, dy = e[0] - s[0], e[1] - s[1]
        n = dx * dx + dy * dy
        t = 0.0 if n < _ZERO else max(0.0, min(1.0, ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / n))
        return (s[0] + t * dx, s[1] + t * dy)
    best = (math.inf, a, c)
    for p in (a, b):
        q = proj(p, c, d)
        dd = math.hypot(p[0] - q[0], p[1] - q[1])
        if dd < best[0]:
            best = (dd, p, q)
    for q in (c, d):
        p = proj(q, a, b)
        dd = math.hypot(p[0] - q[0], p[1] - q[1])
        if dd < best[0]:
            best = (dd, p, q)
    return best


def _necks_of_component(comp: dict, thr: float) -> tuple:
    """Narrow copper between two boundary edges of one fill component: (offenders [(width, mid)], edges_examined)."""
    loops = [comp["loop"]] + list(comp["holes"])
    edges: list = []
    for li, lp in enumerate(loops):
        n = len(lp)
        cum = [0.0]
        for i in range(n):
            cum.append(cum[-1] + _seg_len(lp[i], lp[(i + 1) % n]))
        for i in range(n):
            edges.append((li, i, lp[i], lp[(i + 1) % n], cum, n))
    cell = max(thr, 0.25)
    grid: dict = {}
    for k, (_li, _i, a, b, _c, _n) in enumerate(edges):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for gx in range(int(math.floor((x0 - thr) / cell)), int(math.floor((x1 + thr) / cell)) + 1):
            for gy in range(int(math.floor((y0 - thr) / cell)), int(math.floor((y1 + thr) / cell)) + 1):
                grid.setdefault((gx, gy), []).append(k)
    seen: set = set()
    found: list = []
    for ks in grid.values():
        for ii in range(len(ks)):
            for jj in range(ii + 1, len(ks)):
                i, j = ks[ii], ks[jj]
                if (i, j) in seen:
                    continue
                seen.add((i, j))
                li, ei, a, b, cum, n = edges[i]
                lj, ej, c, d, _c2, _n2 = edges[j]
                dist, p, q = _closest_pair(a, b, c, d)
                if dist < 1e-6 or dist >= thr - EPS:
                    continue
                if li == lj:
                    total = cum[-1]
                    lo, hi = (ei, ej) if ei < ej else (ej, ei)
                    sep = min(cum[hi] - cum[lo + 1], total - (cum[hi + 1] - cum[lo]))
                    if sep <= NECK_MIN_BOUNDARY_FACTOR * thr:
                        continue
                mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                if _in_component(mid, comp):
                    found.append((dist, mid))
    return found, len(edges)


def gate_pour_necks(brd: dict, table: dict, cmap: dict) -> dict:
    off: list = []
    examined: list = []
    unmeasured: list = []
    for z in brd["zones"]:
        if z["keepout"] or not z["net"]:
            continue
        cl = cmap.get(z["net"])
        thr = table[cl]["min_track_width_mm"] if cl else None
        if not thr:
            unmeasured.append({"zone": z["name"], "net": z["net"],
                               "reason": "net has no class or the class has no min_track_width_mm; neck threshold undefined"})
            continue
        if not z["fills"]:
            unmeasured.append({"zone": z["name"], "net": z["net"], "reason": "zone has no stored filled_polygon (not filled)"})
            continue
        for f in z["fills"]:
            comps = _components(f["chain"])
            n_edges = 0
            raw: dict = {}
            for c in comps:
                found, ne = _necks_of_component(c, thr)
                n_edges += ne
                for dist, mid in found:
                    key = (round(mid[0]), round(mid[1]))
                    if key not in raw or dist < raw[key][0]:
                        raw[key] = (dist, mid)
            for dist, mid in sorted(raw.values(), key=lambda t: (t[0], t[1])):
                off.append({"zone": z["name"], "net": z["net"], "layer": f["layer"], "class": cl, "neck_width": round(dist, 4),
                            "min_width": thr, "location": [round(mid[0], 4), round(mid[1], 4)], "kind": "neck_or_spike"})
            examined.append({"zone": z["name"], "net": z["net"], "layer": f["layer"], "components": len(comps), "edges": n_edges,
                             "narrow_clusters": len(raw), "threshold_mm": thr})
    measured = {"zones_examined": examined, "unmeasured_items": unmeasured,
                "rule": "narrow copper = two boundary edges of one fill component closer than the net's class min track width, with the "
                        "midpoint inside copper and (same loop) boundary-path separation > 3x threshold; clustered per 1 mm cell keeping "
                        "the narrowest; geometry is polygon-edge distance of the stored fill"}
    if off:
        return _gate("fail", measured, off)
    if not examined:
        measured["reason"] = "no filled non-keepout zone with a net and a class min width; a vacuous pass is not issued"
        return _gate("unmeasured", measured, off)
    return _gate("unmeasured" if unmeasured else "pass", measured, off)


# ------------------------------------------------------------------------------------------- R-08
_DIRS = ((1.0, 0.0, "+x"), (-1.0, 0.0, "-x"), (0.0, 1.0, "+y"), (0.0, -1.0, "-y"))


def _model_parts(pad: dict) -> tuple:
    """(parts in the pad-local frame, None) or (None, reason)."""
    if pad.get("parts"):
        return pad["parts"], None
    sh, w, h = pad["shape"], pad["w"], pad["h"]
    if sh == "custom":
        return None, pad.get("unmodelled") or "custom pad not modelled"
    if w <= 0 or h <= 0:
        return None, "pad has no size"
    if sh in ("rect", "roundrect"):
        return [("poly", [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])], None
    if sh == "circle":
        return [("circ", (0.0, 0.0), w / 2)], None
    if sh == "oval":
        if w >= h:
            hf = (w - h) / 2
            return [("poly", [(-hf, -h / 2), (hf, -h / 2), (hf, h / 2), (-hf, h / 2)]), ("circ", (-hf, 0.0), h / 2), ("circ", (hf, 0.0), h / 2)], None
        hf = (h - w) / 2
        return [("poly", [(-w / 2, -hf), (w / 2, -hf), (w / 2, hf), (-w / 2, hf)]), ("circ", (0.0, -hf), w / 2), ("circ", (0.0, hf), w / 2)], None
    return None, f"pad shape {sh!r} not modelled"


def _rbound(parts: list) -> float:
    r = 0.0
    for q in parts:
        r = max(r, max(math.hypot(*v) for v in q[1]) if q[0] == "poly" else math.hypot(*q[1]) + q[2])
    return r


def _frame_parts(parts: list, src: dict, dst: dict, dx: float, dy: float) -> list:
    """Parts of ``src`` (its local frame) in ``dst``'s exit frame: forward = (dx, dy) in dst-local, lateral = (-dy, dx)."""
    def conv(pt: tuple) -> tuple:
        rx, ry = _rot(pt[0], pt[1], src["ang"])
        lx, ly = _rot(src["c"][0] + rx - dst["c"][0], src["c"][1] + ry - dst["c"][1], -dst["ang"])
        return (lx * dx + ly * dy, -lx * dy + ly * dx)
    return [("poly", [conv(v) for v in q[1]]) if q[0] == "poly" else ("circ", conv(q[1]), q[2]) for q in parts]


def _clip_f(pts: list, bound: float, keep_ge: bool) -> list:
    out: list = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        ina = a[0] >= bound if keep_ge else a[0] <= bound
        inb = b[0] >= bound if keep_ge else b[0] <= bound
        if ina:
            out.append(a)
        if ina != inb:
            t = (bound - a[0]) / (b[0] - a[0])
            out.append((bound, a[1] + t * (b[1] - a[1])))
    return out


def _lateral_interval(fparts: list, f1: float):
    """Lateral extent (ymin, ymax) of the copper inside the forward slab [0, f1]; None when it does not enter the slab."""
    lo, hi = math.inf, -math.inf
    for q in fparts:
        if q[0] == "poly":
            pts = _clip_f(_clip_f(q[1], 0.0, True), f1, False)
            for v in pts:
                lo, hi = min(lo, v[1]), max(hi, v[1])
        else:
            cf, cl = q[1]
            dz = abs(cf - min(max(cf, 0.0), f1))
            if dz <= q[2]:
                hw = math.sqrt(max(0.0, q[2] ** 2 - dz ** 2))
                lo, hi = min(lo, cl - hw), max(hi, cl + hw)
    return None if lo > hi else (lo, hi)


def _track_fits(lo: float, hi: float, obs: list, w: float, c: float) -> bool:
    """Is there a centreline offset in [lo, hi] (track end must sit on the pad) keeping w/2 + c from every obstacle interval?"""
    h = w / 2 + c
    cands = [lo, hi]
    for y0, y1 in obs:
        cands += [y0 - h, y1 + h]
    for t in cands:
        if lo - EPS <= t <= hi + EPS and all(t <= y0 - h + EPS or t >= y1 + h - EPS for y0, y1 in obs):
            return True
    return False


def _fit_width(lo: float, hi: float, obs: list, w: float, c: float) -> float:
    """w when it fits, else the largest width that does (bisection, 0 when even a hairline cannot pass)."""
    if _track_fits(lo, hi, obs, w, c):
        return w
    if not _track_fits(lo, hi, obs, 0.0, c):
        return 0.0
    a, b = 0.0, w
    for _ in range(40):
        m = (a + b) / 2
        a, b = (m, b) if _track_fits(lo, hi, obs, m, c) else (a, m)
    return a


def gate_escape(brd: dict, table: dict, cmap: dict, pre_route: bool) -> dict:
    items: list = []
    unmodelled: list = []
    flipped: dict = {}
    for pad in brd["pads"]:
        if not pad["cu"]:
            continue
        if pad["flipped"]:
            flipped.setdefault(pad["ref"], 0)
            flipped[pad["ref"]] += 1
            continue
        parts, why = _model_parts(pad)
        if parts is None:
            unmodelled.append({"ref": pad["ref"], "pad": pad["number"], "reason": why})
            continue
        items.append({"pad": pad, "parts": parts, "rb": _rbound(parts)})
    unmeasured = [{"ref": u["ref"], "pad": u["pad"], "reason": u["reason"] + " (pad is neither judged nor used as an obstacle)"} for u in unmodelled]
    unmeasured += [{"ref": r, "pads": n, "reason": "back-side footprint pad frame not modelled (pads neither judged nor used as obstacles)"}
                   for r, n in sorted(flipped.items())]
    off: list = []
    per_class: dict = {}
    skipped = {"no_net": 0, "no_connect_net": 0, "no_class": 0}
    class_gaps: set = set()
    examined = 0
    same_net_ignored = 0

    def run(it: dict, nbrs: list, w: float, c: float) -> tuple:
        pad = it["pad"]
        best = (-1.0, None, None)
        n_exit = 0
        feasible = False
        for layer in pad["cu"]:
            on = [n for n in nbrs if layer in n["pad"]["cu"]]
            for dx, dy, side in _DIRS:
                n_exit += 1
                own = _frame_parts(it["parts"], pad, pad, dx, dy)
                fl = [v[0] for q in own for v in (q[1] if q[0] == "poly" else [(q[1][0] + q[2], 0.0)])]
                ll = [v[1] for q in own for v in (q[1] if q[0] == "poly" else [(0.0, q[1][1] - q[2]), (0.0, q[1][1] + q[2])])]
                f1 = max(max(fl), 0.0) + w + 2 * c
                obs = []
                for n in on:
                    iv = _lateral_interval(_frame_parts(n["parts"], n["pad"], pad, dx, dy), f1)
                    if iv:
                        obs.append(iv)
                got = _fit_width(min(ll), max(ll), obs, w, c)
                if got >= w - EPS:
                    feasible = True
                if got > best[0]:
                    best = (got, layer, side)
            if feasible:
                break
        return feasible, best, n_exit

    for it in items:
        pad = it["pad"]
        net = pad["net"]
        if not net:
            skipped["no_net"] += 1
            continue
        if net.startswith("unconnected-"):
            skipped["no_connect_net"] += 1
            continue
        cl = cmap.get(net)
        if cl is None:
            skipped["no_class"] += 1
            continue
        w, c = table[cl]["min_track_width_mm"], table[cl].get("clearance_mm")
        if not w or c is None:
            if cl not in class_gaps:
                class_gaps.add(cl)
                unmeasured.append({"class": cl, "reason": "class has no min_track_width_mm or clearance_mm (pass class_rules={class: {clearance_mm}}); its pads are not judged"})
            continue
        reach = it["rb"] + w + 3 * c
        near_all = [n for n in items if n is not it and math.hypot(n["pad"]["c"][0] - pad["c"][0], n["pad"]["c"][1] - pad["c"][1]) <= reach + n["rb"]]
        near = [n for n in near_all if n["pad"]["net"] != net]
        same_net_ignored += len(near_all) - len(near)
        feasible, best, n_exit = run(it, near, w, c)
        st = per_class.setdefault(cl, {"min_width_mm": w, "clearance_mm": c, "pads": 0, "infeasible": 0})
        st["pads"] += 1
        examined += 1
        if feasible:
            continue
        st["infeasible"] += 1
        off.append({"ref": pad["ref"], "pad": pad["number"], "net": net, "class": cl, "layer": best[1], "best_exit_side": best[2],
                    "min_gap_mm": round(best[0] + 2 * c, 4), "max_feasible_width_mm": round(best[0], 4),
                    "class_min_width_mm": w, "clearance_mm": c, "exits_examined": n_exit})
    measured = {"mode": "pre_route" if pre_route else "routed_informational", "counts_toward_ok": pre_route, "pads_examined": examined,
                "pads_infeasible": len(off), "pads_skipped": skipped, "same_net_neighbour_pairs_ignored": same_net_ignored, "per_class": per_class, "unmeasured_items": unmeasured,
                "model": "per pad, per copper layer, per local side (+x -x +y -y): the track end must sit on the pad; the strip from the pad "
                         "centre outward to the pad edge + one run of (W + 2C) is checked against every other-NET pad (same layer) as lateral "
                         "intervals (same-net pads are not obstacles: copper of one net needs no clearance, so overlapping/adjacent same-net "
                         "pads such as Type-C A1/B12 do not block each other; a deviation from 'pads of any net', counted in "
                         "same_net_neighbour_pairs_ignored); a width W fits when a centreline exists keeping W/2 + C from every interval; infeasible when no exit "
                         "side fits; min_gap = max_feasible_width + 2C of the best exit",
                "note": "pre-route mode (board has no segments/arcs/vias): counts toward ok; on a routed board the result is informational"}
    if off:
        return _gate("fail", measured, off)
    if not examined:
        measured["reason"] = "no pad with a class min width and clearance was examined; a vacuous pass is not issued"
        return _gate("unmeasured", measured, off)
    return _gate("unmeasured" if unmeasured else "pass", measured, off)


# ------------------------------------------------------------------------------------------- R-05
def _validate_pairs(pairs: Any) -> list:
    if not isinstance(pairs, list) or not pairs:
        raise C04GateInputError("C04_ROUTING_INPUT_FIELD: pairs must be a non-empty list of {a, b, max_len_mm, max_skew_mm}")
    out = []
    for i, p in enumerate(pairs):
        if not isinstance(p, dict):
            raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: pairs[{i}] is not an object")
        miss = [k for k in ("a", "b", "max_len_mm", "max_skew_mm") if k not in p]
        if miss:
            raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: pairs[{i}] missing {miss}")
        if not isinstance(p["a"], str) or not isinstance(p["b"], str) or not p["a"] or not p["b"] or p["a"] == p["b"]:
            raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: pairs[{i}] a/b must be two distinct net names")
        out.append({"a": p["a"], "b": p["b"], "max_len_mm": _num(p["max_len_mm"], f"pairs[{i}].max_len_mm", 0.0),
                    "max_skew_mm": _num(p["max_skew_mm"], f"pairs[{i}].max_skew_mm", 0.0)})
    return out


def gate_pairs(brd: dict, pairs: list | None) -> dict:
    if pairs is None:
        return _gate("unmeasured", {"reason": "no pairs declared (pairs=[{a,b,max_len_mm,max_skew_mm}]); length/skew is not assessed"}, [])
    known = set(brd["nets"].values())
    for p in pairs:
        for n in (p["a"], p["b"]):
            if n not in known:
                raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: pair net {n!r} is not a net on the board")
    off: list = []
    rows: list = []
    for p in pairs:
        ln = {n: sum(_seg_len(s["a"], s["b"]) for s in brd["segs"] if s["net"] == n) for n in (p["a"], p["b"])}
        skew = abs(ln[p["a"]] - ln[p["b"]])
        rows.append({"a": p["a"], "b": p["b"], "len_a_mm": round(ln[p["a"]], 4), "len_b_mm": round(ln[p["b"]], 4),
                     "skew_mm": round(skew, 4), "max_len_mm": p["max_len_mm"], "max_skew_mm": p["max_skew_mm"]})
        for n in (p["a"], p["b"]):
            if ln[n] <= 0:
                off.append({"pair": [p["a"], p["b"]], "kind": "no_track_length", "net": n})
            elif ln[n] > p["max_len_mm"] + EPS:
                off.append({"pair": [p["a"], p["b"]], "kind": "over_length", "net": n, "length_mm": round(ln[n], 4),
                            "max_len_mm": p["max_len_mm"]})
        if skew > p["max_skew_mm"] + EPS:
            off.append({"pair": [p["a"], p["b"]], "kind": "skew", "skew_mm": round(skew, 4), "max_skew_mm": p["max_skew_mm"]})
    return _gate("fail" if off else "pass", {"pairs": rows, "length": "sum of every track segment of the net (copper length, not routed path)"}, off)


# ------------------------------------------------------------------------------------------- R-06
def _seg_box_edge_distance(s: dict, box: tuple) -> float:
    return max(0.0, _box_seg_distance(box, (*s["a"], *s["b"])) - s["w"] / 2)


def _point_box_distance(p: tuple, box: tuple) -> float:
    return math.hypot(max(box[0] - p[0], p[0] - box[2], 0.0), max(box[1] - p[1], p[1] - box[3], 0.0))


def gate_keepout_margin(brd: dict, kos: list, margin: float) -> dict:
    if not kos:
        return _gate("unmeasured", {"reason": "no keepouts declared; nothing to measure, a vacuous pass is not issued"}, [])
    refs = {p["ref"] for p in brd["pads"]}
    off: list = []
    rows: list = []
    exempt: list = []
    comps_by: dict = {}
    for z in brd["zones"]:
        if z["keepout"] or not z["net"]:
            continue
        for f in z["fills"]:
            comps_by.setdefault(f["layer"], []).extend((z["name"], c) for c in _components(f["chain"]))
    for ko in kos:
        if ko.get("owner_ref") and ko["owner_ref"] not in refs:
            raise C04GateInputError(f"C04_GATE_INPUT_FIELD: keepout {ko['name']!r} owner_ref {ko['owner_ref']!r} is not a footprint on the board")
        for layer in ([ko["layer"]] if ko["layer"] else brd["layers"]):
            best = {"track": (math.inf, None), "via": (math.inf, None), "fill": (math.inf, None), "pad": (math.inf, None)}

            def take(kind: str, d: float, what: Any) -> None:
                if d < best[kind][0]:
                    best[kind] = (d, what)
                if d < margin - EPS:
                    off.append({"keepout": ko["name"], "layer": layer, "kind": kind, "distance_mm": round(d, 4),
                                "margin_mm": margin, "item": what})
            for s in brd["segs"]:
                if s["layer"] == layer:
                    take("track", _seg_box_edge_distance(s, ko["box"]),
                         {"net": s["net"], "at": [round(s["a"][0], 3), round(s["a"][1], 3)]})
            for v in brd["vias"]:
                if layer in v["span"]:
                    take("via", max(0.0, _point_box_distance(v["c"], ko["box"]) - v["size"] / 2),
                         {"net": v["net"], "at": [round(v["c"][0], 3), round(v["c"][1], 3)]})
            for zn, c in comps_by.get(layer, []):
                take("fill", _box_polygon_distance(ko["box"], c), {"zone": zn, "area_mm2": round(c["area"], 3)})
            for pad in brd["pads"]:
                if layer not in pad["cu"]:
                    continue
                if ko.get("owner_ref") == pad["ref"]:
                    exempt.append({"keepout": ko["name"], "ref": pad["ref"], "pad": pad["number"], "layer": layer})
                    continue
                r = math.hypot(pad["w"], pad["h"]) / 2
                take("pad", max(0.0, _point_box_distance(pad["c"], ko["box"]) - r),
                     {"ref": pad["ref"], "pad": pad["number"], "distance_is_lower_bound": "pad radius = half diagonal"})
            rows.append({"keepout": ko["name"], "layer": layer,
                         "min_mm": {k: (None if v[0] == math.inf else round(v[0], 4)) for k, v in best.items()}})
    seen = set()
    pad_exempt = []
    for e in exempt:
        k = (e["keepout"], e["ref"], e["pad"], e["layer"])
        if k not in seen:
            seen.add(k)
            pad_exempt.append(e)
    measured = {"keepout_margin_mm": margin, "min_distance_per_layer": rows, "owner_exempt_pads": pad_exempt,
                "model": "edge-to-edge: track half-width / via radius subtracted; fills by polygon distance; pads by centre distance minus half diagonal (conservative)"}
    return _gate("fail" if off else "pass", measured, off)


# --------------------------------------------------------------------------------------- entrypoint
def c04_routing_gate(board_path: str, *, classes: Any = None, class_rules: Any = None, project_path: Any = None,
                     escape_exemptions: Any = None, min_entry_angle_deg: Any = None, max_island_area_mm2: Any = None,
                     pairs: Any = None, keepouts: Any = None, keepout_margin_mm: Any = None) -> dict:
    """Routing-class gate R-01..R-08 (see module docstring). Never mutates inputs."""
    text = _read(board_path, "board_path", ".kicad_pcb")
    brd = load_routing(text)
    table, cmap, src = resolve_classes(text, board_path, classes, class_rules, project_path, brd["nets"])
    ex: list = []
    if escape_exemptions is not None:
        if not isinstance(escape_exemptions, list):
            raise C04GateInputError("C04_ROUTING_INPUT_FIELD: escape_exemptions must be a list of {ref, max_length_mm}")
        for i, e in enumerate(escape_exemptions):
            if not isinstance(e, dict) or not isinstance(e.get("ref"), str) or not e["ref"] or "max_length_mm" not in e:
                raise C04GateInputError(f"C04_ROUTING_INPUT_FIELD: escape_exemptions[{i}] needs {{ref, max_length_mm}}")
            ex.append({"ref": e["ref"], "max_length_mm": _num(e["max_length_mm"], f"escape_exemptions[{i}].max_length_mm", 0.0)})
    ang = DEFAULT_ENTRY_ANGLE_DEG if min_entry_angle_deg is None else _num(min_entry_angle_deg, "min_entry_angle_deg", 0.0)
    isl = 0.0 if max_island_area_mm2 is None else _num(max_island_area_mm2, "max_island_area_mm2", 0.0)
    kos: list = []
    margin = None
    if keepouts is not None:
        kos = _validate_keepouts(keepouts)
        if kos:
            if keepout_margin_mm is None:
                raise C04GateInputError("C04_ROUTING_INPUT_MISSING: keepout_margin_mm is required when keepouts are given")
            margin = _num(keepout_margin_mm, "keepout_margin_mm", 0.0)
    prs = _validate_pairs(pairs) if pairs is not None else None
    gates = {"R-01": gate_width(brd, table, cmap, ex), "R-02": gate_vias(brd, table, cmap), "R-03": gate_entry_angle(brd, ang),
             "R-04": gate_islands(brd, isl), "R-05": gate_pairs(brd, prs), "R-07": gate_pour_necks(brd, table, cmap),
             "R-08": gate_escape(brd, table, cmap, not (brd["segs"] or brd["vias"])),
             "R-06": gate_keepout_margin(brd, kos, margin) if kos else _gate(
                 "unmeasured", {"reason": "keepouts not supplied or empty; nothing to measure, a vacuous pass is not issued"}, [])}
    must = ["R-01", "R-02", "R-03", "R-04", "R-06", "R-07"] + (["R-05"] if prs is not None else []) \
        + (["R-08"] if gates["R-08"]["measured"]["counts_toward_ok"] else [])
    unclassed = sorted({s["net"] for s in brd["segs"] if s["net"] and s["net"] not in cmap})
    return {"ok": all(gates[g]["status"] == "pass" for g in must), "gates": gates,
            "unmeasured_gates": [g for g in GATE_IDS if gates[g]["status"] == "unmeasured"],
            "classes": {"source": src, "table": {k: {"patterns": v["patterns"], "min_track_width_mm": v["min_track_width_mm"],
                                                   "min_vias_per_transition": v["min_vias_per_transition"], "clearance_mm": v.get("clearance_mm")} for k, v in table.items()},
                        "nets_without_class": unclassed},
            "inputs": {"board_sha256": _sha256(board_path)},
            "method": {"schema": SCHEMA, "limits": list(LIMITS)},
            "scope": "routing-class geometry read from the .kicad_pcb; says nothing about DRC clearance, impedance or electrical function"}
