"""C04 layout constraint package — constraint-first, draft only.

C04 is owned by the layout engineer (bodesign_role = "constraints"). bodesign does
NOT place parts, route, or emit Gerbers here; it assembles the explicit placement
constraints the layout engineer needs from the two upstream hard-constraint sources
that already exist in runtime:

- C01 `Interface_Constraints.json` — preferred component faces, visibility/RF/acoustic
  placement intent, exposed components.
- C03 `Mechanical_Constraint_Export.json` — component heights, connector edge openings,
  heat sources, antenna keepouts, battery envelope, ESD/EMC notes.

Board outline, mounting holes, placement coordinates, and stackup stay PENDING and
layout-owned — they are never fabricated. Inputs may be passed explicitly or, when a
project folder already holds the upstream exports, auto-loaded from it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .c01_id_package import C01_OUTPUTS
from .c03_mechanical_constraints import C03_OUTPUT
from .feasibility import classify_product_feasibility
from .readiness_common import boundary_next_step, root_guard
from .guide_dod import guide_compliance_for

C04_FOLDER = Path("C04-Layout")
C04_CONSTRAINTS_OUTPUT = C04_FOLDER / "Layout_Constraints.json"
C04_PLACEMENT_OUTPUT = C04_FOLDER / "Placement_Constraints.md"

# BR_20260901e: this used to be a second, independent literal spelling of the
# same path C01's emitter writes. Two literals with no link between them is a
# drift surface, not a duplicate string: C01 would keep reporting "emitted" while
# C04 reported "upstream missing", each verb correct in isolation. The read side
# now derives from the WRITE side, which is the only source of truth for where
# the file lands.
_C01_CONSTRAINTS_REL = C01_OUTPUTS["constraints"]
_C03_FOLDER = Path("C03-EE")

# Tier-1 acceptance inputs. These paths are PINNED, never searched for: a search
# chain is itself a silent fallback (it would let a report found somewhere else
# stand in for the one the contract names). C03 writes them by passing
# `out_dir=<root>/C03-EE` to the two gates.
_C03_ENTRY_GATE_REPORT = _C03_FOLDER / "check_c03.report.json"
_C03_PRD_CROSSCHECK_REPORT = _C03_FOLDER / "prd_bom_crosscheck.report.json"

_ENTRY_GATE_REMEDY = (
    "produce it in C03 with `bodesign_check_c03(bom_csv=<C03-EE>/BOM.csv, "
    "pin_allocation_csv=<C03-EE>/Pin_Allocation.csv, netlist_path=[<C03-EE>/*.net], "
    "covers_boards=[<the boards those netlists cover>], out_dir={out_dir})`"
)
_PRD_CROSSCHECK_REMEDY = (
    "produce it in C03 with `bodesign_prd_bom_crosscheck(manifest_path=<C00>/"
    "main_components_structured.json, netlist_path=<C03-EE>/*.net, out_dir={out_dir})`"
)

# Feasibility-triage signals bodesign accepts. Anything else is ignored (not guessed).
_FEASIBILITY_KEYS = {
    "layer_count", "finest_bga_pitch_mm", "hdi_required", "high_speed_nets",
    "rf", "component_count", "board_area_mm2", "source",
}

# Constraint groups the layout engineer owns — bodesign never guesses these.
_LAYOUT_OWNED_PENDING = [
    {"item": "board_outline", "owner": "layout engineer", "note": "Final board outline/dimensions are layout/ME owned."},
    {"item": "mounting_holes", "owner": "layout engineer", "note": "Mounting hole positions come from the enclosure (C02) + board."},
    {"item": "placement_coordinates", "owner": "layout engineer", "note": "Exact XY placement and rotation are layout decisions."},
    {"item": "layer_stackup", "owner": "layout engineer", "note": "Stackup/impedance targets are layout/fab decisions unless given."},
]


@dataclass(slots=True)
class C04LayoutReadiness:
    folder: str
    present_groups: list[str]
    pending: list[dict[str, Any]]
    constraints_present: bool
    placement_doc_present: bool
    status: str
    next_step: str
    root_visible: bool = True
    warnings: list[str] = field(default_factory=list)
    upstream: dict[str, Any] = field(default_factory=dict)
    feasibility: dict[str, Any] = field(default_factory=dict)
    c03_acceptance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "folder": self.folder,
            "present_groups": list(self.present_groups),
            "pending": list(self.pending),
            "constraints_present": self.constraints_present,
            "placement_doc_present": self.placement_doc_present,
            "status": self.status,
            "next_step": self.next_step,
            "root_visible": self.root_visible,
            "warnings": list(self.warnings),
            "upstream": dict(self.upstream),
            "upstream_fulfilled": bool(self.upstream.get("fulfilled")) if self.upstream else None,
            "c03_acceptance": dict(self.c03_acceptance),
            # Tri-state, never collapsed to a bool: None = tier-1 never reached
            # (tier-0 already blocked, so the reports were not consulted at all),
            # which must stay distinguishable from False = consulted and refused.
            "c03_accepted": (bool(self.c03_acceptance.get("accepted"))
                             if self.c03_acceptance else None),
            "feasibility": dict(self.feasibility),
            "feasibility_tier": self.feasibility.get("tier") if self.feasibility else None,
            "board_ready": False,
            "gerber_ready": False,
            "layout_approval": False,
        }
        gc = guide_compliance_for(self.folder, "c04", root_visible=self.root_visible)
        if gc is not None:
            d["guide_compliance"] = gc
            d["dod_ok"] = bool(gc.get("dod_ok"))
        return d


@dataclass(slots=True)
class C04LayoutResult:
    folder: str
    files: list[str]
    constraints: dict[str, Any]
    readiness: C04LayoutReadiness
    pending: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "files": list(self.files),
            "constraints": self.constraints,
            "pending": list(self.pending),
            "readiness": self.readiness.to_dict(),
            "layout_approval": False,
        }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _c03_constraints(c03: dict[str, Any] | None) -> dict[str, Any]:
    if not c03:
        return {}
    # Accept either the raw export payload ({constraints: {...}}) or the inner dict.
    return c03.get("constraints", c03) if isinstance(c03, dict) else {}


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def _c03_netlist_present(root: Path) -> bool:
    """True when C03 has emitted at least one KiCad netlist (.net) — the disk-of-truth
    evidence that C00's components were realised into electrical connectivity and can
    actually land on the board."""
    c03 = root / _C03_FOLDER
    return c03.is_dir() and any(c03.glob("*.net"))


def _assess_upstream_fulfilment(root: Path) -> dict[str, Any]:
    """Honest cross-stage check: has C03 electrical design actually happened?

    C04 layout constraints are premature — and misleading — when no netlist exists,
    because it means C00's main_components have NOT been realised into a board. No
    silent pass: an empty upstream produces an explicit gap list, not a clean draft.
    """
    c03_dir = root / _C03_FOLDER
    mech = root / C03_OUTPUT
    netlist = _c03_netlist_present(root)
    gaps: list[str] = []
    if not c03_dir.is_dir():
        gaps.append("C03-EE/ absent — the electrical-design stage has not run; no schematic/BOM/netlist exists")
    if not netlist:
        gaps.append(
            "C03 netlist (.net) missing — C00 main_components have not been realised into an "
            "electrical netlist, so nothing has landed on the board yet"
        )
    if not mech.exists():
        gaps.append(
            f"{C03_OUTPUT.as_posix()} missing — no mechanical constraints exported from C03"
        )
    return {
        "c03_dir_present": c03_dir.is_dir(),
        "c03_netlist_present": netlist,
        "c03_mechanical_export_present": mech.exists(),
        "gaps": gaps,
        "fulfilled": not gaps,
    }


def _load_gate_report(path: Path) -> tuple[str, dict[str, Any] | None, str]:
    """Load a C03 gate report, keeping ABSENT and MALFORMED distinguishable.

    `_load_json` returns None both for "file is not there" and for "file is there
    but unparseable". Collapsing those two would let a corrupt report read as a
    gate that merely has not run yet — the same output for a missing thing and a
    broken thing — and they need different remedies. This reader never merges
    them, and it refuses to guess a verdict for a payload that carries none.
    """
    if not path.exists():
        return "absent", None, ""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return "malformed", None, f"unreadable ({exc.__class__.__name__})"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return "malformed", None, f"not valid JSON ({exc.msg}, line {exc.lineno})"
    if not isinstance(data, dict):
        return "malformed", None, f"top level is {type(data).__name__}, expected an object"
    gate = data.get("gate")
    if not isinstance(gate, str):
        return "malformed", None, "no string `gate` field — not a bodesign gate report"
    if gate not in ("PASS", "FAIL"):
        return "malformed", None, f"gate={gate!r} is neither PASS nor FAIL"
    return "ok", data, ""


def _scope_status(report: dict[str, Any], field_name: str) -> str:
    """Read a sub-scope verdict's own status. A sub-scope block that is missing
    entirely is treated as `not_run` (never as clean) — an older report that
    never carried the field genuinely did not check that scope."""
    block = report.get(field_name)
    if not isinstance(block, dict):
        return "not_run"
    status = block.get("status")
    return status if isinstance(status, str) else "not_run"


def _assess_c03_acceptance(root: Path) -> dict[str, Any]:
    """Tier-1 cross-stage check: is C03's delivery ACCEPTABLE?

    Tier-0 (`_assess_upstream_fulfilment`) asks whether C03 *ran* — do three files
    exist. That is necessary and not sufficient: the BR_20260707 symptom class
    (BOM carrying draft/blocked rows, BOM<->Pin_Allocation conflicts, pad counts
    not synced to a frozen value) occurs precisely when those files DO exist, so
    an existence check standing in an acceptance check's position returns
    `fulfilled: true` and waves it through. This tier reads the verdicts C03
    already signs and refuses entry on anything but a PASS of adequate scope.

    Producer-signs / consumer-reads (no-silent-fallback): C04 does NOT re-run the
    C03 gates. Their inputs — which CSV is the BOM, which `.net` files cover which
    boards — are knowledge only C03 holds; `check_c03`'s own docstring records
    that inferring `covers_boards` "cannot tell 'no netlist covers this board'
    from 'every row on it is undrawn'". Re-deriving that here would plant a silent
    fallback inside the very gate meant to forbid one. So C04 consumes the signed
    report, or it refuses.

    Scope, not just verdict (BR_20260730 discipline): `check_c03` states in its own
    docstring that with no netlist supplied `gate=PASS` "must NOT be read as 'every
    BOM row is drawn'". C04 layout rests on exactly that guarantee, so a PASS whose
    `netlist_crosscheck` never ran is BLOCKING here. That is not C04 overruling the
    gate — it is C04 declining to read "not checked" as "checked and clean", which
    is this BR's whole subject. `ssot_crosscheck` / `pin_polarity` are quality
    signals rather than load-bearing preconditions, so they warn instead.
    """
    gaps: list[str] = []
    warnings: list[str] = []
    codes: set[str] = set()
    reports: dict[str, dict[str, Any]] = {}

    out_dir = str(root / _C03_FOLDER)

    for key, rel, remedy, scope_gated in (
        ("entry_gate", _C03_ENTRY_GATE_REPORT, _ENTRY_GATE_REMEDY, True),
        ("prd_bom_crosscheck", _C03_PRD_CROSSCHECK_REPORT, _PRD_CROSSCHECK_REMEDY, False),
    ):
        path = root / rel
        state, payload, detail = _load_gate_report(path)
        block: dict[str, Any] = {
            "report": str(rel),
            "expected_path": str(path),
            "present": state != "absent",
            "gate": payload["gate"] if payload else None,
            "status": "",
        }
        if state == "absent":
            block["status"] = "not_run"
            codes.add("not_run")
            gaps.append(
                f"{rel} missing — the C03 gate has NOT run, which is not the same as "
                f"passing. Expected at {path}; " + remedy.format(out_dir=out_dir)
            )
        elif state == "malformed":
            block["status"] = "malformed"
            block["detail"] = detail
            codes.add("malformed")
            gaps.append(
                f"{rel} present but unusable ({detail}) — a report that cannot be read "
                f"carries no verdict and is never assumed to pass. Re-emit it: "
                + remedy.format(out_dir=out_dir)
            )
        elif payload["gate"] == "FAIL":
            block["status"] = "failed"
            blocking = payload.get("blocking")
            block["blocking_count"] = len(blocking) if isinstance(blocking, list) else None
            codes.add("failed")
            gaps.append(
                f"{rel} reports gate=FAIL"
                + (f" ({block['blocking_count']} blocking finding(s))"
                   if block["blocking_count"] else "")
                + " — C03's own gate rejects this delivery; fix the design/BOM in C03 "
                  "and re-run it. C04 entry is refused (the gate value is never relaxed)."
            )
        else:
            block["status"] = "pass"
            if scope_gated:
                netlist_scope = _scope_status(payload, "netlist_crosscheck")
                block["netlist_crosscheck_status"] = netlist_scope
                if netlist_scope == "not_run":
                    block["status"] = "scope_incomplete"
                    codes.add("scope_incomplete")
                    gaps.append(
                        f"{rel} reports gate=PASS but netlist_crosscheck.status=not_run — "
                        "the gate never checked that every BOM row is actually drawn into "
                        "the schematic (its own docstring says such a PASS must NOT be read "
                        "that way). C04 placement rests on that guarantee, so this is "
                        "blocking. Re-run the gate supplying netlist_path=[...] and "
                        "covers_boards=[...]."
                    )
                for field_name, label in (("ssot_crosscheck", "BOM<->Pin_Allocation SSOT"),
                                          ("pin_polarity", "pin-spec polarity")):
                    sub = _scope_status(payload, field_name)
                    block[f"{field_name}_status"] = sub
                    if sub == "not_run":
                        warnings.append(
                            f"{rel}: {field_name}.status=not_run — the {label} scope was "
                            "never checked; this PASS does not cover it (warn, not blocking)"
                        )
        reports[key] = block

    # Precedence: something that never ran outranks a failure, which outranks a
    # pass of insufficient scope — each names a different first action.
    status_code = None
    for code, mapped in (
        ("not_run", "blocked_c03_entry_gate_not_run"),
        ("malformed", "blocked_c03_entry_gate_report_unusable"),
        ("failed", "blocked_c03_entry_gate_failed"),
        ("scope_incomplete", "blocked_c03_entry_gate_scope_incomplete"),
    ):
        if code in codes:
            status_code = mapped
            break

    return {
        "reports": reports,
        "gaps": gaps,
        "warnings": warnings,
        "accepted": not gaps,
        "status_code": status_code,
    }


def _assess_feasibility(signals: dict[str, Any] | None) -> dict[str, Any]:
    """Run the feasibility triage when signals are supplied.

    Honesty model (no-silent-fallback): with no complexity signals bodesign does NOT
    guess a tier — a fabricated Tier 1 would understate the routing wall. It returns
    tier=None / label=not-assessed and asks for the signals instead.
    """
    kwargs = {k: v for k, v in (signals or {}).items() if k in _FEASIBILITY_KEYS}
    if not kwargs:
        return {
            "tier": None,
            "label": "not-assessed",
            "reason": (
                "No feasibility signals supplied (layer_count / finest_bga_pitch_mm / hdi_required / "
                "high_speed_nets / rf). bodesign does not guess a tier — supply C00/C03 complexity "
                "signals to classify the C04 delivery ceiling."
            ),
        }
    return classify_product_feasibility(**kwargs).to_dict()


def _render_feasibility_upstream(constraints: dict[str, Any]) -> list[str]:
    feas = constraints.get("feasibility") or {}
    up = constraints.get("upstream_fulfilment") or {}
    if not feas and not up:
        return []
    lines = ["", "## Feasibility & upstream fulfilment"]
    tier = feas.get("tier")
    lines.append(
        f"- **Feasibility tier**: {tier if tier is not None else 'not assessed'}"
        + (f" — {feas['label']}" if feas.get("label") else "")
    )
    if feas.get("c04_target"):
        lines.append(f"- **C04 delivery target**: {feas['c04_target']}")
    if feas.get("reason"):
        lines.append(f"- {feas['reason']}")
    fulfilled = up.get("fulfilled")
    lines.append(f"- **Upstream C03 fulfilled**: {'yes' if fulfilled else 'NO — see gaps below'}")
    for g in up.get("gaps", []):
        lines.append(f"  - GAP: {g}")
    return lines


def _build_layout_constraints(
    c01: dict[str, Any] | None,
    c03: dict[str, Any] | None,
    upstream: dict[str, Any] | None = None,
    feasibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    c03c = _c03_constraints(c03)
    c01 = c01 or {}
    placement_intent = []
    if isinstance(c01.get("downstream_targets"), dict):
        placement_intent = c01["downstream_targets"].get("C04") or []

    upstream = upstream or {}
    fulfilled = bool(upstream.get("fulfilled", True))
    return {
        "schema": "bodesign.c04.layout_constraints.v1",
        # Honest state: constraints are only a normal draft when C03 has actually
        # realised the netlist. With no upstream electrical design, the package is
        # blocked-on-upstream, not a clean draft.
        "state": "drafted" if fulfilled else "blocked_on_upstream",
        "source": {
            "layer": "C04",
            "from_c01": bool(c01),
            "from_c03": bool(c03c),
            "notes": "Assembled from C01 interface intent + C03 mechanical constraints. Board outline/placement/stackup remain layout-owned.",
        },
        "upstream_fulfilment": upstream,
        "feasibility": feasibility or {},
        "placement_intent": placement_intent,
        "exposed_components": c01.get("exposed_components", []),
        "component_heights": c03c.get("component_heights", []),
        "connector_edge_openings": c03c.get("connector_openings", []),
        "heat_zones": c03c.get("heat_sources", []),
        "antenna_keepouts": c03c.get("antenna_keepouts", []),
        "battery_zone": c03c.get("battery_envelope"),
        "emc_esd_notes": c03c.get("esd_emc_notes", []),
        "open_decisions": [
            "board outline, mounting holes, and exact placement remain layout-engineer decisions",
            "layer stackup / impedance targets require layout + fab confirmation",
        ],
    }


_GROUP_KEYS = [
    "placement_intent", "exposed_components", "component_heights",
    "connector_edge_openings", "heat_zones", "antenna_keepouts", "battery_zone", "emc_esd_notes",
]


def _render_placement_md(constraints: dict[str, Any]) -> str:
    lines = [
        "# C04 Layout — Placement Constraints (DRAFT)",
        "",
        "> Constraint-first handoff for the layout engineer. bodesign does not place, route, or",
        "> emit Gerbers here. Board outline, mounting holes, exact placement, and stackup are",
        "> layout-owned and remain open below.",
        "",
        "## Inputs",
        f"- From C01 interface constraints: {'yes' if constraints['source']['from_c01'] else 'MISSING'}",
        f"- From C03 mechanical constraints: {'yes' if constraints['source']['from_c03'] else 'MISSING'}",
        "",
        "## Assembled constraints",
    ]
    for key in _GROUP_KEYS:
        value = constraints.get(key)
        present = _nonempty(value)
        lines.append(f"- **{key}**: {'present' if present else '— (not provided upstream)'}")
    lines += _render_feasibility_upstream(constraints)
    lines += [
        "",
        "## Layout-owned (open — not fabricated)",
    ]
    for item in _LAYOUT_OWNED_PENDING:
        lines.append(f"- **{item['item']}** — owner: {item['owner']}. {item['note']}")
    lines += ["", "## Open decisions"]
    for dec in constraints.get("open_decisions", []):
        lines.append(f"- {dec}")
    return "\n".join(lines) + "\n"


def emit_c04_layout_package(
    out_dir: str | Path,
    c01: dict[str, Any] | None = None,
    c03: dict[str, Any] | None = None,
    feasibility_signals: dict[str, Any] | None = None,
) -> C04LayoutResult:
    """Assemble the C04 layout constraint package from C01/C03 inputs.

    Inputs may be passed explicitly; when omitted, they are auto-loaded from the
    project folder's existing C01/C03 exports if present.

    Honesty model (no-silent-fallback): absent upstream is NOT silently treated as a
    clean draft. The emitted package records an explicit `upstream_fulfilment` block
    (C03 dir / netlist / mechanical export presence + a gap list) and, when C03 has
    not realised a netlist, the package `state` is `blocked_on_upstream` rather than
    `drafted` — so a product whose C00 components never landed on a board can never
    look delivered. `feasibility_signals` (optional) runs the tier triage; with no
    signals the tier is reported `not-assessed`, never guessed.
    """
    root = Path(out_dir)
    if c01 is None:
        c01 = _load_json(root / _C01_CONSTRAINTS_REL)
    if c03 is None:
        c03 = _load_json(root / C03_OUTPUT)

    upstream = _assess_upstream_fulfilment(root)
    feasibility = _assess_feasibility(feasibility_signals)
    constraints = _build_layout_constraints(c01, c03, upstream=upstream, feasibility=feasibility)
    files: list[str] = []
    for rel, content in (
        (C04_CONSTRAINTS_OUTPUT, json.dumps(constraints, ensure_ascii=False, indent=2) + "\n"),
        (C04_PLACEMENT_OUTPUT, _render_placement_md(constraints)),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        files.append(str(rel))

    readiness = assess_c04_layout_readiness(root, feasibility_signals=feasibility_signals)
    return C04LayoutResult(str(root), files, constraints, readiness, pending=list(_LAYOUT_OWNED_PENDING))


def assess_c04_layout_readiness(
    folder: str | Path,
    feasibility_signals: dict[str, Any] | None = None,
) -> C04LayoutReadiness:
    root, visible, warning = root_guard(folder)
    if not visible:
        return C04LayoutReadiness(
            folder=str(root), present_groups=[], pending=list(_LAYOUT_OWNED_PENDING),
            constraints_present=False, placement_doc_present=False,
            status="path-not-visible", next_step=boundary_next_step(folder),
            root_visible=False, warnings=[warning] if warning else [],
        )
    constraints_path = root / C04_CONSTRAINTS_OUTPUT
    placement_path = root / C04_PLACEMENT_OUTPUT
    constraints = _load_json(constraints_path) or {}
    present_groups = [k for k in _GROUP_KEYS if _nonempty(constraints.get(k))]
    constraints_present = constraints_path.exists()
    placement_present = placement_path.exists()

    # Cross-stage fulfilment: has C03 actually realised C00's components into a
    # netlist? This is independent of whether the constraint groups are non-empty.
    upstream = _assess_upstream_fulfilment(root)
    # Prefer the feasibility recorded in the emitted package; else compute from signals.
    feasibility = constraints.get("feasibility") or _assess_feasibility(feasibility_signals)
    tier = feasibility.get("tier")
    warnings: list[str] = []

    # Tier-1 acceptance is only consulted once tier-0 holds: with no netlist on disk
    # there is nothing for a BOM<->netlist verdict to be about, and reporting a
    # missing report there would bury the real first action (run C03) under a
    # second-order complaint. Left empty, `c03_accepted` reports None (not reached)
    # rather than False (reached and refused).
    acceptance: dict[str, Any] = {}

    if not constraints_present:
        status = "missing"
        next_step = "Run bodesign_c04_emit_layout_package with C01/C03 constraints."
    elif not upstream["fulfilled"]:
        # The load-bearing fix: upstream electrical design is incomplete. Never report
        # 'drafted' — that reads as 'a delivered draft' when in truth no component has
        # landed on the board. This is BLOCKING (no-silent-fallback).
        status = "blocked_upstream_c03_missing"
        warnings.append(
            "C04 constraints exist but upstream C03 has not realised a netlist — C00 "
            "main_components have NOT landed on a board. This is not a delivered draft."
        )
        gap_txt = "; ".join(upstream["gaps"]) or "C03 electrical design incomplete"
        if tier == 3:
            next_step = (
                "Tier-3 product: complete C03 (schematic + netlist), then emit the SI "
                "constraint handoff (emit_si_constraint_export) for pro-EDA routing. "
                f"Upstream gaps: {gap_txt}"
            )
        else:
            next_step = (
                "Run C03 electrical design first (compose_schematic → export_netlist) so "
                f"C00 components are realised, then re-run C04. Upstream gaps: {gap_txt}"
            )
    elif not (acceptance := _assess_c03_acceptance(root))["accepted"]:
        # Tier-1: C03 ran, but its own signed verdicts do not clear this delivery for
        # layout. Each status names a different first action, so they are never merged
        # into one "blocked" — an absent report (nobody ran the gate), an unusable one,
        # a FAIL, and a PASS of insufficient scope are four different problems.
        status = acceptance["status_code"]
        warnings.append(
            "C03 ran, but its stage-entry verdicts do not clear this delivery for C04 "
            "layout. Existence of the C03 files is not acceptance of them."
        )
        gap_txt = " | ".join(acceptance["gaps"])
        next_step = (
            "Clear the C03 stage-entry gates before starting layout — the gate values "
            f"are never relaxed to pass (no-silent-fallback). {gap_txt}"
        )
    elif not present_groups:
        status = "blocked"
        next_step = "No upstream constraints provided — supply C01 interface and C03 mechanical constraints."
    elif tier == 3:
        status = "layout_constraints_drafted_tier3_handoff"
        next_step = (
            "Tier-3 delivery ceiling = placement + SI constraints; routing goes to a "
            "professional EDA tool + human SI. Emit the SI constraint handoff "
            "(emit_si_constraint_export), then hand to the layout/SI engineer."
        )
    else:
        status = "layout_constraints_drafted"
        next_step = "Hand to the layout engineer for board outline, placement, and stackup decisions."

    # Scope warnings are merged on ONE path, not inside the blocking branch: a
    # narrowed verdict is exactly as true when entry opens as when it closes, and
    # attaching them only to the refusal would drop them precisely in the case a
    # reader acts on ("cleared for layout") — the scope caveat vanishing at the
    # moment it starts to matter.
    warnings.extend(acceptance.get("warnings", []))

    return C04LayoutReadiness(
        folder=str(root),
        present_groups=present_groups,
        pending=list(_LAYOUT_OWNED_PENDING),
        constraints_present=constraints_present,
        placement_doc_present=placement_present,
        status=status,
        next_step=next_step,
        warnings=warnings,
        upstream=upstream,
        feasibility=feasibility,
        c03_acceptance=acceptance,
    )
