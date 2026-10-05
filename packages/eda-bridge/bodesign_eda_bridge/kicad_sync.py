"""Schematic placement-only differential sync; no electrical merge is implied."""

from copy import deepcopy
import math
from pathlib import Path
import re


def _tree(text):
    stack, roots = [], []
    tokens = re.compile(r'\s+|"(?:\\.|[^"\\])*"|[()]|[^\s()"]+')
    end = 0
    for match in tokens.finditer(text):
        if match.start() != end:
            raise ValueError("KICAD_SYNC_INVALID_SEXPR")
        end = match.end()
        token = match.group()
        if token.isspace():
            continue
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError("KICAD_SYNC_INVALID_SEXPR")
            stack.pop()
        else:
            if not stack:
                raise ValueError("KICAD_SYNC_INVALID_SEXPR")
            if token.startswith('"'):
                token = re.sub(r'\\(.)', r'\1', token[1:-1])
            stack[-1].append(token)
    if end != len(text) or stack or len(roots) != 1:
        raise ValueError("KICAD_SYNC_INVALID_SEXPR")
    return roots[0]


def _pose(value):
    result = {}
    for key in ("x", "y", "rotation"):
        if key not in value or value[key] is None:
            raise ValueError(f"KICAD_SYNC_MISSING_POSE: {key}")
        number = value[key]
        if isinstance(number, bool):
            raise ValueError("KICAD_SYNC_INVALID_POSE")
        number = float(number)
        if not math.isfinite(number):
            raise ValueError("KICAD_SYNC_INVALID_POSE")
        result[key] = number
    return result


def _placements(path):
    root = _tree(Path(path).read_text(encoding="utf-8"))
    if not root or root[0] != "kicad_sch":
        raise ValueError("KICAD_SYNC_EXPECTED_SCHEMATIC")
    placements = {}
    for node in root[1:]:
        if not isinstance(node, list) or not node or node[0] != "symbol":
            continue
        ats = [n for n in node if isinstance(n, list) and n and n[0] == "at"]
        refs = [n[2] for n in node if isinstance(n, list) and len(n) >= 3
                and n[:2] == ["property", "Reference"]]
        if len(refs) != 1 or len(ats) != 1 or len(ats[0]) != 4:
            raise ValueError("KICAD_SYNC_MISSING_OR_AMBIGUOUS_PLACEMENT")
        ref = refs[0]
        if ref in placements:
            raise ValueError(f"KICAD_SYNC_DUPLICATE_REFERENCE: {ref}")
        placements[ref] = _pose(dict(zip(("x", "y", "rotation"), ats[0][1:])))
    return placements


def diff_kicad_schematic(baseline_sch_path, current_sch_path) -> dict:
    """Return ref -> current x/y/rotation for moved or rotated instances.

    Added/deleted references and multi-unit duplicate references are rejected:
    they cannot be merged honestly by this placement-only interface.
    Library definitions and property text positions are not instances.
    """
    before, after = _placements(baseline_sch_path), _placements(current_sch_path)
    if before.keys() != after.keys():
        raise ValueError(f"KICAD_SYNC_COMPONENT_SET_CHANGED: added={sorted(after.keys() - before.keys())}, "
                         f"removed={sorted(before.keys() - after.keys())}")
    return {ref: after[ref] for ref in sorted(after) if before[ref] != after[ref]}


def apply_user_pinning(design_ir, modified_components):
    """Copy a composer-spec dict, recording human poses in component x/y/rotation.

    The input is never mutated, including on validation failure. Unknown or
    ambiguous references fail rather than losing a human edit.
    """
    result = deepcopy(design_ir)
    by_ref = {}
    for component in result["components"]:
        ref = component["ref"]
        if ref in by_ref:
            raise ValueError(f"KICAD_SYNC_DUPLICATE_REFERENCE: {ref}")
        by_ref[ref] = component
    for ref, pose in modified_components.items():
        if ref not in by_ref:
            raise ValueError(f"KICAD_SYNC_UNKNOWN_REFERENCE: {ref}")
        by_ref[ref].update(_pose(pose), user_pinned=True)
    return result
