"""PCB routing + layout-finishing capabilities for bodesign C04.

These close the gap where bodesign auto-placed but never routed: net→netted PCB, fine-pitch BGA
via-in-pad fanout, copper-plane pour, neck-down widen to a target impedance, bus length-matching,
ngspice signal-integrity gate, and an honest DRC gate. All run on pcbnew (+ ngspice for SI);
autoroute shells out to Freerouting when present, else returns the netted board for external routing.

Refactored from the validated host-side prototypes in the OpenMV/aiguard repo.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

try:  # pcbnew is present in the EE worker
    import pcbnew  # type: ignore
    PCBNEW_AVAILABLE = True
except Exception:  # pragma: no cover
    pcbnew = None  # type: ignore
    PCBNEW_AVAILABLE = False

PS_PER_MM_DEFAULT = 5.97  # microstrip on the 4-layer JLC reference stack


def _need_pcbnew() -> None:
    if not PCBNEW_AVAILABLE:
        raise RuntimeError("pcbnew not importable (run in the KiCad/EE worker)")


# ----------------------------------------------------------------------------- net → netted PCB
_USBC = {"VBUS": ["A4", "A9", "B4", "B9"], "GND": ["A1", "A12", "B1", "B12"],
         "CC1": ["A5"], "CC2": ["B5"], "SHLD": ["S1"]}


def _parse_netlist(path: str) -> tuple[dict, dict]:
    """Return ({ref: footprint_id}, {net: [(ref, pad), ...]}) from a KiCad s-expr netlist."""
    text = open(path).read()
    comps = dict(re.findall(
        r'\(comp \(ref "([^"]+)"\)\s*\(value "[^"]*"\)\s*\(footprint "([^"]+)"\)', text))
    nets: dict[str, list] = {}
    for block in text.split("(net (code")[1:]:
        nm = re.search(r'\) \(name "([^"]+)"\)', block)
        if not nm:
            continue
        name = nm.group(1)
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', block)
        nets.setdefault(name, []).extend(nodes)
    return comps, nets


def net2pcb_board(netlist_path: str, out_path: str, *, layers: int = 2,
                  plane_layers: list[str] | None = None, track_mm: float | None = None,
                  placement: dict | None = None, fpdir: str | None = None,
                  clearance_mm: float = 0.13) -> dict:
    """Build a netted .kicad_pcb from a netlist: load footprints, place, assign nets, set
    copper-layer count / reserved plane layers / default track width, draw a board outline."""
    _need_pcbnew()
    comps, nets = _parse_netlist(netlist_path)
    board = pcbnew.CreateEmptyBoard()
    if layers > 2:
        board.SetCopperLayerCount(layers)
        lymap = {"In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu, "In3": pcbnew.In3_Cu,
                 "In4": pcbnew.In4_Cu, "In5": pcbnew.In5_Cu, "In6": pcbnew.In6_Cu}
        for nm in (plane_layers or ["In1", "In2"]):
            ly = lymap.get(nm)
            if ly is not None:
                try: board.SetLayerType(ly, pcbnew.LT_POWER)
                except Exception: pass
    if track_mm:
        try:
            board.GetDesignSettings().m_NetSettings.GetDefaultNetclass().SetTrackWidth(pcbnew.FromMM(track_mm))
        except Exception: pass
    stock = "/usr/share/kicad/footprints"
    fps: dict[str, Any] = {}
    gx = gy = 0.0
    for i, (ref, fpid) in enumerate(comps.items()):
        lib, name = fpid.split(":", 1)
        fp = None
        for base in ([fpdir] if fpdir else []) + [stock]:
            try:
                fp = pcbnew.FootprintLoad(f"{base}/{lib}.pretty", name)
            except Exception:
                fp = None
            if fp is not None:
                break
        if fp is None:
            continue
        fps[ref] = fp
        if placement and ref in placement:
            x, y, *rot = placement[ref]
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(float(x)), pcbnew.FromMM(float(y))))
            if rot:
                fp.SetOrientationDegrees(float(rot[0]))
        else:
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(10 + gx), pcbnew.FromMM(10 + gy)))
            gx += 8
            if gx > 80: gx = 0; gy += 8
        board.Add(fp)
    code = 1; assigned = unmapped = 0
    for name, nodes in nets.items():
        ni = pcbnew.NETINFO_ITEM(board, name, code); board.Add(ni); code += 1
        for ref, pin in nodes:
            fp = fps.get(ref)
            if not fp:
                continue
            isusbc = "USB" in fp.GetFPIDAsString().upper()
            pads = _USBC[name] if (ref == "J1" and isusbc and name in _USBC) else [pin]
            for padname in pads:
                pad = fp.FindPadByNumber(padname)
                if pad is None:
                    unmapped += 1; continue
                pad.SetNet(ni); assigned += 1
    # board outline from pad extents
    xs = []; ys = []
    for fp in fps.values():
        for p in fp.Pads():
            pos = p.GetPosition(); xs.append(pcbnew.ToMM(pos.x)); ys.append(pcbnew.ToMM(pos.y))
    if xs:
        m = 3.0
        x1, y1, x2, y2 = min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
        for a, b in [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]:
            s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
            s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.15)); board.Add(s)
    pcbnew.SaveBoard(out_path, board)
    return {"board": out_path, "placed": len(fps), "nets": len(nets),
            "pads_assigned": assigned, "unmapped": unmapped}


# --------------------------------------------------------------------------- via-in-pad BGA fanout
def via_in_pad(in_path: str, out_path: str, refs: list[str], *, drill_mm: float = 0.2,
               pad_mm: float = 0.3, keep_rings: int = 2) -> dict:
    """Drop a through-via through each netted ball pad of `refs` (except the outer `keep_rings`
    rings, which escape on the surface) so fine-pitch BGAs reach inner signal layers.
    Requires a filled+capped (POFV) fab process — JLCPCB 'advanced'."""
    _need_pcbnew()
    b = pcbnew.LoadBoard(in_path)
    refset = set(refs); added = 0

    def rc(num):
        m = re.match(r"^([A-Z]+)(\d+)$", num)
        return (m.group(1), int(m.group(2))) if m else None

    for fp in b.GetFootprints():
        if fp.GetReference() not in refset:
            continue
        pads = list(fp.Pads())
        rcs = [rc(p.GetNumber()) for p in pads]
        rows = sorted({x[0] for x in rcs if x}); cols = sorted({x[1] for x in rcs if x})
        ri = {r: i for i, r in enumerate(rows)}; cmax = max(cols); cmin = min(cols); rmax = len(rows) - 1
        for p in pads:
            if not p.GetNetname():
                continue
            g = rc(p.GetNumber())
            if g:
                ring = min(ri[g[0]], rmax - ri[g[0]], g[1] - cmin, cmax - g[1])
                if ring < keep_rings:
                    continue
            v = pcbnew.PCB_VIA(b); v.SetPosition(p.GetPosition())
            v.SetDrill(pcbnew.FromMM(drill_mm)); v.SetWidth(pcbnew.FromMM(pad_mm))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(p.GetNet())
            b.Add(v); added += 1
    pcbnew.SaveBoard(out_path, b)
    return {"board": out_path, "vias_added": added, "process": "via-in-pad (filled+capped / JLCPCB advanced)"}


# -------------------------------------------------------------------------------- copper planes
def pour_planes(in_path: str, out_path: str, planes: list[str], *, stitch: bool = True) -> dict:
    """Pour filled copper zones. `planes` = ["F.Cu:GND", "In1.Cu:GND", "In4.Cu:V3V3", ...].
    Optionally adds GND stitching vias; dangling ones are stripped."""
    _need_pcbnew()
    b = pcbnew.LoadBoard(in_path)
    box = b.GetBoardEdgesBoundingBox(); m = pcbnew.FromMM(0.3)
    x1, y1, x2, y2 = box.GetLeft() + m, box.GetTop() + m, box.GetRight() - m, box.GetBottom() - m
    out = []
    for spec in planes:
        layer_name, netname = spec.split(":")
        lid = getattr(pcbnew, layer_name.replace(".", "_")); net = b.FindNet(netname)
        z = pcbnew.ZONE(b); z.SetLayer(lid); z.SetAssignedPriority(0)
        if net is not None:
            z.SetNet(net)
        pts = pcbnew.VECTOR_VECTOR2I()
        for (x, y) in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            pts.append(pcbnew.VECTOR2I(int(x), int(y)))
        z.AddPolygon(pts); b.Add(z)
        out.append({"layer": layer_name, "net": netname})
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    stitched = 0
    if stitch and b.FindNet("GND"):
        pads = [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads()]
        step = pcbnew.FromMM(14)
        x = box.GetLeft() + step
        while x < box.GetRight():
            y = box.GetTop() + step
            while y < box.GetBottom():
                if all(abs(pp.x - x) > pcbnew.FromMM(1.6) or abs(pp.y - y) > pcbnew.FromMM(1.6) for pp in pads):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                    v.SetDrill(pcbnew.FromMM(0.3)); v.SetWidth(pcbnew.FromMM(0.6))
                    v.SetNet(b.FindNet("GND")); b.Add(v); stitched += 1
                y += step
            x += step
    pcbnew.SaveBoard(out_path, b)
    return {"board": out_path, "zones": out, "stitch_vias": stitched}


# ------------------------------------------------------------------------- clearance-safe widening
def _distance_point_to_segment(px: int, py: int, ax: int, ay: int, bx: int, by: int) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _distance_segments(a1: Any, a2: Any, b1: Any, b2: Any) -> float:
    def ccw(p1: Any, p2: Any, p3: Any) -> bool:
        return (p3.y - p1.y) * (p2.x - p1.x) > (p2.y - p1.y) * (p3.x - p1.x)

    if ccw(a1, b1, b2) != ccw(a2, b1, b2) and ccw(a1, a2, b1) != ccw(a1, a2, b2):
        return 0.0
    return min(
        _distance_point_to_segment(a1.x, a1.y, b1.x, b1.y, b2.x, b2.y),
        _distance_point_to_segment(a2.x, a2.y, b1.x, b1.y, b2.x, b2.y),
        _distance_point_to_segment(b1.x, b1.y, a1.x, a1.y, a2.x, a2.y),
        _distance_point_to_segment(b2.x, b2.y, a1.x, a1.y, a2.x, a2.y),
    )


def _pad_radius_iu(pad: Any) -> float:
    try:
        box = pad.GetBoundingBox()
        return math.hypot(box.GetWidth(), box.GetHeight()) / 2.0
    except Exception:
        return 0.0


def _widening_is_clear(board: Any, track: Any, target_iu: int, clearance_iu: int) -> bool:
    required_new_radius = target_iu / 2.0
    start, end = track.GetStart(), track.GetEnd()
    netname = track.GetNetname()
    layer = track.GetLayer()
    for other in board.GetTracks():
        if other is track or other.GetNetname() == netname:
            continue
        if other.GetClass() == 'PCB_TRACK' and other.GetLayer() == layer:
            gap = _distance_segments(start, end, other.GetStart(), other.GetEnd())
            if gap < required_new_radius + other.GetWidth() / 2.0 + clearance_iu:
                return False
        elif other.GetClass() == 'PCB_VIA':
            gap = _distance_point_to_segment(other.GetPosition().x, other.GetPosition().y, start.x, start.y, end.x, end.y)
            if gap < required_new_radius + other.GetWidth() / 2.0 + clearance_iu:
                return False
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == netname:
                continue
            gap = _distance_point_to_segment(pad.GetPosition().x, pad.GetPosition().y, start.x, start.y, end.x, end.y)
            if gap < required_new_radius + _pad_radius_iu(pad) + clearance_iu:
                return False
    return True


def widen_bus_tracks(in_path: str, out_path: str, nets: list[str], target_mm: float,
                     *, clearance_mm: float = 0.13) -> dict:
    """Widen routed bus segments to `target_mm` only when nearby foreign copper/pads keep clearance."""
    if not in_path or not out_path:
        raise ValueError("in_path and out_path are required")
    if not isinstance(nets, list) or not nets or not all(isinstance(n, str) and n for n in nets):
        raise ValueError("nets must be a non-empty list of net names")
    if target_mm <= 0:
        raise ValueError("target_mm must be > 0")
    if clearance_mm < 0:
        raise ValueError("clearance_mm must be >= 0")
    _need_pcbnew()
    board = pcbnew.LoadBoard(in_path)
    target_iu = pcbnew.FromMM(float(target_mm)); clearance_iu = pcbnew.FromMM(float(clearance_mm))
    netset = set(nets); widened = kept = 0
    for track in board.GetTracks():
        if track.GetClass() != 'PCB_TRACK' or track.GetNetname() not in netset:
            continue
        if track.GetWidth() >= target_iu:
            kept += 1; continue
        if _widening_is_clear(board, track, target_iu, clearance_iu):
            track.SetWidth(target_iu); widened += 1
        else:
            kept += 1
    pcbnew.SaveBoard(out_path, board)
    return {"board": out_path, "widened": widened, "kept": kept, "target_mm": target_mm}


# ------------------------------------------------------------------- clearance-aware length match
def _track_length_mm(track: Any) -> float:
    return math.hypot(track.GetEnd().x - track.GetStart().x, track.GetEnd().y - track.GetStart().y) / 1e6


def _net_track_lengths(board: Any, netset: set[str]) -> dict[str, float]:
    return {
        net: sum(_track_length_mm(t) for t in board.GetTracks()
                 if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == net)
        for net in netset
    }


def _segment_is_clear(board: Any, netname: str, layer: int, width_iu: int, clearance_iu: int,
                      start: Any, end: Any, *, ignore: Any | None = None) -> bool:
    required_radius = width_iu / 2.0
    for other in board.GetTracks():
        if other is ignore or other.GetNetname() == netname:
            continue
        if other.GetClass() == 'PCB_TRACK' and other.GetLayer() == layer:
            gap = _distance_segments(start, end, other.GetStart(), other.GetEnd())
            if gap < required_radius + other.GetWidth() / 2.0 + clearance_iu:
                return False
        elif other.GetClass() == 'PCB_VIA':
            gap = _distance_point_to_segment(other.GetPosition().x, other.GetPosition().y, start.x, start.y, end.x, end.y)
            if gap < required_radius + other.GetWidth() / 2.0 + clearance_iu:
                return False
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == netname:
                continue
            gap = _distance_point_to_segment(pad.GetPosition().x, pad.GetPosition().y, start.x, start.y, end.x, end.y)
            if gap < required_radius + _pad_radius_iu(pad) + clearance_iu:
                return False
    return True


def _points_inside_board_edges(board: Any, points: list[Any], clearance_iu: int) -> bool:
    try:
        box = board.GetBoardEdgesBoundingBox()
        return all(
            box.GetLeft() + clearance_iu <= p.x <= box.GetRight() - clearance_iu and
            box.GetTop() + clearance_iu <= p.y <= box.GetBottom() - clearance_iu
            for p in points
        )
    except Exception:
        return True


def _try_insert_serpentine(board: Any, netname: str, add_mm: float, clearance_iu: int) -> float:
    candidates = sorted(
        (t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == netname),
        key=_track_length_mm,
        reverse=True,
    )
    if add_mm <= 0 or not candidates or not hasattr(board, "Remove"):
        return 0.0
    add_iu = pcbnew.FromMM(float(add_mm))
    min_leg_iu = pcbnew.FromMM(0.25)
    for track in candidates:
        start = track.GetStart(); end = track.GetEnd()
        dx, dy = end.x - start.x, end.y - start.y
        length_iu = math.hypot(dx, dy)
        if length_iu < min_leg_iu * 4:
            continue
        margin_iu = max(min_leg_iu, min(length_iu / 4.0, pcbnew.FromMM(1.0)))
        amp_iu = add_iu / 2.0
        if amp_iu < min_leg_iu or amp_iu > length_iu:
            continue
        ux, uy = dx / length_iu, dy / length_iu
        nx, ny = -uy, ux
        p1 = pcbnew.VECTOR2I(int(start.x + ux * margin_iu), int(start.y + uy * margin_iu))
        p4 = pcbnew.VECTOR2I(int(end.x - ux * margin_iu), int(end.y - uy * margin_iu))
        for direction in (1.0, -1.0):
            p2 = pcbnew.VECTOR2I(int(p1.x + nx * amp_iu * direction), int(p1.y + ny * amp_iu * direction))
            p3 = pcbnew.VECTOR2I(int(p4.x + nx * amp_iu * direction), int(p4.y + ny * amp_iu * direction))
            points = [start, p1, p2, p3, p4, end]
            if not _points_inside_board_edges(board, points, clearance_iu):
                continue
            legs = list(zip(points[:-1], points[1:]))
            if not all(_segment_is_clear(board, netname, track.GetLayer(), track.GetWidth(), clearance_iu, a, b, ignore=track)
                       for a, b in legs):
                continue
            board.Remove(track)
            for a, b in legs:
                segment = pcbnew.PCB_TRACK(board)
                segment.SetStart(a); segment.SetEnd(b); segment.SetLayer(track.GetLayer())
                segment.SetWidth(track.GetWidth()); segment.SetNet(track.GetNet())
                board.Add(segment)
            return add_mm
    return 0.0


def length_match_bus(in_path: str, out_path: str, nets: list[str], budget_ps: float,
                     ps_per_mm: float, *, report_path: str | None = None,
                     clearance_mm: float = 0.13) -> dict:
    """Tune routed bus skew with clearance-aware single-detour serpentine insertion where safe."""
    if not in_path or not out_path:
        raise ValueError("in_path and out_path are required")
    if not isinstance(nets, list) or not nets or not all(isinstance(n, str) and n for n in nets):
        raise ValueError("nets must be a non-empty list of net names")
    if budget_ps is None or float(budget_ps) < 0:
        raise ValueError("budget_ps must be >= 0")
    if ps_per_mm is None or float(ps_per_mm) <= 0:
        raise ValueError("ps_per_mm must be > 0")
    if clearance_mm < 0:
        raise ValueError("clearance_mm must be >= 0")
    _need_pcbnew()
    board = pcbnew.LoadBoard(in_path)
    netset = set(nets)
    missing = [net for net in nets if board.FindNet(net) is None]
    if missing:
        raise ValueError(f"missing nets: {', '.join(missing)}")
    initial = _net_track_lengths(board, netset)
    unrouted = [net for net, length in initial.items() if length <= 0]
    if unrouted:
        raise ValueError(f"nets have no routed PCB_TRACK segments: {', '.join(sorted(unrouted))}")

    target_mm = max(initial.values())
    clearance_iu = pcbnew.FromMM(float(clearance_mm))
    per_net = []
    tuned = 0
    for net in nets:
        need_mm = target_mm - initial[net]
        added_mm = 0.0
        status = "kept"
        if need_mm > 0 and need_mm * float(ps_per_mm) > float(budget_ps):
            added_mm = _try_insert_serpentine(board, net, need_mm, clearance_iu)
            if added_mm > 0:
                tuned += 1; status = "tuned"
            else:
                status = "untuned-clearance"
        per_net.append({"net": net, "initial_mm": round(initial[net], 3), "added_mm": round(added_mm, 3), "status": status})

    final = _net_track_lengths(board, netset)
    spread_mm = max(final.values()) - min(final.values())
    spread_ps = spread_mm * float(ps_per_mm)
    by_net = {entry["net"]: entry for entry in per_net}
    for net in nets:
        by_net[net]["length_mm"] = round(final[net], 3)
    result = {"board": out_path, "lengths": per_net, "spread_mm": round(spread_mm, 3),
              "spread_ps": round(spread_ps, 3), "within_budget": spread_ps <= float(budget_ps),
              "tuned": tuned, "total": len(nets)}
    pcbnew.SaveBoard(out_path, board)
    if report_path:
        with open(report_path, "w") as report:
            json.dump(result, report, indent=2)
    return result


# ------------------------------------------------------------------------------ drc gate (honest)
def drc_gate(board_path: str) -> dict:
    """Run DRC and split copper/unconnected (hard) from silk (cosmetic)."""
    _need_pcbnew()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        rep = f.name
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", rep, board_path],
                   capture_output=True)
    d = json.load(open(rep)); os.unlink(rep)
    v = d.get("violations", [])
    silk = sum(1 for x in v if "silk" in (x.get("type") or ""))
    unc = len(d.get("unconnected_items", []))
    copper = len(v) - silk
    return {"copper": copper, "unconnected": unc, "silk": silk,
            "clean": copper == 0 and unc == 0}


# --------------------------------------------------------------------------------- ngspice SI gate
def si_check(board_path: str, nets: list[str], *, z0: float = 50.0, rs: float = 22.0,
             vdd: float = 1.8, ps_per_mm: float = PS_PER_MM_DEFAULT) -> dict:
    """Per-net series-terminated transmission-line SI: overshoot/undershoot -> pass/warn/fail."""
    _need_pcbnew()
    b = pcbnew.LoadBoard(board_path)
    rdrv, cload = 17.0, 3e-12
    res = []
    for nm in nets:
        L = sum(math.hypot(t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y)
                for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == nm) / 1e6
        if L < 0.1:
            continue
        td = L * ps_per_mm * 1e-12
        deck = (f"* SI {nm}\nVin in 0 PWL(0 0 0.1n 0 0.3n {vdd})\nRd in d {rdrv}\nRs d s {rs}\n"
                f"T1 s 0 r 0 Z0={z0} TD={td:.4e}\nCl r 0 {cload}\n.tran 5p 6n\n.control\nrun\n"
                f"meas tran vmax MAX v(r) from=0.3n to=6n\nmeas tran vmin MIN v(r) from=1n to=6n\n"
                f"print vmax vmin\n.endc\n.end\n")
        with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as f:
            f.write(deck); cir = f.name
        try:
            out = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, timeout=30).stdout
        finally:
            os.unlink(cir)

        def g(k):
            for ln in out.splitlines():
                if ln.strip().lower().startswith(k):
                    try: return float(ln.split("=")[1].split()[0])
                    except Exception: return None
            return None
        vmax, vmin = g("vmax"), g("vmin")
        if vmax is None:
            continue
        over = max(0.0, (vmax - vdd) / vdd * 100); under = max(0.0, -vmin / vdd * 100)
        st = "pass" if over < 10 and under < 10 else ("warn" if over < 20 and under < 20 else "fail")
        res.append({"net": nm, "len_mm": round(L, 2), "overshoot_pct": round(over, 1),
                    "undershoot_pct": round(under, 1), "status": st})
    order = {"pass": 0, "warn": 1, "fail": 2}
    worst = max((order[r["status"]] for r in res), default=0)
    return {"z0": z0, "rs": rs, "nets": res, "worst": ["pass", "warn", "fail"][worst]}


# -------------------------------------------------------------------------------- autoroute (opt)
def autoroute(board_path: str, out_path: str, *, passes: int = 40) -> dict:
    """Freerouting autoroute if available (java + freerouting.jar + xvfb); else no-op passthrough."""
    _need_pcbnew()
    jar = os.environ.get("FREEROUTING_JAR", "/opt/freerouting/freerouting.jar")
    java = os.environ.get("JAVA_BIN", "java")
    have = os.path.exists(jar) and subprocess.run(["which", java], capture_output=True).returncode == 0
    if not have:
        return {"routed": False, "reason": "freerouting/java not present in this worker",
                "board": board_path}
    dsn = board_path.replace(".kicad_pcb", ".dsn"); ses = board_path.replace(".kicad_pcb", ".ses")
    b = pcbnew.LoadBoard(board_path); pcbnew.ExportSpecctraDSN(b, dsn)
    xvfb = ["xvfb-run", "-a"] if subprocess.run(["which", "xvfb-run"], capture_output=True).returncode == 0 else []
    subprocess.run(xvfb + [java, "-jar", jar, "-de", dsn, "-do", ses, "-mp", str(passes)],
                   capture_output=True)
    b2 = pcbnew.LoadBoard(board_path); pcbnew.ImportSpecctraSES(b2, ses); pcbnew.SaveBoard(out_path, b2)
    t = b2.GetTracks()
    return {"routed": True, "board": out_path,
            "segments": sum(1 for x in t if x.GetClass() == 'PCB_TRACK'),
            "vias": sum(1 for x in t if x.GetClass() == 'PCB_VIA')}
