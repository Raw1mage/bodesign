"""Deterministic KiCad UUID change-map SVG, not native artwork or DRC.

Coordinates are millimetres. Footprint pad coordinates are transformed into
board coordinates. Net declarations have no UUID in KiCad: their name is their
identity. Electrical connectivity is NOT inferred from graphical wires.
"""

from hashlib import sha256
from html import escape
import math
from pathlib import Path

from .kicad_sync import _tree


def _children(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def _one(node, key):
    values = _children(node, key)
    if len(values) != 1:
        raise ValueError(f"VISUAL_FIELD_MISSING_OR_AMBIGUOUS: {key}")
    return values[0]


def _number(value):
    if isinstance(value, bool):
        raise ValueError("VISUAL_NONFINITE_COORDINATE")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("VISUAL_NONFINITE_COORDINATE")
    return result


def _point(node, key="at"):
    values = _one(node, key)
    if len(values) < 3:
        raise ValueError(f"VISUAL_INVALID_POINT: {key}")
    return [_number(values[1]), _number(values[2])]


def _snapshot(path):
    data = Path(path).read_bytes()
    root = _tree(data.decode("utf-8"))
    if not root or root[0] not in ("kicad_sch", "kicad_pcb"):
        raise ValueError("VISUAL_EXPECTED_KICAD_DOCUMENT")
    pcb = root[0] == "kicad_pcb"
    items, unsupported = {}, set()
    nets = {}
    if pcb:
        for net in _children(root, "net"):
            if len(net) != 3 or net[1] in nets:
                raise ValueError("VISUAL_INVALID_NET")
            nets[net[1]] = net[2]

    def visit(node, parent=None):
        kind = node[0]
        uuid = _one(node, "uuid")
        if len(uuid) != 2 or not uuid[1] or uuid[1] in items:
            raise ValueError("VISUAL_INVALID_OR_DUPLICATE_UUID")
        props = {p[1]: p[2] for p in _children(node, "property") if len(p) >= 3}
        attrs = {"properties": props}
        if kind in ("wire", "segment"):
            if kind == "wire":
                points = [[_number(x) for x in p[1:]] for p in _children(_one(node, "pts"), "xy")]
                if len(points) != 2 or any(len(p) != 2 for p in points):
                    raise ValueError("VISUAL_INVALID_WIRE")
            else:
                points = [_point(node, "start"), _point(node, "end")]
        else:
            points = [_point(node)]
            at = _one(node, "at")
            attrs["rotation"] = _number(at[3]) if len(at) == 4 else 0.0
        for key in ("layer", "layers", "width", "size", "drill", "lib_id", "net"):
            fields = _children(node, key)
            if fields:
                if len(fields) != 1:
                    raise ValueError(f"VISUAL_AMBIGUOUS_FIELD: {key}")
                attrs[key] = fields[0][1:]
        if pcb and "net" in attrs:
            net_id = attrs["net"][0]
            if net_id not in nets:
                raise ValueError(f"VISUAL_UNKNOWN_NET: {net_id}")
            attrs["net"] = nets[net_id]
        if kind in ("label", "global_label", "hierarchical_label", "pad", "footprint"):
            attrs["name"] = node[1]
        if parent is not None:
            origin, angle = parent
            angle = math.radians(angle)
            points = [[origin[0] + x * math.cos(angle) + y * math.sin(angle),
                       origin[1] - x * math.sin(angle) + y * math.cos(angle)] for x, y in points]
        items[uuid[1]] = {"kind": kind, "points": points, "attributes": attrs}
        if kind == "footprint":
            if _children(node, "zone"):
                unsupported.add("footprint/zone")
            for pad in _children(node, "pad"):
                if _children(pad, "primitives"):
                    unsupported.add("pad/primitives")
                visit(pad, (points[0], attrs["rotation"]))

    supported = ({"footprint", "segment", "via"} if pcb else
                 {"symbol", "wire", "label", "global_label", "hierarchical_label", "junction", "no_connect"})
    for node in root[1:]:
        if not isinstance(node, list) or not node:
            continue
        if node[0] in supported:
            visit(node)
        elif node[0] in {"arc", "zone", "sheet", "bus", "bus_entry", "group", "gr_line", "gr_arc", "gr_poly"}:
            unsupported.add(node[0])
    for name in sorted(set(nets.values()) - {""}):
        items[f"net:{name}"] = {"kind": "net", "points": [], "attributes": {"name": name}}
    return {"kind": root[0], "items": items, "unsupported": sorted(unsupported),
            "sha256": sha256(data).hexdigest()}


def generate_visual_diff(baseline_path, current_path, output_svg, *, diagnostics=None,
                         user_pinned_refs=()):
    """Write a draft SVG and return structured changes and evidence boundaries.

    ``diagnostics`` is None (not supplied) or a list of located findings with
    nonempty ``code``, ``source``, ``message`` and finite ``x``, ``y``. An empty
    list means only 'no supplied findings', never 'DRC passed'.
    ``user_pinned_refs`` supplies IR metadata, never inferred from movement.
    """
    target = Path(output_svg)
    if isinstance(user_pinned_refs, str) or not isinstance(user_pinned_refs, (list, tuple, set)) or any(
        not isinstance(ref, str) or not ref for ref in user_pinned_refs
    ):
        raise ValueError("VISUAL_INVALID_PINNED_REFS")
    if target.suffix.lower() != ".svg" or target.resolve() in {
        Path(baseline_path).resolve(), Path(current_path).resolve()
    }:
        raise ValueError("VISUAL_OUTPUT_MUST_BE_SEPARATE_SVG")
    before, after = _snapshot(baseline_path), _snapshot(current_path)
    if before["kind"] != after["kind"]:
        raise ValueError("VISUAL_DOCUMENT_KIND_MISMATCH")
    if diagnostics is not None and not isinstance(diagnostics, list):
        raise ValueError("VISUAL_INVALID_DIAGNOSTICS")
    findings = []
    for finding in diagnostics or []:
        if not isinstance(finding, dict) or any(
            not isinstance(finding.get(k), str) or not finding[k].strip()
            for k in ("code", "source", "message")
        ) or "x" not in finding or "y" not in finding:
            raise ValueError("VISUAL_LOCATED_DIAGNOSTIC_REQUIRED")
        findings.append({k: finding[k] for k in ("code", "source", "message")})
        findings[-1].update(x=_number(finding["x"]), y=_number(finding["y"]))
    changes = []
    for identity in sorted(before["items"].keys() | after["items"].keys()):
        old, new = before["items"].get(identity), after["items"].get(identity)
        if old == new:
            continue
        status = "added" if old is None else "removed" if new is None else "changed"
        ref = (new or old)["attributes"]["properties"].get("Reference") if "properties" in (new or old)["attributes"] else None
        changes.append({"id": identity, "status": status, "before": old, "after": new,
                        "user_pinned": ref in user_pinned_refs if ref else False})
    report = {"status": "draft", "human_approved": False, "png_rendered": False,
              "baseline_sha256": before["sha256"], "current_sha256": after["sha256"],
              "changes": changes, "diagnostics": findings,
              "diagnostics_status": "not_supplied" if diagnostics is None else "supplied_only_not_verified",
              "unsupported_present": sorted(set(before["unsupported"] + after["unsupported"])),
              "not_checked": ["Electrical connectivity and net equivalence", "Native DRC/ERC and spacing validation",
                              "Native symbol/footprint artwork", "Curved tracks, copper zones, hierarchical sheets"],
              "files": []}
    svg = _render(report, after["items"])
    target.write_text(svg, encoding="utf-8")
    report["files"] = [str(target)]
    return report


def _render(report, current):
    """Context geometry plus colour overlays and a non-overlapping change index."""
    all_points = [p for item in current.values() for p in item["points"]]
    all_points += [p for c in report["changes"] for p in (c["before"] or {"points": []})["points"]]
    all_points += [[f["x"], f["y"]] for f in report["diagnostics"]]
    min_x = min((p[0] for p in all_points), default=0)
    min_y = min((p[1] for p in all_points), default=0)
    max_x = max((p[0] for p in all_points), default=1)
    max_y = max((p[1] for p in all_points), default=1)
    scale = min(850 / max(max_x - min_x, 1), 350 / max(max_y - min_y, 1))
    def xy(p):
        return (40 + (p[0] - min_x) * scale, 160 + (p[1] - min_y) * scale)
    rows = []
    height = 590 + 22 * (len(report["changes"]) + len(report["diagnostics"]))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g font-family="sans-serif" font-size="13">',
             '<text x="20" y="25">DRAFT - change map only - not native artwork or design approval</text>',
             '<text x="20" y="48">Green: added | Yellow: changed | Gray dashed: removed/previous | Red: supplied finding</text>',
             f'<text x="20" y="71">Diagnostics: {escape(report["diagnostics_status"])}; no DRC/ERC executed</text>',
             '<text x="20" y="94">Not checked: connectivity, spacing, curved tracks, copper zones, hierarchical sheets</text>',
             f'<text x="20" y="117">Unsupported present: {escape(", ".join(report["unsupported_present"]) or "none detected in supported scan")}</text>']
    def draw(item, color, dashed=False):
        pts = [xy(p) for p in item["points"]]
        dash = ' stroke-dasharray="5 4"' if dashed else ''
        if len(pts) == 2:
            parts.append(f'<line x1="{pts[0][0]:.3f}" y1="{pts[0][1]:.3f}" x2="{pts[1][0]:.3f}" y2="{pts[1][1]:.3f}" stroke="{color}" stroke-width="3"{dash}/>')
        elif pts:
            parts.append(f'<circle cx="{pts[0][0]:.3f}" cy="{pts[0][1]:.3f}" r="5" fill="white" stroke="{color}" stroke-width="3"{dash}/>')
    for item in current.values():
        draw(item, "#cccccc")
    for index, change in enumerate(report["changes"], 1):
        old, new = change["before"], change["after"]
        if old:
            draw(old, "#777777", True)
        if new:
            draw(new, "#16803c" if change["status"] == "added" else "#e0ad00")
        points = (new or old)["points"]
        if points:
            x, y = xy(points[0])
            parts.append(f'<text x="{x + 7:.3f}" y="{y - 7:.3f}">{index}</text>')
        rows.append(f'{index}. {change["status"]}: {change["id"]}' + (' [user_pinned]' if change["user_pinned"] else ''))
    for finding in report["diagnostics"]:
        x, y = xy([finding["x"], finding["y"]])
        parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="10" fill="none" stroke="#cc2222" stroke-width="3"/>')
        rows.append(f'WARNING {finding["code"]} [{finding["source"]}]: {finding["message"]}')
    if not rows:
        rows.append("No changes in the supported geometry subset; not an electrical equivalence verdict.")
    for index, row in enumerate(rows):
        color = "#333333"
        if index < len(report["changes"]):
            color = {"added": "#16803c", "changed": "#e0ad00", "removed": "#777777"}[report["changes"][index]["status"]]
        elif report["diagnostics"]:
            color = "#cc2222"
        parts.append(f'<text x="20" y="{560 + index * 22}" fill="{color}" textLength="940" lengthAdjust="spacingAndGlyphs">{escape(row)}</text>')
    parts.append('</g></svg>')
    return '\n'.join(parts)
