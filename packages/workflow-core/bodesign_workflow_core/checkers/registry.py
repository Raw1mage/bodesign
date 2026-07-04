"""M1-4 — verify-checker registry (DD-4: control.* ↔ executable checker map).

The registry is the single, inspectable table of skillification progress: for
every control that has been (or will be) realised as a checker, it records the
DD-1 executability tier, which of the 5 trust layers it belongs to, the pipeline
stage it runs at, the callable, the IR fields it reads, and its landing status
(landed / stub / advisory). It is the observability panel for "how many of the
N controls are actually enforced".

Design (DD-4):
- Each entry is a `checker_binding` (see plan data-schema.json): control_id, tier,
  trust_layer, stage, checker_fn, ir_fields[], status.
- The registry connects to ORACLE_TOOLS: a landed T-A checker emits its evidence
  under an ORACLE_TOOLS member (`envelope_tool`), so an ExtractedRequirement can
  point its oracle_tool at it. Every binding's envelope_tool is validated against
  ORACLE_TOOLS at construction — a typo fails fast, never a silent bad oracle.
- no-fabrication guard: a binding whose control confidence is partial/todo may
  NOT be registered at tier T-A (reuses guard_tier). Registration enforces it.

The registry does NOT duplicate ragbase: the control's authoritative confidence
and threshold_block live in ragbase; the binding records the code-side mapping
(tier/stage/fn/ir_fields/status) plus the control_id join key. Confidence is
passed in at registration so the tier guard can run without a DB read here.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from ..requirement_planning import ORACLE_TOOLS
from .board_edge_keepout import check_board_edge_keepout, guard_tier
from .copper_spacing import check_spacing_via_return_path
from .datasheet_derating import check_datasheet_derating
from .decoupling_pdn import check_decoupling_pdn
from .placement_topology import check_placement_topology
from .errors import CheckerError

_VALID_TIERS: frozenset[str] = frozenset({"T-A", "T-B", "T-C"})
_VALID_STATUS: frozenset[str] = frozenset({"landed", "stub", "advisory"})


@dataclass(frozen=True, slots=True)
class CheckerBinding:
    """One control.* → checker mapping row (plan data-schema.json checker_binding).

    Taxonomy:
      - name: CheckerBinding
      - represents: the code-side skillification record for a single control.
      - input (construction): control_id, tier, trust_layer(1..5), stage(C00..C04),
        status(landed|stub|advisory), optional checker_fn callable, ir_fields[],
        envelope_tool(ORACLE_TOOLS member or None), confidence(verified|partial|todo).
      - output: an immutable validated row; __post_init__ raises on any contract
        breach (bad tier/status/trust_layer, unknown envelope_tool, partial→T-A).
      - must NOT be read as: the source of truth for confidence/threshold — those
        stay in ragbase; this row carries the join key + code mapping only.
      - complete when: construction returns without raising.
    """

    control_id: str
    tier: str
    trust_layer: int
    stage: str
    status: str
    confidence: str
    checker_fn: Callable[..., Any] | None = None
    ir_fields: tuple[str, ...] = ()
    envelope_tool: str | None = None

    def __post_init__(self) -> None:
        if self.tier not in _VALID_TIERS:
            raise CheckerError(
                "CHK_BINDING_INVALID",
                f"binding {self.control_id!r} has invalid tier {self.tier!r}",
                control_id=self.control_id,
            )
        if self.status not in _VALID_STATUS:
            raise CheckerError(
                "CHK_BINDING_INVALID",
                f"binding {self.control_id!r} has invalid status {self.status!r}",
                control_id=self.control_id,
            )
        if not (1 <= self.trust_layer <= 5):
            raise CheckerError(
                "CHK_BINDING_INVALID",
                f"binding {self.control_id!r} trust_layer {self.trust_layer} out of 1..5",
                control_id=self.control_id,
            )
        if self.envelope_tool is not None and self.envelope_tool not in ORACLE_TOOLS:
            raise CheckerError(
                "CHK_BINDING_INVALID",
                f"binding {self.control_id!r} envelope_tool {self.envelope_tool!r} "
                f"not in ORACLE_TOOLS (allowed: {', '.join(ORACLE_TOOLS)})",
                control_id=self.control_id,
            )
        # no-fabrication: partial/todo control may not be a T-A hard gate.
        guard_tier(self.control_id, self.confidence, self.tier)


@dataclass
class CheckerRegistry:
    """The skillification progress table (DD-4 observability panel).

    Taxonomy:
      - name: CheckerRegistry
      - represents: the in-memory collection of CheckerBinding rows keyed by
        control_id, plus progress counters.
      - input: register(binding) calls.
      - output: lookup(control_id), all(), and summary() (landed/stub/advisory
        + tier counts).
      - must NOT be read as: a persistence layer — ragbase remains the durable
        store; this projects the code-side map for a running process.
      - complete when: (a lookup/summary is a pure read of what was registered).
    """

    _bindings: dict[str, CheckerBinding] = field(default_factory=dict)

    def register(self, binding: CheckerBinding) -> None:
        if binding.control_id in self._bindings:
            raise CheckerError(
                "CHK_BINDING_DUPLICATE",
                f"binding for {binding.control_id!r} already registered",
                control_id=binding.control_id,
            )
        self._bindings[binding.control_id] = binding

    def lookup(self, control_id: str) -> CheckerBinding | None:
        return self._bindings.get(control_id)

    def all(self) -> tuple[CheckerBinding, ...]:
        return tuple(self._bindings[k] for k in sorted(self._bindings))

    def summary(self) -> dict[str, int]:
        """Return counts by status and tier — the progress panel."""
        out: dict[str, int] = {
            "total": len(self._bindings),
            "landed": 0, "stub": 0, "advisory": 0,
            "T-A": 0, "T-B": 0, "T-C": 0,
        }
        for b in self._bindings.values():
            out[b.status] += 1
            out[b.tier] += 1
        return out


def build_pilot_registry() -> CheckerRegistry:
    """Register the M1 三試點 into a fresh registry (the DD-6 pilots).

    - decoupling-pdn : T-A landed, trust layer 2 (crosscheck/placement), C04,
      IR-native, emits under drc_gate.
    - board-edge-keepout : T-B stub, trust layer 2, C04, needs board_outline
      (M2-2 backlog) — no envelope_tool yet (not landed).
    - kicad-default-severities : T-A landed, trust layer 1 (ERC/DRC), C03/C04,
      erc artifact, emits under erc.
    """
    reg = CheckerRegistry()
    reg.register(CheckerBinding(
        control_id="control.power.decoupling-pdn-strategy",
        tier="T-A", trust_layer=2, stage="C04", status="landed",
        confidence="verified", checker_fn=check_decoupling_pdn,
        ir_fields=("components[].placement.x", "components[].placement.y", "power_pin"),
        envelope_tool="drc_gate",
    ))
    reg.register(CheckerBinding(
        control_id="control.mech.board-edge-keepout",
        tier="T-B", trust_layer=2, stage="C04", status="landed",
        confidence="verified", checker_fn=check_board_edge_keepout,
        ir_fields=("board_outline.edges", "features[].x", "features[].y"),
        envelope_tool="drc_gate",
    ))
    reg.register(CheckerBinding(
        control_id="control.verify.kicad-default-severities",
        tier="T-A", trust_layer=1, stage="C03", status="landed",
        confidence="verified", checker_fn=None,  # realised as _adapt_erc adapter
        ir_fields=("erc_report",),
        envelope_tool="erc",
    ))
    _register_spacing_cluster(reg)
    _register_placement_cluster(reg)
    _register_derating_cluster(reg)
    return reg


def _register_spacing_cluster(reg: "CheckerRegistry") -> None:
    """Register the M2-1 copper-spacing/clearance control cluster (DD-7).

    One IR-readable metric is landed T-A; the rest are honest T-B backlog —
    their clearance metric needs copper trace / polygon / creepage-path geometry
    that the design IR does NOT carry (contracts.py: only placement x/y,
    Net.connected_pads netlist, GeometryPrimitive x/y). We register them at T-B
    with the IR fields they WOULD need, so the progress panel shows the parser
    gap rather than a false green — never hard-coding a fake IR field.

    - si.spacing-via-return-path : T-A landed, trust layer 2 (crosscheck/layout),
      C04. Signal-via→return-via distance over net-tagged located features
      (GeometryPrimitive x/y). Emits under drc_gate.
    - dfm.ipc-clearance-voltage / safety.creepage-clearance /
      safety.functional-spacing-formula / mech.mounting-hole-clearance : T-B
      stub — verified knowledge, but the gated quantity (copper edge-to-edge /
      creepage surface path / functional net-pair spacing) is not present in IR.
      No envelope_tool (not landed as a gate).
    """
    reg.register(CheckerBinding(
        control_id="control.si.spacing-via-return-path",
        tier="T-A", trust_layer=2, stage="C04", status="landed",
        confidence="verified", checker_fn=check_spacing_via_return_path,
        ir_fields=("signal_vias[].x", "signal_vias[].y",
                   "return_vias[].x", "return_vias[].y"),
        envelope_tool="drc_gate",
    ))
    reg.register(CheckerBinding(
        control_id="control.dfm.ipc-clearance-voltage",
        tier="T-B", trust_layer=1, stage="C04", status="stub",
        confidence="verified", checker_fn=None,
        ir_fields=("net_pair_spacing_mm",),  # copper edge-to-edge: NOT in IR
    ))
    reg.register(CheckerBinding(
        control_id="control.safety.creepage-clearance",
        tier="T-B", trust_layer=1, stage="C04", status="stub",
        confidence="verified", checker_fn=None,
        ir_fields=("creepage_surface_path_mm",),  # surface path: NOT in IR
    ))
    reg.register(CheckerBinding(
        control_id="control.safety.functional-spacing-formula",
        tier="T-B", trust_layer=1, stage="C04", status="stub",
        confidence="verified", checker_fn=None,
        ir_fields=("net_pair_spacing_mm", "working_voltage_v"),  # trace geom: NOT in IR
    ))
    reg.register(CheckerBinding(
        control_id="control.mech.mounting-hole-clearance",
        tier="T-B", trust_layer=2, stage="C04", status="stub",
        confidence="verified", checker_fn=None,
        ir_fields=("mounting_holes[].x", "mounting_holes[].y",
                   "copper_keepout_mm"),  # hole-to-copper keepout: NOT in IR
    ))


def _register_placement_cluster(reg: "CheckerRegistry") -> None:
    """Register the M2-3 placement-topology control cluster (DD-7).

    Of the placement/power/rf/protection/esd controls, only those carrying a
    verbatim ABSOLUTE distance with a cited source anchor can be a clean T-A
    distance gate here (component-to-anchor over placement x/y). The rest gate
    a COMPARATIVE / in-line / net-semantic topology that the design IR does not
    yet resolve, so they are honest T-B backlog (verified knowledge, IR gap) —
    never hard-coded, so the panel shows the parser gap instead of a false green.

    - esd.tvs-placement-routing : T-A landed, trust layer 2, C04. TVS-to-connector
      absolute distance <=10mm (TI slva680A / atlaspcb). threshold_block
      materialized into ragbase. Emits under drc_gate.
    - protection.tvs-esd-layout / power.current-sense-layout / power.charger-ic-layout
      / power.high-current-via-ground / power.power-stage-hot-loop /
      rf.antenna-keepout / rf.transmission-line-ground : T-B stub — verified,
      but the gated relation (comparative trace length, in-line ordering, net
      classification, ground-plane presence) is not IR-readable. No envelope_tool.
    """
    reg.register(CheckerBinding(
        control_id="control.esd.tvs-placement-routing",
        tier="T-A", trust_layer=2, stage="C04", status="landed",
        confidence="verified", checker_fn=check_placement_topology,
        ir_fields=("anchor.x", "anchor.y", "parts[].x", "parts[].y"),
        envelope_tool="drc_gate",
    ))
    for cid, layer in (
        ("control.protection.tvs-esd-layout", 2),
        ("control.power.current-sense-layout", 2),
        ("control.power.charger-ic-layout", 2),
        ("control.power.high-current-via-ground", 2),
        ("control.power.power-stage-hot-loop", 2),
        ("control.rf.antenna-keepout", 2),
        ("control.rf.transmission-line-ground", 2),
    ):
        reg.register(CheckerBinding(
            control_id=cid,
            tier="T-B", trust_layer=layer, stage="C04", status="stub",
            confidence="verified", checker_fn=None,
            ir_fields=("net_semantic_classification",),  # topology relation: NOT in IR
        ))


def _register_derating_cluster(reg: "CheckerRegistry") -> None:
    """Register the M2-4 datasheet-derating control cluster (DD-7).

    These gate a component's DESIGN value against its datasheet RATING via a
    numeric derating factor / surge formula read from the ragbase threshold_block
    (materialized in M2-4) — not IR geometry. All three carry a verbatim原廠
    derating value with a cited source anchor and are verified, so they are clean
    T-A landed gates. They emit under `spice` (the electrical/component-spec
    oracle). The design/rating inputs are supplied by the caller (BOM + datasheet
    lookup); a missing input fails fast, never a silent default rating.

    - protection.fuse-ptc-derating : fuse continuous current <= 0.75×rating
      (Littelfuse Fuseology 25% derating).
    - protection.mov-surge-selection : system continuous voltage <= VM ceiling
      (Littelfuse Varistor AN).
    - protection.ntc-inrush-selection : t=0 surge V/R25 <= max inrush
      (Vishay/Ametherm Doc#24291).
    """
    for cid, fields in (
        ("control.protection.fuse-ptc-derating",
         ("design_value", "rating")),
        ("control.protection.mov-surge-selection",
         ("design_value", "rating")),
        ("control.protection.ntc-inrush-selection",
         ("input_voltage_v", "r25_ohm", "max_inrush_current_a")),
    ):
        reg.register(CheckerBinding(
            control_id=cid,
            tier="T-A", trust_layer=4, stage="C03", status="landed",
            confidence="verified", checker_fn=check_datasheet_derating,
            ir_fields=fields,
            envelope_tool="spice",
        ))
