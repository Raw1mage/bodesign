"""M1-2 — decoupling-pdn IR-native checker (control.power.decoupling-pdn-strategy).

Realises the decoupling/PDN placement control as a T-A machine-checkable gate:
each decoupling cap must sit within the threshold distance of its power pin.
The threshold value is NEVER hard-coded — it is supplied at run time via a
threshold_block sourced from the ragbase control body (DD-3), and its
source_anchor rides into the ValidationEvidence envelope (DD-2,
datasheet-grounded).

Fail-fast contract (errors.md, no-silent-fallback):
- missing placement.x/placement.y or missing power_pin -> CHK_IR_FIELD_MISSING
  with the explicit missing_fields[] list; the checker NEVER substitutes a
  default coordinate and continues.

Determinism: same IR + same threshold_block -> byte-identical evidence dict.
"""

import math
from typing import Any

from ..validation_evidence import ValidationEvidence, ValidationFinding
from .errors import CheckerError

# The ORACLE_TOOLS member the envelope is emitted under. Decoupling placement is
# a deterministic layout/copper-domain judgement -> drc_gate is the closest
# registered oracle (validation_evidence.ValidationEvidence.__post_init__
# enforces membership).
_ENVELOPE_TOOL = "drc_gate"


def _require_xy(placement: dict[str, Any], path_prefix: str, missing: list[str]) -> tuple[float, float] | None:
    """Extract (x, y) from a placement dict, recording missing coords.

    Taxonomy:
      - name: _require_xy
      - represents: strict coordinate extraction with no default substitution.
      - input: placement dict, a dotted path prefix for error reporting, and a
        mutable `missing` list to append missing field paths onto.
      - output: (x, y) float tuple when BOTH present; None when any coord is
        missing (and the path is appended to `missing`).
      - must NOT be read as: returning (0, 0) or any default on absence — a
        missing coord is a hard fail, surfaced via `missing`.
      - complete when: both x and y are present and float-coercible, or the
        missing paths have been recorded.
    """
    ok = True
    if "x" not in placement:
        missing.append(f"{path_prefix}.x")
        ok = False
    if "y" not in placement:
        missing.append(f"{path_prefix}.y")
        ok = False
    if not ok:
        return None
    return float(placement["x"]), float(placement["y"])


def check_decoupling_pdn(
    ir: dict[str, Any],
    *,
    control_id: str,
    threshold_block: dict[str, Any] | None,
) -> ValidationEvidence:
    """Gate every decoupling cap on its distance to the supply pin.

    Args:
      ir: design-IR dict. Expected shape:
        {"components": [{"refdes": str, "placement": {"x": float, "y": float}}, ...],
         "power_pin": {"x": float, "y": float}}
      control_id: the ragbase control.* id this verdict is grounded in.
      threshold_block: {"metric", "value": max_distance_mm, "unit", "source_anchor"}.
        Read at run time (DD-3); the value is never hard-coded here.

    Returns:
      ValidationEvidence(tool="drc_gate") carrying control_id + source_anchor in
      inputs/anchors; one `major` finding per cap that exceeds the threshold.

    Raises:
      CheckerError(CHK_IR_FIELD_MISSING): a required IR field is absent
        (no-silent-fallback — the missing paths are listed, no default is used).
      CheckerError(CHK_THRESHOLD_UNBOUND): no threshold_block supplied.
      CheckerError(CHK_SOURCE_ANCHOR_MISSING): threshold has no source_anchor.
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
    components = ir.get("components", [])
    # Collect all cap coordinates first, recording every missing field, so the
    # fail-fast report is complete (all gaps at once, not just the first).
    cap_coords: list[tuple[str, float, float]] = []
    for i, comp in enumerate(components):
        placement = comp.get("placement", {})
        xy = _require_xy(placement, f"components[{i}].placement", missing)
        if xy is not None:
            cap_coords.append((str(comp.get("refdes", f"C{i}")), xy[0], xy[1]))

    power_pin = ir.get("power_pin")
    ppx = ppy = None
    if not isinstance(power_pin, dict) or "x" not in power_pin or "y" not in power_pin:
        missing.append("power_pin")
    else:
        ppx, ppy = float(power_pin["x"]), float(power_pin["y"])

    if missing:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"decoupling checker missing IR fields for control {control_id!r}",
            missing_fields=missing,
            control_id=control_id,
        )

    # source_anchor is mandatory for an electrical threshold gate (datasheet-grounded).
    if not source_anchor:
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )

    findings: list[ValidationFinding] = []
    for refdes, x, y in cap_coords:
        dist = math.hypot(x - ppx, y - ppy)
        if dist > limit:
            findings.append(ValidationFinding(
                f"decoupling-{refdes}", "major",
                f"decoupling cap {refdes} is {dist:.3f}mm from supply pin "
                f"(limit {limit:.3f}mm)",
                {"kind": "component", "ref": refdes}))

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
        raw_result={"cap_count": len(cap_coords), "over_limit": len(findings),
                    "limit_mm": limit},
    )
