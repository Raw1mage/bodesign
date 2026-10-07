"""bodesign_c04_board_manifest: the section 2.2 board geometry packet (c04-entry-freeze-20261007.md).

Reads a placed ``.kicad_pcb`` through ``c04_gate``'s s-expression loader (``parse_sexpr`` /
``load_board`` -- reused, not forked) and emits the packet that C02' consumes:

* ``outline``       Edge.Cuts polygon, lines + arcs flattened (declared step), canonical orientation.
* ``thickness``     ``(general (thickness ..))``; absent => fail-fast, never defaulted.
* ``mounting_holes`` measured list; ``[]`` is a MEASURED empty (see ``measured.mounting_holes``).
* ``connectors``    keyed by the caller's ``connector_refs``: origin / rotation / side / courtyard bbox / pad bbox, plus
                    ``mating_normal`` (caller-declared via ``mating_normals``; else null + status ``unmeasured``).
* ``component_height_envelope`` per board ref: ``unmeasured`` unless the caller supplies ``height_envelope_mm``
                    {ref: {z_max_above_board_top_mm, [z_min_below_board_top_mm], evidence}} (evidence string required).
* ``exported_outline_sha256`` / ``exported_mounting_holes_sha256``: sha256 of the canonical JSON
  (sorted keys, compact separators, floats rounded to 1e-6) of the ``outline`` object and of the
  ``mounting_holes`` list exactly as they appear in the packet (section 2.3 chain).

Declared limits: footprint-internal Edge.Cuts graphics are not read; arcs are 24 equal-angle chords and
circles a 48-gon (``c04_gate`` flattening); a mounting hole is a drilled pad of a footprint whose
reference starts with ``H`` or ``MH`` (and that is ``through_hole`` or carries an NP pad). Drilled NP
pads of any OTHER footprint (e.g. connector locating pegs) are NOT mounting holes; they are listed in
``measured.other_drilled_np_pads`` so nothing is dropped silently. Coordinates stay in the board file's
frame (mm, y down); the packet records the outline bbox so a consumer can re-origin.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from .c04_gate import (C04GateInputError, _bbox, _f, _kid, _kids, _point_in_outline, _read, _rot, _sha256,
                       _union, _xy, load_board, parse_sexpr)

SCHEMA = "c04_board_manifest/1"
ARC_FLATTEN = "gr_arc = 24 equal-angle chords; gr_circle = 48-gon (c04_gate flattening)"
_CHAIN_TOL_MM = 1e-3
_HOLE_REF = re.compile(r"^(MH|H)")


def _r6(v: Any) -> Any:
    if isinstance(v, float):
        v = round(v, 6)
        return 0.0 if v == 0 else v
    if isinstance(v, (list, tuple)):
        return [_r6(x) for x in v]
    if isinstance(v, dict):
        return {k: _r6(x) for k, x in v.items()}
    return v


def canonical_sha256(obj: Any) -> str:
    """sha256 of the canonical JSON (sorted keys, compact, floats rounded to 1e-6, ASCII)."""
    return hashlib.sha256(json.dumps(_r6(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                          .encode("ascii")).hexdigest()


def _area(poly: list) -> float:
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2.0


def _close(a: tuple, b: tuple) -> bool:
    return abs(a[0] - b[0]) <= _CHAIN_TOL_MM and abs(a[1] - b[1]) <= _CHAIN_TOL_MM


def _chain(segs: list[tuple]) -> list[list[tuple[float, float]]]:
    """Chain Edge.Cuts segments into closed loops; an open chain raises with the gap location."""
    left = [((s[0], s[1]), (s[2], s[3])) for s in segs if math.hypot(s[2] - s[0], s[3] - s[1]) > 1e-9]
    loops: list[list[tuple[float, float]]] = []
    while left:
        a, b = left.pop(0)
        pts = [a, b]
        while not _close(pts[-1], pts[0]):
            for i, (p, q) in enumerate(left):
                if _close(p, pts[-1]):
                    pts.append(q)
                    left.pop(i)
                    break
                if _close(q, pts[-1]):
                    pts.append(p)
                    left.pop(i)
                    break
            else:
                raise C04GateInputError(
                    f"C04_MANIFEST_OUTLINE_OPEN: Edge.Cuts chain does not close; open end at "
                    f"({pts[-1][0]:.4f}, {pts[-1][1]:.4f}) mm (tolerance {_CHAIN_TOL_MM} mm)")
        pts.pop()  # last == first
        if len(pts) < 3:
            raise C04GateInputError("C04_MANIFEST_OUTLINE_DEGENERATE: an Edge.Cuts loop has fewer than 3 vertices")
        loops.append(pts)
    return loops


def _canon_loop(pts: list[tuple[float, float]]) -> list[list[float]]:
    pts = [(round(x, 6), round(y, 6)) for x, y in pts]
    if _area(pts) < 0:
        pts.reverse()
    i0 = min(range(len(pts)), key=lambda i: pts[i])
    pts = pts[i0:] + pts[:i0]
    return [[x, y] for x, y in pts]


def _drills(fp_node: list, ref: str) -> list[dict]:
    out = []
    for p in _kids(fp_node, "pad"):
        d = _kid(p, "drill")
        if d is None:
            continue
        nums = [t for t in d[1:] if isinstance(t, str) and t != "oval"]
        if not nums:
            continue
        num = p[1] if len(p) > 1 else ""
        kind = p[2] if len(p) > 2 else ""
        sz = _kid(p, "size")
        out.append({"pad": num, "kind": kind, "drill": _f(nums[0], f"{ref}.pad{num}.drill"),
                    "pad_dia": max(_f(sz[1], f"{ref}.pad{num}.size"), _f(sz[-1], f"{ref}.pad{num}.size")) if sz else None,
                    "at": _xy(_kid(p, "at"), f"{ref}.pad{num}.at"), "oval": "oval" in d})
    return out


def c04_board_hashes(board_path: str) -> dict:
    """The chain hashes only (outline + mounting holes), recomputed from the board; no connector input needed."""
    m = c04_board_manifest(board_path, [], require_connectors=False)
    return {"exported_outline_sha256": m["exported_outline_sha256"],
            "exported_mounting_holes_sha256": m["exported_mounting_holes_sha256"], "board_sha256": m["inputs"]["board_sha256"]}


def _vec3(v: Any, what: str) -> list:
    if (not isinstance(v, (list, tuple)) or len(v) != 3 or any(isinstance(c, bool) or not isinstance(c, (int, float))
                                                              or not math.isfinite(c) for c in v)):
        raise C04GateInputError(f"C04_MANIFEST_INPUT_FIELD: {what} must be [x, y, z] finite numbers")
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-9:
        raise C04GateInputError(f"C04_MANIFEST_INPUT_FIELD: {what} is a zero vector")
    return [round(c / n, 6) + 0.0 for c in v]


def c04_board_manifest(board_path: str, connector_refs: list | None = None, *, mating_normals: dict | None = None,
                       height_envelope_mm: dict | None = None, require_connectors: bool = True) -> dict:
    text = _read(board_path, "board_path", ".kicad_pcb")
    if require_connectors and (not isinstance(connector_refs, list) or not connector_refs
                               or not all(isinstance(r, str) and r for r in connector_refs)):
        raise C04GateInputError("C04_MANIFEST_INPUT_MISSING: connector_refs is required (non-empty list of reference strings)")
    connector_refs = connector_refs or []
    for nm, v in (("mating_normals", mating_normals), ("height_envelope_mm", height_envelope_mm)):
        if v is not None and not isinstance(v, dict):
            raise C04GateInputError(f"C04_MANIFEST_INPUT_FIELD: {nm} must be an object keyed by reference")
    root = parse_sexpr(text)
    if len(root) != 1 or not root[0] or root[0][0] != "kicad_pcb":
        raise C04GateInputError("C04_GATE_BOARD_FORMAT: top-level form is not (kicad_pcb ...)")
    pcb = root[0]
    gen = _kid(pcb, "general")
    th = _kid(gen, "thickness") if gen else None
    if th is None or len(th) < 2:
        raise C04GateInputError("C04_MANIFEST_THICKNESS_MISSING: (general (thickness ..)) is absent; board thickness is never defaulted")
    thickness = _f(th[1], "general.thickness")
    if not (thickness > 0 and math.isfinite(thickness)):
        raise C04GateInputError(f"C04_MANIFEST_THICKNESS_MISSING: thickness {thickness} is not a positive number")

    board = load_board(text)
    if not board["edge"]:
        raise C04GateInputError("C04_MANIFEST_OUTLINE_MISSING: board has no top-level Edge.Cuts outline")
    loops = _chain(board["edge"])
    loops.sort(key=lambda l: -abs(_area(l)))
    outer = loops[0]
    outer_segs = [(*outer[i], *outer[(i + 1) % len(outer)]) for i in range(len(outer))]
    for cut in loops[1:]:
        if not _point_in_outline(cut[0], outer_segs):
            raise C04GateInputError("C04_MANIFEST_OUTLINE_MULTIPLE: more than one disjoint outer Edge.Cuts loop; refusing to pick one")
    cutouts = sorted((_canon_loop(c) for c in loops[1:]), key=lambda c: c[0])
    poly = _canon_loop(outer)
    bb = _bbox([tuple(p) for p in poly])
    outline = {"units": "mm", "frame": "kicad board file coordinates, y down", "arc_flatten": ARC_FLATTEN,
               "polygon": poly, "cutouts": cutouts, "bbox": [round(v, 6) for v in bb],
               "area_mm2": round(abs(_area([tuple(p) for p in poly])) - sum(abs(_area([tuple(p) for p in c])) for c in cutouts), 6)}

    by_ref = {fp["ref"]: fp for fp in board["footprints"]}
    nodes = {}
    for fp in _kids(pcb, "footprint"):
        from .c04_gate import _fp_ref
        nodes[_fp_ref(fp)] = fp
    missing = [r for r in connector_refs if r not in by_ref]
    if missing:
        raise C04GateInputError(f"C04_MANIFEST_CONNECTOR_MISSING: refs not on the board: {sorted(missing)}")
    for nm, v in (("mating_normals", mating_normals), ("height_envelope_mm", height_envelope_mm)):
        bad = sorted(set(v or {}) - set(by_ref))
        if bad:
            raise C04GateInputError(f"C04_MANIFEST_INPUT_FIELD: {nm} names refs not on the board: {bad}")

    holes: list[dict] = []
    hole_fps: list[str] = []
    other_np: list[dict] = []
    for ref, node in sorted(nodes.items()):
        ds = _drills(node, ref)
        if not ds:
            continue
        at = _kid(node, "at")
        fx, fy = _xy(at, f"{ref}.at")
        rot = _f(at[3], f"{ref}.at.angle") if len(at) > 3 else 0.0
        attr = _kid(node, "attr") or []
        is_hole_fp = bool(_HOLE_REF.match(ref)) and ("through_hole" in attr or any(d["kind"] == "np_thru_hole" for d in ds))
        if is_hole_fp:
            hole_fps.append(ref)
            for d in ds:
                rx, ry = _rot(d["at"][0], d["at"][1], rot)
                holes.append({"ref": ref, "pad": d["pad"], "x": fx + rx, "y": fy + ry, "drill_mm": d["drill"],
                              "pad_dia_mm": d["pad_dia"], "plated": d["kind"] != "np_thru_hole", "oval": d["oval"]})
        else:
            npn = [d for d in ds if d["kind"] == "np_thru_hole"]
            if npn:
                other_np.append({"ref": ref, "count": len(npn), "drills_mm": sorted({d["drill"] for d in npn})})
    holes = _r6(sorted(holes, key=lambda h: (h["ref"], h["pad"])))

    connectors: dict[str, dict] = {}
    for ref in connector_refs:
        fp, node = by_ref[ref], nodes[ref]
        if not fp["pads"]:
            raise C04GateInputError(f"C04_MANIFEST_CONNECTOR_GEOMETRY: {ref} has no pads")
        if fp["courtyard"] is None:
            raise C04GateInputError(f"C04_MANIFEST_CONNECTOR_GEOMETRY: {ref} has no courtyard geometry")
        at = _kid(node, "at")
        x, y = _xy(at, f"{ref}.at")
        pb = fp["pads"][0]["bbox"]
        for p in fp["pads"][1:]:
            pb = _union(pb, p["bbox"])
        side = "F" if fp["side"].startswith("F") else "B" if fp["side"].startswith("B") else None
        if side is None:
            raise C04GateInputError(f"C04_MANIFEST_CONNECTOR_GEOMETRY: {ref} has no F/B copper layer ({fp['side']!r})")
        connectors[ref] = _r6({"footprint": node[1] if len(node) > 1 else "", "origin": [x, y],
                               "rotation_deg": _f(at[3], f"{ref}.at.angle") if len(at) > 3 else 0.0,
                               "side": side, "courtyard_bbox": list(fp["courtyard"]),
                               "courtyard_bbox_basis": "drawn centreline bbox; pcbnew outset below",
                               "courtyard_outset_mm": fp["court_outset"], "pad_bbox": list(pb),
                               "pad_count": len(fp["pads"]),
                               "mating_normal": (_vec3(mating_normals[ref], f"mating_normals[{ref}]") if mating_normals and ref in mating_normals else None),
                               "mating_normal_status": "declared" if mating_normals and ref in mating_normals else "unmeasured"})

    envelope: dict[str, dict] = {}
    for ref in sorted(by_ref):
        e = (height_envelope_mm or {}).get(ref)
        if e is None:
            envelope[ref] = {"status": "unmeasured"}
            continue
        if (not isinstance(e, dict) or not isinstance(e.get("z_max_above_board_top_mm"), (int, float))
                or isinstance(e.get("z_max_above_board_top_mm"), bool) or not isinstance(e.get("evidence"), str) or not e["evidence"]):
            raise C04GateInputError(f"C04_MANIFEST_INPUT_FIELD: height_envelope_mm[{ref}] needs numeric z_max_above_board_top_mm and a non-empty evidence string")
        envelope[ref] = {"status": "declared", "z_max_above_board_top_mm": float(e["z_max_above_board_top_mm"]),
                         "z_min_below_board_top_mm": float(e.get("z_min_below_board_top_mm", 0.0)), "evidence": e["evidence"]}

    return {"ok": True, "schema": SCHEMA, "units": "mm", "thickness": thickness, "outline": _r6(outline),
            "mounting_holes": holes, "connectors": connectors, "component_height_envelope": _r6(envelope),
            "exported_outline_sha256": canonical_sha256(_r6(outline)),
            "exported_mounting_holes_sha256": canonical_sha256(holes),
            "measured": {"mounting_holes": {"status": "measured", "count": len(holes),
                                            "rule": "drilled pads of footprints with ref prefix H/MH that are through_hole or carry an NP pad",
                                            "hole_footprints": hole_fps},
                         "other_drilled_np_pads": other_np,
                         "outline_loops": len(loops), "footprints_on_board": len(by_ref)},
            "inputs": {"board_sha256": _sha256(board_path)}}
