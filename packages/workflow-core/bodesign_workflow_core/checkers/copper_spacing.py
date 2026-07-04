"""M2-1 — copper-spacing / clearance geometry (parser + checkers).

Skillifies the spacing/clearance control cluster. Like board_outline.py (M2-2),
this is a pure-python, zero-LLM, zero-pcbnew module that CONSUMES already-parsed
IR geometry — it does NOT parse gerber/.kicad_pcb s-expr itself.

DD-7 unlock intent: one spacing primitive (pairwise point-to-point distance over
net-tagged located features) unlocks the T-A member of the spacing cluster; the
rest of the cluster (edge-to-edge copper clearance, creepage over a surface path,
functional spacing that needs trace/polygon geometry) stays a T-B backlog because
the design IR carries no copper trace / polygon geometry (contracts.py: only
placement x/y, Net.connected_pads netlist, GeometryPrimitive x/y). Those T-B
controls are registered honestly (no hard-coded fake fields) so the progress
panel shows the parser gap rather than a false green.

The single T-A path realised here:
- si.spacing-via-return-path — a signal via must sit within the threshold
  distance of a return-path (ground) via. Both are located features
  (GeometryPrimitive-shaped: net + x + y), so the metric is IR-readable.

Determinism: pure float math; same features + same threshold_block ->
byte-identical evidence dict.
"""

import math
from typing import Any

from ..validation_evidence import ValidationEvidence, ValidationFinding
from .errors import CheckerError

# Spacing/clearance is a copper-domain deterministic judgement -> drc_gate is the
# closest registered ORACLE_TOOLS member (enforced by ValidationEvidence).
_ENVELOPE_TOOL = "drc_gate"


def _require_feature_xy(
    feat: dict[str, Any], path_prefix: str, missing: list[str]
) -> tuple[float, float] | None:
    """Extract (x, y) from a located-feature dict, recording missing coords.

    Taxonomy:
      - name: _require_feature_xy
      - represents: strict coordinate extraction for a net-tagged located
        feature (GeometryPrimitive-shaped: {"net", "x", "y", "ref"}).
      - input: the feature dict, a dotted path prefix identifying the feature
        (e.g. "signal_vias[0]") for accurate error reporting, and a mutable
        `missing` list to append missing dotted paths onto.
      - output: (x, y) float tuple when BOTH present; None when any coord is
        missing (and the path is appended to `missing`).
      - must NOT be read as: substituting (0, 0) on absence — a missing coord is
        a hard fail surfaced via `missing`, never a default.
      - complete when: both x and y present and float-coercible, or the missing
        paths recorded.
    """
    ok = True
    if "x" not in feat:
        missing.append(f"{path_prefix}.x")
        ok = False
    if "y" not in feat:
        missing.append(f"{path_prefix}.y")
        ok = False
    if not ok:
        return None
    return float(feat["x"]), float(feat["y"])


def nearest_return_via_distance(
    sig_x: float, sig_y: float, return_vias: list[tuple[str, float, float]]
) -> tuple[str, float] | None:
    """Nearest return-path via to a signal via (deterministic min over points).

    Taxonomy:
      - name: nearest_return_via_distance
      - represents: the spacing metric for si.spacing-via-return-path — the
        shortest Euclidean distance from a signal via to any return (ground) via.
      - input: the signal via (sig_x, sig_y) and the list of return vias
        (ref, x, y).
      - output: (nearest_ref, distance_mm) for the closest return via; None when
        there are NO return vias.
      - must NOT be read as: returning 0 or a passing distance when no return via
        exists — None signals "no return reference available" and the CALLER must
        fail fast (no-silent-fallback), never treat it as a pass.
      - complete when: the min over all return vias is found, or None is returned
        for an empty return set.
    """
    best_ref: str | None = None
    best = math.inf
    for ref, rx, ry in return_vias:
        d = math.hypot(sig_x - rx, sig_y - ry)
        if d < best:
            best = d
            best_ref = ref
    if best_ref is None:
        return None
    return best_ref, best


def check_spacing_via_return_path(
    ir: dict[str, Any],
    *,
    control_id: str = "control.si.spacing-via-return-path",
    threshold_block: dict[str, Any] | None,
) -> ValidationEvidence:
    """Gate each signal via on its distance to the nearest return-path via (T-A).

    Args:
      ir: design-IR dict. Expected shape (net-tagged located features):
        {"signal_vias": [{"ref": str, "x": float, "y": float}, ...],
         "return_vias": [{"ref": str, "x": float, "y": float}, ...]}
        These are GeometryPrimitive-shaped points (net + x + y); the caller
        materialises them from the IR's located features by net class.
      control_id: the ragbase control.* id this verdict is grounded in.
      threshold_block: {"metric", "value": max_return_distance_mm, "unit",
        "source_anchor"}. Read at run time (DD-3); never hard-coded here.

    Returns:
      ValidationEvidence(tool="drc_gate") with one `major` finding per signal via
      whose nearest return via exceeds the threshold; carries control_id +
      source_anchor for datasheet-grounded traceability (DD-2).

    Raises:
      CheckerError(CHK_THRESHOLD_UNBOUND): no threshold_block supplied.
      CheckerError(CHK_SOURCE_ANCHOR_MISSING): threshold has no source_anchor.
      CheckerError(CHK_IR_FIELD_MISSING): a via lacks x/y, or there are no return
        vias to measure against (no-silent-fallback — missing paths listed).
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
    signal_vias = ir.get("signal_vias", [])
    return_via_raw = ir.get("return_vias", [])

    sig_coords: list[tuple[str, float, float]] = []
    for i, feat in enumerate(signal_vias):
        xy = _require_feature_xy(feat, f"signal_vias[{i}]", missing)
        if xy is not None:
            sig_coords.append((str(feat.get("ref", f"SV{i}")), xy[0], xy[1]))

    ret_coords: list[tuple[str, float, float]] = []
    for i, feat in enumerate(return_via_raw):
        xy = _require_feature_xy(feat, f"return_vias[{i}]", missing)
        if xy is not None:
            ret_coords.append((str(feat.get("ref", f"RV{i}")), xy[0], xy[1]))

    if missing:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"spacing-via-return-path checker missing IR fields for control {control_id!r}",
            missing_fields=missing,
            control_id=control_id,
        )

    # A via-to-return-path gate with no return vias cannot be evaluated — fail
    # fast rather than silently pass every signal via.
    if not ret_coords:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"spacing-via-return-path checker for {control_id!r} has no return "
            f"vias to measure against; clearance not computable",
            missing_fields=["return_vias"],
            control_id=control_id,
        )

    if not source_anchor:
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )

    findings: list[ValidationFinding] = []
    for ref, x, y in sig_coords:
        nearest = nearest_return_via_distance(x, y, ret_coords)
        # nearest is guaranteed non-None here (ret_coords non-empty checked above).
        assert nearest is not None
        near_ref, dist = nearest
        if dist > limit:
            findings.append(ValidationFinding(
                f"via-return-{ref}", "major",
                f"signal via {ref} nearest return via {near_ref} is "
                f"{dist:.3f}mm away (limit {limit:.3f}mm)",
                {"kind": "via", "ref": ref}))

    severity = "major" if findings else "info"
    return ValidationEvidence(
        tool=_ENVELOPE_TOOL,
        inputs={"control_id": control_id, "source_anchor": str(source_anchor),
                "threshold": dict(threshold_block)},
        findings=findings,
        severity=severity,
        anchors=[{"kind": "control", "ref": control_id},
                 {"kind": "source", "ref": str(source_anchor)}],
        raw_result={"signal_via_count": len(sig_coords),
                    "return_via_count": len(ret_coords),
                    "over_limit": len(findings), "limit_mm": limit},
    )
