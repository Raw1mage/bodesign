"""Step-2 cross-spec extend — copper-clearance checker (control.dfm.ipc-clearance-voltage).

This control gates the minimum edge-to-edge copper spacing between distinct nets
per IPC-2221 (working-voltage clearance). The gated quantity (net_pair_spacing_mm)
was NOT in the design IR, so the control stayed a T-B *stub*. Two now-graduated
specs supply the missing pieces and let it graduate to *landed*:

  - specs/gerber-core/copper-geometry-parser: build_copper_geometry + edge_to_edge
    give real edge-to-edge copper spacing between net-islands, with curve-skip
    provenance and fail-fast on missing geometry.
  - specs/design-ir/net-role-extension: NET_ROLES is the closed, explicitly-supplied
    role enum; each island's role is validated against it (no net-name heuristic,
    no guessed default).

Contract (retains the fail-fast discipline of the sibling checkers):
  - CHK_THRESHOLD_UNBOUND     : no threshold_block bound.
  - CHK_SOURCE_ANCHOR_MISSING : threshold has no source_anchor (datasheet-grounded).
  - CHK_IR_FIELD_MISSING      : copper_geometry / island_roles absent, or a query
    hits an empty/uncomputable island set (edge_to_edge MissingGeometryError).
  - CHK_IR_FIELD_INVALID      : an island role is outside the closed NET_ROLES enum
    (no-fabrication: a bad role is rejected, never silently coerced).

Determinism: pure float math over the parser primitives + a stable pair scan; same
geometry + same island_roles + same threshold_block -> byte-identical evidence.
"""

from typing import Any

from bodesign_design_ir import NET_ROLES
from bodesign_gerber_core import CopperGeometry, edge_to_edge

from ..validation_evidence import ValidationEvidence, ValidationFinding
from .errors import CheckerError

_ENVELOPE_TOOL = "drc_gate"


def check_copper_clearance(
    ir: dict[str, Any],
    *,
    control_id: str = "control.dfm.ipc-clearance-voltage",
    threshold_block: dict[str, Any] | None,
) -> ValidationEvidence:
    """Gate every distinct-net copper-island pair on its edge-to-edge spacing.

    Args:
      ir: design-IR dict. Expected shape:
        {"copper_geometry": CopperGeometry,          # gerber-core parser output
         "island_roles": {island_id: role, ...}}     # design-ir NET_ROLES value
        `copper_geometry` is a built CopperGeometry (net-attributed primitives);
        `island_roles` maps each net-island id to an EXPLICITLY-supplied role from
        the closed NET_ROLES enum (validated here; never heuristic-inferred).
      control_id: the ragbase control.* id this verdict is grounded in.
      threshold_block: {"metric", "value": min_clearance_mm, "unit", "source_anchor"}.
        Read at run time (DD-3); never hard-coded.

    Returns:
      ValidationEvidence(tool="drc_gate") with one `major` finding per distinct-net
      island pair whose edge-to-edge spacing is below the threshold; carries
      control_id + source_anchor + the role pair for datasheet-grounded traceability.

    Raises:
      CheckerError(CHK_THRESHOLD_UNBOUND / CHK_SOURCE_ANCHOR_MISSING /
        CHK_IR_FIELD_MISSING / CHK_IR_FIELD_INVALID) — see module docstring.
    """
    if not threshold_block or "value" not in threshold_block:
        raise CheckerError(
            "CHK_THRESHOLD_UNBOUND",
            f"no threshold block bound for control {control_id!r}",
            control_id=control_id,
        )
    limit = float(threshold_block["value"])
    source_anchor = threshold_block.get("source_anchor")

    geom = ir.get("copper_geometry")
    if not isinstance(geom, CopperGeometry):
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"copper-clearance checker for {control_id!r} needs a built "
            f"CopperGeometry (ir['copper_geometry']); none present",
            missing_fields=["copper_geometry"],
            control_id=control_id,
        )

    island_roles = ir.get("island_roles")
    if not isinstance(island_roles, dict) or not island_roles:
        raise CheckerError(
            "CHK_IR_FIELD_MISSING",
            f"copper-clearance checker for {control_id!r} needs an explicit "
            f"island_roles map (design-ir NET_ROLES); none present",
            missing_fields=["island_roles"],
            control_id=control_id,
        )

    # no-fabrication: every supplied role must be in the closed enum. A bad token
    # is rejected, never coerced to a default.
    bad = sorted(
        f"{iid}={role!r}" for iid, role in island_roles.items() if role not in NET_ROLES
    )
    if bad:
        raise CheckerError(
            "CHK_IR_FIELD_INVALID",
            f"copper-clearance checker for {control_id!r} got island roles outside "
            f"the closed NET_ROLES enum: {', '.join(bad)}",
            invalid_fields=bad,
            control_id=control_id,
        )

    if not source_anchor:
        raise CheckerError(
            "CHK_SOURCE_ANCHOR_MISSING",
            f"threshold for control {control_id!r} has no source_anchor",
            control_id=control_id,
        )

    island_ids = sorted(island_roles)
    findings: list[ValidationFinding] = []
    pair_count = 0
    skipped_curves: set[str] = set()
    for i in range(len(island_ids)):
        for j in range(i + 1, len(island_ids)):
            a, b = island_ids[i], island_ids[j]
            res = edge_to_edge(geom, a, b)
            if res.error is not None:
                # A pair we were asked to gate has no computable geometry -> fail
                # fast (no-silent-fallback), never treat as a passing clearance.
                raise CheckerError(
                    "CHK_IR_FIELD_MISSING",
                    f"copper-clearance for {control_id!r} could not compute spacing "
                    f"for island pair ({a}, {b}): {res.error.reason}",
                    missing_fields=list(res.error.missing_items),
                    control_id=control_id,
                )
            pair_count += 1
            skipped_curves.update(res.provenance.skipped_curves)
            if res.distance_mm is not None and res.distance_mm < limit:
                findings.append(ValidationFinding(
                    f"clearance-{a}-{b}", "major",
                    f"copper spacing between net-islands {a} ({island_roles[a]}) and "
                    f"{b} ({island_roles[b]}) is {res.distance_mm:.3f}mm "
                    f"(min {limit:.3f}mm)",
                    {"kind": "net_pair", "ref": f"{a}|{b}",
                     "roles": f"{island_roles[a]}|{island_roles[b]}"}))

    severity = "major" if findings else "info"
    return ValidationEvidence(
        tool=_ENVELOPE_TOOL,
        inputs={"control_id": control_id, "source_anchor": str(source_anchor),
                "threshold": dict(threshold_block)},
        findings=findings,
        severity=severity,
        anchors=[{"kind": "control", "ref": control_id},
                 {"kind": "source", "ref": str(source_anchor)}],
        raw_result={"island_pair_count": pair_count, "under_limit": len(findings),
                    "limit_mm": limit, "skipped_curves": sorted(skipped_curves)},
    )
