"""Deterministic DD-18 scene identity gates. Pixel colour is never judged.

S-05 measures axis-ordered STL extents only, not interfaces, CMF, image content,
physical fit or approval. Missing required evidence never becomes a pass.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter

from .c02_chain import _png_info
from .c02_mesh_gate import C02MeshInputError, load_stl
from .c04_gate import _sha256


class C01SceneInputError(ValueError):
    """Fail-fast malformed or unavailable scene inputs."""


def _error(message):
    raise C01SceneInputError("C01_SCENE_INPUT: " + message)


def _json(path):
    if not isinstance(path, str) or not os.path.isfile(path):
        _error(f"JSON file not found: {path!r}")
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, ValueError) as e:
        _error(f"unreadable JSON {path!r}: {e}")
    if not isinstance(value, dict):
        _error(f"JSON must be an object: {path!r}")
    return value


def _strings(value, field, nonempty=True):
    if (not isinstance(value, list) or (nonempty and not value)
            or any(not isinstance(v, str) or not v for v in value)):
        _error(f"{field} must be a list of nonempty strings")
    return value


def _gate(offenders):
    return {"status": "fail" if offenders else "pass", "offenders": offenders}


def c01_scene_gate(scene_manifest_path, c02_manifest_path=None, human_dir=None,
                   expected_bbox_mm=None, bbox_tol_mm=None, required_views=None, stage_prefix="c01-"):
    """Check S-01..S-05 without rendering or judging pixel colour/content."""
    m = _json(scene_manifest_path)
    try:
        digest = _sha256(scene_manifest_path)
    except OSError as e:
        _error(str(e))
    base = os.path.dirname(os.path.abspath(scene_manifest_path))
    paths = m.get("consumed_enclosure_mesh_path")
    hashes = m.get("consumed_enclosure_mesh_sha256")
    if not isinstance(paths, dict) or not paths or not isinstance(hashes, dict):
        _error("consumed_enclosure_mesh_path and consumed_enclosure_mesh_sha256 objects required")
    if set(paths) != set(hashes):
        _error("mesh path/hash part sets differ")
    assets, meshes = [], {}
    for part, path in paths.items():
        if not isinstance(path, str) or not path:
            _error(f"mesh path invalid: {part}")
        path = os.path.join(base, path)
        if not os.path.isfile(path):
            assets.append({"part": part, "path": path, "reason": "missing asset"})
            continue
        try:
            actual = _sha256(path)
            mesh = load_stl(path)
        except (OSError, C02MeshInputError) as e:
            _error(str(e))
        if mesh["problem"] or not mesh["triangles"]:
            _error(f"unparseable STL {path}: {mesh['problem'] or 'empty mesh'}")
        meshes[part] = mesh
        if actual != hashes[part]:
            assets.append({"part": part, "declared": hashes[part], "recomputed": actual,
                           "stale_side": "scene_manifest"})
    # Additional consumed_* paths are assets too, not just the enclosure meshes.
    for key, value in m.items():
        if key.startswith("consumed_") and key.endswith("_path") and key != "consumed_enclosure_mesh_path":
            values = value.values() if isinstance(value, dict) else [value]
            for path in values:
                if not isinstance(path, str) or not path:
                    _error(f"invalid asset path in {key}")
                if not os.path.isfile(os.path.join(base, path)):
                    assets.append({"field": key, "path": path, "reason": "missing asset"})
    primary = _gate(assets)
    secondary = {"status": "unmeasured", "reason": "c02_manifest_path not supplied"}
    if c02_manifest_path is not None:
        c02 = _json(c02_manifest_path)
        exported = c02.get("exported_enclosure_mesh_sha256")
        secondary = {"schema": c02.get("schema")}
        if exported is None:
            secondary.update(status="unmeasured", reason=f"c02_manifest schema {c02.get('schema')} carries no exported mesh sha")
        elif not isinstance(exported, dict):
            _error("exported_enclosure_mesh_sha256 must be an object")
        else:
            bad = [{"part": p, "consumed": hashes[p], "exported": exported.get(p),
                    "stale_side": "scene_manifest_vs_c02_manifest"} for p in hashes if hashes[p] != exported.get(p)]
            secondary.update(_gate(bad))
    s01 = {"status": "fail" if primary["status"] == "fail" or secondary["status"] == "fail" else
           ("unmeasured" if secondary["status"] == "unmeasured" else "pass"),
           "primary": primary, "secondary": secondary}
    bindings, materials = m.get("token_bindings"), m.get("materials")
    if not isinstance(bindings, dict) or not bindings or not isinstance(materials, dict) or not materials:
        _error("nonempty token_bindings and materials objects required")
    for token, surfaces in bindings.items():
        _strings(surfaces, f"token_bindings.{token}", False)
    universe = _strings(m.get("surfaces", sorted({s for ss in bindings.values() for s in ss})), "surfaces", False)
    counts = Counter(s for ss in bindings.values() for s in ss)
    undeclared, material_surfaces = [], []
    for name, material in materials.items():
        if not isinstance(material, dict) or not isinstance(material.get("token"), str):
            _error(f"material {name} requires token")
        if material["token"] not in bindings:
            undeclared.append(name)
        if "surfaces" in material:
            material_surfaces.extend(_strings(material["surfaces"], f"materials.{name}.surfaces", False))
    offenders = {"unbound_surfaces": sorted(s for s in universe if counts[s] == 0),
                 "orphan_tokens": sorted(t for t, ss in bindings.items() if not ss),
                 "double_bound_surfaces": sorted(s for s, n in counts.items() if n > 1),
                 "undeclared_material_tokens": undeclared,
                 "undeclared_surfaces": sorted((set(counts) | set(material_surfaces)) - set(universe))}
    s02 = {"status": "fail" if any(offenders.values()) else "pass", **offenders}
    views = _strings(m.get("declared_views"), "declared_views")
    required = views if required_views is None else _strings(required_views, "required_views")
    views = list(dict.fromkeys(views + required))
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", v) for v in views):
        _error("invalid declared view name")
    if not isinstance(stage_prefix, str) or not stage_prefix:
        _error("stage_prefix must be nonempty")
    directory = human_dir if human_dir is not None else m.get("human_tree_dir")
    if not isinstance(directory, str) or not os.path.isdir(directory):
        _error(f"human_dir is not a directory: {directory!r}")
    px = m.get("output_px")
    if not isinstance(px, list) or len(px) != 2 or any(type(n) is not int or n <= 0 for n in px):
        _error("output_px must be two positive integers")
    missing, invalid, unbound, reports, render_bad = [], [], [], {}, []
    renderer = m.get("renderer")
    if (not isinstance(renderer, dict) or any(not isinstance(renderer.get(k), str) or not renderer[k].strip()
                                             for k in ("name", "version"))):
        render_bad.append("renderer name/version missing or empty")
    if "seed" not in m or type(m["seed"]) is not int:
        render_bad.append("integer seed missing")
    try:
        names = os.listdir(directory)
    except OSError as e:
        _error(str(e))
    for view in views:
        pattern = re.compile(r"(?:[0-9]{2}\.)?" + re.escape(stage_prefix + view) + r"-v([0-9]+)\.png")
        candidates = sorted((int(match[1]), name) for name in names
                            if (match := pattern.fullmatch(name)))
        if not candidates:
            missing.append(view)
            continue
        version, name = candidates[-1]
        path = os.path.join(directory, name)
        info, reason = _png_info(path)
        if info is None or info["width"] < px[0] or info["height"] < px[1]:
            invalid.append({"view": view, "reason": reason or "below output_px"})
        sidepath = os.path.splitext(path)[0] + ".json"
        if not os.path.isfile(sidepath):
            unbound.append({"view": view, "reason": "sidecar missing"})
            render_bad.append(f"{view}: sidecar missing")
        else:
            side = _json(sidepath)
            if side.get("scene_manifest_sha256") != digest:
                unbound.append({"view": view, "reason": "scene manifest sha mismatch"})
            if side.get("renderer") != renderer:
                render_bad.append(f"{view}: renderer mismatch")
        reports[view] = {"file": name, "version": version, "png": info}
    s03 = {"status": "fail" if missing or invalid or unbound else "pass", "missing": missing,
           "invalid": invalid, "unbound": unbound, "views": reports}
    s04 = _gate(render_bad)
    if (expected_bbox_mm is None) != (bbox_tol_mm is None):
        _error("expected_bbox_mm and bbox_tol_mm must be supplied together")
    s05 = {"status": "unmeasured", "reason": "expected_bbox_mm and bbox_tol_mm not declared"}
    if expected_bbox_mm is not None:
        if (isinstance(bbox_tol_mm, bool) or not isinstance(bbox_tol_mm, (int, float))
                or not math.isfinite(bbox_tol_mm) or bbox_tol_mm < 0):
            _error("bbox_tol_mm must be finite and nonnegative")
        measured, bad = {}, []
        for part in paths:
            expected = expected_bbox_mm.get(part) if isinstance(expected_bbox_mm, dict) else expected_bbox_mm
            if (not isinstance(expected, (list, tuple)) or len(expected) != 3
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in expected)):
                _error(f"expected_bbox_mm requires positive finite XYZ extents for {part}")
            if part not in meshes:
                bad.append({"part": part, "reason": "asset missing"})
                continue
            vertices = [v for t in meshes[part]["triangles"] for v in t]
            if any(not math.isfinite(n) for v in vertices for n in v):
                _error(f"nonfinite STL vertices: {part}")
            extents = [max(v[i] for v in vertices) - min(v[i] for v in vertices) for i in range(3)]
            measured[part] = extents
            if any(abs(a-b) > bbox_tol_mm for a, b in zip(extents, expected)):
                bad.append({"part": part, "actual": extents, "expected": expected})
        s05 = {**_gate(bad), "bbox_mm": measured, "bbox_tol_mm": bbox_tol_mm}
    gates = dict(zip(("S-01", "S-02", "S-03", "S-04", "S-05"), (s01, s02, s03, s04, s05)))
    return {"ok": all(gates[g]["status"] == "pass" for g in ("S-01", "S-02", "S-03", "S-04")),
            "gates": gates, "inputs": {"scene_manifest_sha256": digest},
            "measured": {"notes": ["Pixel colour and image content are never judged.",
                                    "S-05 measures axis-ordered STL extents only and is not included in ok."]}}
