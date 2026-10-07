"""bodesign_c02_mesh_gate: deterministic printable-enclosure mesh gates M-01..M-06 (DD-19, c04-entry-freeze 2.2/2.3).

Pure python (no numpy / trimesh dependency in core). ``trimesh`` is imported ONLY as an optional
cross-check when importable; it never changes a verdict (``measured.trimesh_crosscheck`` says so).

Honesty rules (AGENTS.md section 2): missing/unreadable inputs raise ``C02MeshInputError``; a gate that
cannot be computed robustly is ``unmeasured`` with a reason and is NEVER ``pass``.

Gates (per STL part unless noted):
  M-01 nonempty valid mesh: triangle count, degenerate (zero-area / collapsed / non-finite) triangles.
  M-02 half-edge topology after vertex welding (1e-5 mm): every undirected edge shared by exactly 2 faces
       (manifold), none by 1 (watertight), no edge with same-direction twins (consistent orientation), and
       signed volume > 0 (outward normals). Stored STL normals are ignored; winding is authoritative.
  M-03 bbox extents vs declared ``expected_bbox_mm`` within declared ``bbox_tol_mm`` (axis-ordered, no rotation).
  M-04 wall thickness: ray from the centroid of sampled faces along -normal, first hit distance. LIMITS: the
       sampled normal-direction distance, not a true minimum thickness; it can OVER-estimate at oblique or
       curved walls and misses thin features between samples; samples are a deterministic stride over the
       non-degenerate faces (count reported). Needs M-02 pass (inward direction is undefined otherwise).
  M-05 (assembly) board clearance: needs ``board_manifest_path`` AND a ``board_placement_mm`` registration
       (explicit argument wins; else the C02' manifest's ``board_placement_mm``; the origin is reported as
       ``measured.placement_source`` = argument | c02_manifest); the extruded bare board outline (top/bottom faces sampled) must be enclosed (even ray parity
       and a hit in all six axis directions) and >= clearance from every surface. LIMITS: component heights and
       connector protrusions are not modelled; enclosure is a necessary-not-sufficient test; sample count capped.
  M-06 (assembly) chain: ``consumed_board_outline_sha256`` of the C02' manifest == board manifest
       ``exported_outline_sha256``.
"""
from __future__ import annotations

import json
import math
import os
import re
import struct
import sys
from typing import Any

from .c04_gate import _sha256
from .c04_manifest import canonical_sha256

GATE_IDS = ("M-01", "M-02", "M-03", "M-04", "M-05", "M-06")
WELD_DECIMALS = 5
AREA_EPS_MM2 = 1e-9
DEFAULT_WALL_SAMPLES = 2000
DEFAULT_CLEARANCE_SAMPLES = 600
_OFFENDER_CAP = 20
_RAY_EPS = 1e-5


class C02MeshInputError(ValueError):
    """Explicit fail-fast input error (never a silent default)."""


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _add(a, b, k=1.0):
    return (a[0] + k * b[0], a[1] + k * b[1], a[2] + k * b[2])


# --------------------------------------------------------------------------------------- STL loading
def load_stl(path: str) -> dict:
    """{"format", "triangles":[((x,y,z)*3)...], "problem": str|None}. A malformed file is a problem, not a raise."""
    if not isinstance(path, str) or not path:
        raise C02MeshInputError("C02_MESH_INPUT_MISSING: stl_path is required (non-empty path string)")
    if not os.path.isfile(path):
        raise C02MeshInputError(f"C02_MESH_INPUT_NOT_FOUND: stl_path={path!r} does not exist or is not a file")
    if not path.lower().endswith(".stl"):
        raise C02MeshInputError(f"C02_MESH_INPUT_SUFFIX: stl_path={path!r} must end with .stl")
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if len(data) == 84 + 50 * n:
            tris = []
            for i in range(n):
                f = struct.unpack("<12f", data[84 + 50 * i: 84 + 50 * i + 48])
                tris.append(((f[3], f[4], f[5]), (f[6], f[7], f[8]), (f[9], f[10], f[11])))
            return {"format": "binary", "triangles": tris, "problem": None}
    if data.lstrip()[:5].lower() == b"solid":
        found = re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)
        try:
            pts = [(float(a), float(b), float(c)) for a, b, c in found]
        except ValueError:
            return {"format": "ascii", "triangles": [], "problem": "ascii STL vertex is not a number"}
        if not pts or len(pts) % 3:
            return {"format": "ascii", "triangles": [],
                    "problem": f"ascii STL has {len(pts)} vertices (not a positive multiple of 3)"}
        return {"format": "ascii", "triangles": [tuple(pts[i:i + 3]) for i in range(0, len(pts), 3)], "problem": None}
    return {"format": "unknown", "triangles": [],
            "problem": "not a binary STL (size != 84+50*n) and no ascii 'solid' header"}


def prepare(tris: list) -> dict:
    """Weld vertices and classify triangles. Returns verts, faces [(a,b,c,orig)], degenerate/nonfinite orig indices."""
    vmap: dict[tuple, int] = {}
    verts: list[tuple] = []
    faces: list[tuple] = []
    degenerate: list[int] = []
    nonfinite: list[int] = []
    for oi, tri in enumerate(tris):
        if not all(math.isfinite(c) for p in tri for c in p):
            nonfinite.append(oi)
            continue
        idx = []
        for p in tri:
            k = tuple(round(c, WELD_DECIMALS) + 0.0 for c in p)
            if k not in vmap:
                vmap[k] = len(verts)
                verts.append(k)
            idx.append(vmap[k])
        a, b, c = (verts[i] for i in idx)
        cr = _cross(_sub(b, a), _sub(c, a))
        area = 0.5 * math.sqrt(_dot(cr, cr))
        if len(set(idx)) < 3 or area < AREA_EPS_MM2:
            degenerate.append(oi)
            continue
        faces.append((idx[0], idx[1], idx[2], oi))
    return {"verts": verts, "faces": faces, "degenerate": degenerate, "nonfinite": nonfinite}


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def gate_m01(loaded: dict, prep: dict) -> dict:
    n = len(loaded["triangles"])
    meas = {"format": loaded["format"], "triangle_count": n, "valid_triangle_count": len(prep["faces"]),
            "degenerate_count": len(prep["degenerate"]), "nonfinite_count": len(prep["nonfinite"]),
            "degenerate_area_eps_mm2": AREA_EPS_MM2, "weld_decimals": WELD_DECIMALS}
    offenders = [{"kind": "degenerate", "triangle": i} for i in prep["degenerate"][:_OFFENDER_CAP]]
    offenders += [{"kind": "nonfinite", "triangle": i} for i in prep["nonfinite"][:_OFFENDER_CAP]]
    if loaded["problem"]:
        meas["problem"] = loaded["problem"]
        return {"status": "fail", "measured": meas, "offenders": [{"kind": "unreadable", "reason": loaded["problem"]}]}
    ok = n > 0 and not prep["degenerate"] and not prep["nonfinite"] and bool(prep["faces"])
    if n == 0:
        offenders.append({"kind": "empty", "reason": "zero triangles"})
    return {"status": _status(ok), "measured": meas, "offenders": offenders}


def gate_m02(prep: dict) -> dict:
    verts, faces = prep["verts"], prep["faces"]
    if not faces:
        return {"status": "unmeasured", "measured": {"reason": "no valid triangles"}, "offenders": []}
    directed: dict[tuple, int] = {}
    for a, b, c, _ in faces:
        for e in ((a, b), (b, c), (c, a)):
            directed[e] = directed.get(e, 0) + 1
    und: dict[tuple, int] = {}
    for (a, b), c in directed.items():
        k = (a, b) if a < b else (b, a)
        und[k] = und.get(k, 0) + c
    boundary = sorted(k for k, c in und.items() if c == 1)
    nonman = sorted(k for k, c in und.items() if c > 2)
    inconsistent = sorted(k for k, c in und.items()
                          if c == 2 and (directed.get(k, 0) == 2 or directed.get((k[1], k[0]), 0) == 2))
    vol = 0.0
    for a, b, c, _ in faces:
        vol += _dot(verts[a], _cross(verts[b], verts[c])) / 6.0
    parent: dict[int, int] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c, _ in faces:
        for x in (b, c):
            parent[find(x)] = find(a)
    comps = len({find(v) for f in faces for v in f[:3]})

    def edge(k):
        return [list(verts[k[0]]), list(verts[k[1]])]
    offenders = ([{"kind": "boundary_edge", "edge": edge(k)} for k in boundary[:_OFFENDER_CAP]]
                 + [{"kind": "non_manifold_edge", "edge": edge(k), "faces": und[k]} for k in nonman[:_OFFENDER_CAP]]
                 + [{"kind": "inconsistent_orientation_edge", "edge": edge(k)} for k in inconsistent[:_OFFENDER_CAP]])
    if not boundary and not nonman and not inconsistent and vol <= 1e-9:
        offenders.append({"kind": "inverted_or_zero_volume_shell", "signed_volume_mm3": round(vol, 6)})
    ok = not boundary and not nonman and not inconsistent and vol > 1e-9
    meas = {"edges": len(und), "faces": len(faces), "vertices": len({v for f in faces for v in f[:3]}),
            "boundary_edges": len(boundary), "non_manifold_edges": len(nonman),
            "inconsistent_orientation_edges": len(inconsistent), "signed_volume_mm3": round(vol, 6),
            "components": comps, "method": "pure-python half-edge count after 1e-5 mm vertex weld"}
    return {"status": _status(ok), "measured": meas, "offenders": offenders}


def _trimesh_crosscheck(prep: dict, m02: dict) -> dict:
    try:
        import trimesh  # type: ignore
    except Exception:
        return {"available": False, "note": "trimesh not importable; cross-check skipped (verdicts never depend on it)"}
    try:
        tm = trimesh.Trimesh(vertices=prep["verts"], faces=[f[:3] for f in prep["faces"]], process=False)
        theirs = {"is_watertight": bool(tm.is_watertight), "is_winding_consistent": bool(tm.is_winding_consistent)}
        m = m02["measured"]
        mine = {"is_watertight": m.get("boundary_edges") == 0 and m.get("non_manifold_edges") == 0,
                "is_winding_consistent": m.get("inconsistent_orientation_edges") == 0}
        return {"available": True, "trimesh": theirs, "bodesign": mine, "agree": theirs == mine,
                "note": "cross-check only; never changes a verdict"}
    except Exception as e:  # cross-check must not break the gate
        return {"available": True, "error": f"{type(e).__name__}: {e}", "note": "cross-check failed; verdicts unaffected"}


def _num(v: Any, what: str, positive: bool = True) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (positive and v <= 0):
        raise C02MeshInputError(f"C02_MESH_INPUT_FIELD: {what} must be a finite {'positive ' if positive else ''}number, got {v!r}")
    return float(v)


def _extent(prep: dict) -> tuple[list[float], list[float]]:
    vs = [prep["verts"][i] for f in prep["faces"] for i in f[:3]]
    return [min(v[k] for v in vs) for k in range(3)], [max(v[k] for v in vs) for k in range(3)]


def gate_m03(prep: dict, expected: Any, tol: Any) -> dict:
    if expected is None:
        return {"status": "unmeasured", "measured": {"reason": "expected_bbox_mm not declared"}, "offenders": []}
    if not isinstance(expected, list) or len(expected) != 3:
        raise C02MeshInputError("C02_MESH_INPUT_FIELD: expected_bbox_mm must be [x, y, z] extents in mm")
    exp = [_num(v, "expected_bbox_mm") for v in expected]
    if tol is None:
        raise C02MeshInputError("C02_MESH_INPUT_MISSING: bbox_tol_mm is required when expected_bbox_mm is declared (no default tolerance)")
    tol = _num(tol, "bbox_tol_mm", positive=False)
    if not prep["faces"]:
        return {"status": "unmeasured", "measured": {"reason": "no valid triangles"}, "offenders": []}
    lo, hi = _extent(prep)
    ext = [hi[k] - lo[k] for k in range(3)]
    offenders = [{"axis": "xyz"[k], "measured_mm": round(ext[k], 6), "expected_mm": exp[k],
                  "ratio": round(ext[k] / exp[k], 4)} for k in range(3) if abs(ext[k] - exp[k]) > tol]
    return {"status": "fail" if offenders else "pass",
            "measured": {"extents_mm": [round(v, 6) for v in ext], "min_mm": [round(v, 6) for v in lo],
                         "max_mm": [round(v, 6) for v in hi], "expected_bbox_mm": exp, "bbox_tol_mm": tol,
                         "method": "axis-ordered extents of valid triangles, no rotation; units assumed mm (STL carries none)"},
            "offenders": offenders}


def _tri_data(prep: dict) -> list[tuple]:
    out = []
    v = prep["verts"]
    for a, b, c, oi in prep["faces"]:
        out.append((v[a], _sub(v[b], v[a]), _sub(v[c], v[a]), oi))
    return out


def _first_hit(o, d, tris: list, skip: int = -1) -> float | None:
    """Smallest t > _RAY_EPS of ray o + t*d against triangles (Moller-Trumbore, double sided)."""
    best = None
    d0, d1, d2 = d
    for k, (v0, e1, e2, _) in enumerate(tris):
        if k == skip:
            continue
        px, py, pz = d1 * e2[2] - d2 * e2[1], d2 * e2[0] - d0 * e2[2], d0 * e2[1] - d1 * e2[0]
        det = e1[0] * px + e1[1] * py + e1[2] * pz
        if -1e-12 < det < 1e-12:
            continue
        inv = 1.0 / det
        tx, ty, tz = o[0] - v0[0], o[1] - v0[1], o[2] - v0[2]
        u = (tx * px + ty * py + tz * pz) * inv
        if u < 0.0 or u > 1.0:
            continue
        qx, qy, qz = ty * e1[2] - tz * e1[1], tz * e1[0] - tx * e1[2], tx * e1[1] - ty * e1[0]
        w = (d0 * qx + d1 * qy + d2 * qz) * inv
        if w < 0.0 or u + w > 1.0:
            continue
        t = (e2[0] * qx + e2[1] * qy + e2[2] * qz) * inv
        if t > _RAY_EPS and (best is None or t < best):
            best = t
    return best


def gate_m04(prep: dict, m02: dict, wall_min: Any, samples: int) -> dict:
    wall_min = _num(wall_min, "wall_min_mm")
    if m02["status"] != "pass":
        return {"status": "unmeasured", "offenders": [],
                "measured": {"reason": f"M-02 is {m02['status']}: inward direction is undefined on a non-manifold/open/inverted mesh"}}
    tris = _tri_data(prep)
    n = len(tris)
    idxs = list(range(n)) if n <= samples else sorted({int(i * n / samples) for i in range(samples)})
    th: list[float] = []
    offenders: list[dict] = []
    no_hit = 0
    for k in idxs:
        v0, e1, e2, oi = tris[k]
        nn = _cross(e1, e2)
        ln = math.sqrt(_dot(nn, nn))
        nn = (nn[0] / ln, nn[1] / ln, nn[2] / ln)
        cen = (v0[0] + (e1[0] + e2[0]) / 3, v0[1] + (e1[1] + e2[1]) / 3, v0[2] + (e1[2] + e2[2]) / 3)
        t = _first_hit(cen, (-nn[0], -nn[1], -nn[2]), tris, skip=k)
        if t is None:
            no_hit += 1
            continue
        th.append(t)
        if t < wall_min - 1e-9 and len(offenders) < _OFFENDER_CAP:
            offenders.append({"triangle": oi, "point_mm": [round(c, 4) for c in cen], "thickness_mm": round(t, 4),
                              "required_mm": wall_min})
    meas = {"wall_min_mm": wall_min, "faces_total": n, "samples": len(idxs), "sampled_all_faces": len(idxs) == n,
            "no_hit_samples": no_hit, "min_thickness_mm": round(min(th), 4) if th else None,
            "method": "ray from each sampled face centroid along -outward-normal (winding), first hit distance",
            "limits": "sampled normal-direction distance, not a true minimum thickness: over-estimates at oblique/curved "
                      "walls, misses thin features between samples (deterministic stride when faces > samples)"}
    if not th:
        meas["reason"] = "no ray hit any surface"
        return {"status": "unmeasured", "measured": meas, "offenders": []}
    n_bad = sum(1 for t in th if t < wall_min - 1e-9)
    meas["samples_below_threshold"] = n_bad
    return {"status": "fail" if n_bad else "pass", "measured": meas, "offenders": offenders}


_PARITY_DIR = (0.57735, 0.31415, 0.75431)  # skew direction: avoids axis-aligned edge/vertex grazing
_AXES = (("+x", (1.0, 0.0, 0.0)), ("-x", (-1.0, 0.0, 0.0)), ("+y", (0.0, 1.0, 0.0)),
         ("-y", (0.0, -1.0, 0.0)), ("+z", (0.0, 0.0, 1.0)), ("-z", (0.0, 0.0, -1.0)))
_WORK_BUDGET = 6_000_000  # triangle tests allowed for M-05 (pure python)


def _count_hits(o, d, tris: list) -> int:
    n = 0
    d0, d1, d2 = d
    for v0, e1, e2, _ in tris:
        px, py, pz = d1 * e2[2] - d2 * e2[1], d2 * e2[0] - d0 * e2[2], d0 * e2[1] - d1 * e2[0]
        det = e1[0] * px + e1[1] * py + e1[2] * pz
        if -1e-12 < det < 1e-12:
            continue
        inv = 1.0 / det
        tx, ty, tz = o[0] - v0[0], o[1] - v0[1], o[2] - v0[2]
        u = (tx * px + ty * py + tz * pz) * inv
        if u < 0.0 or u > 1.0:
            continue
        qx, qy, qz = ty * e1[2] - tz * e1[1], tz * e1[0] - tx * e1[2], tx * e1[1] - ty * e1[0]
        w = (d0 * qx + d1 * qy + d2 * qz) * inv
        if w < 0.0 or u + w > 1.0:
            continue
        if (e2[0] * qx + e2[1] * qy + e2[2] * qz) * inv > _RAY_EPS:
            n += 1
    return n


def _pt_tri_dist(p, v0, e1, e2) -> float:
    """Distance from p to triangle (v0, v0+e1, v0+e2) (Ericson, closest point on triangle)."""
    a = v0
    b = (v0[0] + e1[0], v0[1] + e1[1], v0[2] + e1[2])
    c = (v0[0] + e2[0], v0[1] + e2[1], v0[2] + e2[2])
    ab, ac, ap = e1, e2, _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        q = a
    else:
        bp = _sub(p, b)
        d3, d4 = _dot(ab, bp), _dot(ac, bp)
        cp = _sub(p, c)
        d5, d6 = _dot(ab, cp), _dot(ac, cp)
        vc = d1 * d4 - d3 * d2
        vb = d5 * d2 - d1 * d6
        va = d3 * d6 - d5 * d4
        if d3 >= 0 and d4 <= d3:
            q = b
        elif vc <= 0 and d1 >= 0 and d3 <= 0:
            q = _add(a, ab, d1 / (d1 - d3))
        elif d6 >= 0 and d5 <= d6:
            q = c
        elif vb <= 0 and d2 >= 0 and d6 <= 0:
            q = _add(a, ac, d2 / (d2 - d6))
        elif va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
            q = _add(b, _sub(c, b), (d4 - d3) / ((d4 - d3) + (d5 - d6)))
        else:
            den = 1.0 / (va + vb + vc)
            q = _add(_add(a, ab, vb * den), ac, vc * den)
    dv = _sub(p, q)
    return math.sqrt(_dot(dv, dv))


def _load_json(path: Any, arg: str) -> dict:
    if not isinstance(path, str) or not path or not os.path.isfile(path):
        raise C02MeshInputError(f"C02_MESH_INPUT_NOT_FOUND: {arg}={path!r} does not exist or is not a file")
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        raise C02MeshInputError(f"C02_MESH_INPUT_FORMAT: {arg}={path!r} is not readable JSON: {e}") from None
    if not isinstance(d, dict):
        raise C02MeshInputError(f"C02_MESH_INPUT_FORMAT: {arg}={path!r} top level is not an object")
    return d


def gate_m05(tris: list, board: dict | None, placement: Any, clearance: float | None) -> dict:
    """Assembly gate over the union of all parts (board bare outline extruded by thickness)."""
    if board is None:
        return {"status": "unmeasured", "measured": {"reason": "board_manifest_path not given"}, "offenders": []}
    if placement is None:
        return {"status": "unmeasured", "offenders": [],
                "measured": {"reason": "board_placement_mm [dx,dy,dz] not declared: board-to-enclosure registration is never guessed"}}
    if not isinstance(placement, list) or len(placement) != 3:
        raise C02MeshInputError("C02_MESH_INPUT_FIELD: board_placement_mm must be [dx, dy, dz] (mm)")
    dx, dy, dz = (_num(v, "board_placement_mm", positive=False) for v in placement)
    poly = (board.get("outline") or {}).get("polygon")
    th = board.get("thickness")
    if not isinstance(poly, list) or len(poly) < 3 or not isinstance(th, (int, float)) or th <= 0:
        raise C02MeshInputError("C02_MESH_INPUT_FORMAT: board manifest lacks outline.polygon / thickness")
    if not tris:
        return {"status": "unmeasured", "measured": {"reason": "no valid triangles"}, "offenders": []}
    pts = [(x + dx, y + dy, z) for x, y in poly for z in (dz, dz + float(th))]
    passes = 8
    cap = max(0, _WORK_BUDGET // (passes * len(tris)))
    if cap < 8:
        return {"status": "unmeasured", "offenders": [],
                "measured": {"reason": f"mesh too large for the pure-python budget ({len(tris)} triangles); not sampled"}}
    stride = max(1, math.ceil(len(pts) / cap))
    pts = pts[::stride]
    offenders: list[dict] = []
    worst = None
    for p in pts:
        enclosed = all(_first_hit(p, d, tris) is not None for _, d in _AXES)
        parity = _count_hits(p, _PARITY_DIR, tris) % 2
        dist = min(_pt_tri_dist(p, v0, e1, e2) for v0, e1, e2, _ in tris)
        worst = dist if worst is None else min(worst, dist)
        reason = "outside enclosure" if not enclosed else "inside wall material" if parity else None
        if reason or dist < clearance - 1e-9:
            if len(offenders) < _OFFENDER_CAP:
                offenders.append({"point_mm": [round(c, 4) for c in p], "distance_mm": round(dist, 4),
                                  "required_mm": clearance, "reason": reason or "clearance"})
    return {"status": "fail" if offenders else "pass", "offenders": offenders,
            "measured": {"clearance_min_mm": clearance, "min_distance_mm": round(worst, 4), "points_tested": len(pts),
                         "board_placement_mm": [dx, dy, dz], "board_thickness_mm": float(th),
                         "method": "outline vertices at board bottom/top, translated by board_placement_mm; point is in the cavity when "
                                   "rays in all six axis directions hit a surface and skew-ray parity is even; distance = min point-triangle distance",
                         "limits": "translation only (no rotation/flip registration); component heights, connector protrusions and the "
                                   "board interior between outline vertices are not tested; necessary-not-sufficient; parts must not overlap"}}


def gate_m06(board: dict | None, c02: dict | None) -> dict:
    if board is None or c02 is None:
        return {"status": "unmeasured", "offenders": [],
                "measured": {"reason": "needs both board_manifest_path and c02_manifest_path"}}
    exp = board.get("exported_outline_sha256")
    own = canonical_sha256(board.get("outline")) if board.get("outline") is not None else None
    got = c02.get("consumed_board_outline_sha256")
    meas = {"board_exported_outline_sha256": exp, "board_outline_recomputed_sha256": own, "consumed_board_outline_sha256": got}
    if not exp or not got:
        meas["reason"] = "exported_outline_sha256 / consumed_board_outline_sha256 absent"
        return {"status": "unmeasured", "measured": meas, "offenders": []}
    off = []
    if own != exp:
        off.append({"kind": "STALE_BOARD_MANIFEST", "detail": "board manifest outline no longer hashes to its exported_outline_sha256"})
    if got != exp:
        off.append({"kind": "STALE_UPSTREAM_MANIFEST", "detail": "C02' consumed_board_outline_sha256 != board exported_outline_sha256"})
    hexp, hgot = board.get("exported_mounting_holes_sha256"), c02.get("consumed_mounting_holes_sha256")
    meas["mounting_holes_chain"] = {"board": hexp, "consumed": hgot}
    if hexp and hgot and hexp != hgot:
        off.append({"kind": "STALE_UPSTREAM_MANIFEST", "detail": "consumed_mounting_holes_sha256 != exported_mounting_holes_sha256"})
    return {"status": "fail" if off else "pass", "measured": meas, "offenders": off}


def c02_mesh_gate(stl_paths: Any, wall_min_mm: Any = None, *, board_manifest_path: Any = None,
                  c02_manifest_path: Any = None, clearance_min_mm: Any = None, expected_bbox_mm: Any = None,
                  bbox_tol_mm: Any = None, board_placement_mm: Any = None, wall_samples: Any = None) -> dict:
    """Run M-01..M-04 per STL part and M-05/M-06 over the assembly. Never mutates inputs.

    ``expected_bbox_mm``: [x,y,z] applied to every part, or {basename: [x,y,z]} (every part must then be named).
    """
    if isinstance(stl_paths, str):
        stl_paths = [stl_paths]
    if not isinstance(stl_paths, list) or not stl_paths or not all(isinstance(p, str) and p for p in stl_paths):
        raise C02MeshInputError("C02_MESH_INPUT_MISSING: stl_path is required (one path string or a non-empty list)")
    if wall_min_mm is None:
        raise C02MeshInputError("C02_MESH_INPUT_MISSING: wall_min_mm is required (no default wall threshold)")
    wall = _num(wall_min_mm, "wall_min_mm")
    samples = DEFAULT_WALL_SAMPLES if wall_samples is None else int(_num(wall_samples, "wall_samples"))
    if board_manifest_path is not None and clearance_min_mm is None:
        raise C02MeshInputError("C02_MESH_INPUT_MISSING: clearance_min_mm is required when board_manifest_path is given")
    clearance = None if clearance_min_mm is None else _num(clearance_min_mm, "clearance_min_mm", positive=False)
    board = None if board_manifest_path is None else _load_json(board_manifest_path, "board_manifest_path")
    c02 = None if c02_manifest_path is None else _load_json(c02_manifest_path, "c02_manifest_path")
    names = [os.path.basename(p) for p in stl_paths]
    if len(set(names)) != len(names):
        raise C02MeshInputError(f"C02_MESH_INPUT_FIELD: duplicate STL basenames {sorted(names)}")
    if isinstance(expected_bbox_mm, dict):
        absent = [n for n in names if n not in expected_bbox_mm]
        if absent:
            raise C02MeshInputError(f"C02_MESH_INPUT_FIELD: expected_bbox_mm has no entry for {absent}")
    parts: dict[str, dict] = {}
    all_tris: list = []
    for path, name in zip(stl_paths, names):
        loaded = load_stl(path)
        prep = prepare(loaded["triangles"])
        m01, m02 = gate_m01(loaded, prep), gate_m02(prep)
        exp = expected_bbox_mm[name] if isinstance(expected_bbox_mm, dict) else expected_bbox_mm
        parts[name] = {"M-01": m01, "M-02": m02, "M-03": gate_m03(prep, exp, bbox_tol_mm),
                       "M-04": gate_m04(prep, m02, wall, samples),
                       "trimesh_crosscheck": _trimesh_crosscheck(prep, m02), "sha256": _sha256(path)}
        if m02["status"] == "pass":
            all_tris += _tri_data(prep)
    all_pass = all(p["M-02"]["status"] == "pass" for p in parts.values())
    placement, placement_source = board_placement_mm, ("argument" if board_placement_mm is not None else None)
    if placement is None and c02 is not None and c02.get("board_placement_mm") is not None:
        placement, placement_source = c02["board_placement_mm"], "c02_manifest"
    if all_pass:
        m05 = gate_m05(all_tris, board, placement, clearance)
        m05["measured"]["placement_source"] = placement_source
    else:
        m05 = {"status": "unmeasured", "offenders": [],
               "measured": {"reason": "at least one part failed M-02; the cavity is undefined for a non-manifold/open part"}}
    asm = {"M-05": m05, "M-06": gate_m06(board, c02)}
    statuses = [g["status"] for p in parts.values() for k, g in p.items() if k.startswith("M-")]
    statuses += [g["status"] for g in asm.values()]
    unmeasured = sorted({f"{n}:{k}" for n, p in parts.items() for k, g in p.items() if k.startswith("M-") and g["status"] == "unmeasured"}
                        | {k for k, g in asm.items() if g["status"] == "unmeasured"})
    inputs = {"stl_sha256": {n: p["sha256"] for n, p in parts.items()}}
    if board_manifest_path:
        inputs["board_manifest_sha256"] = _sha256(board_manifest_path)
    if c02_manifest_path:
        inputs["c02_manifest_sha256"] = _sha256(c02_manifest_path)
    return {"ok": "fail" not in statuses and all(p["M-01"]["status"] == "pass" for p in parts.values()),
            "parts": parts, "assembly": asm, "unmeasured_gates": unmeasured, "inputs": inputs,
            "note": "ok = no measured gate failed; unmeasured gates are listed and never read as pass. Watertight is not printable (DD-19): "
                    "no slicer, process, fit or strength claim follows."}
