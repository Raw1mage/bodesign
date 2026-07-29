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


def _ensure_parent_dir(path: str) -> None:
    """T7 fix: create the parent directory of an output path so a write never lands in a
    non-existent directory (which pcbnew/open silently “succeed” into a doomed container layer)."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


# ----------------------------------------------------------------------------- net → netted PCB
_USBC = {"VBUS": ["A4", "A9", "B4", "B9"], "GND": ["A1", "A12", "B1", "B12"],
         "CC1": ["A5"], "CC2": ["B5"], "SHLD": ["S1"]}


def resolve_connector_pads(ref: str, net: str, pin: str, *, connectors: dict,
                           usb_refs: set) -> tuple[list[str], bool]:
    """H1: decide the physical pads a (ref, net) node expands to, without any refdes hardcoding.

    Returns (pads, expanded). An explicit ``connectors[ref]`` map wins; otherwise a USB-C
    footprint (ref in ``usb_refs``, detected by FPID, not by being named J1) uses the built-in
    USB-C table. If no map matches the net, the node keeps its single ``pin`` and expanded=False.
    Pure + pcbnew-free so the silent-failure fix is testable on a bare host."""
    pinmap = connectors.get(ref) or (_USBC if ref in usb_refs else None)
    if pinmap and net in pinmap:
        return list(pinmap[net]), True
    return [pin], False


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


def _extract_part_geoms(fps: dict) -> tuple[dict, list[str]]:
    """Build pure PartGeom records from loaded pcbnew footprints (deterministic strategy).
    Returns (parts, missing) — refs whose bbox/pads are unusable go to `missing`."""
    from .preplace import PartGeom
    parts: dict = {}
    missing: list[str] = []
    for ref, fp in fps.items():
        try:
            box = fp.GetBoundingBox()
            w = pcbnew.ToMM(box.GetWidth())
            h = pcbnew.ToMM(box.GetHeight())
            origin = fp.GetPosition()
            pads = {}
            for p in fp.Pads():
                pos = p.GetPosition()
                pads[p.GetNumber()] = (pcbnew.ToMM(pos.x - origin.x),
                                       pcbnew.ToMM(pos.y - origin.y))
            value = fp.GetValue() or ""
        except Exception:
            missing.append(ref)
            continue
        if w <= 0 or h <= 0 or not pads:
            missing.append(ref)
            continue
        parts[ref] = PartGeom(ref=ref, w_mm=w, h_mm=h, pads=pads, value=value)
    return parts, missing


def net2pcb_board(netlist_path: str, out_path: str, *, layers: int = 2,
                  plane_layers: list[str] | None = None, track_mm: float | None = None,
                  placement: dict | None = None, fpdir: str | None = None,
                  fp_dirs: list[str] | None = None,
                  clearance_mm: float = 0.13, connectors: dict | None = None,
                  strategy: str = "grid", seed: int = 42,
                  board_mm: tuple[float, float] | list | None = None) -> dict:
    """Build a netted .kicad_pcb from a netlist: load footprints, place, assign nets, set
    copper-layer count / reserved plane layers / default track width, draw a board outline.

    Connector pin expansion (one logical symbol pin -> several physical pads, e.g. USB-C
    VBUS -> A4/A9/B4/B9) is caller-overridable and reported, never silently refdes-gated:
    pass ``connectors = {refdes: {net_name: [pads]}}`` to map an arbitrary connector; when
    omitted, any USB-C footprint (by FPID, on ANY refdes — not just J1) uses the built-in
    USB-C table. The result reports ``applied_pinmaps`` and ``unmapped_connectors`` so a
    USB-C/declared connector that got no expansion is surfaced, not lost.

    Placement strategy (G3): ``strategy="grid"`` keeps the historical 8mm naive grid
    (baseline, regression-frozen); ``strategy="deterministic"`` runs the pure-python
    electrically-aware pre-placement (anchor + affinity clustering + greedy + fixed-seed
    SA + R1/R8 anchored checks) and requires an explicit ``board_mm`` — missing geometry
    or board size FAILS FAST (no silent fallback to grid). An explicit ``placement`` map
    always wins over either strategy for the refs it names."""
    _need_pcbnew()
    if strategy not in ("grid", "deterministic"):
        raise ValueError(f"PREPLACE_UNKNOWN_STRATEGY: {strategy!r} (grid|deterministic)")
    comps, nets = _parse_netlist(netlist_path)
    board = pcbnew.CreateEmptyBoard()
    # BR_20260729 §D: plane-layer specs are NORMALISED and every one of them is
    # accounted for. The old code looked the raw string up in a bare-name map and
    # skipped any miss (`if ly is not None`) with no record, then swallowed real
    # SetLayerType failures in `except Exception: pass`. A caller passing the
    # natural KiCad spelling "In1.Cu:GND" therefore got ok:true with NO power
    # plane built at all — a 4-layer board with two idle copper layers, while
    # `layers` and `track_mm` from the SAME call did take effect. Downstream
    # (pour_planes / autoroute / drc_gate / si_check) cannot detect it, so the
    # board reaches fab with its return-path + Z0 assumptions silently void.
    plane_layers_applied: list[dict] = []
    if layers > 2:
        board.SetCopperLayerCount(layers)
        lymap = {"In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu, "In3": pcbnew.In3_Cu,
                 "In4": pcbnew.In4_Cu, "In5": pcbnew.In5_Cu, "In6": pcbnew.In6_Cu}
        unknown_planes: list[str] = []
        for nm in (plane_layers or ["In1", "In2"]):
            spec = str(nm).strip()
            # Accept "In1", "In1.Cu" and "In1.Cu:GND" (layer[.Cu][:NET]); the net
            # half is intent for pour_planes and is echoed back, not discarded.
            head, _, net = spec.partition(":")
            key = head.split(".", 1)[0].strip()
            ly = lymap.get(key)
            if ly is None:
                unknown_planes.append(spec)
                continue
            board.SetLayerType(ly, pcbnew.LT_POWER)
            plane_layers_applied.append(
                {"spec": spec, "layer": key, "net": net.strip() or None, "type": "LT_POWER"})
        if unknown_planes:
            raise ValueError(
                f"PLANE_LAYER_UNKNOWN: {unknown_planes} — unrecognised plane-layer spec(s). "
                f"Accepted forms: 'In1', 'In1.Cu', 'In1.Cu:GND' (layer must be one of "
                f"{sorted(lymap)}). Refusing to build a board whose requested power "
                f"planes were not created.")
    elif plane_layers:
        raise ValueError(
            f"PLANE_LAYER_UNKNOWN: plane_layers={list(plane_layers)} requested but "
            f"layers={layers} has no inner copper layers to reserve (need layers>2).")
    if track_mm:
        board.GetDesignSettings().m_NetSettings.GetDefaultNetclass().SetTrackWidth(pcbnew.FromMM(track_mm))
    stock = "/usr/share/kicad/footprints"
    # BR_20260729 §B: footprint search dirs are a MERGE (project libs + stock),
    # not mutually exclusive. Legacy single `fpdir` is folded in for back-compat;
    # `fp_dirs` (plural) lets a caller supply project .pretty dirs alongside stock.
    fp_search: list[str] = []
    for _d in ([fpdir] if fpdir else []) + list(fp_dirs or []) + [stock]:
        if _d and _d not in fp_search:
            fp_search.append(_d)
    fps: dict[str, Any] = {}
    dropped: list[dict] = []
    gx = gy = 0.0
    for i, (ref, fpid) in enumerate(comps.items()):
        lib, name = fpid.split(":", 1)
        fp = None
        for base in fp_search:
            try:
                fp = pcbnew.FootprintLoad(f"{base}/{lib}.pretty", name)
            except Exception:
                fp = None
            if fp is not None:
                break
        if fp is None:
            # BR_20260729 §B: a footprint that resolves in NO search dir must NOT be
            # silently skipped (that silently drops whole components — the 8-active-IC
            # disappearance with unmapped:0). Record it; grid mode now surfaces
            # dropped_components + ok:false, deterministic still fails fast.
            dropped.append({"ref": ref, "fpid": fpid, "reason": "footprint_lib_unresolved"})
            if strategy == "deterministic":
                raise ValueError(
                    f"PREPLACE_MISSING_GEOMETRY: footprint {fpid!r} for {ref} not found "
                    f"in {fp_search} — deterministic strategy does not skip parts")
            continue
        fps[ref] = fp
        fp.SetReference(ref)
        if placement and ref in placement:
            x, y, *rot = placement[ref]
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(float(x)), pcbnew.FromMM(float(y))))
            if rot:
                fp.SetOrientationDegrees(float(rot[0]))
        elif strategy == "grid":
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(10 + gx), pcbnew.FromMM(10 + gy)))
            gx += 8
            if gx > 80: gx = 0; gy += 8
        board.Add(fp)
    preplace_out: dict = {}
    if strategy == "deterministic":
        from .preplace import preplace
        if not board_mm:
            raise ValueError("PREPLACE_BOARD_TOO_SMALL: strategy=deterministic requires "
                             "an explicit board_mm=(width, height); it is not derivable "
                             "before placement")
        parts, missing = _extract_part_geoms(fps)
        if missing:
            raise ValueError("PREPLACE_MISSING_GEOMETRY: no usable bbox/pads for refs: "
                             + ", ".join(sorted(missing)))
        pin_nets = {net: [(r, p) for r, p in nodes if r in parts]
                    for net, nodes in nets.items()}
        # F4: explicit caller placement enters preplace as PINNED (frozen but
        # obstacle/metric-participating), so reported hpwl/overlaps/R1/R8 describe
        # the true final board instead of a phantom solver-only layout.
        pinned = {r: tuple(placement[r]) for r in placement} if placement else None
        res = preplace(parts, pin_nets, board_mm, seed=seed, pinned=pinned)
        for ref, (x, y, rot) in res.placement.items():
            fp = fps[ref]
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(float(x)), pcbnew.FromMM(float(y))))
            fp.SetOrientationDegrees(float(rot))
        # BR_20260708 placement quality: report courtyard utilization + the
        # concrete overlapping pairs so a route-time preflight (and the owner
        # review) can see the floorplan quality, not just a bare board file.
        from .preplace import compute_utilization, overlap_pair_details
        util = compute_utilization(res.placement, parts, board_mm)
        overlaps = overlap_pair_details(res.placement, parts)
        preplace_out = {"placement_violations": res.violations, "anchor": res.anchor,
                        "hpwl_mm": res.hpwl_mm, "overlap_pairs": res.overlap_pairs,
                        "overlap_details": overlaps, "utilization": util,
                        "effective": res.effective}
    # H1: per-connector effective pin map — explicit caller map, else built-in USB-C
    # table for any USB-C footprint (detected by FPID on ANY refdes). Tracked + reported.
    connectors = connectors or {}
    usb_refs = {ref for ref, fp in fps.items() if "USB" in fp.GetFPIDAsString().upper()}
    applied_pinmaps: set[str] = set()
    code = 1; assigned = unmapped = 0
    for name, nodes in nets.items():
        ni = pcbnew.NETINFO_ITEM(board, name, code); board.Add(ni); code += 1
        for ref, pin in nodes:
            fp = fps.get(ref)
            if not fp:
                continue
            pads, expanded = resolve_connector_pads(ref, name, pin, connectors=connectors,
                                                     usb_refs=usb_refs)
            if expanded:
                applied_pinmaps.add(ref)
            for padname in pads:
                pad = fp.FindPadByNumber(padname)
                if pad is None:
                    unmapped += 1; continue
                pad.SetNet(ni); assigned += 1
    # Connectors that look like they need expansion (USB-C footprint or an explicit caller
    # entry) but matched no net name -> reported, never a silent no-op.
    unmapped_connectors = sorted((usb_refs | set(connectors)) - applied_pinmaps)
    # Board outline: an explicit board_mm is the single source of truth for the
    # Edge.Cuts rectangle (0,0)-(W,H) — it must match the preplace R_edge boundary
    # exactly, on ANY strategy (not just deterministic). Only when board_mm is
    # absent do we fall back to a pad-extent + 3mm auto-frame.
    outline_source = None
    if board_mm:
        w, h = float(board_mm[0]), float(board_mm[1])
        corners = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
        for a, b in [(corners[0], corners[1]), (corners[1], corners[2]),
                     (corners[2], corners[3]), (corners[3], corners[0])]:
            s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
            s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.15)); board.Add(s)
        outline_source = "board_mm"
    else:
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
            outline_source = "pad_extent"
    _ensure_parent_dir(out_path)
    pcbnew.SaveBoard(out_path, board)
    # BR_20260729 §B: ok=False when any netlist component was dropped for an
    # unresolved footprint lib — a partial board that silently lost active ICs
    # must NOT read as success. expected_components vs placed makes the gap loud;
    # dropped_components carries the evidence (ref+fpid) so the caller supplies
    # fp_dirs and re-runs rather than routing a board missing its MCU.
    expected = len(comps)
    out = {"ok": not dropped, "board": out_path, "placed": len(fps),
           "expected_components": expected, "nets": len(nets),
           "pads_assigned": assigned, "unmapped": unmapped,
           "dropped_components": dropped,
           "plane_layers_applied": plane_layers_applied,
           "applied_pinmaps": sorted(applied_pinmaps),
           "unmapped_connectors": unmapped_connectors, "strategy": strategy,
           "outline_source": outline_source}
    if dropped:
        out["reason"] = (
            f"footprint_lib_unresolved: {len(dropped)} of {expected} components dropped "
            f"(missing project footprint dirs) — pass fp_dirs=[...] with the project "
            f".pretty libraries so these parts are placed, not silently skipped")
    out.update(preplace_out)
    return out


# --------------------------------------------------------------- placement preflight (pre-route gate)
def placement_preflight(board_path: str, *, min_utilization: float = 0.40,
                        board_mm: tuple[float, float] | list | None = None,
                        courtyard_margin_mm: float = 0.0) -> dict:
    """Read a placed .kicad_pcb and gate its floorplan BEFORE routing (BR_20260708).

    Two fail-fast conditions, both from real footprint courtyards (no guessing):
      1. courtyard overlap  — any two footprints whose bounding boxes intersect
         (optionally grown by ``courtyard_margin_mm``) are an overlap; route would
         inherit a wall of clearance DRC. ``overlaps`` lists the offending pairs.
      2. sheet under-fill    — total courtyard area / usable board area below
         ``min_utilization`` means everything is crammed in a strip (the 20%%
         center-strip symptom). ``utilization`` reports the ratio.

    ``passed`` is True only when there are zero overlaps AND utilization meets the
    floor. This never mutates the board and never routes; it is a gate the caller
    checks and, on failure, re-places (strategy="deterministic") rather than
    routing into a doomed floorplan. Board size is read from Edge.Cuts unless an
    explicit ``board_mm`` overrides it.
    """
    _need_pcbnew()
    b = pcbnew.LoadBoard(board_path)
    # BR_20260729 §C: measure REAL courtyards via the API this pcbnew actually has.
    # The old code called fp.GetCourtyardBoundingBox() — which does NOT exist on
    # pcbnew 9.x — inside a bare `except Exception:` that silently fell back to
    # fp.GetBoundingBox(), whose box INCLUDES F.SilkS/F.Fab text. Every footprint
    # took the fallback, so every verdict was computed from silkscreen text boxes:
    # 92-part board reported 135 overlaps / 11151mm² parts area / utilization 1.27
    # (>100% = physically impossible) when the true courtyards give 6 / 1009mm² /
    # ~0.115. Two 0402s 8mm apart were "overlapping 27.8mm²" — their text frames.
    #
    # Order: real courtyard polygon (F_CrtYd, then B_CrtYd for bottom parts) →
    # pad/edge bbox EXCLUDING text. The degraded basis is REPORTED, never silent:
    # `basis` says which rule produced the verdict and `courtyard_missing` names
    # the parts that had no courtyard layer. An AttributeError here means the
    # pcbnew API changed under us (a deployment fact, not a per-part variation)
    # and is raised loudly instead of being swallowed into a different metric.
    boxes: dict[str, tuple[float, float, float, float]] = {}
    courtyard_missing: list[str] = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        bb = None
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            poly = fp.GetCourtyard(layer)
            if poly.OutlineCount() > 0:
                cand = poly.BBox()
                if cand.GetWidth() > 0 and cand.GetHeight() > 0:
                    bb = cand
                    break
        if bb is None:
            # No courtyard on either layer for THIS part (a legitimate per-part
            # variation, unlike a missing API). Degrade to the geometry bbox with
            # text EXCLUDED, and record the part so the caller sees the basis.
            courtyard_missing.append(ref)
            bb = fp.GetBoundingBox(False, False)
        x1 = pcbnew.ToMM(bb.GetLeft()); y1 = pcbnew.ToMM(bb.GetTop())
        x2 = pcbnew.ToMM(bb.GetRight()); y2 = pcbnew.ToMM(bb.GetBottom())
        boxes[ref] = (x1, y1, x2, y2)
    basis = "courtyard" if not courtyard_missing else (
        "bbox_no_text" if len(courtyard_missing) == len(boxes) else "mixed")
    m = float(courtyard_margin_mm)
    refs = sorted(boxes)
    overlaps: list[dict] = []
    for i, a in enumerate(refs):
        ax1, ay1, ax2, ay2 = boxes[a]
        for c in refs[i + 1:]:
            cx1, cy1, cx2, cy2 = boxes[c]
            ox = min(ax2 + m, cx2 + m) - max(ax1 - m, cx1 - m)
            oy = min(ay2 + m, cy2 + m) - max(ay1 - m, cy1 - m)
            if ox > 1e-6 and oy > 1e-6:
                overlaps.append({"refs": [a, c], "overlap_mm2": round(ox * oy, 4)})
    overlaps.sort(key=lambda d: (-d["overlap_mm2"], d["refs"]))
    # Board area from Edge.Cuts (or explicit override).
    if board_mm:
        bw, bh = float(board_mm[0]), float(board_mm[1])
    else:
        eb = b.GetBoardEdgesBoundingBox()
        bw = pcbnew.ToMM(eb.GetWidth()); bh = pcbnew.ToMM(eb.GetHeight())
    parts_area = sum((x2 - x1) * (y2 - y1) for (x1, y1, x2, y2) in boxes.values())
    board_area = bw * bh
    utilization = round(parts_area / board_area, 4) if board_area > 0 else None
    under_filled = utilization is not None and utilization < float(min_utilization)
    # BR_20260729 §C (implausible-measurement tripwire): parts area may not exceed
    # the board it sits on. utilization > 1.0 is physically impossible for a valid
    # floorplan, so it is evidence the MEASUREMENT is wrong, not that the board is
    # over-full — the exact signal the old silkscreen-bbox fallback produced (1.27).
    # Report it as an unusable verdict instead of a confident `passed:false`, which
    # would push the caller to "fix" a floorplan that was never measured correctly.
    implausible = utilization is not None and utilization > 1.0
    passed = (not overlaps and utilization is not None
              and not under_filled and not implausible)
    reasons: list[str] = []
    if implausible:
        reasons.append(
            f"implausible_measurement: utilization {utilization} > 1.0 — parts area "
            f"{round(parts_area,1)}mm² exceeds board area {round(board_area,1)}mm², "
            f"which is geometrically impossible (basis={basis}). Treat this verdict "
            f"as UNUSABLE for floorplan decisions and fix the measurement first.")
    if overlaps:
        reasons.append(f"courtyard_overlap: {len(overlaps)} pair(s) intersect "
                       f"(worst {overlaps[0]['refs']} {overlaps[0]['overlap_mm2']}mm²)")
    if under_filled:
        reasons.append(f"sheet_under_filled: utilization {utilization} < "
                       f"{min_utilization} floor (parts {round(parts_area,1)}mm² / "
                       f"board {round(board_area,1)}mm²)")
    if courtyard_missing:
        reasons.append(
            f"courtyard_missing: {len(courtyard_missing)} of {len(boxes)} part(s) have no "
            f"F/B.CrtYd outline; their extent was measured from the text-excluded "
            f"geometry bbox instead (basis={basis})")
    return {"passed": passed, "board": board_path, "components": len(boxes),
            "overlaps": overlaps, "overlap_pairs": len(overlaps),
            "utilization": utilization, "min_utilization": float(min_utilization),
            "parts_area_mm2": round(parts_area, 3), "board_area_mm2": round(board_area, 3),
            "board_mm": [round(bw, 3), round(bh, 3)],
            "basis": basis, "courtyard_missing": courtyard_missing,
            "implausible_measurement": implausible, "reasons": reasons}


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
    _ensure_parent_dir(out_path)
    pcbnew.SaveBoard(out_path, b)
    return {"board": out_path, "vias_added": added, "process": "via-in-pad (filled+capped / JLCPCB advanced)"}


# -------------------------------------------------------------------------------- copper planes
def _parse_plane_spec(spec: str) -> tuple[str, str]:
    """Parse a "LAYER:NET" plane spec (e.g. "B.Cu:GND") into (layer_name, netname).

    Fail-fast on a malformed spec BEFORE any getattr(pcbnew, ...) — otherwise a
    caller who swaps the fields ("GND:B.Cu") or omits the layer gets a misleading
    `AttributeError: module 'pcbnew' has no attribute 'GND'` instead of a spec error."""
    if not isinstance(spec, str) or spec.count(":") != 1:
        raise ValueError(
            f'POUR_PLANES_BAD_SPEC: expected "LAYER:NET" e.g. "B.Cu:GND", got {spec!r}')
    layer_name, netname = spec.split(":")
    layer_name = layer_name.strip(); netname = netname.strip()
    if not layer_name or not netname:
        raise ValueError(
            f'POUR_PLANES_BAD_SPEC: expected "LAYER:NET" e.g. "B.Cu:GND", got {spec!r}')
    if not hasattr(pcbnew, layer_name.replace(".", "_")):
        raise ValueError(
            f'POUR_PLANES_BAD_SPEC: expected "LAYER:NET" e.g. "B.Cu:GND", got {spec!r} '
            f'(layer {layer_name!r} is not a pcbnew layer)')
    return layer_name, netname


def pour_planes(in_path: str, out_path: str, planes: list[str], *, stitch: bool = True,
                stitch_net: str = "GND", stitch_pitch_mm: float = 14.0,
                stitch_drill_mm: float = 0.3, stitch_pad_mm: float = 0.6,
                pad_connection: str = "thermal") -> dict:
    """Pour filled copper zones. `planes` = ["F.Cu:GND", "In1.Cu:GND", "In4.Cu:V3V3", ...].
    Optionally adds stitching vias on `stitch_net`; dangling ones are stripped.

    H5: the stitch net + grid/via geometry are caller-overridable. Defaults
    (GND, 14mm pitch, 0.3/0.6mm drill/pad) are a JLCPCB-class process reference,
    not a hidden assumption — pass stitch_net/stitch_pitch_mm/stitch_drill_mm/
    stitch_pad_mm for a different ground name or denser/looser stitching.

    pad_connection ("thermal"|"solid", default "thermal"): how zone-net pads bond
    to the pour. "thermal" keeps KiCad thermal-relief spokes (default); "solid"
    sets ZONE_CONNECTION_FULL so PTH/plane-net pads bond fully to copper, avoiding
    the starved_thermal DRC error on isolated islands. An illegal value fails fast."""
    if pad_connection not in ("thermal", "solid"):
        raise ValueError(
            f'POUR_PLANES_BAD_PAD_CONNECTION: expected "thermal" or "solid", '
            f'got {pad_connection!r}')
    _need_pcbnew()
    b = pcbnew.LoadBoard(in_path)
    box = b.GetBoardEdgesBoundingBox(); m = pcbnew.FromMM(0.3)
    x1, y1, x2, y2 = box.GetLeft() + m, box.GetTop() + m, box.GetRight() - m, box.GetBottom() - m
    out = []
    for spec in planes:
        layer_name, netname = _parse_plane_spec(spec)
        lid = getattr(pcbnew, layer_name.replace(".", "_")); net = b.FindNet(netname)
        z = pcbnew.ZONE(b); z.SetLayer(lid); z.SetAssignedPriority(0)
        if net is not None:
            z.SetNet(net)
        if pad_connection == "solid":
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        pts = pcbnew.VECTOR_VECTOR2I()
        for (x, y) in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            pts.append(pcbnew.VECTOR2I(int(x), int(y)))
        z.AddPolygon(pts); b.Add(z)
        out.append({"layer": layer_name, "net": netname, "pad_connection": pad_connection})
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    stitched = 0
    gnd = b.FindNet(stitch_net)
    if stitch and gnd:
        pads = [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads()]
        step = pcbnew.FromMM(stitch_pitch_mm)
        x = box.GetLeft() + step
        while x < box.GetRight():
            y = box.GetTop() + step
            while y < box.GetBottom():
                if all(abs(pp.x - x) > pcbnew.FromMM(1.6) or abs(pp.y - y) > pcbnew.FromMM(1.6) for pp in pads):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                    v.SetDrill(pcbnew.FromMM(stitch_drill_mm)); v.SetWidth(pcbnew.FromMM(stitch_pad_mm))
                    v.SetNet(gnd); b.Add(v); stitched += 1
                y += step
            x += step
    _ensure_parent_dir(out_path)
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
                     *, clearance_mm: float = 0.13, post_widen_drc: bool = False) -> dict:
    """Widen routed bus segments to `target_mm` only when nearby foreign copper/pads keep clearance.

    ``post_widen_drc`` (BR_20260708 Ask #3): after the geometric-clearance widen pass, run a
    real DRC and REVERT any track whose widening introduced a NEW copper violation. The
    fast ``_widening_is_clear`` geometric predictor misses cases only kicad-cli DRC catches
    (e.g. widening near a teardropped/tented via — the CHG_STAT vs USB_CC2 symptom), which is
    why finish needs a post-widen DRC loop, not just the pre-check. Reverted tracks are
    reported under ``reverted`` so nothing silently stays over-wide or silently fails the gate."""
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
    widened_tracks = []  # (track, original_width_iu) for post-widen DRC revert
    for track in board.GetTracks():
        if track.GetClass() != 'PCB_TRACK' or track.GetNetname() not in netset:
            continue
        if track.GetWidth() >= target_iu:
            kept += 1; continue
        if _widening_is_clear(board, track, target_iu, clearance_iu):
            orig = track.GetWidth()
            track.SetWidth(target_iu); widened += 1
            widened_tracks.append((track, orig))
        else:
            kept += 1
    reverted = 0
    if post_widen_drc and widened_tracks:
        _ensure_parent_dir(out_path)
        pcbnew.SaveBoard(out_path, board)
        base_copper = drc_gate(out_path).get("copper", 0)
        # revert widenings until the copper count is no worse than before this widen pass;
        # a widening that adds a copper violation the pre-check missed is undone width-only.
        while base_copper > 0 and widened_tracks:
            track, orig = widened_tracks.pop()
            track.SetWidth(orig); reverted += 1; widened -= 1; kept += 1
            pcbnew.SaveBoard(out_path, board)
            base_copper = drc_gate(out_path).get("copper", 0)
        result_copper = base_copper
    else:
        _ensure_parent_dir(out_path)
        pcbnew.SaveBoard(out_path, board)
        result_copper = None
    out = {"board": out_path, "widened": widened, "kept": kept, "target_mm": target_mm}
    if post_widen_drc:
        out["reverted"] = reverted
        out["copper_after"] = result_copper
    return out


# ----------------------------------------------------- pad-intrinsic clearance override (finish)
def apply_pad_intrinsic_overrides(in_path: str, out_path: str, *, override_mm: float = 0.09,
                                  sidecar_path: str | None = None) -> dict:
    """Auto-resolve package-intrinsic pad-gap DRC violations with pad-level clearance overrides
    (BR_20260708 Ask #1).

    A ``clearance`` violation whose two items are pads OF THE SAME footprint is the land
    pattern's own geometry (USB-C 0.10mm pad gaps, LGA 0.10mm) — not a routing error and
    unfixable by routing. The honest resolution is a pad-level ``SetLocalClearance`` override
    on exactly the offending pads, recorded to a sidecar for audit. This runs the DRC gate,
    classifies each violation with ``classify_clearance_violation``, and for every
    ``package_intrinsic`` pair sets ``override_mm`` (default 0.09mm, below the 0.10mm land
    gap) on the named footprint's pads.

    Only same-footprint pad pairs are touched; true copper violations are left untouched so
    they still fail the gate. The sidecar lists every override (ref + pads + old/new clearance)
    so nothing is silently changed. Returns the applied count + the audit records."""
    _need_pcbnew()
    board = pcbnew.LoadBoard(in_path)
    report = drc_gate(in_path, classify_intrinsic=True)
    override_iu = pcbnew.FromMM(float(override_mm))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    applied = []
    for item in report.get("package_intrinsic_items", []):
        refs = item.get("refs") or []
        # classify_clearance_violation only tags package_intrinsic when both refs match
        ref = refs[0] if refs else None
        fp = fps.get(ref)
        if fp is None:
            continue
        touched_pads = []
        for pad in fp.Pads():
            old_iu = pad.GetLocalClearance() if hasattr(pad, "GetLocalClearance") else 0
            # GetLocalClearance may return an optional wrapper; normalize to int IU
            try:
                old_val = int(old_iu)
            except (TypeError, ValueError):
                old_val = 0
            if old_val == 0 or old_val > override_iu:
                pad.SetLocalClearance(override_iu)
                touched_pads.append(pad.GetPadName() or pad.GetNumber())
        if touched_pads:
            applied.append({"ref": ref, "pads": touched_pads,
                            "old_clearance_mm": None,
                            "new_clearance_mm": round(override_mm, 4),
                            "violation": item.get("type")})
    _ensure_parent_dir(out_path)
    pcbnew.SaveBoard(out_path, board)
    result = {"board": out_path, "applied": len(applied), "override_mm": override_mm,
              "overrides": applied,
              "package_intrinsic_seen": len(report.get("package_intrinsic_items", []))}
    if sidecar_path:
        _ensure_parent_dir(sidecar_path)
        with open(sidecar_path, "w") as sc:
            json.dump(result, sc, indent=2)
        result["sidecar"] = sidecar_path
    return result


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
    _ensure_parent_dir(out_path)
    pcbnew.SaveBoard(out_path, board)
    if report_path:
        _ensure_parent_dir(report_path)
        with open(report_path, "w") as report:
            json.dump(result, report, indent=2)
    return result


# ------------------------------------------------------------------------------ drc gate (honest)
def _violation_item_refs(v: dict) -> list[str]:
    """Best-effort refdes extraction from a kicad-cli DRC violation's item descriptions.
    Each item usually reads like 'Pad 2 of R1 ...' — we pull the refdes tokens."""
    refs: list[str] = []
    for it in v.get("items", []) or []:
        desc = it.get("description") or ""
        m = re.search(r"\bof\s+([A-Za-z][A-Za-z0-9_]*)", desc)
        if m:
            refs.append(m.group(1))
    return refs


def classify_clearance_violation(v: dict, *, pad_adjacency: dict | None = None,
                                 intrinsic_tol_mm: float = 0.02) -> str:
    """Pure: label one DRC violation as 'package_intrinsic' | 'copper' | 'other' (BR_20260708).

    A ``clearance`` violation whose two items are pads OF THE SAME footprint that are a
    known package-intrinsic distance apart is NOT a routing error — it is the land pattern's
    own geometry (USB-C 0.10mm pad gaps, LGA 0.10mm) and cannot be 'fixed' by routing; the
    honest resolution is a pad-level clearance override, not a gate fail. ``pad_adjacency``
    optionally maps 'REF' -> True for footprints known to have intrinsic sub-rule pad gaps;
    when absent, same-footprint pad-to-pad clearance violations are still flagged intrinsic
    (that pairing is definitionally the package, not a track). Non-clearance or cross-part
    violations are 'copper'. Pure; no pcbnew."""
    vtype = (v.get("type") or "").lower()
    if "silk" in vtype:
        return "other"
    if "clearance" not in vtype:
        return "copper"
    refs = _violation_item_refs(v)
    # two items, same footprint, both pads -> package-intrinsic land pattern geometry
    if len(refs) == 2 and refs[0] == refs[1]:
        if pad_adjacency is None or pad_adjacency.get(refs[0], True):
            return "package_intrinsic"
    return "copper"


def drc_gate(board_path: str, *, classify_intrinsic: bool = False,
             pad_adjacency: dict | None = None) -> dict:
    """Run DRC and split copper/unconnected (hard) from silk (cosmetic).

    ``classify_intrinsic`` (BR_20260708): further split copper clearance violations into
    ``package_intrinsic`` (same-footprint adjacent pads at the land pattern's own spacing —
    a pad-level override matter, NOT a routing error) vs true ``copper``. When on, the
    returned ``copper`` count EXCLUDES package-intrinsic ones and ``package_intrinsic`` +
    an evidence list are reported; ``clean`` still requires zero TRUE copper + unconnected,
    so intrinsic pad gaps do not silently pass as clean but also don't masquerade as routing
    errors. Gate values are never relaxed to pass — intrinsic items are reclassified with
    evidence, not waved through."""
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
    out = {"copper": copper, "unconnected": unc, "silk": silk,
           "clean": copper == 0 and unc == 0}
    if classify_intrinsic:
        intrinsic = []
        for x in v:
            if classify_clearance_violation(x, pad_adjacency=pad_adjacency) == "package_intrinsic":
                intrinsic.append({"type": x.get("type"),
                                  "refs": _violation_item_refs(x),
                                  "description": (x.get("description") or "")[:160]})
        true_copper = copper - len(intrinsic)
        out.update({"copper": true_copper, "package_intrinsic": len(intrinsic),
                    "package_intrinsic_items": intrinsic,
                    "clean": true_copper == 0 and unc == 0})
    return out


# ------------------------------------------------------------------------ micro-stub cleanup (finish)
def clean_micro_stubs(in_path: str, out_path: str, *, min_len_mm: float = 0.02) -> dict:
    """Remove track segments shorter than ``min_len_mm`` left by SES import (BR_20260708).

    Freerouting SES import can leave <0.01mm track fragments that read as false unconnected /
    false clearance (the MIC1 GND 0.0001mm-track symptom). This strips only true micro-stubs
    (length below the threshold) and reports how many + their nets, so the removal is auditable
    and never silently drops real routing. Vias and zones are untouched."""
    _need_pcbnew()
    b = pcbnew.LoadBoard(in_path)
    thr_iu = pcbnew.FromMM(float(min_len_mm))
    removed = []
    for t in list(b.GetTracks()):
        if t.GetClass() != "PCB_TRACK":
            continue
        length = math.hypot(t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y)
        if length < thr_iu:
            removed.append({"net": t.GetNetname(), "len_mm": round(length / 1e6, 5)})
            b.Remove(t)
    _ensure_parent_dir(out_path)
    pcbnew.SaveBoard(out_path, b)
    return {"board": out_path, "removed": len(removed), "min_len_mm": min_len_mm,
            "removed_stubs": removed}


# --------------------------------------------------------------------------------- ngspice SI gate
def si_status(over_pct: float, under_pct: float, pass_pct: float, warn_pct: float) -> str:
    """H2: classify overshoot/undershoot vs caller-overridable thresholds (pure, ngspice-free)."""
    if over_pct < pass_pct and under_pct < pass_pct:
        return "pass"
    if over_pct < warn_pct and under_pct < warn_pct:
        return "warn"
    return "fail"


def si_check(board_path: str, nets: list[str], *, z0: float = 50.0, rs: float = 22.0,
             vdd: float = 1.8, ps_per_mm: float = PS_PER_MM_DEFAULT,
             rdrv: float = 17.0, cload: float = 3e-12, edge_ns: float = 0.3,
             overshoot_pass_pct: float = 10.0, overshoot_warn_pct: float = 20.0) -> dict:
    """Per-net series-terminated transmission-line SI: overshoot/undershoot -> pass/warn/fail.

    Driver/load/edge/thresholds are caller-overridable (H2); the defaults are a documented
    STM32-class CMOS output-buffer reference, NOT a hidden assumption. The result echoes the
    effective values used (``effective``) so the verdict is interpretable on any device."""
    _need_pcbnew()
    b = pcbnew.LoadBoard(board_path)
    res = []
    for nm in nets:
        L = sum(math.hypot(t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y)
                for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == nm) / 1e6
        if L < 0.1:
            continue
        td = L * ps_per_mm * 1e-12
        deck = (f"* SI {nm}\nVin in 0 PWL(0 0 0.1n 0 {edge_ns}n {vdd})\nRd in d {rdrv}\nRs d s {rs}\n"
                f"T1 s 0 r 0 Z0={z0} TD={td:.4e}\nCl r 0 {cload}\n.tran 5p 6n\n.control\nrun\n"
                f"meas tran vmax MAX v(r) from={edge_ns}n to=6n\nmeas tran vmin MIN v(r) from=1n to=6n\n"
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
        st = si_status(over, under, overshoot_pass_pct, overshoot_warn_pct)
        res.append({"net": nm, "len_mm": round(L, 2), "overshoot_pct": round(over, 1),
                    "undershoot_pct": round(under, 1), "status": st})
    order = {"pass": 0, "warn": 1, "fail": 2}
    worst = max((order[r["status"]] for r in res), default=0)
    return {"z0": z0, "rs": rs, "nets": res, "worst": ["pass", "warn", "fail"][worst],
            "effective": {"z0": z0, "rs": rs, "vdd": vdd, "ps_per_mm": ps_per_mm,
                          "rdrv": rdrv, "cload": cload, "edge_ns": edge_ns,
                          "overshoot_pass_pct": overshoot_pass_pct,
                          "overshoot_warn_pct": overshoot_warn_pct}}


# --------------------------------------------------------------- Specctra DSN net-class rules (pure)
def _balanced_end(text: str, start: int) -> int:
    """Given text[start] == '(', return the index just past the matching ')'."""
    depth = 0
    n = len(text)
    j = start
    while j < n:
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def _dsn_unit_per_mm(dsn_text: str) -> tuple[str, float]:
    """Read the DSN (resolution UNIT PREC) and return (unit, units_per_mm). Fail fast on
    a missing/again-unsupported unit rather than guessing a scale (no silent fallback)."""
    m = re.search(r"\(resolution\s+(\w+)\s+(\d+)\)", dsn_text)
    if not m:
        raise ValueError("DSN_NO_RESOLUTION: no (resolution UNIT PREC) block — refusing to "
                         "guess DSN units for net-class rule widths")
    unit = m.group(1)
    per_mm = {"um": 1000.0, "mm": 1.0, "inch": 1.0 / 25.4, "mil": 1000.0 / 25.4}.get(unit)
    if per_mm is None:
        raise ValueError(f"DSN_UNSUPPORTED_UNIT: {unit!r} (expected um|mm|inch|mil)")
    return unit, per_mm


def _fmt_dsn_class(name: str, nets: list[str], w: int, c: int, via: str | None) -> str:
    lines = [f"    (class {name}"]
    if nets:
        lines.append("      " + " ".join(nets))
    if via:
        lines.append(f"      (circuit\n        (use_via {via})\n      )")
    lines.append(f"      (rule\n        (width {w})\n        (clearance {c})\n      )")
    lines.append("    )")
    return "\n".join(lines)


def build_dsn_with_netclasses(dsn_text: str, classes: list[dict], *,
                              default_width_mm: float = 0.2,
                              default_clearance_mm: float = 0.2,
                              default_class_name: str = "kicad_default") -> dict:
    """Rewrite a KiCad-exported Specctra DSN's single global net class into per-class rules
    so freerouting honours a tight BGA-escape width/clearance for escape nets while keeping
    signal/power nets at their own widths (BR_20260708).

    ``classes`` is an ORDERED list of {name, width_mm, clearance_mm, nets?:[exact],
    match?:[substrings], via?}. A net joins the FIRST class that claims it (explicit ``nets``
    membership OR any ``match`` substring occurring in the net name); unclaimed nets fall into
    a synthesized default class at default_width_mm/default_clearance_mm. Pure text surgery
    (no pcbnew) so it is bare-host testable. Returns {dsn, unit, classes:[...], default_class,
    missing_explicit_nets, total_nets}. Empty classes are dropped (reported in warnings) since
    freerouting rejects a class with no nets."""
    unit, per_mm = _dsn_unit_per_mm(dsn_text)
    ns = dsn_text.find("(network")
    if ns < 0:
        raise ValueError("DSN_NO_NETWORK: no (network ...) section — not a routable DSN")
    ne = _balanced_end(dsn_text, ns)
    net_section = dsn_text[ns:ne]

    # net declarations: (net NAME (pins ...)) — anchor on (pins to skip class net-token lists
    nets = re.findall(r"\(net\s+\"?([^\"\s()]+)\"?\s+\(pins", net_section)

    # locate existing (class ...) blocks; harvest the via token to preserve fanout
    blocks: list[tuple[int, int]] = []
    i = 0
    while True:
        k = net_section.find("(class ", i)
        if k < 0:
            break
        e = _balanced_end(net_section, k)
        blocks.append((k, e))
        i = e
    orig = net_section[blocks[0][0]:blocks[-1][1]] if blocks else ""
    vm = re.search(r"\(use_via\s+([^\s)]+)", orig)
    via = vm.group(1) if vm else None

    used: set[str] = set()
    report_classes: list[dict] = []
    warnings: list[str] = []
    class_texts: list[str] = []
    for c in classes:
        name = c["name"]
        exact = set(c.get("nets", []))
        match = list(c.get("match", []))
        sel = [n for n in nets if n not in used
               and (n in exact or any(s in n for s in match))]
        for n in sel:
            used.add(n)
        w = int(round(float(c["width_mm"]) * per_mm))
        cl = int(round(float(c["clearance_mm"]) * per_mm))
        if not sel:
            warnings.append(f"class {name!r} matched no nets — dropped")
            report_classes.append({"name": name, "width_mm": c["width_mm"],
                                   "clearance_mm": c["clearance_mm"], "nets": [], "count": 0})
            continue
        class_texts.append(_fmt_dsn_class(name, sel, w, cl, c.get("via", via)))
        report_classes.append({"name": name, "width_mm": c["width_mm"],
                               "clearance_mm": c["clearance_mm"], "width_dsn": w,
                               "clearance_dsn": cl, "nets": sel, "count": len(sel)})

    default_nets = [n for n in nets if n not in used]
    dw = int(round(float(default_width_mm) * per_mm))
    dc = int(round(float(default_clearance_mm) * per_mm))
    default_report = {"name": default_class_name, "width_mm": default_width_mm,
                      "clearance_mm": default_clearance_mm, "width_dsn": dw,
                      "clearance_dsn": dc, "nets": default_nets, "count": len(default_nets)}
    if default_nets:
        class_texts.append(_fmt_dsn_class(default_class_name, default_nets, dw, dc, via))

    missing = sorted({n for c in classes for n in c.get("nets", []) if n not in nets})

    new_classes = "\n".join(class_texts)
    if blocks:
        kept_head = net_section[:blocks[0][0]]
        kept_tail = net_section[blocks[-1][1]:]
        new_net_section = kept_head + new_classes + "\n" + kept_tail.lstrip("\n")
    else:
        insert_at = net_section.rfind(")")
        new_net_section = net_section[:insert_at] + new_classes + "\n  " + net_section[insert_at:]
    new_dsn = dsn_text[:ns] + new_net_section + dsn_text[ne:]
    return {"dsn": new_dsn, "unit": unit, "classes": report_classes,
            "default_class": default_report, "missing_explicit_nets": missing,
            "total_nets": len(nets), "warnings": warnings}


# ------------------------------------------------------------------ autoroute preflight (diagnostic)
def classify_autoroute_readiness(probe: dict) -> dict:
    """Pure classifier: given an environment probe, say whether freerouting can run and,
    if not, EXACTLY what is missing + how to fix it (BR_20260708 Ask #2).

    ``probe`` keys (all bool unless noted): ``jar_present`` (freerouting.jar on disk),
    ``java_present`` (java on PATH), ``xvfb_present`` (xvfb-run on PATH),
    ``awt_headful`` (a full JRE with libawt_xawt.so — freerouting v1.9.0 CLI still calls
    Toolkit.getScreenSize(), so a *-headless JRE throws HeadlessException). Returns
    {ready, missing:[...], reason, remedy}. Pure — bare-host testable; no subprocess.

    Readiness rule: ready IFF jar_present AND java_present AND awt_headful AND
    (xvfb_present OR a real DISPLAY). A headless-only JRE is NOT ready even with xvfb,
    because the missing libawt_xawt.so is the crash, not the display."""
    missing: list[str] = []
    if not probe.get("jar_present"):
        missing.append("freerouting.jar")
    if not probe.get("java_present"):
        missing.append("java")
    if probe.get("java_present") and not probe.get("awt_headful"):
        missing.append("full-JRE-libawt_xawt.so")
    if not (probe.get("xvfb_present") or probe.get("display")):
        missing.append("xvfb-run-or-DISPLAY")
    ready = not missing
    remedy_map = {
        "freerouting.jar": "install freerouting.jar (FREEROUTING_JAR env or /opt/freerouting.jar); "
                           "rebuild the ee worker image (Dockerfile.ee bundles v1.9.0)",
        "java": "install a JRE and put java on PATH (JAVA_BIN env)",
        "full-JRE-libawt_xawt.so": "freerouting v1.9.0 CLI needs a HEADFUL JRE — a *-headless "
                                   "JRE lacks libawt_xawt.so and throws HeadlessException; install a "
                                   "full JRE (e.g. Temurin) not openjdk-*-jre-headless",
        "xvfb-run-or-DISPLAY": "run under `xvfb-run -a` (virtual display) or a real X DISPLAY",
    }
    reason = ("freerouting autoroute ready" if ready else
              "freerouting autoroute NOT runnable — missing: " + ", ".join(missing))
    return {"ready": ready, "missing": missing, "reason": reason,
            "remedy": [remedy_map[m] for m in missing]}


def _probe_autoroute_env() -> dict:
    """Probe the live worker for freerouting prerequisites (subprocess/fs; not pure)."""
    jar = os.environ.get("FREEROUTING_JAR", "/opt/freerouting/freerouting.jar")
    java = os.environ.get("JAVA_BIN", "java")
    java_present = subprocess.run(["which", java], capture_output=True).returncode == 0
    xvfb_present = subprocess.run(["which", "xvfb-run"], capture_output=True).returncode == 0
    # A headful JRE ships libawt_xawt.so; probe the JRE's lib dir for it.
    awt_headful = False
    if java_present:
        try:
            import glob as _glob
            jhome = subprocess.run([java, "-XshowSettings:properties", "-version"],
                                   capture_output=True, text=True)
            txt = (jhome.stderr or "") + (jhome.stdout or "")
            m = re.search(r"java\.home\s*=\s*(\S+)", txt)
            roots = [m.group(1)] if m else ["/usr/lib/jvm/*"]
            for root in roots:
                if _glob.glob(f"{root}/lib/libawt_xawt.so") or _glob.glob(f"{root}/lib/*/libawt_xawt.so"):
                    awt_headful = True
                    break
        except Exception:
            awt_headful = False
    return {"jar_present": os.path.exists(jar), "java_present": java_present,
            "xvfb_present": xvfb_present, "awt_headful": awt_headful,
            "display": bool(os.environ.get("DISPLAY")),
            "jar_path": jar, "java_bin": java}


def autoroute_preflight() -> dict:
    """Diagnostic gate for the C04 route step: probe the worker + classify readiness so a
    caller sees EXACTLY what is missing (jar / java / headful-JRE / xvfb) instead of a raw
    Java HeadlessException stack. Returns the probe merged with the readiness verdict."""
    probe = _probe_autoroute_env()
    verdict = classify_autoroute_readiness(probe)
    return {**verdict, "probe": probe}


# -------------------------------------------------------------------------------- autoroute (opt)
def autoroute(board_path: str, out_path: str, *, passes: int = 40,
              netclasses: list[dict] | None = None,
              default_width_mm: float = 0.2, default_clearance_mm: float = 0.2) -> dict:
    """Freerouting autoroute if available (java + freerouting.jar + xvfb); else no-op passthrough.

    ``netclasses`` (BR_20260708): an ordered list of per-class rules injected into the exported
    Specctra DSN before routing, so a fine-pitch BGA escape region can use 0.1/0.1mm while
    signal/power nets keep their own widths — instead of a single global 0.2mm rule that makes
    0.5mm-pitch BGA escape impossible. Each entry: {name, width_mm, clearance_mm, nets?:[exact],
    match?:[substrings]}. Run BGA fanout (via_in_pad) BEFORE this so escape stubs exist. When
    omitted, the DSN keeps KiCad's default single rule (backward-compatible)."""
    _need_pcbnew()
    jar = os.environ.get("FREEROUTING_JAR", "/opt/freerouting/freerouting.jar")
    java = os.environ.get("JAVA_BIN", "java")
    have = os.path.exists(jar) and subprocess.run(["which", java], capture_output=True).returncode == 0
    if not have:
        return {"routed": False, "reason": "freerouting/java not present in this worker",
                "board": board_path}
    dsn = board_path.replace(".kicad_pcb", ".dsn"); ses = board_path.replace(".kicad_pcb", ".ses")
    b = pcbnew.LoadBoard(board_path)
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        bad = sorted(fp.GetReference() for fp in b.GetFootprints()
                     if not fp.GetReference() or fp.GetReference().startswith("REF**"))
        raise RuntimeError(
            "ExportSpecctraDSN failed (no DSN written) — footprints with missing/unannotated "
            f"references: {bad or 'none detected; inspect the board in pcbnew'}")
    netclass_report = None
    if netclasses:
        with open(dsn) as fh:
            dsn_text = fh.read()
        built = build_dsn_with_netclasses(dsn_text, netclasses,
                                          default_width_mm=default_width_mm,
                                          default_clearance_mm=default_clearance_mm)
        with open(dsn, "w") as fh:
            fh.write(built["dsn"])
        netclass_report = {k: built[k] for k in
                           ("unit", "classes", "default_class", "missing_explicit_nets",
                            "total_nets", "warnings")}
    xvfb = ["xvfb-run", "-a"] if subprocess.run(["which", "xvfb-run"], capture_output=True).returncode == 0 else []
    proc = subprocess.run(xvfb + [java, "-jar", jar, "-de", dsn, "-do", ses, "-mp", str(passes)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-500:]
        raise RuntimeError(f"freerouting exited with code {proc.returncode}: {tail}")
    if not os.path.exists(ses):
        raise RuntimeError(f"freerouting produced no SES session file at {ses} — autoroute did not run")
    b2 = pcbnew.LoadBoard(board_path); pcbnew.ImportSpecctraSES(b2, ses)
    _ensure_parent_dir(out_path)
    pcbnew.SaveBoard(out_path, b2)
    t = b2.GetTracks()
    # BR_20260708: structured completion — report unconnected so a router that converged
    # short ("can't improve") is visible here, not only at downstream DRC.
    unconnected = None
    try:
        b2.BuildConnectivity()
        try:
            unconnected = int(b2.GetConnectivity().GetUnconnectedCount(True))
        except TypeError:
            unconnected = int(b2.GetConnectivity().GetUnconnectedCount())
    except Exception:
        unconnected = None
    out = {"routed": True, "board": out_path,
           "segments": sum(1 for x in t if x.GetClass() == 'PCB_TRACK'),
           "vias": sum(1 for x in t if x.GetClass() == 'PCB_VIA'),
           "unconnected": unconnected, "complete": (unconnected == 0) if unconnected is not None else None}
    if netclass_report is not None:
        out["netclasses"] = netclass_report
    return out
