"""Deterministic electrically-aware pre-placement core (G3; pure Python, no pcbnew).

Pipeline (idef0 A2..A5): anchor selection → pin-affinity clustering → ring-band
greedy initial placement (R4 largest-first) → fixed-seed SA refinement →
R1/R8 post-place checks with anchored, explainable violations.

Contracts (design.md DD-1..DD-8):
  - zero pcbnew dependency; geometry arrives as PartGeom records (adapter's job)
  - sole randomness source is random.Random(seed); same input ⇒ same output
  - fail fast on missing geometry / infeasible board; NEVER fall back silently
  - every rule threshold comes from placement_rules.RULES (source-anchored)
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

from .placement_rules import RULES

GUTTER_MM = 1.0          # min air gap between courtyards in greedy placement
EDGE_MARGIN_MM = 1.0     # keep-out from board outline
GRID_MM = 1.0            # translation quantum (greedy slots + SA moves)
SA_ITERATIONS = 1500
SA_T0 = 10.0
SA_COOL = 0.995
DEFAULT_WEIGHTS = {"w_aff": 4.0, "w_ovl": 10.0, "w_edge": 50.0}
# soft affinity distance targets per cluster priority (mm); excess is penalized
AFFINITY_LIMIT_MM = {"decap": RULES["R1"]["value"], "crystal": 5.0, "signal": 10.0}
MIDFREQ_MAX_F = 1.0e-7   # <=100nF counts as mid-freq for R8 (DD-6)
DECAP_MAX_F = 1.0e-6     # <=1µF counts as a decoupling cap (DD-7)


@dataclass
class PartGeom:
    """Footprint geometry in mm. pads maps pad number -> (dx, dy) from part center."""
    ref: str
    w_mm: float
    h_mm: float
    pads: dict = field(default_factory=dict)
    value: str = ""
    kind: str = ""

    def __post_init__(self) -> None:
        if not self.kind:
            m = re.match(r"^([A-Za-z]+)", self.ref)
            self.kind = m.group(1).upper() if m else ""


@dataclass
class PreplaceResult:
    placement: dict            # {ref: (x_mm, y_mm, rot_deg)}
    violations: list           # [{rule, source, refs, measured_mm, limit_mm, note}]
    effective: dict            # echoed params (seed, weights, margins, board)
    anchor: str
    clusters: dict             # {ref: {target_ref, target_pad, priority}}
    hpwl_mm: float
    overlap_pairs: int


# ------------------------------------------------------------------ priors
_CAP_RE = re.compile(r"^([\d.]+)\s*([pnuµUm]?)\s*F?$", re.IGNORECASE)
_CAP_MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0}


def parse_cap_farads(value: str) -> float | None:
    m = _CAP_RE.match(value.strip()) if value else None
    if not m:
        return None
    suffix = (m.group(2) or "").lower().replace("µ", "u")
    try:
        return float(m.group(1)) * _CAP_MULT.get(suffix, 1.0)
    except ValueError:
        return None


def is_power_net(name: str, nodes: list) -> bool:
    u = name.upper().lstrip("+/")
    if u in ("GND", "AGND", "DGND", "PGND", "VSS", "VSSA"):
        return True
    if u.startswith(("VCC", "VDD", "VBUS", "VBAT", "VIN", "VOUT", "VLED", "VSYS")):
        return True
    if re.fullmatch(r"\d+V\d*", u):
        return True
    return len(nodes) > 3


def _is_ground_net(name: str) -> bool:
    u = name.upper().lstrip("+/")
    return u.startswith(("GND", "VSS")) or u in ("AGND", "DGND", "PGND")


def select_anchor(parts: dict) -> str:
    """Main IC = most pads; deterministic tie-break by lexicographic refdes (DD-7)."""
    return min(parts.values(), key=lambda p: (-len(p.pads), p.ref)).ref


def _shared_target(ref: str, candidates: set, nets: dict, power: set):
    """First (net-sorted) non-power net shared between ref and any candidate."""
    for net in sorted(nets):
        if net in power:
            continue
        nodes = nets[net]
        if not any(r == ref for r, _ in nodes):
            continue
        for r2, p2 in sorted(nodes):
            if r2 in candidates and r2 != ref:
                return r2, p2
    return None


def _decap_target(ref: str, targets: set, nets: dict, power: set):
    """Non-ground power net shared with an IC → that IC's pin on the net."""
    for net in sorted(nets):
        if net not in power or _is_ground_net(net):
            continue
        nodes = nets[net]
        if not any(r == ref for r, _ in nodes):
            continue
        for r2, p2 in sorted(nodes):
            if r2 in targets and r2 != ref:
                return r2, p2
    return None


def build_clusters(parts: dict, nets: dict, anchor: str) -> dict:
    """DD-7 affinity priors. Priorities: edge | crystal | decap | signal | free."""
    power = {net for net, nodes in nets.items() if is_power_net(net, nodes)}
    ics = {r for r, p in parts.items() if p.kind == "U"} | {anchor}
    crystals = {r for r, p in parts.items() if p.kind == "Y"}
    clusters: dict = {}
    for ref in sorted(parts):
        if ref == anchor:
            continue
        part = parts[ref]
        if part.kind in ("J", "MH", "H", "TP"):
            clusters[ref] = {"target_ref": None, "target_pad": None, "priority": "edge"}
            continue
        if part.kind == "C":
            xt = _shared_target(ref, crystals, nets, power)
            if xt:
                clusters[ref] = {"target_ref": xt[0], "target_pad": xt[1], "priority": "crystal"}
                continue
            farads = parse_cap_farads(part.value)
            if farads is not None and farads <= DECAP_MAX_F:
                dt = _decap_target(ref, ics, nets, power)
                if dt:
                    clusters[ref] = {"target_ref": dt[0], "target_pad": dt[1], "priority": "decap"}
                    continue
        st = _shared_target(ref, {anchor}, nets, power)
        if st:
            clusters[ref] = {"target_ref": st[0], "target_pad": st[1], "priority": "signal"}
        else:
            clusters[ref] = {"target_ref": anchor, "target_pad": None, "priority": "free"}
    return clusters


# ------------------------------------------------------------- geometry ops
def _dims(part: PartGeom, rot: float) -> tuple[float, float]:
    return (part.h_mm, part.w_mm) if rot % 180 == 90 else (part.w_mm, part.h_mm)


def pad_abs(placement: dict, parts: dict, ref: str, pad: str) -> tuple[float, float]:
    x, y, rot = placement[ref]
    dx, dy = parts[ref].pads[pad]
    r = rot % 360
    if r == 0:
        return (x + dx, y + dy)
    if r == 90:
        return (x - dy, y + dx)
    if r == 180:
        return (x - dx, y - dy)
    if r == 270:
        return (x + dy, y - dx)
    rad = math.radians(r)
    return (x + dx * math.cos(rad) - dy * math.sin(rad),
            y + dx * math.sin(rad) + dy * math.cos(rad))


def _overlap_area(p1, d1, p2, d2) -> float:
    ox = min(p1[0] + d1[0] / 2, p2[0] + d2[0] / 2) - max(p1[0] - d1[0] / 2, p2[0] - d2[0] / 2)
    oy = min(p1[1] + d1[1] / 2, p2[1] + d2[1] / 2) - max(p1[1] - d1[1] / 2, p2[1] - d2[1] / 2)
    return max(0.0, ox) * max(0.0, oy)


def _inside_board(x, y, w, h, board) -> bool:
    return (x - w / 2 >= EDGE_MARGIN_MM and y - h / 2 >= EDGE_MARGIN_MM
            and x + w / 2 <= board[0] - EDGE_MARGIN_MM and y + h / 2 <= board[1] - EDGE_MARGIN_MM)


def _overlaps_any(x, y, w, h, ref, placement, parts) -> bool:
    for r2, (x2, y2, rot2) in placement.items():
        if r2 == ref:
            continue
        w2, h2 = _dims(parts[r2], rot2)
        if _overlap_area((x, y), (w + GUTTER_MM, h + GUTTER_MM), (x2, y2), (w2, h2)) > 0:
            return True
    return False


def compute_hpwl(placement: dict, parts: dict, nets: dict) -> float:
    total = 0.0
    for net in sorted(nets):
        xs, ys = [], []
        for ref, pad in nets[net]:
            if ref in placement and pad in parts[ref].pads:
                px, py = pad_abs(placement, parts, ref, pad)
                xs.append(px)
                ys.append(py)
        if len(xs) >= 2:
            total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total


def count_overlap_pairs(placement: dict, parts: dict) -> int:
    refs = sorted(placement)
    n = 0
    for i, a in enumerate(refs):
        da = _dims(parts[a], placement[a][2])
        for b in refs[i + 1:]:
            db = _dims(parts[b], placement[b][2])
            if _overlap_area(placement[a][:2], da, placement[b][:2], db) > 1e-9:
                n += 1
    return n


# ------------------------------------------------------------------ greedy
def _ring_offsets(r: int):
    out = []
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if max(abs(dx), abs(dy)) == r:
                out.append((dx, dy))
    out.sort(key=lambda o: (o[0] * o[0] + o[1] * o[1], o[0], o[1]))
    return out


def _find_slot(part, target_xy, placement, parts, board):
    w, h = part.w_mm, part.h_mm
    max_ring = int(max(board)) + 1
    for r in range(0, max_ring):
        for dx, dy in _ring_offsets(r):
            x = target_xy[0] + dx * GRID_MM
            y = target_xy[1] + dy * GRID_MM
            if _inside_board(x, y, w, h, board) and not _overlaps_any(x, y, w, h, part.ref, placement, parts):
                return (x, y)
    raise ValueError(
        f"PREPLACE_BOARD_TOO_SMALL: no feasible slot for {part.ref} "
        f"({w}x{h}mm) on board {board[0]}x{board[1]}mm")


def _edge_slots(board):
    W, H = board
    slots = []
    step = 2.0
    x = EDGE_MARGIN_MM
    while x <= W - EDGE_MARGIN_MM:
        slots.append((x, EDGE_MARGIN_MM, "top"))
        slots.append((x, H - EDGE_MARGIN_MM, "bottom"))
        x += step
    y = EDGE_MARGIN_MM
    while y <= H - EDGE_MARGIN_MM:
        slots.append((EDGE_MARGIN_MM, y, "left"))
        slots.append((W - EDGE_MARGIN_MM, y, "right"))
        y += step
    return slots


def greedy_initial(parts: dict, clusters: dict, anchor: str, board) -> dict:
    W, H = board
    placement = {anchor: (W / 2.0, H / 2.0, 0.0)}
    prio_rank = {"decap": 0, "crystal": 1, "signal": 2, "free": 3}
    inner = [r for r, c in clusters.items() if c["priority"] != "edge"]
    # R4: within each priority, largest footprint first (source-anchored ordering)
    inner.sort(key=lambda r: (prio_rank[clusters[r]["priority"]],
                              -(parts[r].w_mm * parts[r].h_mm), r))
    for ref in inner:
        c = clusters[ref]
        if c["target_ref"] and c["target_ref"] in placement and c["target_pad"] and \
                c["target_pad"] in parts[c["target_ref"]].pads:
            target = pad_abs(placement, parts, c["target_ref"], c["target_pad"])
        elif c["target_ref"] and c["target_ref"] in placement:
            target = placement[c["target_ref"]][:2]
        else:
            target = (W / 2.0, H / 2.0)
        placement[ref] = (*_find_slot(parts[ref], target, placement, parts, board), 0.0)
    edge = sorted(r for r, c in clusters.items() if c["priority"] == "edge")
    edge.sort(key=lambda r: (-(parts[r].w_mm * parts[r].h_mm), r))
    for ref in edge:
        part = parts[ref]
        ax, ay = placement[anchor][:2]
        placed = False
        for x, y, side in sorted(_edge_slots(board),
                                 key=lambda s: ((s[0] - ax) ** 2 + (s[1] - ay) ** 2, s[0], s[1])):
            w, h = part.w_mm, part.h_mm
            # pull the slot inward so the courtyard sits inside the outline
            if side == "top":
                y = EDGE_MARGIN_MM + h / 2
            elif side == "bottom":
                y = board[1] - EDGE_MARGIN_MM - h / 2
            elif side == "left":
                x = EDGE_MARGIN_MM + w / 2
            else:
                x = board[0] - EDGE_MARGIN_MM - w / 2
            if _inside_board(x, y, w, h, board) and not _overlaps_any(x, y, w, h, ref, placement, parts):
                placement[ref] = (x, y, 0.0)
                placed = True
                break
        if not placed:
            raise ValueError(
                f"PREPLACE_BOARD_TOO_SMALL: no edge slot for connector/mount {ref}")
    return placement


# ---------------------------------------------------------------------- SA
def _energy(placement, parts, clusters, nets, board, weights) -> float:
    e = compute_hpwl(placement, parts, nets)
    aff = 0.0
    for ref in sorted(clusters):
        c = clusters[ref]
        limit = AFFINITY_LIMIT_MM.get(c["priority"])
        if limit is None or not c["target_ref"] or c["target_ref"] not in placement:
            continue
        if c["target_pad"] and c["target_pad"] in parts[c["target_ref"]].pads:
            tx, ty = pad_abs(placement, parts, c["target_ref"], c["target_pad"])
        else:
            tx, ty = placement[c["target_ref"]][:2]
        d = math.hypot(placement[ref][0] - tx, placement[ref][1] - ty)
        aff += max(0.0, d - limit)
    ovl = 0.0
    refs = sorted(placement)
    for i, a in enumerate(refs):
        da = _dims(parts[a], placement[a][2])
        for b in refs[i + 1:]:
            db = _dims(parts[b], placement[b][2])
            ovl += _overlap_area(placement[a][:2], da, placement[b][:2], db)
    edge = 0.0
    for r in refs:
        x, y, rot = placement[r]
        w, h = _dims(parts[r], rot)
        edge += max(0.0, EDGE_MARGIN_MM - (x - w / 2)) + max(0.0, (x + w / 2) - (board[0] - EDGE_MARGIN_MM))
        edge += max(0.0, EDGE_MARGIN_MM - (y - h / 2)) + max(0.0, (y + h / 2) - (board[1] - EDGE_MARGIN_MM))
    return e + weights["w_aff"] * aff + weights["w_ovl"] * ovl + weights["w_edge"] * edge


def sa_refine(placement, parts, clusters, nets, board, anchor, seed, weights,
              iterations: int = SA_ITERATIONS):
    rng = random.Random(seed)
    movable = [r for r in sorted(placement)
               if r != anchor and clusters.get(r, {}).get("priority") != "edge"]
    if not movable:
        return dict(placement)
    by_kind: dict = {}
    for r in movable:
        by_kind.setdefault(parts[r].kind, []).append(r)
    cur = dict(placement)
    cur_e = _energy(cur, parts, clusters, nets, board, weights)
    best, best_e = dict(cur), cur_e
    T = SA_T0
    for _ in range(iterations):
        ref = rng.choice(movable)
        x, y, rot = cur[ref]
        kind_move = rng.random()
        prev = dict(cur)
        if kind_move < 0.6:
            dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            step = GRID_MM * rng.choice([1, 2, 4])
            nx = min(max(x + dx * step, EDGE_MARGIN_MM), board[0] - EDGE_MARGIN_MM)
            ny = min(max(y + dy * step, EDGE_MARGIN_MM), board[1] - EDGE_MARGIN_MM)
            cur[ref] = (nx, ny, rot)
        elif kind_move < 0.8:
            cur[ref] = (x, y, (rot + 90.0) % 360.0)
        else:
            peers = by_kind[parts[ref].kind]
            other = rng.choice(peers)
            if other != ref:
                cur[ref], cur[other] = (cur[other][0], cur[other][1], rot), \
                                       (x, y, cur[other][2])
        new_e = _energy(cur, parts, clusters, nets, board, weights)
        if new_e <= cur_e or rng.random() < math.exp(-(new_e - cur_e) / max(T, 1e-9)):
            cur_e = new_e
            if new_e < best_e:
                best, best_e = dict(cur), new_e
        else:
            cur = prev
        T *= SA_COOL
    return best


# ------------------------------------------------------------------ checks
def check_rules(placement, parts, clusters, die_shadow_margin_mm: float | None = None):
    r1 = RULES["R1"]
    r8 = RULES["R8"]
    margin = r8["value"] if die_shadow_margin_mm is None else die_shadow_margin_mm
    violations = []
    for ref in sorted(clusters):
        c = clusters[ref]
        if c["priority"] != "decap" or not c["target_ref"]:
            continue
        tref = c["target_ref"]
        if tref not in placement or ref not in placement:
            continue
        if c["target_pad"] and c["target_pad"] in parts[tref].pads:
            tx, ty = pad_abs(placement, parts, tref, c["target_pad"])
        else:
            tx, ty = placement[tref][:2]
        d = math.hypot(placement[ref][0] - tx, placement[ref][1] - ty)
        if d > r1["value"] + 1e-9:
            violations.append({
                "rule": "R1", "source": r1["source"], "refs": [ref, tref],
                "measured_mm": round(d, 3), "limit_mm": r1["value"],
                "note": f"decap {ref} is {d:.2f}mm from {tref} power pin "
                        f"{c['target_pad']} (limit {r1['value']}mm)"})
        farads = parse_cap_farads(parts[ref].value)
        if farads is not None and farads <= MIDFREQ_MAX_F + 1e-15:
            ax, ay, arot = placement[tref]
            aw, ah = _dims(parts[tref], arot)
            hx, hy = aw / 2 + margin, ah / 2 + margin
            cx, cy = placement[ref][:2]
            if not (ax - hx <= cx <= ax + hx and ay - hy <= cy <= ay + hy):
                over = max(abs(cx - ax) - hx, abs(cy - ay) - hy)
                violations.append({
                    "rule": "R8", "source": r8["source"], "refs": [ref, tref],
                    "measured_mm": round(over, 3), "limit_mm": margin,
                    "note": f"mid-freq decap {ref} sits outside {tref} die-shadow "
                            f"proxy (courtyard + {margin}mm)"})
    return violations


# --------------------------------------------------------------- top level
def preplace(parts: dict, nets: dict, board_mm, *, seed: int = 42,
             weights: dict | None = None, die_shadow_margin_mm: float | None = None,
             sa_iterations: int = SA_ITERATIONS) -> PreplaceResult:
    """Deterministic pre-placement. parts={ref:PartGeom}, nets={net:[(ref,pad),..]}."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"PREPLACE_INVALID_SEED: seed must be an int, got {seed!r}")
    if not board_mm or len(board_mm) != 2 or board_mm[0] <= 0 or board_mm[1] <= 0:
        raise ValueError(f"PREPLACE_BOARD_TOO_SMALL: invalid board_mm {board_mm!r}")
    board = (float(board_mm[0]), float(board_mm[1]))

    missing = sorted(p.ref for p in parts.values() if p.w_mm <= 0 or p.h_mm <= 0 or not p.pads)
    missing += sorted({ref for nodes in nets.values() for ref, _ in nodes} - set(parts))
    if missing:
        raise ValueError("PREPLACE_MISSING_GEOMETRY: no usable footprint geometry for "
                         "refs: " + ", ".join(missing))

    need = sum((p.w_mm + GUTTER_MM) * (p.h_mm + GUTTER_MM) for p in parts.values())
    if need > board[0] * board[1]:
        raise ValueError(f"PREPLACE_BOARD_TOO_SMALL: parts need ≥{need:.0f}mm², "
                         f"board offers {board[0] * board[1]:.0f}mm²")

    eff_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        eff_weights.update(weights)
    anchor = select_anchor(parts)
    clusters = build_clusters(parts, nets, anchor)
    placement = greedy_initial(parts, clusters, anchor, board)
    placement = sa_refine(placement, parts, clusters, nets, board, anchor,
                          seed, eff_weights, iterations=sa_iterations)
    violations = check_rules(placement, parts, clusters, die_shadow_margin_mm)
    return PreplaceResult(
        placement={r: tuple(placement[r]) for r in sorted(placement)},
        violations=violations,
        effective={"seed": seed, "weights": eff_weights,
                   "die_shadow_margin_mm": RULES["R8"]["value"]
                   if die_shadow_margin_mm is None else die_shadow_margin_mm,
                   "board_mm": list(board), "sa_iterations": sa_iterations,
                   "grid_mm": GRID_MM},
        anchor=anchor,
        clusters=clusters,
        hpwl_mm=round(compute_hpwl(placement, parts, nets), 3),
        overlap_pairs=count_overlap_pairs(placement, parts),
    )
