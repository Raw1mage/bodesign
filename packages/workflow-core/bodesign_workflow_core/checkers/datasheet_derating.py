"""M2-4 — datasheet derating checker (protection component rating vs design value).

Unlike the geometry/placement checkers, this gate is a NUMERIC derating
comparison between a component's datasheet RATING and the DESIGN value chosen for
it: a fuse's continuous current must stay under a fraction of its rating, a MOV's
continuous system voltage must stay under its VM ceiling, and an NTC's t=0 surge
current (V/R25) must stay under the maximum allowed inrush. The derating factor /
formula is NEVER hard-coded — it is read at run time from the owning ragbase
control's threshold_block (DD-3), and its verbatim source_anchor rides into the
ValidationEvidence envelope (DD-2, datasheet-grounded).

Supported gate directions (threshold_block["direction"]):
- "max_fraction":  design_value <= rating * value        (fuse / mov ceiling)
- "surge_formula": input_voltage / r25 <= max_inrush     (ntc ICL)

Fail-fast contract (errors.md, no-silent-fallback): a missing design/rating
input is reported as CHK_IR_FIELD_MISSING with the explicit missing_fields[]
list — the checker NEVER substitutes a default rating and continues.

Determinism: same inputs + same threshold_block -> byte-identical evidence dict.
"""

from typing import Any

from ..validation_evidence import ValidationEvidence, ValidationFinding
from .errors import CheckerError

# The ORACLE_TOOLS member the envelope is emitted under. A datasheet derating
# gate is a component-spec electrical judgement; among the registered oracles
# `spice` is the electrical/component-model oracle, the closest fit.
_ENVELOPE_TOOL = "spice"

_SUPPORTED_DIRECTIONS: frozenset[str] = frozenset({"max_fraction", "surge_formula"})


def _require_number(inputs: dict[str, Any], key: str, missing: list[str]) -> float | None:
    """Extract a required numeric input, recording it as missing if absent.

    Taxonomy:
      - name: _require_number
      - represents: strict numeric extraction with no default substitution.
      - input: the design `inputs` dict, the key to read, and a mutable `missing`
        list to append the key onto when absent/None.
      - output: float(value) when present and coercible; None when absent (and
        the key is appended to `missing`).
      - must NOT be read as: returning 0 or any default on absence — a missing
        rating/design value is a hard fail surfaced via `missing`.
      - complete when: the value is present and float-coercible, or the missing
        key has been recorded.
    """
    if key not in inputs or inputs[key] is None:
        missing.append(key)
        return None
    return float(inputs[key])


def check_datasheet_derating(
    inputs: dict[str, Any],
    *,
    control_id: str,
    threshold_block: dict[str, Any] | None,
) -> ValidationEvidence:
    """Gate a protection component's design value against its datasheet rating.

    Args:
      inputs: the design-side values for one component. Expected keys depend on
        threshold_block["direction"]:
          - "max_fraction":  {"refdes": str, "design_value": float, "rating": float}
            gates design_value <= rating * threshold_block["value"].
          - "surge_formula": {"refdes": str, "input_voltage_v": float,
            "r25_ohm": float, "max_inrush_current_a": float}
            gates (input_voltage_v / r25_ohm) <= max_inrush_current_a.
      control_id: the ragbase control.* id this verdict is grounded in.
      threshold_block: {"metric", "value", "unit", "direction", "source_anchor"}.
        Read at run time (DD-3); the derating factor is never hard-coded here.

    Returns:
      ValidationEvidence(tool="spice") carrying control_id + source_anchor in
      inputs/anchors; a single `major` finding when the design value violates the
      derating gate, else severity "info".

    Raises:
      CheckerError(CHK_THRESHOLD_UNBOUND): no threshold_block, or an unsupported
        direction (the checker refuses to guess a gate it does not implement).
      CheckerError(CHK_SOURCE_ANCHOR_MISSING): threshold has no source_anchor.
      CheckerError(CHK_IR_FIELD_MISSING): a required design/rating input is absent
        (no-silent-fallback — the missing keys are listed, no default is used).
    """
    if not threshold_block or "value" not in threshold_block:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"no threshold block bound for control {control_id!r}",
            control_id=control_id,
        )

    direction = threshold_block.get("direction")
    if direction not in _SUPPORTED_DIRECTIONS:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"control {control_id!r} threshold direction {direction!r} unsupported "
            f"(allowed: {', '.join(sorted(_SUPPORTED_DIRECTIONS))})",
            control_id=control_id,
        )

    source_anchor = threshold_block.get("source_anchor")
    if not source_anchor:
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )

    refdes = str(inputs.get("refdes", "?"))
    missing: list[str] = []
    finding: ValidationFinding | None = None
    raw: dict[str, Any] = {"direction": direction}

    if direction == "max_fraction":
        design_value = _require_number(inputs, "design_value", missing)
        rating = _require_number(inputs, "rating", missing)
        if missing:
            raise CheckerError(
                "CHK_IR_FIELD_MISSING",
                f"datasheet-derating checker missing inputs for control {control_id!r}",
                missing_fields=missing,
                control_id=control_id,
            )
        factor = float(threshold_block["value"])
        allowed = rating * factor  # type: ignore[operator]  # non-None: missing would have raised
        raw.update({"design_value": design_value, "rating": rating,
                    "factor": factor, "allowed_max": allowed})
        if design_value > allowed:  # type: ignore[operator]
            finding = ValidationFinding(
                f"derating-{refdes}", "major",
                f"{refdes} design value {design_value:.4g} exceeds "
                f"{factor:.4g}×rating {rating:.4g} = {allowed:.4g}",
                {"kind": "component", "ref": refdes})

    else:  # surge_formula
        v = _require_number(inputs, "input_voltage_v", missing)
        r25 = _require_number(inputs, "r25_ohm", missing)
        imax = _require_number(inputs, "max_inrush_current_a", missing)
        if missing:
            raise CheckerError(
                "CHK_IR_FIELD_MISSING",
                f"datasheet-derating checker missing inputs for control {control_id!r}",
                missing_fields=missing,
                control_id=control_id,
            )
        if r25 == 0:
            raise CheckerError(
                "CHK_IR_FIELD_MISSING",
                f"NTC r25_ohm is zero for control {control_id!r} (division undefined)",
                missing_fields=["r25_ohm(nonzero)"],
                control_id=control_id,
            )
        surge = v / r25  # type: ignore[operator]  # non-None: missing would have raised
        raw.update({"input_voltage_v": v, "r25_ohm": r25,
                    "surge_current_a": surge, "max_inrush_current_a": imax})
        if surge > imax:  # type: ignore[operator]
            finding = ValidationFinding(
                f"inrush-{refdes}", "major",
                f"{refdes} t=0 surge V/R25 = {surge:.4g}A exceeds max inrush "
                f"{imax:.4g}A",
                {"kind": "component", "ref": refdes})

    findings = [finding] if finding is not None else []
    severity = "major" if findings else "info"
    return ValidationEvidence(
        tool=_ENVELOPE_TOOL,
        inputs={"control_id": control_id, "source_anchor": str(source_anchor),
                "threshold": dict(threshold_block)},
        findings=findings,
        severity=severity,
        anchors=[{"kind": "control", "ref": control_id},
                 {"kind": "source", "ref": str(source_anchor)}],
        raw_result=raw,
    )
