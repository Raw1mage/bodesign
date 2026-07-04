"""M2-3 — placement-topology geometry + checker (protection/power/rf placement).

A large cluster of verified `control.*` objects gate the *placement topology* of
a component relative to an anchor point (a connector, a supply pin, a protected
net): "TVS within N mm of the I/O connector", "shunt in-line with the power
stage", "decoupling cap nearest the supply pin". This module is the pure-python,
zero-LLM, zero-pcbnew parser for those spatial relations, plus a checker that
gates a labelled component's distance-to-anchor on a threshold_block.

Scope decision (DD-6/DD-7, grounded in the ragbase threshold_block audit):
- Of the placement/power/rf/protection/esd controls, ONLY those carrying a
  *verbatim absolute distance* with a cited source anchor can be a clean T-A
  gate here. `control.esd.tvs-placement-routing` is that case ("TVS 到 connector
  距離≤10mm", TI slva680A / atlaspcb) — realised T-A landed.
- The rest (in-line/comparative topology, net-semantic classification, or no
  materialized threshold_block) are honest T-B backlog: the judgement is clear
  but the IR / threshold is not yet machine-readable. They are registered T-B,
  NOT hard-coded (no-fabrication).

Determinism: pure float math + a dict lookup; same IR + same threshold_block ->
byte-identical evidence dict.
"""

import math
from typing import Any

from ..validation_evidence import ValidationEvidence, ValidationFinding
from .errors import CheckerError

# The ORACLE_TOOLS member the envelope is emitted under. Placement topology is a
# deterministic layout/copper-domain judgement -> drc_gate is the closest
# registered oracle (validation_evidence enforces membership).
_ENVELOPE_TOOL = "drc_gate"


def _require_point(node: Any, path: str, missing: list[str]) -> tuple[float, float] | None:
    """Extract (x, y) from a point-bearing node, recording missing coords.

    Taxonomy:
      - name: _require_point
      - represents: strict coordinate extraction with no default substitution,
        shared by the anchor lookup and the component scan.
      - input: a node expected to carry x/y (dict), a dotted path for error
        reporting, and a mutable `missing` list to append missing paths onto.
      - output: (x, y) float tuple when BOTH present; None when any coord is
        missing (and the path is appended to `missing`).
      - must NOT be read as: returning (0, 0) or any default on absence — a
        missing coord is a hard fail surfaced via `missing`.
      - complete when: both x and y are present and float-coercible, or the
        missing paths have been recorded.
    """
    if not isinstance(node, dict):
        missing.append(path)
        return None
    ok = True
    if "x" not in node:
        missing.append(f"{path}.x")
        ok = False
    if "y" not in node:
        missing.append(f"{path}.y")
        ok = False
    if not ok:
        return None
    return float(node["x"]), float(node["y"])


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance between two placement points (mm).

    Taxonomy:
      - name: distance
      - represents: the exact deterministic spatial metric between a component
        and an anchor (connector / supply pin / protected net pad).
      - input: two 2D points (ax,ay) and (bx,by) in mm.
      - output: the Euclidean distance (float, mm).
      - must NOT be read as: a routed trace length — this is a straight-line
        placement distance, an honest upper-bound proxy for topology, not the
        Manhattan/routed length.
      - complete when: returns math.hypot of the deltas.
    """
    return math.hypot(ax - bx, ay - by)


def nearest_anchor(
    px: float, py: float, anchors: list[tuple[str, float, float]]
) -> tuple[str, float]:
    """Return the (ref, distance) of the closest anchor to a point.

    Taxonomy:
      - name: nearest_anchor
      - represents: the nearest-neighbour reduction used by "component X must sit
        nearest anchor Y" topology rules.
      - input: a query point (px,py) and a list of (ref, x, y) anchor tuples.
      - output: (nearest_ref, distance_mm). Raises when anchors is empty — an
        empty anchor set is a caller contract breach, never a silent inf pass.
      - must NOT be read as: tolerant of an empty anchor list — the caller must
        supply at least one anchor or fail fast upstream.
      - complete when: every anchor has been measured and the minimum returned.
    """
    if not anchors:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            "nearest_anchor called with no anchors (no-silent-fallback)",
            missing_fields=["anchors"],
        )
    best_ref = ""
    best_d = math.inf
    for ref, ax, ay in anchors:
        d = math.hypot(px - ax, py - ay)
        if d < best_d:
            best_d = d
            best_ref = ref
    return best_ref, best_d


def check_placement_topology(
    ir: dict[str, Any],
    *,
    control_id: str,
    threshold_block: dict[str, Any] | None,
) -> ValidationEvidence:
    """Gate labelled components on their distance to a named anchor point.

    Realises the absolute-distance placement-topology rule (e.g. "TVS within
    N mm of the I/O connector"): each component in `ir["parts"]` is measured
    against the anchor `ir["anchor"]`, and a `major` finding is raised for any
    part whose distance exceeds the threshold_block value.

    Args:
      ir: design-IR dict. Expected shape:
        {"anchor": {"ref": str, "x": float, "y": float},
         "parts": [{"ref": str, "x": float, "y": float}, ...]}
        `anchor` is the reference point (connector/supply pin); `parts` are the
        components whose placement distance is gated.
      control_id: the ragbase control.* id this verdict is grounded in.
      threshold_block: {"metric", "value": max_distance_mm, "unit", "source_anchor"}.
        Read at run time (DD-3); the value is never hard-coded here.

    Returns:
      ValidationEvidence(tool="drc_gate") carrying control_id + source_anchor in
      inputs/anchors; one `major` finding per part beyond the threshold distance.

    Raises:
      CheckerError(CHK_THRESHOLD_UNBOUND): no threshold_block supplied.
      CheckerError(CHK_SOURCE_ANCHOR_MISSING): threshold has no source_anchor.
      CheckerError(CHK_IR_FIELD_MISSING): the anchor or a part lacks x/y
        (no-silent-fallback — the missing paths are listed, no default used).
    """
    if not threshold_block or "value" not in threshold_block:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"no threshold block bound for control {control_id!r}",
            control_id=control_id,
        )

    limit = float(threshold_block["value"])
    source_anchor = threshold_block.get("source_anchor")

    missing: list[str] = []
    anchor_xy = _require_point(ir.get("anchor"), "anchor", missing)

    part_coords: list[tuple[str, float, float]] = []
    parts = ir.get("parts", [])
    for i, part in enumerate(parts):
        xy = _require_point(part, f"parts[{i}]", missing)
        if xy is not None:
            part_coords.append((str(part.get("ref", f"P{i}")), xy[0], xy[1]))

    if missing:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"placement-topology checker missing IR fields for control {control_id!r}",
            missing_fields=missing,
            control_id=control_id,
        )

    # source_anchor is mandatory for a distance gate (datasheet-grounded).
    if not source_anchor:
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )

    ax, ay = anchor_xy  # type: ignore[misc]  # guaranteed non-None: missing would have raised
    findings: list[ValidationFinding] = []
    for ref, x, y in part_coords:
        d = distance(x, y, ax, ay)
        if d > limit:
            findings.append(ValidationFinding(
                f"placement-{ref}", "major",
                f"part {ref} is {d:.3f}mm from anchor "
                f"(limit {limit:.3f}mm)",
                {"kind": "component", "ref": ref}))

    severity = "major" if findings else "info"
    anchors: list[dict[str, Any]] = [
        {"kind": "control", "ref": control_id},
        {"kind": "source", "ref": str(source_anchor)},
    ]
    return ValidationEvidence(
        tool=_ENVELOPE_TOOL,
        inputs={"control_id": control_id, "source_anchor": str(source_anchor),
                "threshold": dict(threshold_block)},
        findings=findings,
        severity=severity,
        anchors=anchors,
        raw_result={"part_count": len(part_coords), "over_limit": len(findings),
                    "limit_mm": limit},
    )
