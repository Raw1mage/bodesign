"""M2-2 — board-edge-keepout checker (control.mech.board-edge-keepout), landed.

This control is verified knowledge classified T-B: it gates
component/via-to-board-edge clearance, which needs a board OUTLINE. The M2-2
board-outline parser (board_outline.py, ported from the proven skills logic)
now supplies that geometry, so this checker graduates from stub -> landed: given
`ir["board_outline"]["edges"]` (parsed Edge.Cuts) + point features, it computes
real point-to-edge clearance and gates on the threshold_block distance.

no-silent-fallback contract retained: if the IR carries no board_outline / no
edges, the checker FAILS FAST (CHK_IR_FIELD_MISSING) — a board with no parseable
outline is an honest gap, never a silent pass. The threshold is read at run time
(DD-3), never hard-coded.

Also hosts the tier guard (guard_tier) that enforces the no-fabrication rule at
registration time: a control whose confidence is partial/todo may NOT be built
as a T-A hard gate (CHK_TIER_FORBIDDEN_PARTIAL); it is advisory-only.
"""

from typing import Any

from ..validation_evidence import ValidationEvidence, ValidationFinding
from .board_outline import edges_to_segments, min_clearance_to_edge
from .errors import CheckerError

_ENVELOPE_TOOL = "drc_gate"

# Confidence levels that forbid a T-A hard gate (no-fabrication天條): partial and
# todo knowledge is not authoritative enough to block a design deterministically.
_FORBIDDEN_TA_CONFIDENCE: frozenset[str] = frozenset({"partial", "todo"})


def guard_tier(control_id: str, confidence: str, requested_tier: str) -> None:
    """Reject building a T-A hard gate on non-verified knowledge.

    Taxonomy:
      - name: guard_tier
      - represents: the no-fabrication registration gate — decides whether a
        control MAY be realised at the requested executability tier.
      - input: control_id, the control's confidence ("verified"/"partial"/"todo"),
        and the requested tier ("T-A"/"T-B"/"T-C").
      - output: None on success (allowed). Raises CheckerError otherwise.
      - must NOT be read as: a runtime data check — this is a build/registration
        time policy guard, not an IR read.
      - complete when: a partial/todo control requesting T-A raises
        CHK_TIER_FORBIDDEN_PARTIAL; every other combination returns None.
    """
    if requested_tier == "T-A" and confidence in _FORBIDDEN_TA_CONFIDENCE:
        raise CheckerError(
            "CHK_TIER_FORBIDDEN_PARTIAL",
            f"control {control_id!r} is confidence={confidence!r}; a T-A hard "
            f"gate is forbidden (advisory-only until verified)",
            control_id=control_id,
            confidence=confidence,
        )


def check_board_edge_keepout(
    ir: dict[str, Any],
    *,
    control_id: str = "control.mech.board-edge-keepout",
    threshold_block: dict[str, Any] | None,
) -> ValidationEvidence:
    """Gate every point feature on its clearance to the board edge (M2-2 landed).

    Args:
      ir: design-IR dict. Expected shape:
        {"board_outline": {"edges": [{"type": "line", "start": [x,y], "end": [x,y]}, ...]},
         "features": [{"ref": str, "x": float, "y": float}, ...]}
        `features` are the points to gate (vias/pads/holes); `edges` is the parsed
        Edge.Cuts geometry the M2-2 parser materialised.
      control_id: the ragbase control.* id this verdict is grounded in.
      threshold_block: {"metric", "value": min_clearance_mm, "unit", "source_anchor"}.
        Read at run time (DD-3); never hard-coded.

    Returns:
      ValidationEvidence(tool="drc_gate") with one `major` finding per feature
      whose edge clearance is below the threshold; carries control_id + source_anchor.

    Raises:
      CheckerError(CHK_THRESHOLD_UNBOUND): no threshold_block supplied.
      CheckerError(CHK_SOURCE_ANCHOR_MISSING): threshold has no source_anchor.
      CheckerError(CHK_IR_FIELD_MISSING): board_outline / edges absent, or a
        feature lacks x/y (no-silent-fallback — the missing paths are listed).
    """
    if not threshold_block or "value" not in threshold_block:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"no threshold block bound for control {control_id!r}",
            control_id=control_id,
        )
    limit = float(threshold_block["value"])
    source_anchor = threshold_block.get("source_anchor")

    outline = ir.get("board_outline")
    if not isinstance(outline, dict) or not outline.get("edges"):
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"board-edge-keepout checker for {control_id!r} needs a parsed board "
            f"outline (ir['board_outline']['edges']); none present",
            missing_fields=["board_outline.edges"],
            control_id=control_id,
        )

    segments = edges_to_segments(outline["edges"])
    if not segments:
        # Edges present but none linearisable (all arc/circle/curve) -> cannot
        # compute clearance; fail fast rather than pass on zero segments.
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"board outline for {control_id!r} has no straight edge segments "
            f"(only curved primitives); clearance not computable",
            missing_fields=["board_outline.edges[line|rect]"],
            control_id=control_id,
        )

    if not source_anchor:
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )

    features = ir.get("features", [])
    missing: list[str] = []
    coords: list[tuple[str, float, float]] = []
    for i, feat in enumerate(features):
        if "x" not in feat or "y" not in feat:
            if "x" not in feat:
                missing.append(f"features[{i}].x")
            if "y" not in feat:
                missing.append(f"features[{i}].y")
            continue
        coords.append((str(feat.get("ref", f"F{i}")), float(feat["x"]), float(feat["y"])))
    if missing:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"board-edge-keepout missing feature coords for control {control_id!r}",
            missing_fields=missing,
            control_id=control_id,
        )

    findings: list[ValidationFinding] = []
    for ref, x, y in coords:
        clearance = min_clearance_to_edge(x, y, segments)
        if clearance < limit:
            findings.append(ValidationFinding(
                f"board-edge-{ref}", "major",
                f"feature {ref} is {clearance:.3f}mm from board edge "
                f"(min {limit:.3f}mm)",
                {"kind": "feature", "ref": ref}))

    severity = "major" if findings else "info"
    return ValidationEvidence(
        tool=_ENVELOPE_TOOL,
        inputs={"control_id": control_id, "source_anchor": str(source_anchor),
                "threshold": dict(threshold_block)},
        findings=findings,
        severity=severity,
        anchors=[{"kind": "control", "ref": control_id},
                 {"kind": "source", "ref": str(source_anchor)}],
        raw_result={"feature_count": len(coords), "under_limit": len(findings),
                    "limit_mm": limit, "segment_count": len(segments)},
    )
