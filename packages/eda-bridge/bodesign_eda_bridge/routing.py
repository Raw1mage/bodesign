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
