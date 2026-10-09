"""S1 readability instrument (master plan DD-14, slice S1).

Measures the reviewer-cited presentation defect classes (a)-(f) on a PAIRED native
set: the ``.kicad_sch`` (object semantics + pin geometry), the ``kicad-cli`` exported
netlist (net identity) and the ``kicad-cli`` SVG (render-space geometry). All three
are hash-bound in the report. SVG alone is refused: it cannot recover net identity.

This instrument models the failure classes reviewers cited on the archived CP1-CP3
renders. It is NOT claimed to be equivalent to human judgement, and a PASS here does
not replace the fresh-eyes gate (DD-14). It never authorizes electrical correctness,
fidelity or manufacturing release.

Policy constants are frozen (``POLICY``) before any calibration run; they are not
tuned against the calibration set.

Calibration-record limit (round 4): ``_resolve_calibration`` checks a record for
STRUCTURAL consistency only (schema, policy digest, hex64 artifact hash + non-empty
decision ref per entry, >=1 rejecting and >=1 accepting entry per class, scope
cover). It does NOT authenticate evidence: it cannot verify that the hash names
the artifact the reviewer looked at, that the decision ref resolves to a real
review, or that the review adjudicates the class it is filed under. That binding
belongs to an application boundary that does not yet exist; until it does every
``calibration_ref`` carries ``evidence_authenticated=False, authenticated_by=None``
and a structurally complete record must not be read as calibrated evidence.

Sheet-layer graphic ink (round 9, spec s1-sheet-graphics-spec.md): root-level
``rectangle`` / ``polyline`` / ``circle`` / ``arc`` nodes are parsed into a SEPARATE
``Sheet.ink`` list. Parsing geometry does not imply schematic semantics are
understood: ink never enters the drawn graph, the union-find, the pin inventory or
any net/branch reasoning. Its only output is the ``observations`` population on
class f (kind="observation"): GEOMETRIC-PATH INTERSECTION OBSERVATIONS on the
centerline, not rendered ink (dash gaps, stroke envelope, fill, z-order are NOT
assessed). Observations are never findings: they cannot change a class verdict,
``scoped_verdict``, ``verdict`` or any calibration cell. Measurements are not proof
of intention or defect.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

POLICY: dict = {
    "version": "s1-readability-policy-v1",
    "frozen_on": "2026-10-06",
    # coordinate coincidence tolerance (KiCad writes 0.01 mm resolution)
    "coord_eps_mm": 0.01,
    # a foreign wire passing within this band of a pin tip reads as attached
    "pin_tip_band_mm": 1.27,
    # a foreign wire parallel to a pin-tip row within this band, alongside at
    # least `corridor_min_pins` tips, reads as a bus into those pins
    "corridor_band_mm": 2.54,
    "corridor_min_pins": 2,
    # Frozen label-outline clearance: four times the measured max 0.4 mm stroke.
    "e": {"label_flag_corridor_band_mm": 1.6},
    # class (c): local (intra-sheet) nets with <= K visible nodes must be drawn
    "local_net_max_nodes_k": 4,
    # class (f): text box vs wire / symbol body clearance
    "text_graphics_clearance_mm": 0.25,
    # class (f): text-vs-text overlap ratio (same as render_qa.THRESH)
    "text_overlap_ratio": 0.15,
    # class (f): page-use is REPORTED, never gated (DD-14: 50 % uncalibrated)
    "page_use_gate": None,
    "page_grid_cell_mm": 10.0,
    "frame_margin_mm": 12.0,
    "rotation_support": "0/90/180/270 + mirror implemented; calibrated at 0 only",
}

# Round 9 measurement scope. Kept OUT of POLICY on purpose: POLICY's digest is bound
# into every stored manifest and calibration record, and the ink observations never
# move a finding. The scope version and the chord tolerance are reported beside the
# policy digest (``ReadabilityReport.measurement_scope``) and hashed into the subject
# manifest only for subjects that carry ink or an ink-owner declaration.
MEASUREMENT_SCOPE_VERSION = "s1-measurement-scope-v2-sheet-ink-observations"
INK_CHORD_TOL_MM = 0.05

CLASS_TITLES = {
    "a": "junction ambiguity",
    "b": "cross-net contact / crossing ambiguity",
    "c": "local wired-path completeness",
    "d": "series-path legibility",
    "e": "foreign-net corridors / pin-row proximity / wire through body",
    "f": "text clearance, clipping, scale, page occupancy",
}

DOES_NOT_AUTHORIZE = ["electrical_correctness", "fidelity", "manufacturing_release",
                      "human_readability_acceptance"]


class ReadabilityInputError(ValueError):
    """Raised when an input cannot be bound; the caller must not treat it as pass."""


# --------------------------------------------------------------------------- sexpr

def parse_sexpr(text: str) -> list:
    """String-aware s-expression reader. Returns the top-level node (a list)."""
    root: list = []
    stack: list[list] = [root]
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "(":
            node: list = []
            stack[-1].append(node)
            stack.append(node)
            i += 1
        elif c == ")":
            if len(stack) == 1:
                raise ReadabilityInputError("E_SEXPR_UNBALANCED: stray ')'")
            stack.pop()
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                ch = text[j]
                if ch == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if ch == '"':
                    break
                buf.append(ch)
                j += 1
            else:
                raise ReadabilityInputError("E_SEXPR_UNTERMINATED_STRING")
            stack[-1].append("".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            stack[-1].append(text[i:j])
            i = j
    if len(stack) != 1:
        raise ReadabilityInputError("E_SEXPR_UNBALANCED: unclosed '('")
    if len(root) != 1 or not isinstance(root[0], list):
        raise ReadabilityInputError("E_SEXPR_NO_SINGLE_ROOT")
    return root[0]


def _kids(node, tag: str):
    for k in node:
        if isinstance(k, list) and k and k[0] == tag:
            yield k


def _first(node, tag: str):
    for k in _kids(node, tag):
        return k
    return None


def _f(v) -> float:
    return float(v)


def _has_hide(node) -> bool:
    for k in node:
        if k == "hide":
            return True
        if isinstance(k, list) and k and k[0] == "hide" and len(k) > 1 and k[1] == "yes":
            return True
    return False


# --------------------------------------------------------------------------- model

Point = tuple[float, float]


@dataclass
class Pin:
    ref: str
    number: str
    name: str
    tip: Point
    end: Point
    hidden: bool
    pin_type: str

    @property
    def id(self) -> str:
        return f"{self.ref}.{self.number}"


@dataclass
class Symbol:
    ref: str
    lib_id: str
    uuid: str
    at: Point
    rot: float
    mirror: str | None
    in_bom: bool
    on_board: bool
    unit: int
    pins: list[Pin] = field(default_factory=list)
    body: tuple[float, float, float, float] | None = None

    @property
    def is_power(self) -> bool:
        return self.lib_id.lower().startswith("power:")

    @property
    def is_replica(self) -> bool:
        return (not self.in_bom) and (not self.on_board)


@dataclass
class Wire:
    a: Point
    b: Point
    uuid: str


@dataclass
class Label:
    kind: str  # label | global_label | hierarchical_label
    text: str
    at: Point
    uuid: str


@dataclass
class Sheet:
    paper: str
    symbols: list[Symbol]
    wires: list[Wire]
    junctions: list[tuple[Point, str]]
    labels: list[Label]
    no_connects: list[Point]
    texts: list[tuple[str, Point]]
    # Round 9: separate graphic-ink population; never read by the drawn graph.
    ink: list = field(default_factory=list)
    ink_unparsed: dict = field(default_factory=dict)
    ink_missing_uuid: int = 0


@dataclass
class InkItem:
    """One sheet-layer graphic (root-level rectangle/polyline/circle/arc). Page
    coordinates (mm, y down); no symbol transform applies. NOT part of the drawn
    graph: it is read only by the observation pass."""
    uuid: str
    kind: str
    geometry_mm: dict
    stroke_type: str
    stroke_width: float | None
    fill_type: str
    closed: bool
    owner: str = "unknown"
    source_line: int | None = None


_INK_KINDS = ("rectangle", "polyline", "circle", "arc")
# root-level graphic-like nodes this slice does not model: counted, never dropped
_INK_UNPARSED_KINDS = ("bezier", "text_box", "rule_area", "image", "sheet")


def _root_node_lines(text: str, kind: str) -> list[int]:
    """1-based line numbers of ROOT-level `(kind` nodes (one tab or two spaces of
    indent); lib_symbols graphics sit deeper and are not matched."""
    pat = re.compile(r"^(?:\t| {2})\(" + re.escape(kind) + r"\b")
    return [i for i, ln in enumerate(text.split("\n"), 1) if pat.match(ln)]


def _parse_ink(root, text: str, eps: float = 0.01):
    items: list[InkItem] = []
    unparsed: dict[str, int] = {}
    missing_uuid = 0
    lines = {k: _root_node_lines(text, k) for k in _INK_KINDS}
    seen = {k: 0 for k in _INK_KINDS}
    for node in root:
        if not (isinstance(node, list) and node and isinstance(node[0], str)):
            continue
        tag = node[0]
        if tag in _INK_UNPARSED_KINDS:
            unparsed[tag] = unparsed.get(tag, 0) + 1
            continue
        if tag not in _INK_KINDS:
            continue
        idx = seen[tag]
        seen[tag] += 1
        sl = lines[tag][idx] if idx < len(lines[tag]) else None
        try:
            if tag == "rectangle":
                a, b = _xy(_first(node, "start")), _xy(_first(node, "end"))
                geom = {"corners": [a, (b[0], a[1]), b, (a[0], b[1])]}
                closed = True
            elif tag == "polyline":
                p = _first(node, "pts")
                pts = [_xy(k) for k in _kids(p, "xy")] if p else []
                if len(pts) < 2:
                    unparsed["polyline"] = unparsed.get("polyline", 0) + 1
                    continue
                geom = {"points": pts}
                closed = _near(pts[0], pts[-1], eps)
            elif tag == "circle":
                geom = {"center": _xy(_first(node, "center")),
                        "radius": round(_f(_first(node, "radius")[1]), 4)}
                closed = True
            else:
                geom = {"start": _xy(_first(node, "start")), "mid": _xy(_first(node, "mid")),
                        "end": _xy(_first(node, "end"))}
                closed = False
        except (TypeError, IndexError, ValueError):
            unparsed[tag] = unparsed.get(tag, 0) + 1
            continue
        st = _first(node, "stroke")
        if st is None:
            stype, sw = "unknown", None
        else:
            t = _first(st, "type")
            w = _first(st, "width")
            stype = t[1] if t and len(t) > 1 else "unknown"
            sw = _f(w[1]) if w and len(w) > 1 else None
        fl = _first(node, "fill")
        ft = _first(fl, "type") if fl else None
        u = _first(node, "uuid")
        uid = u[1] if u and len(u) > 1 else ""
        if not uid:
            missing_uuid += 1
        items.append(InkItem(uuid=uid, kind=tag, geometry_mm=geom, stroke_type=stype,
                             stroke_width=sw, fill_type=ft[1] if ft and len(ft) > 1 else "unknown",
                             closed=closed, source_line=sl))
    return items, unparsed, missing_uuid


_PAPER_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0),
             "A1": (841.0, 594.0), "A0": (1189.0, 841.0), "A": (279.4, 215.9),
             "B": (431.8, 279.4), "C": (558.8, 431.8), "D": (863.6, 558.8),
             "E": (1117.6, 863.6), "USLetter": (279.4, 215.9), "USLegal": (355.6, 215.9),
             "USLedger": (431.8, 279.4)}


def _xy(node) -> Point:
    return (round(_f(node[1]), 4), round(_f(node[2]), 4))


def _graphic_bbox(g) -> tuple[float, float, float, float] | None:
    tag = g[0]
    pts: list[Point] = []
    if tag == "rectangle":
        pts = [_xy(_first(g, "start")), _xy(_first(g, "end"))]
    elif tag == "polyline":
        p = _first(g, "pts")
        pts = [_xy(k) for k in _kids(p, "xy")] if p else []
    elif tag == "circle":
        c = _xy(_first(g, "center"))
        r = _f(_first(g, "radius")[1])
        pts = [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
    elif tag == "arc":
        pts = [_xy(_first(g, t)) for t in ("start", "mid", "end") if _first(g, t)]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _lib_units(lib_node, unit: int):
    """Sub-symbol nodes applicable to a placed unit (unit 0 = common)."""
    name = lib_node[1]
    for sub in _kids(lib_node, "symbol"):
        sub_name = sub[1]
        m = re.match(re.escape(name.split(":", 1)[-1]) + r"_(\d+)_(\d+)$", sub_name)
        if not m:
            continue
        u = int(m.group(1))
        if u == 0 or u == unit:
            yield sub
    # some writers put pins directly under the lib symbol
    yield lib_node


def _parse_lib_pins_and_graphics(lib_node, unit: int):
    pins = []
    boxes = []
    seen_pin = set()
    for sub in _lib_units(lib_node, unit):
        for p in _kids(sub, "pin"):
            at = _first(p, "at")
            if at is None:
                continue
            number = _first(p, "number")
            name = _first(p, "name")
            key = (number[1] if number else "?", round(_f(at[1]), 3), round(_f(at[2]), 3))
            if key in seen_pin:
                continue
            seen_pin.add(key)
            length = _first(p, "length")
            pins.append({
                "number": number[1] if number else "?",
                "name": name[1] if name else "~",
                "x": _f(at[1]), "y": _f(at[2]),
                "rot": _f(at[3]) if len(at) > 3 else 0.0,
                "length": _f(length[1]) if length else 0.0,
                "hidden": _has_hide(p),
                "type": p[1] if len(p) > 1 and isinstance(p[1], str) else "passive",
            })
        for g in sub:
            if isinstance(g, list) and g and g[0] in ("rectangle", "polyline", "circle", "arc"):
                bb = _graphic_bbox(g)
                if bb:
                    boxes.append(bb)
    return pins, boxes


def _transform(sym_at: Point, rot: float, mirror: str | None, px: float, py: float) -> Point:
    # Round 6: KiCad applies the mirror AFTER the rotation (in symbol-local y-up
    # axes). Mirror-then-rotate is only equivalent at rot 0/180; at 90/270 it put
    # every pin of a mirrored symbol on the wrong side (measured against kicad-cli
    # 9.0.9 ink: 0/3 pin tips on ink for 90/270 x mirror, 3/3 after this order).
    r = math.radians(rot)
    cs, sn = round(math.cos(r), 12), round(math.sin(r), 12)
    x = px * cs - py * sn
    y = px * sn + py * cs
    if mirror == "y":
        x = -x
    if mirror == "x":
        y = -y
    return (round(sym_at[0] + x, 4), round(sym_at[1] - y, 4))


def parse_sheet(text: str) -> Sheet:
    root = parse_sexpr(text)
    if root[0] != "kicad_sch":
        raise ReadabilityInputError("E_NOT_KICAD_SCH")
    paper_node = _first(root, "paper")
    paper = paper_node[1] if paper_node else "?"
    libs = {}
    lib_syms = _first(root, "lib_symbols")
    if lib_syms:
        for ls in _kids(lib_syms, "symbol"):
            libs[ls[1]] = ls
    symbols: list[Symbol] = []
    for s in _kids(root, "symbol"):
        lib_id_n = _first(s, "lib_id")
        if lib_id_n is None:
            continue
        lib_id = lib_id_n[1]
        at = _first(s, "at")
        sym_at = (round(_f(at[1]), 4), round(_f(at[2]), 4))
        rot = _f(at[3]) if len(at) > 3 else 0.0
        mirror_n = _first(s, "mirror")
        mirror = mirror_n[1] if mirror_n else None
        unit_n = _first(s, "unit")
        unit = int(unit_n[1]) if unit_n else 1
        ref = "?"
        for prop in _kids(s, "property"):
            if prop[1] == "Reference":
                ref = prop[2]
        uuid_n = _first(s, "uuid")
        in_bom = (_first(s, "in_bom") or ["", "yes"])[1] == "yes"
        on_board = (_first(s, "on_board") or ["", "yes"])[1] == "yes"
        sym = Symbol(ref=ref, lib_id=lib_id, uuid=uuid_n[1] if uuid_n else "", at=sym_at,
                     rot=rot, mirror=mirror, in_bom=in_bom, on_board=on_board, unit=unit)
        lib = libs.get(lib_id)
        if lib is None:
            raise ReadabilityInputError(
                f"E_LIB_SYMBOL_MISSING: {ref} lib_id {lib_id!r} not embedded in lib_symbols")
        pins, boxes = _parse_lib_pins_and_graphics(lib, unit)
        for p in pins:
            tip = _transform(sym_at, rot, mirror, p["x"], p["y"])
            a = math.radians(p["rot"])
            end = _transform(sym_at, rot, mirror, p["x"] + p["length"] * math.cos(a),
                             p["y"] + p["length"] * math.sin(a))
            sym.pins.append(Pin(ref=ref, number=p["number"], name=p["name"], tip=tip,
                                end=end, hidden=p["hidden"], pin_type=p["type"]))
        if boxes:
            corners = []
            for (x0, y0, x1, y1) in boxes:
                for (px, py) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                    corners.append(_transform(sym_at, rot, mirror, px, py))
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            sym.body = (min(xs), min(ys), max(xs), max(ys))
        symbols.append(sym)
    wires = []
    for w in _kids(root, "wire"):
        pts = _first(w, "pts")
        xy = [_xy(k) for k in _kids(pts, "xy")] if pts else []
        u = _first(w, "uuid")
        for i in range(len(xy) - 1):
            wires.append(Wire(a=xy[i], b=xy[i + 1], uuid=u[1] if u else ""))
    junctions = []
    for j in _kids(root, "junction"):
        u = _first(j, "uuid")
        junctions.append((_xy(_first(j, "at")), u[1] if u else ""))
    labels = []
    for kind in ("label", "global_label", "hierarchical_label"):
        for l in _kids(root, kind):
            u = _first(l, "uuid")
            labels.append(Label(kind=kind, text=l[1], at=_xy(_first(l, "at")),
                                uuid=u[1] if u else ""))
    ncs = [_xy(_first(nc, "at")) for nc in _kids(root, "no_connect")]
    texts = [(t[1], _xy(_first(t, "at"))) for t in _kids(root, "text") if _first(t, "at")]
    ink, ink_unparsed, ink_missing_uuid = _parse_ink(root, text)
    return Sheet(paper=paper, symbols=symbols, wires=wires, junctions=junctions,
                 labels=labels, no_connects=ncs, texts=texts, ink=ink,
                 ink_unparsed=ink_unparsed, ink_missing_uuid=ink_missing_uuid)


# --------------------------------------------------------------------------- netlist

def parse_netlist(text: str) -> dict[str, list[tuple[str, str]]]:
    """net name -> [(ref, pin)] from a kicad-cli ``kicadsexpr`` netlist."""
    root = parse_sexpr(text)
    if root[0] != "export":
        raise ReadabilityInputError("E_NOT_KICAD_NETLIST")
    nets_node = _first(root, "nets")
    out: dict[str, list[tuple[str, str]]] = {}
    if nets_node is None:
        return out
    for net in _kids(nets_node, "net"):
        name = _first(net, "name")[1]
        nodes = []
        for nd in _kids(net, "node"):
            nodes.append((_first(nd, "ref")[1], _first(nd, "pin")[1]))
        out[name] = nodes
    return out


def netlist_source(text: str) -> str | None:
    root = parse_sexpr(text)
    design = _first(root, "design")
    src = _first(design, "source") if design else None
    return src[1] if src else None


# --------------------------------------------------------------------------- geometry

def _near(a: Point, b: Point, eps: float) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _seg_len(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _dist_point_seg(p: Point, a: Point, b: Point) -> float:
    L = _seg_len(a, b)
    if L < 1e-9:
        return _seg_len(p, a)
    t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)
    t = max(0.0, min(1.0, t))
    q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return _seg_len(p, q)


def _on_interior(p: Point, a: Point, b: Point, eps: float) -> bool:
    if _near(p, a, eps) or _near(p, b, eps):
        return False
    return _dist_point_seg(p, a, b) <= eps


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _proper_cross(a: Point, b: Point, c: Point, d: Point, eps: float) -> Point | None:
    """Interior/interior crossing point of ab and cd, else None."""
    d1, d2 = _orient(c, d, a), _orient(c, d, b)
    d3, d4 = _orient(a, b, c), _orient(a, b, d)
    if (d1 * d2 < 0) and (d3 * d4 < 0):
        den = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
        if abs(den) < 1e-12:
            return None
        t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / den
        p = (round(a[0] + t * (b[0] - a[0]), 4), round(a[1] + t * (b[1] - a[1]), 4))
        for q in (a, b, c, d):
            if _near(p, q, eps):
                return None
        return p
    return None


def _unit(a: Point, b: Point) -> tuple[float, float] | None:
    L = _seg_len(a, b)
    if L < 1e-9:
        return None
    return (round((b[0] - a[0]) / L, 3), round((b[1] - a[1]) / L, 3))


def _parallel_overlap(a: Point, b: Point, c: Point, d: Point, band: float) -> float:
    """Length of the projected overlap of cd onto ab when the two segments are
    parallel and separated by <= band. 0.0 otherwise."""
    u = _unit(a, b)
    v = _unit(c, d)
    if u is None or v is None:
        return 0.0
    if abs(u[0] * v[1] - u[1] * v[0]) > 1e-3:  # not parallel
        return 0.0
    # perpendicular separation of line cd from line ab
    sep = abs(_orient(a, b, c)) / _seg_len(a, b)
    if sep > band:
        return 0.0
    L = _seg_len(a, b)
    def proj(p):
        return ((p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1])
    lo, hi = sorted((proj(c), proj(d)))
    ov = min(hi, L) - max(lo, 0.0)
    return max(0.0, ov)


class _UF:
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
            self.p[rb] = ra


# --------------------------------------------------------------------------- findings

@dataclass
class Finding:
    cls: str
    code: str
    kind: str  # electrical | perceptual | measurement
    message: str
    at: Point | None = None
    objects: list[str] = field(default_factory=list)
    region: tuple[float, float, float, float] | None = None
    measurements: dict = field(default_factory=dict)


@dataclass
class ClassReport:
    id: str
    title: str
    applicability: str
    measured: bool
    expected_ids: list[str] = field(default_factory=list)
    examined_ids: list[str] = field(default_factory=list)
    omitted: list[dict] = field(default_factory=list)
    measurements: dict = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    verdict: str = "indeterminate"
    not_measured_reason: str | None = None
    # Round 9: kind="observation" population. Deliberately NOT part of `findings`:
    # offenders(), offender_classes(), every verdict and every calibration cell read
    # `findings` only.
    observations: list = field(default_factory=list)
    observation_counts: dict = field(default_factory=dict)


@dataclass
class ReadabilityReport:
    subject_manifest_sha256: str
    presentation_baseline_ref: str
    render_context: dict
    policy_ref: dict
    classes: list[ClassReport]
    calibration_ref: dict
    execution: str
    verdict: str
    human_review_ref: str | None
    does_not_authorize: list[str]
    anomalies: list[str]
    # round 3: the scoped decision (a-e) is named explicitly; the six-class
    # report never claims PASS while f is partial / unmeasured.
    verdict_scope: str = "a-e"
    scoped_verdict: str = "indeterminate"
    authority_digests: dict = field(default_factory=dict)
    # Round 9: version of what this build measures, beside the policy digest, so a
    # historical calibration record cannot imply coverage of the observations.
    measurement_scope: dict = field(default_factory=dict)
    sheet_graphic_ink: list = field(default_factory=list)
    ink_report: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def offenders(self) -> dict[str, list[Finding]]:
        return {c.id: list(c.findings) for c in self.classes if c.findings}

    def offender_classes(self) -> set[str]:
        return {c.id for c in self.classes if c.findings}


# --------------------------------------------------------------------------- svg

_SVG_ROOT_RE = re.compile(
    r'<svg[^>]*?width="([0-9.]+)(mm|in|px)?"[^>]*?height="([0-9.]+)(mm|in|px)?"'
    r'[^>]*?viewBox="([-0-9. ]+)"', re.S)
_SVG_TOKEN_RE = re.compile(
    r'<g style="([^"]*)"|'
    r'<path d="\s*M\s*([-0-9.]+)\s+([-0-9.]+)\s*((?:L\s*[-0-9.]+\s+[-0-9.]+\s*)+)"|'
    r'<circle cx="([-0-9.]+)" cy="([-0-9.]+)" r="([-0-9.]+)"', re.S)
_SVG_L_RE = re.compile(r'L\s*([-0-9.]+)\s+([-0-9.]+)')
_SVG_TEXT_RE = re.compile(
    r'(?:<g transform="rotate\(([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\)">\s*)?'
    r'<text x="([-0-9.]+)" y="([-0-9.]+)"\s*'
    r'(?:textLength="([-0-9.]+)"\s*)?font-size="([-0-9.]+)"[^>]*?'
    r'text-anchor="(start|middle|end)"[^>]*>([^<]*)</text>', re.S)
_STROKE_W_RE = re.compile(r'stroke-width:\s*([0-9.]+)')
_SVG_POLY_RE = re.compile(
    r'stroke-width:\s*([0-9.]+)[^"]*"\s*d="M\s*([-0-9.]+),([-0-9.]+)\s*'
    r'((?:[-0-9.]+,[-0-9.]+\s*)+)Z"', re.S)
_SVG_XY_RE = re.compile(r'([-0-9.]+),([-0-9.]+)')


@dataclass
class SvgText:
    content: str
    anchor: Point
    bbox: tuple[float, float, float, float]
    font_size: float
    rotation: float


@dataclass
class SvgDoc:
    width_mm: float
    height_mm: float
    viewbox: tuple[float, float, float, float]
    unit_scale: float  # mm per viewBox unit
    paths: list[tuple[list[Point], float]]  # (points, stroke width)
    circles: list[tuple[Point, float, float]]  # (center, r, stroke width)
    texts: list[SvgText]
    segments: set[tuple[Point, Point]]  # canonical two-point paths (rounded)
    # closed comma-format polygons (`M x,y x,y ... Z`): label flag outlines, symbol
    # bodies. Round 5: global/hier label flag ink is modelled; bodies are not.
    polys: list[tuple[list[Point], float]] = field(default_factory=list)


def _rot_point(p: Point, deg: float, c: Point) -> Point:
    r = math.radians(deg)
    cs, sn = math.cos(r), math.sin(r)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * cs - dy * sn, c[1] + dx * sn + dy * cs)


def parse_svg(text: str) -> SvgDoc:
    m = _SVG_ROOT_RE.search(text)
    if not m:
        raise ReadabilityInputError("E_SVG_ROOT_UNPARSED: no width/height/viewBox")
    w, wu, h, hu, vb = m.groups()
    vbx, vby, vbw, vbh = (float(v) for v in vb.split())
    if (wu or "mm") != "mm" or (hu or "mm") != "mm":
        raise ReadabilityInputError(f"E_SVG_UNIT_UNSUPPORTED: {wu!r}/{hu!r}")
    width_mm, height_mm = float(w), float(h)
    if vbw <= 0:
        raise ReadabilityInputError("E_SVG_VIEWBOX_DEGENERATE")
    unit_scale = width_mm / vbw
    paths: list[tuple[list[Point], float]] = []
    circles: list[tuple[Point, float, float]] = []
    segments: set[tuple[Point, Point]] = set()
    stroke_w = 0.0
    for tok in _SVG_TOKEN_RE.finditer(text):
        if tok.group(1) is not None:
            sw = _STROKE_W_RE.search(tok.group(1))
            stroke_w = float(sw.group(1)) if sw else stroke_w
        elif tok.group(2) is not None:
            pts = [(float(tok.group(2)), float(tok.group(3)))]
            pts += [(float(a), float(b)) for a, b in _SVG_L_RE.findall(tok.group(4))]
            paths.append((pts, stroke_w))
            if len(pts) == 2:
                a = (round(pts[0][0], 2), round(pts[0][1], 2))
                b = (round(pts[1][0], 2), round(pts[1][1], 2))
                segments.add((a, b))
                segments.add((b, a))
        else:
            circles.append(((float(tok.group(5)), float(tok.group(6))),
                            float(tok.group(7)), stroke_w))
    texts: list[SvgText] = []
    seen = set()
    for tm in _SVG_TEXT_RE.finditer(text):
        rot, cx, cy, x, y, tlen, fs, anchor, content = tm.groups()
        content = content.strip()
        if not content:
            continue
        x, y, fs = float(x), float(y), float(fs)
        key = (round(x, 2), round(y, 2), content)
        if key in seen:  # KiCad emits a hidden measuring copy + stroked glyph group
            continue
        seen.add(key)
        wdt = float(tlen) if tlen else len(content) * fs * 0.6
        if anchor == "start":
            x0, x1 = x, x + wdt
        elif anchor == "end":
            x0, x1 = x - wdt, x
        else:
            x0, x1 = x - wdt / 2, x + wdt / 2
        y0, y1 = y - fs * 0.8, y + fs * 0.2
        corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
        deg = 0.0
        if rot is not None:
            deg = float(rot)
            c = (float(cx), float(cy))
            corners = [_rot_point(p, deg, c) for p in corners]
        xs = [p[0] for p in corners]
        ys = [p[1] for p in corners]
        texts.append(SvgText(content=content, anchor=(x, y), font_size=fs, rotation=deg,
                             bbox=(min(xs), min(ys), max(xs), max(ys))))
    polys: list[tuple[list[Point], float]] = []
    seen_poly = set()
    for pm in _SVG_POLY_RE.finditer(text):
        pts = [(float(pm.group(2)), float(pm.group(3)))]
        pts += [(float(a), float(b)) for a, b in _SVG_XY_RE.findall(pm.group(4))]
        key = tuple((round(x, 2), round(y, 2)) for x, y in pts)
        if key in seen_poly:  # KiCad emits flag outlines twice per duplicated label
            continue
        seen_poly.add(key)
        polys.append((pts, float(pm.group(1))))
    return SvgDoc(width_mm=width_mm, height_mm=height_mm, viewbox=(vbx, vby, vbw, vbh),
                  unit_scale=unit_scale, paths=paths, circles=circles, texts=texts,
                  segments=segments, polys=polys)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- drawn graph

@dataclass
class DrawnGraph:
    """Connectivity a reader can see: wires, junction dots and pin tips. Labels are
    NOT edges (they name, they do not draw). Every wire segment and pin gets a
    component id; `net_of` maps a component to the native net name(s) it carries."""
    uf: _UF
    wire_comp: list  # component id per wire index
    pin_comp: dict[str, object]  # pin id -> component id
    comp_nets: dict[object, set[str]]
    comp_pins: dict[object, list[str]]
    comp_labels: dict[object, set[str]]
    pin_net: dict[str, str]
    visible_pins: list[Pin]
    # pre-union structure, kept so a contested contact can be examined WITHOUT the
    # union that would erase the conflict (round-2 invariant 2)
    contacts: list[tuple[int, int, Point]] = field(default_factory=list)  # (wire i, wire j, where)
    pin_wires: dict[str, set[int]] = field(default_factory=dict)  # pin id -> wires its tip lies on


def build_drawn_graph(sheet: Sheet, nets: dict[str, list[tuple[str, str]]],
                      eps: float) -> DrawnGraph:
    uf = _UF()
    wires = sheet.wires
    wkey = [("w", i) for i in range(len(wires))]
    contacts: list[tuple[int, int, Point]] = []
    # wire-wire: shared endpoints, or an endpoint on another wire's interior (T)
    for i, w in enumerate(wires):
        for j in range(i + 1, len(wires)):
            v = wires[j]
            where = None
            for e in (w.a, w.b):
                if _near(e, v.a, eps) or _near(e, v.b, eps) or _on_interior(e, v.a, v.b, eps):
                    where = e
                    break
            if where is None:
                for e in (v.a, v.b):
                    if _on_interior(e, w.a, w.b, eps):
                        where = e
                        break
            if where is not None:
                contacts.append((i, j, where))
                uf.union(wkey[i], wkey[j])
    # junction dots join everything passing through the point
    for (jp, _u) in sheet.junctions:
        touching = [i for i, w in enumerate(wires)
                    if _near(jp, w.a, eps) or _near(jp, w.b, eps) or _on_interior(jp, w.a, w.b, eps)]
        for k in touching[1:]:
            contacts.append((touching[0], k, jp))
            uf.union(wkey[touching[0]], wkey[k])
    pin_net: dict[str, str] = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pin_net[f"{ref}.{pin}"] = name
    visible_pins: list[Pin] = []
    pin_comp: dict[str, object] = {}
    pin_wires: dict[str, set[int]] = {}
    for s in sheet.symbols:
        for p in s.pins:
            if p.hidden:
                continue
            visible_pins.append(p)
            key = ("p", p.id)
            pin_comp[p.id] = key
            for i, w in enumerate(wires):
                if _near(p.tip, w.a, eps) or _near(p.tip, w.b, eps) or _on_interior(p.tip, w.a, w.b, eps):
                    uf.union(key, wkey[i])
                    pin_wires.setdefault(p.id, set()).add(i)
    # stacked pins (same tip, e.g. USB VBUS A4/A9) are one drawn point
    for i, p in enumerate(visible_pins):
        for q in visible_pins[i + 1:]:
            if _near(p.tip, q.tip, eps):
                uf.union(("p", p.id), ("p", q.id))
    comp_nets: dict[object, set[str]] = {}
    comp_pins: dict[object, list[str]] = {}
    comp_labels: dict[object, set[str]] = {}
    for p in visible_pins:
        c = uf.find(("p", p.id))
        comp_pins.setdefault(c, []).append(p.id)
        if p.id in pin_net:
            comp_nets.setdefault(c, set()).add(pin_net[p.id])
    wire_comp = [uf.find(k) for k in wkey]
    for lab in sheet.labels:
        for i, w in enumerate(wires):
            if _near(lab.at, w.a, eps) or _near(lab.at, w.b, eps) or _on_interior(lab.at, w.a, w.b, eps):
                comp_labels.setdefault(wire_comp[i], set()).add(lab.text)
        for p in visible_pins:
            if _near(lab.at, p.tip, eps):
                comp_labels.setdefault(uf.find(("p", p.id)), set()).add(lab.text)
    return DrawnGraph(uf=uf, wire_comp=wire_comp, pin_comp=pin_comp, comp_nets=comp_nets,
                      comp_pins=comp_pins, comp_labels=comp_labels, pin_net=pin_net,
                      visible_pins=visible_pins, contacts=contacts, pin_wires=pin_wires)


def _branch_identities(sheet: Sheet, g: DrawnGraph, p: Point, pin_map: dict[str, str],
                       eps: float) -> list[tuple[str, set[str]]]:
    """Net identity of every branch incident to meet point p, computed WITHOUT
    traversing any contact located at p. This is the pre-union view: a dotted
    foreign contact keeps two identities here even though the merged component
    has one. `pin_map` is the pin->net authority (native or declared)."""
    wires = sheet.wires
    adj: dict[int, set[int]] = {i: set() for i in range(len(wires))}
    for (i, j, q) in g.contacts:
        if _near(q, p, eps):
            continue
        adj[i].add(j)
        adj[j].add(i)
    out: list[tuple[str, set[str]]] = []
    incident = [i for i, w in enumerate(wires)
                if _near(p, w.a, eps) or _near(p, w.b, eps) or _on_interior(p, w.a, w.b, eps)]
    for i in incident:
        comp = {i}
        stack = [i]
        while stack:
            k = stack.pop()
            for m in adj[k]:
                if m not in comp:
                    comp.add(m)
                    stack.append(m)
        nets: set[str] = set()
        for pin in g.visible_pins:
            if _near(pin.tip, p, eps) or pin.id not in pin_map:
                continue
            if g.pin_wires.get(pin.id, set()) & comp:
                nets.add(pin_map[pin.id])
        out.append((f"wireidx:{i}", nets))
    for pin in g.visible_pins:
        if _near(pin.tip, p, eps):
            out.append((f"pin:{pin.id}", {pin_map[pin.id]} if pin.id in pin_map else set()))
    return out


def _foreign_branches(idents: list[tuple[str, set[str]]]) -> list[tuple[str, set[str]]]:
    """Branches whose identities are mutually disjoint (>=2 distinct non-empty
    identities present). Empty when all named branches agree."""
    named = [(b, n) for b, n in idents if n]
    distinct: list[set[str]] = []
    for _b, n in named:
        if not any(n & d for d in distinct):
            distinct.append(set(n))
    return named if len(distinct) >= 2 else []


def _comp_identity(g: DrawnGraph, c) -> set[str]:
    """Identity of a drawn component: the native nets of its pins; else the label
    names on it; else a synthetic id so two unnamed drawn components still differ.
    (A pin the native export left out of every net is 'unlisted', not 'any net'.)"""
    nets = g.comp_nets.get(c)
    if nets:
        return set(nets)
    labs = g.comp_labels.get(c)
    if labs:
        return {("/" + t) if ("/" + t) in g.pin_net.values() else t for t in labs}
    return {f"unnamed:{c!r}"}


def _wire_nets(g: DrawnGraph, i: int) -> set[str]:
    return _comp_identity(g, g.wire_comp[i])


def _pin_nets(g: DrawnGraph, pin_id: str) -> set[str]:
    return _comp_identity(g, g.uf.find(("p", pin_id)))


def _foreign(nets_a: set[str], nets_b: set[str]) -> bool:
    """Two objects are foreign when both carry an identity and share none."""
    return bool(nets_a) and bool(nets_b) and not (nets_a & nets_b)


# --------------------------------------------------------------------------- meets

def _branches_at(sheet: Sheet, g: DrawnGraph, p: Point, eps: float) -> tuple[set, list[str]]:
    """Normalized incident branches at point p: the set of distinct outward unit
    directions of wires (endpoint or interior) and visible pins. A collinear split
    (two segments meeting end-to-end) yields the same two directions as one
    segment interior, so segmentation does not change the count."""
    dirs: set = set()
    objs: list[str] = []
    for i, w in enumerate(sheet.wires):
        if _near(p, w.a, eps):
            u = _unit(w.a, w.b)
            if u:
                dirs.add(u)
                objs.append(f"wireidx:{i}")
        elif _near(p, w.b, eps):
            u = _unit(w.b, w.a)
            if u:
                dirs.add(u)
                objs.append(f"wireidx:{i}")
        elif _on_interior(p, w.a, w.b, eps):
            u = _unit(w.a, w.b)
            if u:
                dirs.add(u)
                dirs.add((-u[0], -u[1]))
                objs.append(f"wireidx:{i}")
    for pin in g.visible_pins:
        if _near(p, pin.tip, eps):
            u = _unit(pin.tip, pin.end)
            if u:
                dirs.add(u)
            objs.append(f"pin:{pin.id}")
    return dirs, objs


def _nets_at(sheet: Sheet, g: DrawnGraph, p: Point, eps: float) -> list[set[str]]:
    out = []
    for i, w in enumerate(sheet.wires):
        if _near(p, w.a, eps) or _near(p, w.b, eps) or _on_interior(p, w.a, w.b, eps):
            out.append(_wire_nets(g, i))
    for pin in g.visible_pins:
        if _near(p, pin.tip, eps):
            out.append(_pin_nets(g, pin.id))
    return out


def _meet_points(sheet: Sheet, g: DrawnGraph, eps: float) -> list[Point]:
    pts: list[Point] = []
    def add(p):
        for q in pts:
            if _near(p, q, eps):
                return
        pts.append(p)
    for w in sheet.wires:
        add(w.a)
        add(w.b)
    for (jp, _u) in sheet.junctions:
        add(jp)
    for pin in g.visible_pins:
        add(pin.tip)
    return pts


# --------------------------------------------------------------------------- class a

def _class_a(sheet: Sheet, g: DrawnGraph, pol: dict) -> ClassReport:
    """Junction ambiguity. Dot present iff normalized branches >= 3 and one net;
    dot on a pin tip is flagged as misleading (reads as a bypass of that pin's
    device) even when electrically a plain T."""
    eps = pol["coord_eps_mm"]
    rep = ClassReport(id="a", title=CLASS_TITLES["a"], applicability="all wire/pin meets",
                      measured=True)
    dots = [jp for (jp, _u) in sheet.junctions]
    rep.expected_ids = [f"junction:{u}" for (_p, u) in sheet.junctions]
    pts = _meet_points(sheet, g, eps)
    rep.measurements["meet_points"] = len(pts)
    rep.measurements["dots"] = len(dots)
    for p in pts:
        dirs, objs = _branches_at(sheet, g, p, eps)
        n = len(dirs)
        has_dot = any(_near(p, d, eps) for d in dots)
        pin_here = [o for o in objs if o.startswith("pin:")]
        if n >= 3 and not has_dot:
            rep.findings.append(Finding(
                cls="a", code="A_DOT_MISSING", kind="perceptual", at=p, objects=objs,
                message=f"{n} branches meet at {p} with no junction dot"))
        elif n < 3 and has_dot:
            rep.findings.append(Finding(
                cls="a", code="A_DOT_SPURIOUS", kind="perceptual", at=p, objects=objs,
                message=f"junction dot at {p} with only {n} branches"))
        if has_dot and pin_here:
            rep.findings.append(Finding(
                cls="a", code="A_DOT_ON_PIN_TIP", kind="perceptual", at=p, objects=objs,
                message=f"junction dot sits on pin tip {','.join(pin_here)}; reads as a "
                        f"pass-through past the device"))
        rep.examined_ids.append(f"meet@{p}")
    rep.verdict = "fail" if rep.findings else "pass"
    return rep


# --------------------------------------------------------------------------- class b

def _class_b(sheet: Sheet, g: DrawnGraph, pol: dict, pin_map: dict[str, str],
             identity_source: str) -> ClassReport:
    """b1 (electrical): a contact (shared endpoint / T / dotted meet) whose
    PRE-UNION branches carry distinct identities; same-net T WITHOUT a dot.
    b2 (perceptual): distinct-net wires crossing WITHOUT a dot.

    Branch identity is computed by `_branch_identities`, which never traverses
    the contact under test -- so unioning at a dot cannot erase the conflict.
    `pin_map` is the authority for pin->net (declared when supplied, else native).
    With no pin authority at all the class is unmeasured, not clean."""
    eps = pol["coord_eps_mm"]
    rep = ClassReport(id="b", title=CLASS_TITLES["b"],
                      applicability=f"all wire contacts and crossings; identity from {identity_source}",
                      measured=bool(pin_map))
    if not pin_map:
        rep.not_measured_reason = "no pin->net authority (native netlist empty and no declared circuit)"
        rep.verdict = "indeterminate"
        return rep
    wires = sheet.wires
    dots = [jp for (jp, _u) in sheet.junctions]
    b1 = b2 = 0
    # contacts: pre-union identities at every contact point
    seen_pts: list[Point] = []
    for (i, j, q) in g.contacts:
        if any(_near(q, s, eps) for s in seen_pts):
            continue
        seen_pts.append(q)
        idents = _branch_identities(sheet, g, q, pin_map, eps)
        foreign = _foreign_branches(idents)
        has_dot = any(_near(q, d, eps) for d in dots)
        if foreign:
            nets = sorted(set().union(*(n for _b, n in foreign)))
            rep.findings.append(Finding(
                cls="b", code="B1_FOREIGN_CONTACT_WITH_DOT" if has_dot else "B1_FOREIGN_CONTACT",
                kind="electrical", at=q,
                objects=[b for b, _n in foreign] + [f"net:{n}" for n in nets],
                message=f"branches of nets {nets} meet at {q}"
                        + (" under a junction dot" if has_dot else " (T / shared endpoint)")))
            b1 += 1
            continue
        dirs, objs = _branches_at(sheet, g, q, eps)
        if len(dirs) >= 3 and not has_dot:
            rep.findings.append(Finding(
                cls="b", code="B1_SAME_NET_T_NO_DOT", kind="electrical", at=q,
                objects=objs, message=f"same-net T at {q} has no junction dot"))
            b1 += 1
    # proper crossings (interior/interior): pre-union identities of the two wires
    for i in range(len(wires)):
        for j in range(i + 1, len(wires)):
            w, v = wires[i], wires[j]
            x = _proper_cross(w.a, w.b, v.a, v.b, eps)
            if x is None:
                continue
            ni, nj = _wire_nets(g, i), _wire_nets(g, j)
            has_dot = any(_near(x, d, eps) for d in dots)
            if has_dot:
                # a dot on a crossing is a contact KiCad did not record as one;
                # identities come from the two sides, computed without that point
                idents = _branch_identities(sheet, g, x, pin_map, eps)
                foreign = _foreign_branches(idents)
                if foreign:
                    nets = sorted(set().union(*(n for _b, n in foreign)))
                    rep.findings.append(Finding(
                        cls="b", code="B1_FOREIGN_CROSS_WITH_DOT", kind="electrical", at=x,
                        objects=[f"wire:{w.uuid}", f"wire:{v.uuid}"] + [f"net:{n}" for n in nets],
                        message=f"nets {nets} cross at {x} with a junction dot"))
                    b1 += 1
                continue
            if _foreign(ni, nj):
                rep.findings.append(Finding(
                    cls="b", code="B2_FOREIGN_CROSS_NO_DOT", kind="perceptual", at=x,
                    objects=[f"wire:{w.uuid}", f"wire:{v.uuid}"] + [f"net:{n}" for n in sorted(ni | nj)],
                    message=f"nets {sorted(ni)} x {sorted(nj)} cross at {x} without a dot"))
                b2 += 1
    rep.measurements["b1_electrical"] = b1
    rep.measurements["b2_perceptual"] = b2
    rep.measurements["contacts_examined"] = len(seen_pts)
    rep.expected_ids = [f"contact@{q}" for q in seen_pts]
    rep.examined_ids = list(rep.expected_ids) + [f"wire:{w.uuid}" for w in wires]
    rep.verdict = "fail" if rep.findings else "pass"
    return rep


# --------------------------------------------------------------------------- class c

def _derive_local_pairs(sheet: Sheet, g: DrawnGraph, nets: dict, pol: dict
                        ) -> tuple[list[tuple[str, str]], dict[str, str], list[dict]]:
    """Policy-K population when no explicit pair list is supplied. Returns
    (required pin pairs, per-pin exception map, omitted records). Exceptions are
    per PIN with a named reason; a global label on a net exempts only the pins
    that sit on that label (continuation), never the whole net."""
    eps = pol["coord_eps_mm"]
    K = pol["local_net_max_nodes_k"]
    power_refs = {s.ref for s in sheet.symbols if s.is_power}
    replica_refs = {s.ref for s in sheet.symbols if s.is_replica}
    nc_pins = {p.id for p in g.visible_pins if any(_near(p.tip, n, eps) for n in sheet.no_connects)}
    cont_pins = {p.id for p in g.visible_pins
                 if any(l.kind != "label" and _near(l.at, p.tip, eps) for l in sheet.labels)}
    visible_ids = {p.id for p in g.visible_pins}
    pairs: list[tuple[str, str]] = []
    exceptions: dict[str, str] = {}
    omitted: list[dict] = []
    for name, nodes in nets.items():
        node_ids = [f"{r}.{p}" for r, p in nodes if f"{r}.{p}" in visible_ids]
        if len(node_ids) < 2:
            omitted.append({"net": name, "reason": f"{len(node_ids)} visible node(s) on sheet"})
            continue
        if len(node_ids) > K:
            omitted.append({"net": name, "reason": f"{len(node_ids)} nodes > K={K}"})
            continue
        eligible = []
        for n in node_ids:
            ref = n.split(".")[0]
            if ref in power_refs:
                exceptions[n] = "power"
            elif ref in replica_refs:
                exceptions[n] = "replica"
            elif n in nc_pins:
                exceptions[n] = "NC"
            elif n in cont_pins:
                exceptions[n] = "continuation (global/hierarchical label on pin)"
            else:
                eligible.append(n)
        if len(eligible) < 2:
            omitted.append({"net": name, "reason": "fewer than 2 eligible pins after exceptions"})
            continue
        for i in range(len(eligible)):
            for j in range(i + 1, len(eligible)):
                pairs.append((eligible[i], eligible[j]))
    return pairs, exceptions, omitted


def _class_c(sheet: Sheet, g: DrawnGraph, nets: dict, pol: dict,
             required_pairs: list[tuple[str, str]] | None = None,
             exceptions: dict[str, str] | None = None) -> ClassReport:
    """Local wired-path completeness over an EXPLICIT pin-pair population.
    `required_pairs` + `exceptions` come from the caller (DD-14 declared policy)
    or, when absent, from `_derive_local_pairs` under policy K. A pair passes
    when both pins are in one drawn component (wires + dots + tips, no labels).
    The population is declared in expected_ids BEFORE any pair is examined."""
    if required_pairs is None:
        required_pairs, derived_exc, omitted = _derive_local_pairs(sheet, g, nets, pol)
        exceptions = {**derived_exc, **(exceptions or {})}
        source = f"derived under policy K={pol['local_net_max_nodes_k']}"
    else:
        exceptions = dict(exceptions or {})
        omitted = []
        source = "caller-declared required pin pairs"
    rep = ClassReport(id="c", title=CLASS_TITLES["c"], applicability=source, measured=True)
    rep.omitted = omitted + [{"pin": p, "reason": r} for p, r in sorted(exceptions.items())]
    visible = {p.id: p for p in g.visible_pins}
    rep.expected_ids = [f"{a}~{b}" for a, b in required_pairs]
    for a, b in required_pairs:
        if a in exceptions or b in exceptions:
            rep.omitted.append({"pair": f"{a}~{b}", "reason": "a pin is under a named exception"})
            continue
        if a not in visible or b not in visible:
            rep.omitted.append({"pair": f"{a}~{b}", "reason": "pin not visible on this sheet"})
            continue
        rep.examined_ids.append(f"{a}~{b}")
        if g.uf.find(("p", a)) != g.uf.find(("p", b)):
            for n in (a, b):
                rep.findings.append(Finding(
                    cls="c", code="C_PIN_LABEL_ONLY", kind="perceptual", at=visible[n].tip,
                    objects=[f"pin:{n}", f"pair:{a}~{b}"] + [f"net:{g.pin_net[n]}"] * (n in g.pin_net),
                    message=f"required local pair {a}~{b}: no drawn wire path (pin {n})"))
    # one finding per pin, not per pair it participates in
    seen = set()
    rep.findings = [f for f in rep.findings if not (f.objects[0] in seen or seen.add(f.objects[0]))]
    rep.measurements["required_pairs"] = len(rep.expected_ids)
    rep.measurements["examined_pairs"] = len(rep.examined_ids)
    rep.measurements["label_only_pins"] = len(rep.findings)
    if not rep.examined_ids:
        rep.verdict = "not-applicable"
        rep.not_measured_reason = "no eligible local pair on this sheet"
    else:
        rep.verdict = "fail" if rep.findings else "pass"
    return rep


# --------------------------------------------------------------------------- class d

def _series_elements(sheet: Sheet) -> list[Symbol]:
    return [s for s in sheet.symbols if not s.is_power and not s.is_replica
            and len([p for p in s.pins if not p.hidden]) == 2]


def _class_d(sheet: Sheet, g: DrawnGraph, pol: dict,
             declared_pin_nets: dict[str, str] | None = None) -> ClassReport:
    """Series-path legibility. Population = every two-terminal non-power,
    non-replica element (expected). Examined = those whose pins resolve to two
    distinct nets under the pin authority. Omitted (with reason) = pins missing
    from the authority, or n1 == n2 -- which native nets alone cannot decide
    (legitimate shunt vs. fused series): assessed against the declared circuit
    when supplied, else `not_assessed`. Findings: D_DRAWN_BYPASS (both pins in one
    drawn component), D_FOREIGN_WIRE_IN_PIN_BAND and D_DOT_ON_PIN_CONTINUES
    (illusions, perceptual)."""
    eps = pol["coord_eps_mm"]
    band = pol["pin_tip_band_mm"]
    authority = declared_pin_nets if declared_pin_nets else g.pin_net
    src = "declared circuit" if declared_pin_nets else "native netlist"
    rep = ClassReport(id="d", title=CLASS_TITLES["d"],
                      applicability=f"two-terminal non-power elements; pin identity from {src}",
                      measured=True)
    dots = [jp for (jp, _u) in sheet.junctions]
    not_assessed = 0
    for s in _series_elements(sheet):
        p1, p2 = [p for p in s.pins if not p.hidden]
        rep.expected_ids.append(s.ref)
        n1, n2 = authority.get(p1.id), authority.get(p2.id)
        if n1 is None or n2 is None:
            rep.omitted.append({"ref": s.ref, "reason": f"a pin is absent from the {src}"})
            continue
        if n1 == n2:
            if declared_pin_nets:
                dn1, dn2 = declared_pin_nets.get(p1.id), declared_pin_nets.get(p2.id)
                if dn1 is not None and dn2 is not None and dn1 != dn2:
                    rep.findings.append(Finding(
                        cls="d", code="D_FUSED_SERIES", kind="electrical", at=s.at,
                        objects=[f"pin:{p1.id}", f"pin:{p2.id}"],
                        message=f"{s.ref}: declared series ({dn1} / {dn2}) but drawn on one net {n1}"))
                    rep.examined_ids.append(s.ref)
                    continue
                rep.omitted.append({"ref": s.ref, "reason": "declared shunt on one net (not series)"})
            else:
                not_assessed += 1
                rep.omitted.append({"ref": s.ref, "reason": "not_assessed: both pins on one net; "
                                    "shunt vs fused series undecidable without declared circuit"})
            continue
        rep.examined_ids.append(s.ref)
        c1, c2 = g.uf.find(("p", p1.id)), g.uf.find(("p", p2.id))
        if c1 == c2:
            rep.findings.append(Finding(
                cls="d", code="D_DRAWN_BYPASS", kind="electrical", at=s.at,
                objects=[f"pin:{p1.id}", f"pin:{p2.id}"],
                message=f"{s.ref}: both pins land in one drawn component ({n1} vs {n2})"))
            continue
        for near, far_net, far in ((p1, n2, p2), (p2, n1, p1)):
            for i, w in enumerate(sheet.wires):
                wn = _wire_nets(g, i)
                if far_net not in wn:
                    continue
                d = _dist_point_seg(near.tip, w.a, w.b)
                if d <= band and not _near(near.tip, w.a, eps) and not _near(near.tip, w.b, eps):
                    rep.findings.append(Finding(
                        cls="d", code="D_FOREIGN_WIRE_IN_PIN_BAND", kind="perceptual",
                        at=near.tip, objects=[f"pin:{near.id}", f"wire:{w.uuid}"],
                        message=f"{s.ref}: wire of {far_net} passes {d:.2f} mm from pin "
                                f"{near.id} ({authority[near.id]}); reads as attached"))
            if any(_near(near.tip, dj, eps) for dj in dots):
                # the dot sits on the pin tip; the rail "continues past" the element
                # when a >=3-branch meet of the same drawn component lies within the
                # pin-tip band of that dot (the T may be a stub-length away).
                comp = g.uf.find(("p", near.id))
                for mp in _meet_points(sheet, g, eps):
                    if _seg_len(mp, near.tip) > band:
                        continue
                    dirs, objs = _branches_at(sheet, g, mp, eps)
                    touching_comp = any(
                        g.wire_comp[int(o.split(":", 1)[1])] == comp
                        for o in objs if o.startswith("wireidx:"))
                    if len(dirs) >= 3 and (touching_comp or _near(mp, near.tip, eps)):
                        rep.findings.append(Finding(
                            cls="d", code="D_DOT_ON_PIN_CONTINUES", kind="perceptual",
                            at=near.tip, objects=[f"pin:{near.id}"] + objs,
                            message=f"{s.ref}: junction dot on pin {near.id} and a {len(dirs)}-"
                                    f"branch meet at {mp} within {band} mm; the rail reads as "
                                    f"continuing past {s.ref}"))
                        break
    rep.measurements["series_elements"] = len(rep.examined_ids)
    rep.measurements["expected"] = len(rep.expected_ids)
    rep.measurements["not_assessed"] = not_assessed
    if rep.findings:
        rep.verdict = "fail"
    elif not rep.expected_ids:
        rep.verdict = "not-applicable"
    elif not_assessed:
        rep.verdict = "indeterminate"
        rep.not_measured_reason = f"{not_assessed} element(s) not_assessed (no declared circuit)"
    else:
        rep.verdict = "pass"
    return rep


# --------------------------------------------------------------------------- class e

def _class_e(sheet: Sheet, g: DrawnGraph, svg: SvgDoc, pol: dict) -> ClassReport:
    """Foreign-net corridors, pin-row proximity and wire-through-body.
    E_PIN_ROW_CORRIDOR: a wire runs parallel within corridor_band of >= N pin tips
    of another net (reads as a bus into those pins). E_COLLINEAR_FOREIGN: two
    wires of different nets are collinear/parallel within the rendered stroke
    width over a positive length. E_WIRE_THROUGH_BODY: a wire segment crosses a
    symbol body box of a symbol whose pins are not on that wire's net."""
    eps = pol["coord_eps_mm"]
    band = pol["corridor_band_mm"]
    min_pins = pol["corridor_min_pins"]
    rep = ClassReport(id="e", title=CLASS_TITLES["e"], applicability="all wires vs foreign pins/wires/bodies",
                      measured=True)
    stroke = max((sw for (_pts, sw) in svg.paths), default=0.0)
    rep.measurements["render_stroke_width_mm"] = round(stroke * svg.unit_scale, 4)
    wires = sheet.wires
    rep.examined_ids = [f"wire:{w.uuid}" for w in wires]
    # pin-row corridor
    for i, w in enumerate(wires):
        wn = _wire_nets(g, i)
        u = _unit(w.a, w.b)
        if u is None:
            continue
        L = _seg_len(w.a, w.b)
        near_pins = []
        for p in g.visible_pins:
            if not _foreign(wn, _pin_nets(g, p.id)):
                continue
            pu = _unit(p.tip, p.end)
            if pu is None or abs(pu[0] * u[0] + pu[1] * u[1]) > 1e-3:
                continue  # the pin must point ACROSS the wire (row alongside it)
            d = _dist_point_seg(p.tip, w.a, w.b)
            t = ((p.tip[0] - w.a[0]) * u[0] + (p.tip[1] - w.a[1]) * u[1])
            if 0 < d <= band and 0 <= t <= L:
                near_pins.append(p.id)
        if len(near_pins) >= min_pins:
            rep.findings.append(Finding(
                cls="e", code="E_PIN_ROW_CORRIDOR", kind="perceptual", at=w.a,
                objects=[f"wire:{w.uuid}"] + [f"pin:{p}" for p in near_pins],
                message=f"wire of {sorted(wn)} runs along {len(near_pins)} foreign pin tips "
                        f"({', '.join(near_pins)}) within {band} mm"))
    # collinear foreign runs (within rendered stroke width, non-zero overlap)
    for i in range(len(wires)):
        for j in range(i + 1, len(wires)):
            ni, nj = _wire_nets(g, i), _wire_nets(g, j)
            if not _foreign(ni, nj):
                continue
            w, v = wires[i], wires[j]
            ov = _parallel_overlap(w.a, w.b, v.a, v.b, max(stroke, eps))
            if ov > eps:
                rep.findings.append(Finding(
                    cls="e", code="E_COLLINEAR_FOREIGN", kind="perceptual", at=w.a,
                    objects=[f"wire:{w.uuid}", f"wire:{v.uuid}"],
                    message=f"wires of {sorted(ni)} and {sorted(nj)} are collinear over {ov:.2f} mm"))
    # wire through a foreign symbol body
    for i, w in enumerate(wires):
        wn = _wire_nets(g, i)
        for s in sheet.symbols:
            if s.body is None or s.is_power:
                continue
            x0, y0, x1, y1 = s.body
            sym_nets = {g.pin_net[p.id] for p in s.pins if p.id in g.pin_net}
            # a wire owned by one of the symbol's own nets may legitimately touch the
            # body edge at its pin; require the segment to pass strictly inside
            # A wire inside ANY body box is a reader-visible defect regardless of net
            # (battery CP3: the BAT_EXT wire runs through J2's own body). Net identity
            # is recorded in the message, not used as an exemption.
            inside = _seg_strictly_inside_box(w.a, w.b, (x0, y0, x1, y1), eps)
            along = _seg_along_box_edge(w.a, w.b, (x0, y0, x1, y1), max(stroke, eps))
            if inside or along > eps:
                how = "through the body" if inside else f"along the body edge for {along:.2f} mm"
                rep.findings.append(Finding(
                    cls="e", code="E_WIRE_THROUGH_BODY", kind="perceptual", at=w.a,
                    objects=[f"wire:{w.uuid}", f"symbol:{s.ref}"],
                    message=f"wire of {sorted(wn)} runs {how} of {s.ref}"))
    # a foreign wire passing within the pin-tip band of a single pin (not ending on it)
    for i, w in enumerate(wires):
        wn = _wire_nets(g, i)
        for p in g.visible_pins:
            if not _foreign(wn, _pin_nets(g, p.id)):
                continue
            d = _dist_point_seg(p.tip, w.a, w.b)
            if 0 < d <= pol["pin_tip_band_mm"]:
                rep.findings.append(Finding(
                    cls="e", code="E_FOREIGN_WIRE_NEAR_PIN_TIP", kind="perceptual", at=p.tip,
                    objects=[f"wire:{w.uuid}", f"pin:{p.id}"],
                    message=f"wire of {sorted(wn)} passes {d:.2f} mm from pin tip {p.id} "
                            f"({sorted(_pin_nets(g, p.id))}); reads as attached"))
    _label_flag_corridors(sheet, g, svg, pol, rep)
    rep.measurements["label_flag_corridors"] = sum(1 for f in rep.findings if f.code == "E_LABEL_FLAG_CORRIDOR")
    rep.measurements["pin_row_corridors"] = sum(1 for f in rep.findings if f.code == "E_PIN_ROW_CORRIDOR")
    rep.measurements["collinear_foreign"] = sum(1 for f in rep.findings if f.code == "E_COLLINEAR_FOREIGN")
    rep.measurements["wire_through_body"] = sum(1 for f in rep.findings if f.code == "E_WIRE_THROUGH_BODY")
    rep.measurements["foreign_wire_near_pin_tip"] = sum(1 for f in rep.findings if f.code == "E_FOREIGN_WIRE_NEAR_PIN_TIP")
    rep.verdict = "fail" if rep.findings else "pass"
    return rep


def _edge_band_interval(a: Point, b: Point, c: Point, d: Point,
                        band: float) -> list[tuple[float, float]]:
    """Parameter intervals of ab inside the closed capsule around edge cd."""
    u = _unit(c, d)
    length = _seg_len(a, b)
    if u is None or length == 0:
        return []
    v = (-u[1], u[0])
    local = lambda p: ((p[0]-c[0])*u[0]+(p[1]-c[1])*u[1],
                       (p[0]-c[0])*v[0]+(p[1]-c[1])*v[1])
    aa, bb = local(a), local(b)
    lo, hi = 0.0, 1.0
    for start, delta, lower, upper in zip(aa, (bb[0]-aa[0], bb[1]-aa[1]),
                                         (0.0, -band), (_seg_len(c, d), band)):
        if abs(delta) < 1e-12:
            if not lower <= start <= upper:
                hi = -1.0
                break
        else:
            t0, t1 = sorted(((lower-start)/delta, (upper-start)/delta))
            lo, hi = max(lo, t0), min(hi, t1)
    intervals = [(lo, hi)] if hi > lo else []
    dx, dy = b[0]-a[0], b[1]-a[1]
    for p in (c, d):
        ax, ay = a[0]-p[0], a[1]-p[1]
        qb = 2*(ax*dx+ay*dy)
        discriminant = qb*qb-4*length*length*(ax*ax+ay*ay-band*band)
        if discriminant > 0:
            root = math.sqrt(discriminant)
            lo, hi = max(0.0, (-qb-root)/(2*length*length)), min(1.0, (-qb+root)/(2*length*length))
            if hi > lo:
                intervals.append((lo, hi))
    return intervals


def _label_flag_corridors(sheet: Sheet, g: DrawnGraph, svg: SvgDoc,
                          pol: dict, rep: ClassReport) -> None:
    """Any-net wire proximity to drawable global/hierarchical label outlines."""
    eps = pol["coord_eps_mm"]
    band = pol["e"]["label_flag_corridor_band_mm"]
    sc = svg.unit_scale
    for lab in sheet.labels:
        if lab.kind not in ("global_label", "hierarchical_label"):
            continue
        polygons = [[(x*sc, y*sc) for x, y in pts] for pts, _sw in svg.polys
                    if pts and math.dist((pts[0][0]*sc, pts[0][1]*sc), lab.at) <= 0.02]
        attached = [(i, w) for i, w in enumerate(sheet.wires)
                    if _near(w.a, lab.at, eps) or _near(w.b, lab.at, eps)]
        label_nets = set().union(*(_wire_nets(g, i) for i, _w in attached))
        for poly in polygons:
            edges = list(zip(poly, poly[1:]+poly[:1]))
            for i, w in enumerate(sheet.wires):
                if any(i == j or (abs((w.b[0]-w.a[0])*(v.b[1]-v.a[1])-
                                     (w.b[1]-w.a[1])*(v.b[0]-v.a[0])) <= eps and
                                  _dist_point_seg(lab.at, w.a, w.b) <= eps)
                       for j, v in attached):
                    continue
                intervals = sorted(t for c, d in edges
                                   for t in _edge_band_interval(w.a, w.b, c, d, band))
                merged = []
                for lo, hi in intervals:
                    if merged and lo <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
                    else:
                        merged.append((lo, hi))
                length = sum(hi-lo for lo, hi in merged)*_seg_len(w.a, w.b)
                if length <= eps:
                    continue
                # Localize on the wire at its closest outline vertex/endpoint pair.
                candidates = []
                for p in poly:
                    dx, dy = w.b[0]-w.a[0], w.b[1]-w.a[1]
                    denom = dx*dx+dy*dy
                    t = max(0.0, min(1.0, ((p[0]-w.a[0])*dx+(p[1]-w.a[1])*dy)/denom))
                    q = (w.a[0]+t*dx, w.a[1]+t*dy)
                    candidates.append((math.dist(p, q), q))
                for p in (w.a, w.b):
                    candidates.append((min(_dist_point_seg(p, c, d) for c, d in edges), p))
                for c, d in edges:
                    hit = _seg_hit(w.a, w.b, c, d, 1e-9)
                    if hit is not None:
                        candidates.append((0.0, hit[1]))
                distance, at = min(candidates)
                wn = _wire_nets(g, i)
                relation = ("unbound" if not label_nets else
                            "foreign" if _foreign(wn, label_nets) else "same")
                xs = [p[0] for p in poly]+[w.a[0], w.b[0]]
                ys = [p[1] for p in poly]+[w.a[1], w.b[1]]
                rep.findings.append(Finding(
                    cls="e", code="E_LABEL_FLAG_CORRIDOR", kind="perceptual", at=at,
                    objects=[f"wire:{w.uuid}", f"label:{lab.uuid}"],
                    region=(min(xs), min(ys), max(xs), max(ys)),
                    measurements={"net_relation": relation, "distance_mm": distance,
                                  "label_net_authority": "attached_wire" if label_nets else "none",
                                  "contact": "through" if distance == 0 else "corridor",
                                  "corridor_length_mm": length, "band_mm": band},
                    message=f"wire of {sorted(wn)} passes {lab.kind} {lab.text!r} outline "
                            f"within {band} mm over {length:.2f} mm; electrical equality "
                            "does not establish perceptual clarity"))


def _seg_along_box_edge(a: Point, b: Point, box, band: float) -> float:
    """Overlap length of segment ab lying on one of the box's four edges (within
    band), excluding the pin-stub case where the segment only touches the edge
    at a point."""
    x0, y0, x1, y1 = box
    edges = (((x0, y0), (x1, y0)), ((x0, y1), (x1, y1)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)))
    best = 0.0
    for e0, e1 in edges:
        best = max(best, _parallel_overlap(e0, e1, a, b, band))
    return best


def _seg_strictly_inside_box(a: Point, b: Point, box, eps: float) -> bool:
    """True when some interior part of segment ab lies strictly inside box
    (shrunk by eps so edge-touching pins do not count)."""
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 + eps, y0 + eps, x1 - eps, y1 - eps
    if x1 <= x0 or y1 <= y0:
        return False
    # sample the segment midpoint and quarter points (axis-aligned wires)
    for t in (0.25, 0.5, 0.75):
        px, py = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        if x0 < px < x1 and y0 < py < y1:
            return True
    return False


# --------------------------------------------------------------------------- class f

def _seg_box_clip(a: Point, b: Point, box) -> tuple[float, Point | None]:
    """(length, midpoint) of segment ab inside the closed box (Liang-Barsky).
    Exact: no sampling, so a wire that crosses the box between sample points is
    still seen (round 5: the old 3-sample test missed all four reviewer strikes
    on the S3 usbc leaf -- each fell between t=0.25/0.5/0.75 of a long wire)."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return 0.0, None
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return 0.0, None
                t0 = max(t0, r)
            else:
                if r < t0:
                    return 0.0, None
                t1 = min(t1, r)
    if t1 <= t0:
        return 0.0, None
    tm = (t0 + t1) / 2
    return (t1 - t0) * math.hypot(dx, dy), (a[0] + tm * dx, a[1] + tm * dy)


def _box_overlap(a, b) -> float:
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    return 0.0 if ix <= 0 or iy <= 0 else ix * iy


def _class_f(sheet: Sheet, svg: SvgDoc, pol: dict) -> ClassReport:
    """Measurements only: text-vs-text overlap, text-vs-wire clearance, clipping,
    page occupancy (two denominators). No PASS gate on page use (DD-14)."""
    rep = ClassReport(id="f", title=CLASS_TITLES["f"],
                      applicability="partial: text-vs-text, wire-through-text and label-flag-outline-"
                                    "through-text only; text-vs-symbol-body/pin-graphics clearance "
                                    "NOT measured; page area excluding frame reported, not gated",
                      measured=True)
    clr = pol["text_graphics_clearance_mm"]
    ratio = pol["text_overlap_ratio"]
    sc = svg.unit_scale
    texts = svg.texts
    rep.examined_ids = [f"text:{t.content}@{t.anchor}" for t in texts]
    # text vs text
    tt = 0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i].bbox, texts[j].bbox
            ov = _box_overlap(a, b)
            area = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            if area > 0 and ov > ratio * area:
                tt += 1
                rep.findings.append(Finding(
                    cls="f", code="F_TEXT_TEXT_OVERLAP", kind="measurement",
                    at=(a[0] * sc, a[1] * sc), objects=[texts[i].content, texts[j].content],
                    region=tuple(v * sc for v in a),
                    message=f"{texts[i].content!r} overlaps {texts[j].content!r} ({ov / area:.2f})"))
    # text vs sheet wire (sheet coords are mm; svg viewBox units are mm here too
    # when unit_scale == 1, otherwise convert)
    # Round 5: exact clip of EVERY wire against the glyph box shrunk by `inset`.
    # The inset keeps a label's own wire (which ends at / runs along the anchor
    # edge) from counting; a wire that crosses the box interior always does. One
    # finding per (text, wire) pair. `at` = midpoint of the struck stretch.
    inset = 5 * pol["coord_eps_mm"]
    tw = 0
    for t in texts:
        bx = tuple(v * sc for v in t.bbox)
        core = (bx[0] + inset, bx[1] + inset, bx[2] - inset, bx[3] - inset)
        if core[2] <= core[0] or core[3] <= core[1]:
            continue
        for w in sheet.wires:
            ln, mid = _seg_box_clip(w.a, w.b, core)
            if ln > 0.0:
                tw += 1
                rep.findings.append(Finding(
                    cls="f", code="F_WIRE_THROUGH_TEXT", kind="measurement", at=mid,
                    objects=[t.content, f"wire:{w.uuid}"], region=bx,
                    message=f"wire passes through text {t.content!r} ({ln:.2f} mm inside the glyph box)"))
    # Round 5: global / hierarchical label FLAG OUTLINES (ink the label draws round
    # its text) against every text that is not the flag's own label. The flag is
    # identified by its first vertex == a sheet label anchor; a text wholly inside
    # the outline's bbox is the flag's own text and is skipped.
    fl = 0
    anchors = [(lab, lab.at) for lab in sheet.labels if lab.kind in ("global_label", "hierarchical_label")]
    for pts, _sw in svg.polys:
        p0 = (pts[0][0] * sc, pts[0][1] * sc)
        owner = next((lab for lab, at in anchors if math.dist(at, p0) <= 0.02), None)
        if owner is None:
            continue  # symbol bodies etc.: not modelled (class f stays partial)
        poly = [(x * sc, y * sc) for x, y in pts]
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        pb = (min(xs), min(ys), max(xs), max(ys))
        edges = list(zip(poly, poly[1:] + poly[:1]))
        for t in texts:
            bx = tuple(v * sc for v in t.bbox)
            if bx[0] >= pb[0] and bx[1] >= pb[1] and bx[2] <= pb[2] and bx[3] <= pb[3]:
                continue  # the flag's own text
            core = (bx[0] + inset, bx[1] + inset, bx[2] - inset, bx[3] - inset)
            if core[2] <= core[0] or core[3] <= core[1]:
                continue
            hit = [(ln, mid) for a, b in edges for ln, mid in [_seg_box_clip(a, b, core)] if ln > 0.0]
            if hit:
                fl += 1
                rep.findings.append(Finding(
                    cls="f", code="F_FLAG_THROUGH_TEXT", kind="measurement", at=hit[0][1],
                    objects=[t.content, f"flag:{owner.kind}:{owner.text}@{owner.at}"], region=bx,
                    message=f"{owner.kind} {owner.text!r} outline crosses text {t.content!r} "
                            f"({sum(h[0] for h in hit):.2f} mm of outline inside the glyph box)"))
    # clipping: any text/wire outside the page
    W, H = svg.width_mm, svg.height_mm
    clipped = [t.content for t in texts if t.bbox[0] * sc < 0 or t.bbox[2] * sc > W
               or t.bbox[1] * sc < 0 or t.bbox[3] * sc > H]
    clipped += [f"wire:{w.uuid}" for w in sheet.wires
                if any(p[0] < 0 or p[0] > W or p[1] < 0 or p[1] > H for p in (w.a, w.b))]
    for c in clipped:
        rep.findings.append(Finding(cls="f", code="F_CLIPPED", kind="measurement", objects=[c],
                                    message=f"{c} extends outside the {W}x{H} mm page"))
    # page occupancy: bbox of symbols+wires+labels over drawable area (page minus frame margin)
    m = pol["frame_margin_mm"]
    draw_w, draw_h = max(W - 2 * m, 1e-6), max(H - 2 * m, 1e-6)
    pts = [w.a for w in sheet.wires] + [w.b for w in sheet.wires] + [s.at for s in sheet.symbols] + [l.at for l in sheet.labels]
    cell = pol["page_grid_cell_mm"]
    cells = set()
    for p in pts:
        cells.add((int(p[0] // cell), int(p[1] // cell)))
    for w in sheet.wires:
        n = max(1, int(_seg_len(w.a, w.b) // cell))
        for k in range(n + 1):
            t = k / n
            cells.add((int((w.a[0] + t * (w.b[0] - w.a[0])) // cell), int((w.a[1] + t * (w.b[1] - w.a[1])) // cell)))
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bbox_use = ((max(xs) - min(xs)) * (max(ys) - min(ys))) / (draw_w * draw_h)
    else:
        bbox_use = 0.0
    grid_use = len(cells) / ((draw_w // cell) * (draw_h // cell))
    rep.measurements.update({
        "texts": len(texts), "text_text_overlaps": tt, "wire_through_text": tw,
        "flag_through_text": fl,
        "clipped": len(clipped),
        "page_mm": [W, H], "drawable_mm": [round(draw_w, 2), round(draw_h, 2)],
        "page_use_bbox_ratio": round(bbox_use, 4),
        "page_use_grid_ratio": round(grid_use, 4),
        "page_use_gate": pol["page_use_gate"],
        "min_font_mm": round(min((t.font_size for t in texts), default=0.0) * sc, 4),
    })
    # f is reported; only hard defects (overlap / through-text / clipped) set fail
    rep.verdict = "fail" if rep.findings else "pass"
    return rep


# --------------------------------------------------------------------------- sheet ink (round 9)

def _ink_paths(item: InkItem, tol: float = INK_CHORD_TOL_MM) -> list[tuple[Point, Point]]:
    """Centerline segments of one ink item. Rectangle: its four EDGES (the interior
    is not ink). Circle/arc: chord polyline with sagitta <= `tol` -- an
    approximation, never exact."""
    g = item.geometry_mm
    if item.kind == "rectangle":
        c = g["corners"]
        return [(c[i], c[(i + 1) % 4]) for i in range(4)]
    if item.kind == "polyline":
        p = g["points"]
        return [(p[i], p[i + 1]) for i in range(len(p) - 1)]
    if item.kind == "circle":
        cx, cy = g["center"]
        r = g["radius"]
        if r <= 0:
            return []
        n = 8 if tol >= r else max(8, math.ceil(math.pi / math.acos(1.0 - tol / r)))
        pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
               for k in range(n)]
        return [(pts[k], pts[(k + 1) % n]) for k in range(n)]
    # arc: circle through start/mid/end, swept start -> end through mid
    a, m, b = g["start"], g["mid"], g["end"]
    d = 2 * (a[0] * (m[1] - b[1]) + m[0] * (b[1] - a[1]) + b[0] * (a[1] - m[1]))
    if abs(d) < 1e-9:  # collinear: a straight path through the three points
        return [(a, m), (m, b)]
    ux = ((a[0] ** 2 + a[1] ** 2) * (m[1] - b[1]) + (m[0] ** 2 + m[1] ** 2) * (b[1] - a[1])
          + (b[0] ** 2 + b[1] ** 2) * (a[1] - m[1])) / d
    uy = ((a[0] ** 2 + a[1] ** 2) * (b[0] - m[0]) + (m[0] ** 2 + m[1] ** 2) * (a[0] - b[0])
          + (b[0] ** 2 + b[1] ** 2) * (m[0] - a[0])) / d
    r = math.hypot(a[0] - ux, a[1] - uy)
    ang = lambda p: math.atan2(p[1] - uy, p[0] - ux)
    t0, tm, t1 = ang(a), ang(m), ang(b)
    tau = 2 * math.pi
    ccw_m, ccw_1 = (tm - t0) % tau, (t1 - t0) % tau
    sweep = ccw_1 if ccw_m <= ccw_1 else -((t0 - t1) % tau)
    n = max(2, math.ceil(abs(sweep) / (2 * math.acos(1.0 - tol / r)))) if tol < r else 8
    pts = [(ux + r * math.cos(t0 + sweep * k / n), uy + r * math.sin(t0 + sweep * k / n))
           for k in range(n + 1)]
    return [(pts[k], pts[k + 1]) for k in range(n)]


def _seg_hit(a: Point, b: Point, c: Point, d: Point, eps: float):
    """Centerline intersection of segment ab with segment cd, or None. Returns
    (label, point): `cross` = proper interior crossing; `overlap` = collinear
    stretch longer than eps; `touch` = an endpoint within eps of the other segment
    (or tangent contact). Degenerate (zero-length) segments are tested as points."""
    la, lc = _seg_len(a, b), _seg_len(c, d)
    if la < 1e-9 or lc < 1e-9:
        p, s0, s1 = (a, c, d) if la < 1e-9 else (c, a, b)
        if _dist_point_seg(p, s0, s1) <= eps:
            return ("touch", (round(p[0], 4), round(p[1], 4)))
        return None
    u, v = _unit(a, b), _unit(c, d)
    if abs(u[0] * v[1] - u[1] * v[0]) <= 1e-3:  # parallel
        if _dist_point_seg(c, a, b) > eps and _dist_point_seg(d, a, b) > eps \
                and _dist_point_seg(a, c, d) > eps and _dist_point_seg(b, c, d) > eps:
            return None
        if abs(_orient(a, b, c)) / la > eps:
            return None
        ov = _parallel_overlap(a, b, c, d, eps)
        pts = [p for p in (a, b, c, d) if _dist_point_seg(p, a, b) <= eps and _dist_point_seg(p, c, d) <= eps]
        at = pts[0] if pts else a
        return ("overlap" if ov > eps else "touch", (round(at[0], 4), round(at[1], 4)))
    p = _proper_cross(a, b, c, d, eps)
    if p is not None:
        return ("cross", p)
    for q, s0, s1 in ((a, c, d), (b, c, d), (c, a, b), (d, a, b)):
        if _dist_point_seg(q, s0, s1) <= eps:
            return ("touch", (round(q[0], 4), round(q[1], 4)))
    return None


_OBS_PRIORITY = {"overlap": 3, "cross": 2, "touch": 1, "strike": 2}


def _path_vs_path(ink_segs, other_segs, eps: float):
    """All centerline hits between two paths -> (strongest label, distinct points)."""
    label, pts = None, []
    for a, b in ink_segs:
        for c, d in other_segs:
            h = _seg_hit(a, b, c, d, eps)
            if h is None:
                continue
            if label is None or _OBS_PRIORITY[h[0]] > _OBS_PRIORITY[label]:
                label = h[0]
            pt = (round(h[1][0], 2), round(h[1][1], 2))
            if pt not in pts:
                pts.append(pt)
    return label, pts


@dataclass
class Observation:
    """kind="observation": a GEOMETRIC-PATH INTERSECTION OBSERVATION. Not a finding,
    not rendered ink. Never reaches a verdict, a defect count or a calibration cell."""
    cls: str
    code: str
    ink_uuid: str
    other: str
    label: str
    points: list
    owner: str
    ownership_assessment: str  # measured | unmeasured
    message: str
    kind: str = "observation"


def _ink_observations(sheet: Sheet, svg: SvgDoc, pol: dict):
    """P1-P4. Returns (observations, counts). counts[code] = expected / examined /
    omitted(list) / emitted with expected == examined + len(omitted)."""
    eps = pol["coord_eps_mm"]
    sc = svg.unit_scale
    obs: list[Observation] = []
    codes = ("F_WIRE_THROUGH_INK", "F_INK_THROUGH_TEXT", "F_FLAG_THROUGH_INK", "F_INK_THROUGH_PIN")
    counts = {c: {"expected": 0, "examined": 0, "omitted": [], "emitted": 0} for c in codes}
    if not sheet.ink:
        return obs, counts

    def emit(code, item, other, label, pts, msg):
        counts[code]["emitted"] += 1
        obs.append(Observation(
            cls="f", code=code, ink_uuid=item.uuid, other=other, label=label, points=pts,
            owner=item.owner,
            ownership_assessment="measured" if item.owner != "unknown" else "unmeasured",
            message=msg))

    inset = 5 * eps
    anchors = [(lab, lab.at) for lab in sheet.labels if lab.kind in ("global_label", "hierarchical_label")]
    flags = []
    for pts, _sw in svg.polys:
        p0 = (pts[0][0] * sc, pts[0][1] * sc)
        owner = next((lab for lab, at in anchors if math.dist(at, p0) <= 0.02), None)
        if owner is not None:
            poly = [(x * sc, y * sc) for x, y in pts]
            flags.append((owner, list(zip(poly, poly[1:] + poly[:1]))))
    wires: dict[str, list] = {}
    for i, w in enumerate(sheet.wires):
        wires.setdefault(w.uuid or f"#w{i}", []).append((w.a, w.b))
    pins = [p for s in sheet.symbols for p in s.pins]
    for item in sheet.ink:
        segs = _ink_paths(item)
        tag = f"ink:{item.uuid}"
        for wid, wsegs in wires.items():
            counts["F_WIRE_THROUGH_INK"]["expected"] += 1
            counts["F_WIRE_THROUGH_INK"]["examined"] += 1
            lab, pts = _path_vs_path(segs, wsegs, eps)
            if lab:
                emit("F_WIRE_THROUGH_INK", item, f"wire:{wid}", lab, pts,
                     f"wire path {lab} ink path {item.uuid}")
        for t in svg.texts:
            counts["F_INK_THROUGH_TEXT"]["expected"] += 1
            bx = tuple(v * sc for v in t.bbox)
            core = (bx[0] + inset, bx[1] + inset, bx[2] - inset, bx[3] - inset)
            if core[2] <= core[0] or core[3] <= core[1]:
                counts["F_INK_THROUGH_TEXT"]["omitted"].append(
                    {"ink": item.uuid, "object": f"text:{t.content}", "reason": "glyph box degenerate after inset"})
                continue
            counts["F_INK_THROUGH_TEXT"]["examined"] += 1
            hit = [m for a, b in segs for ln, m in [_seg_box_clip(a, b, core)] if ln > 0.0]
            if hit:
                emit("F_INK_THROUGH_TEXT", item, f"text:{t.content}", "strike",
                     [(round(hit[0][0], 2), round(hit[0][1], 2))],
                     f"ink path {item.uuid} crosses text {t.content!r} glyph box")
        for lab_, edges in flags:
            counts["F_FLAG_THROUGH_INK"]["expected"] += 1
            counts["F_FLAG_THROUGH_INK"]["examined"] += 1
            lab, pts = _path_vs_path(segs, edges, eps)
            if lab:
                emit("F_FLAG_THROUGH_INK", item, f"flag:{lab_.kind}:{lab_.text}@{lab_.at}", lab, pts,
                     f"label flag outline {lab} ink path {item.uuid}")
        for p in pins:
            counts["F_INK_THROUGH_PIN"]["expected"] += 1
            if p.hidden:
                counts["F_INK_THROUGH_PIN"]["omitted"].append(
                    {"ink": item.uuid, "object": f"pin:{p.id}", "reason": "hidden pin (not drawn)"})
                continue
            counts["F_INK_THROUGH_PIN"]["examined"] += 1
            lab, pts = _path_vs_path(segs, [(p.tip, p.end)], eps)
            if lab:
                emit("F_INK_THROUGH_PIN", item, f"pin:{p.id}", lab, pts,
                     f"ink path {item.uuid} {lab} pin {p.id} stub (geometric proximity only)")
    return obs, counts


def _resolve_ink_owners(sheet: Sheet, owner_map: dict | None, owner_rule: dict | None) -> dict:
    """Assign `owner` ONLY from declared authority. Two separate modes:
      (i)  explicit map {ink_uuid: ref}: exact identities only (no uuid5);
      (ii) rule {id, version, name, targets:[ref]}: the only mode that reproduces
           uuid5(symbol_uuid, name) and matches it to an ink uuid.
    Containment / proximity never sets an owner. Duplicate or ambiguous target
    identities assign NO owner and are recorded as a mismatch."""
    if owner_map is not None and owner_rule is not None:
        raise ReadabilityInputError("E_INK_OWNER_BOTH_MODES: supply an explicit map OR a rule, not both")
    mismatches: list[dict] = []
    by_uuid: dict[str, list[InkItem]] = {}
    for it in sheet.ink:
        by_uuid.setdefault(it.uuid, []).append(it)
    by_ref: dict[str, list[Symbol]] = {}
    for s in sheet.symbols:
        by_ref.setdefault(s.ref, []).append(s)

    def assign(uid, ref, why):
        items = by_uuid.get(uid, [])
        if len(items) != 1 or uid == "":
            mismatches.append({"ink_uuid": uid, "ref": ref, "reason": why or (
                "ink uuid not on sheet" if not items else "ambiguous: duplicate ink uuid")})
            return
        if len(by_ref.get(ref, [])) != 1:
            mismatches.append({"ink_uuid": uid, "ref": ref, "reason":
                               "symbol ref not on sheet" if not by_ref.get(ref) else "ambiguous: duplicate symbol ref"})
            return
        items[0].owner = ref

    mode = "none"
    if owner_map is not None:
        mode = "explicit_map"
        for uid, ref in owner_map.items():
            assign(uid, ref, "")
    elif owner_rule is not None:
        mode = "rule"
        import uuid as _uuid
        name = owner_rule.get("name")
        for ref in owner_rule.get("targets", []):
            syms = by_ref.get(ref, [])
            if len(syms) != 1:
                mismatches.append({"ink_uuid": None, "ref": ref, "reason":
                                   "symbol ref not on sheet" if not syms else "ambiguous: duplicate symbol ref"})
                continue
            try:
                want = str(_uuid.uuid5(_uuid.UUID(syms[0].uuid), name))
            except (ValueError, TypeError, AttributeError):
                mismatches.append({"ink_uuid": None, "ref": ref, "reason": "symbol uuid not a valid uuid"})
                continue
            if want not in by_uuid:
                mismatches.append({"ink_uuid": want, "ref": ref, "reason":
                                   "rule does not reproduce any ink uuid on this sheet"})
                continue
            assign(want, ref, "")
    return {"mode": mode, "mismatches": mismatches,
            "owner_unknown": [it.uuid for it in sheet.ink if it.owner == "unknown"]}


# --------------------------------------------------------------------------- entry

def _check_pairing(sheet_path: Path, sheet: Sheet, svg: SvgDoc, nets: dict,
                   net_text: str, anomalies: list[str]) -> None:
    """Provenance checks between the three inputs. A failed check is an anomaly
    the report carries; the caller decides whether that blocks (it does, via
    verdict=indeterminate) -- it is never silently ignored."""
    paper = _PAPER_MM.get(sheet.paper)
    if paper is None:
        anomalies.append(f"PAIR_PAPER_UNKNOWN: paper {sheet.paper!r} not in table")
    elif abs(paper[0] - svg.width_mm) > 1.0 or abs(paper[1] - svg.height_mm) > 1.0:
        anomalies.append(f"PAIR_PAGE_MISMATCH: sheet paper {sheet.paper} {paper} vs "
                         f"svg {svg.width_mm}x{svg.height_mm} mm")
    # every sheet wire must be covered by rendered segments at the same coordinates
    # (KiCad re-splits a wire at a T, so identity is coverage, not segment equality)
    missing = 0
    rendered = [(pts[0], pts[1]) for (pts, _sw) in svg.paths if len(pts) == 2]
    for w in sheet.wires:
        a = (w.a[0] / svg.unit_scale, w.a[1] / svg.unit_scale)
        b = (w.b[0] / svg.unit_scale, w.b[1] / svg.unit_scale)
        samples = [(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])) for t in (0.0, 0.5, 1.0)]
        if not all(any(_dist_point_seg(s, p, q) <= 0.02 for (p, q) in rendered) for s in samples):
            missing += 1
    if missing:
        anomalies.append(f"PAIR_SVG_WIRES_MISSING: {missing}/{len(sheet.wires)} sheet wires "
                         f"have no rendered segment at the same coordinates")
    src = netlist_source(net_text)
    if src and Path(src).name != sheet_path.name:
        anomalies.append(f"PAIR_NETLIST_SOURCE: netlist source {src!r} != {sheet_path.name}")
    refs = {s.ref for s in sheet.symbols if not s.is_power}
    net_refs = {r for nodes in nets.values() for r, _p in nodes}
    if not net_refs <= refs:
        anomalies.append(f"PAIR_NETLIST_REFS: refs in netlist not on sheet: {sorted(net_refs - refs)}")


# --------------------------------------------------------------------------- provenance

EXPORT_RECEIPT_SCHEMA = "s1-export-receipt-v1"


def write_export_receipt(path: str | Path, *, sheet_paths: list[str | Path],
                         netlist_path: str | Path, svg_path: str | Path,
                         kicad_version: str, commands: list[str]) -> dict:
    """Write the export lineage record that `measure` resolves against. The
    producer of the native exports (the step that ran kicad-cli) writes it; the
    instrument only READS it. Hashes are taken from the bytes at write time."""
    rec = {
        "schema": EXPORT_RECEIPT_SCHEMA,
        "sheet_set": {Path(p).name: _sha256(Path(p)) for p in sheet_paths},
        "netlist_sha256": _sha256(Path(netlist_path)),
        "render_sha256": _sha256(Path(svg_path)),
        "kicad_version": kicad_version,
        "commands": list(commands),
    }
    Path(path).write_text(__import__("json").dumps(rec, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    return rec


def _resolve_provenance(receipt: dict | str | Path | None, hashes: dict[str, str],
                        anomalies: list[str]) -> dict:
    """status: verified | mismatch | unknown. Anything but `verified` blocks PASS;
    findings are retained either way. Filename/page/wire-sample pairing is a
    sanity check, not lineage -- lineage is this receipt."""
    if receipt is None:
        return {"status": "unknown", "reason": "no export receipt supplied"}
    if not isinstance(receipt, dict):
        p = Path(receipt)
        if not p.is_file():
            return {"status": "unknown", "reason": f"export receipt missing: {p}"}
        receipt = __import__("json").loads(p.read_text(encoding="utf-8"))
    if receipt.get("schema") != EXPORT_RECEIPT_SCHEMA:
        return {"status": "unknown", "reason": f"unsupported receipt schema {receipt.get('schema')!r}"}
    mismatches = []
    if hashes["sheet"] not in set(receipt.get("sheet_set", {}).values()):
        mismatches.append("sheet hash not in receipt sheet_set (same-named changed sheet?)")
    if receipt.get("netlist_sha256") != hashes["netlist"]:
        mismatches.append("netlist hash != receipt (stale export)")
    if receipt.get("render_sha256") != hashes["svg"]:
        mismatches.append("render hash != receipt (stale render)")
    for k in ("kicad_version", "commands"):
        if not receipt.get(k):
            mismatches.append(f"receipt lacks {k}")
    if mismatches:
        anomalies.append("PROVENANCE_MISMATCH: " + "; ".join(mismatches))
        return {"status": "mismatch", "reasons": mismatches,
                "kicad_version": receipt.get("kicad_version")}
    return {"status": "verified", "kicad_version": receipt["kicad_version"],
            "commands": receipt["commands"], "sheet_set": receipt["sheet_set"]}


# --------------------------------------------------------------------------- calibration

CALIBRATION_RECORD_SCHEMA = "s1-calibration-record-v2"
CALIBRATION_SCOPED_CLASSES = "abcde"
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _check_entries(entries, where: str, problems: list[str]) -> int:
    """Every adjudicated case must bind an artifact hash AND a reviewer decision
    ref; an entry lacking either is not evidence. Returns the count of valid ones."""
    if not isinstance(entries, list):
        problems.append(f"{where}: entries must be a list")
        return 0
    ok = 0
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"{where}[{i}]: not an object")
            continue
        h, ref = e.get("artifact_sha256"), e.get("decision_ref")
        if not isinstance(h, str) or not _HEX64_RE.match(h):
            problems.append(f"{where}[{i}]: artifact_sha256 missing or not sha256 hex")
            continue
        if not isinstance(ref, str) or not ref.strip():
            problems.append(f"{where}[{i}]: decision_ref missing")
            continue
        ok += 1
    return ok


def _resolve_calibration(record: dict | None, policy_digest: str,
                         classes: list[ClassReport], subject_scope: dict) -> dict:
    """Pure consistency check of a CONTENT-BOUND calibration record (v2). The
    application boundary resolves refs to contents; this function verifies:
      * schema + policy digest match the running instrument;
      * every entry binds an artifact hash and a reviewer decision ref;
      * every required class has >= 1 adjudicated REJECTING and >= 1 independently
        reviewed ACCEPTING (or paired) case;
      * the record's supported scope (rotations, classes) covers the subject.
    A class without accepting evidence is `partial`; any partial class blocks the
    scoped PASS. Nothing here is a caller assertion -- a record that merely says
    'calibrated' resolves to uncalibrated."""
    if record is None:
        return {"status": "uncalibrated", "reason": "no calibration record supplied"}
    if record.get("schema") != CALIBRATION_RECORD_SCHEMA:
        return {"status": "uncalibrated",
                "reason": f"unsupported schema {record.get('schema')!r} (need {CALIBRATION_RECORD_SCHEMA})"}
    if record.get("policy_digest") != policy_digest:
        return {"status": "uncalibrated",
                "reason": f"record policy {record.get('policy_digest')} != running {policy_digest}"}
    problems: list[str] = []
    scope = record.get("supported_scope")
    if not isinstance(scope, dict) or "rotations" not in scope or "classes" not in scope:
        problems.append("supported_scope must declare rotations and classes")
        scope = {"rotations": [], "classes": []}
    covered = record.get("classes")
    if not isinstance(covered, dict):
        problems.append("classes must be an object keyed by class id")
        covered = {}
    required = [c.id for c in classes
                if c.id in CALIBRATION_SCOPED_CLASSES and c.verdict != "not-applicable"]
    per_class: dict[str, dict] = {}
    partial: list[str] = []
    for cid in required:
        ent = covered.get(cid) or {}
        n_rej = _check_entries(ent.get("rejecting", []), f"classes.{cid}.rejecting", problems)
        n_acc = _check_entries(ent.get("accepting", []), f"classes.{cid}.accepting", problems)
        missing = []
        if cid not in set(scope.get("classes", [])):
            missing.append("not in supported_scope.classes")
        if n_rej < 1:
            missing.append("no adjudicated rejecting case")
        if n_acc < 1:
            missing.append("no independently reviewed accepting case")
        per_class[cid] = {"rejecting": n_rej, "accepting": n_acc, "missing": missing}
        if missing:
            partial.append(cid)
    if problems:
        return {"status": "inconsistent", "problems": problems,
                "record_version": record.get("version"), "classes": per_class}
    subj_rot = set(subject_scope.get("rotations", []))
    rec_rot = set(scope.get("rotations", []))
    out_of_scope = sorted(subj_rot - rec_rot, key=str)
    if out_of_scope:
        return {"status": "out_of_scope", "record_version": record.get("version"),
                "reason": f"subject rotations {out_of_scope} not in supported {sorted(rec_rot, key=str)}",
                "classes": per_class}
    base = {"record_version": record.get("version"), "policy_digest": policy_digest,
            "supported_scope": {"rotations": sorted(rec_rot, key=str), "classes": sorted(scope.get("classes", []))},
            "subject_scope": {"rotations": sorted(subj_rot, key=str), "classes": required},
            "classes": per_class,
            # structural check only; no boundary has bound entries to reviewed artifacts
            "evidence_authenticated": False, "authenticated_by": None}
    if partial:
        return {"status": "partial", "partial_classes": partial,
                "reason": "classes lacking rejecting and/or accepting adjudicated evidence", **base}
    return {"status": "calibrated",
            "note": "calibrated against cited reviewer decisions only; not validated sensitivity",
            **base}


def measure(sheet_path: str | Path, svg_path: str | Path, netlist_path: str | Path,
            *, policy: dict | None = None, baseline_ref: str = "",
            export_receipt: dict | str | Path | None = None,
            calibration_record: dict | None = None,
            declared_pin_nets: dict[str, str] | None = None,
            required_local_pairs: list[tuple[str, str]] | None = None,
            local_exceptions: dict[str, str] | None = None,
            ink_owner_map: dict[str, str] | None = None,
            ink_owner_rule: dict | None = None) -> ReadabilityReport:
    """Run classes (a)-(f) on a paired native set. Refuses (raises) when an input
    cannot be parsed; reports verdict=indeterminate when pairing anomalies exist."""
    pol = dict(POLICY)
    if policy:
        pol.update(policy)
    sheet_path, svg_path, netlist_path = Path(sheet_path), Path(svg_path), Path(netlist_path)
    for p in (sheet_path, svg_path, netlist_path):
        if not p.is_file():
            raise ReadabilityInputError(f"E_INPUT_MISSING: {p}")
    anomalies: list[str] = []
    sheet = parse_sheet(sheet_path.read_text(encoding="utf-8"))
    svg = parse_svg(svg_path.read_text(encoding="utf-8"))
    net_text = netlist_path.read_text(encoding="utf-8")
    nets = parse_netlist(net_text)
    _check_pairing(sheet_path, sheet, svg, nets, net_text, anomalies)
    hashes = {"sheet": _sha256(sheet_path), "svg": _sha256(svg_path), "netlist": _sha256(netlist_path)}
    provenance = _resolve_provenance(export_receipt, hashes, anomalies)
    g = build_drawn_graph(sheet, nets, pol["coord_eps_mm"])
    ink_owners = _resolve_ink_owners(sheet, ink_owner_map, ink_owner_rule)
    # pin->net authority: declared circuit when supplied, else the native export
    if declared_pin_nets:
        pin_map, identity_source = dict(declared_pin_nets), "declared circuit"
    else:
        pin_map, identity_source = dict(g.pin_net), "native netlist"
    classes = [
        _class_a(sheet, g, pol),
        _class_b(sheet, g, pol, pin_map, identity_source),
        _class_c(sheet, g, nets, pol, required_local_pairs, local_exceptions),
        _class_d(sheet, g, pol, declared_pin_nets),
        _class_e(sheet, g, svg, pol),
        _class_f(sheet, svg, pol),
    ]
    # Round 9: observations ride on class f but are NOT findings; the class verdict
    # was already fixed by `findings` inside _class_f and is not touched here.
    f_rep0 = classes[5]
    f_rep0.observations, f_rep0.observation_counts = _ink_observations(sheet, svg, pol)
    policy_digest = hashlib.sha256(repr(sorted(pol.items())).encode()).hexdigest()[:16]
    # subject identity = artifacts + every authority input that can change findings
    # (declared nets, required pairs, exceptions, policy). Changing authority under
    # the same artifact bytes yields a different subject manifest.
    authority = {
        "declared_pin_nets": hashlib.sha256(repr(sorted((declared_pin_nets or {}).items())).encode()).hexdigest(),
        # None (derive under policy K) and [] (explicit empty population) are
        # different authority modes with different findings: tag the mode.
        "required_local_pairs": hashlib.sha256(repr(
            {"mode": "derived"} if required_local_pairs is None else
            {"mode": "explicit", "pairs": sorted(tuple(p) for p in required_local_pairs)}
        ).encode()).hexdigest(),
        "local_exceptions": hashlib.sha256(repr(sorted((local_exceptions or {}).items())).encode()).hexdigest(),
        "policy_digest": policy_digest,
    }
    # Round 9: ink authority joins the subject identity ONLY for a subject that
    # carries ink or an ink-owner declaration, so every ink-free manifest stays
    # byte-identical to its 9c18bc51 value. The mode is tagged: None (no
    # declaration), an explicit EMPTY map and a rule are three distinct modes, and a
    # rule is hashed by ALL of its inputs/parameters, not by id/version alone.
    if sheet.ink or ink_owner_map is not None or ink_owner_rule is not None:
        if ink_owner_rule is not None:
            decl = {"mode": "rule", "rule": sorted((k, repr(v)) for k, v in ink_owner_rule.items())}
        elif ink_owner_map is not None:
            decl = {"mode": "explicit_map", "map": sorted(ink_owner_map.items())}
        else:
            decl = {"mode": "none"}
        authority["ink_owner"] = hashlib.sha256(repr(decl).encode()).hexdigest()
        authority["measurement_scope_version"] = MEASUREMENT_SCOPE_VERSION
        authority["ink_chord_tol_mm"] = repr(INK_CHORD_TOL_MM)
    manifest = hashlib.sha256(
        "\n".join(f"{k}:{v}" for k, v in sorted({**hashes, **authority}.items())).encode()).hexdigest()
    render_context = {
        "renderer": "kicad-cli sch export svg (version not embedded in SVG; pin externally)",
        "artifact_hashes": hashes,
        "viewbox": list(svg.viewbox),
        "viewbox_unit_to_mm": svg.unit_scale,
        "page_mm": [svg.width_mm, svg.height_mm],
        "stroke_width_mm": max((sw for (_p, sw) in svg.paths), default=0.0) * svg.unit_scale,
        "text_count": len(svg.texts),
        "sheet_paper": sheet.paper,
    }
    # subject scope = the symbol rotations (and mirror) actually present; the
    # calibration record must declare support for every one of them
    subject_scope = {"rotations": sorted({int(s.rot) % 360 for s in sheet.symbols})
                     + (["mirror"] if any(s.mirror for s in sheet.symbols) else [])}
    # Round 6: transforms are MEASURED correct for pins and body (receipt s11) but
    # NOT calibrated. A subject carrying any rotation != 0 or any mirror is never
    # inside supported scope unless the record names it; this instrument ships no
    # such record, so such subjects resolve out_of_scope with findings retained.
    cal = _resolve_calibration(calibration_record, policy_digest, classes, subject_scope)
    # Precedence (round 3): provenance that is not `verified` -- or inputs that do
    # not describe one artifact -- makes the OVERALL verdict indeterminate. Class
    # outcomes and findings are retained as diagnostics; a class FAIL never
    # outranks unknown lineage. Only under verified lineage can fail / pass be read.
    scoped = [c for c in classes if c.id in CALIBRATION_SCOPED_CLASSES]
    if anomalies and any(a.startswith("PAIR_") for a in anomalies):
        scoped_verdict = "indeterminate"
    elif provenance["status"] != "verified":
        scoped_verdict = "indeterminate"
    elif any(c.verdict == "fail" for c in scoped):
        scoped_verdict = "fail"
    elif any(c.verdict == "indeterminate" or not c.measured for c in scoped):
        scoped_verdict = "indeterminate"
    elif cal["status"] != "calibrated":
        scoped_verdict = "indeterminate"
    else:
        scoped_verdict = "pass"
    # six-class verdict: f is explicitly partial, so the full report can be fail
    # (f or a-e found a hard defect under verified lineage) or indeterminate --
    # never pass -- until f is fully measured or its applicability is justified.
    f_rep = next(c for c in classes if c.id == "f")
    if scoped_verdict == "fail":
        verdict = "fail"
    elif scoped_verdict == "indeterminate":
        verdict = "indeterminate"
    elif f_rep.verdict == "fail":
        verdict = "fail"
    else:
        verdict = "indeterminate"
    render_context["provenance"] = provenance
    return ReadabilityReport(
        subject_manifest_sha256=manifest,
        presentation_baseline_ref=baseline_ref or hashes["sheet"],
        render_context=render_context,
        policy_ref={"version": pol["version"], "frozen_on": pol["frozen_on"],
                    "digest": policy_digest, "values": pol},
        classes=classes,
        calibration_ref=cal,
        execution="succeeded",
        verdict=verdict,
        human_review_ref=None,
        does_not_authorize=list(DOES_NOT_AUTHORIZE),
        anomalies=anomalies,
        verdict_scope="a-e",
        scoped_verdict=scoped_verdict,
        authority_digests=authority,
        measurement_scope={"version": MEASUREMENT_SCOPE_VERSION,
                           "policy_digest": policy_digest,
                           "ink_chord_tol_mm": INK_CHORD_TOL_MM,
                           "observations": "f: F_WIRE_THROUGH_INK, F_INK_THROUGH_TEXT, "
                                           "F_FLAG_THROUGH_INK, F_INK_THROUGH_PIN "
                                           "(kind=observation; never findings)",
                           "not_assessed": ["dash gaps", "stroke envelope", "fill", "z-order",
                                            "ink meaning / grouping", "symbol coherence",
                                            "package-implies-internal-connection"]},
        sheet_graphic_ink=[asdict(i) for i in sheet.ink],
        ink_report={"count": len(sheet.ink), "ink_missing_uuid": sheet.ink_missing_uuid,
                    "ink_unparsed_by_kind": dict(sheet.ink_unparsed),
                    "owner_mode": ink_owners["mode"],
                    "ink_owner_unknown": ink_owners["owner_unknown"],
                    "owner_declaration_mismatch": ink_owners["mismatches"]},
    )
