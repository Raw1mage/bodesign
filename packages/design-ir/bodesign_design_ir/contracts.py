from dataclasses import dataclass, field
from typing import Literal

from bodesign_shared import EvidenceRef

# Closed set of net roles. Role is supplied EXPLICITLY from upstream schematic
# net-class / user annotation — never inferred from the net name (no-fabrication).
NetRole = Literal["power", "ground", "high_current", "rf", "signal", "differential"]
NET_ROLES: tuple[NetRole, ...] = (
    "power",
    "ground",
    "high_current",
    "rf",
    "signal",
    "differential",
)


@dataclass(slots=True)
class ComponentInstance:
    refdes: str
    part_number: str | None = None
    footprint: str | None = None
    placement: dict[str, float | str] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    # G7/DD-13 minimal comparator extensions (all optional; existing callers unaffected):
    # value: passive component value (e.g. "10k", "100n"); None for non-passives.
    # optional: reference designs mark non-essential parts (bulk caps, debug headers);
    #   absence in a candidate is NOT penalized by the reference comparator.
    # flexible_pin_groups: named sets of interchangeable pins (e.g. GPIO banks);
    #   {"GPIO_A": ["PA0", "PA1", "PA2"]} — any member satisfies a match.
    value: str | None = None
    optional: bool = False
    flexible_pin_groups: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class Net:
    name: str
    connected_pads: list[str] = field(default_factory=list)
    constraints: dict[str, str | float] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    # Net-role extension (all optional; existing callers unaffected):
    # role: closed-enum role supplied explicitly from schematic net-class / user
    #   annotation. None when unknown — NEVER guessed from net name (no-fabrication).
    # role_evidence: provenance for role, aligned with ValidationEvidence source_anchor.
    #   Invariant: role is not None <=> role_evidence is not None (enforced by
    #   set_net_role; the dataclass itself does not guard it).
    role: NetRole | None = None
    role_evidence: EvidenceRef | None = None


@dataclass(slots=True)
class BoardLayer:
    name: str
    layer_type: str
    source_artifact_id: str | None = None


@dataclass(slots=True)
class BoardObject:
    id: str
    object_type: str
    layer: str | None = None
    net: str | None = None
    geometry: dict[str, object] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass(slots=True)
class GeometryPrimitive:
    """A spatially-located board feature fused from manufacturing evidence.

    Coordinates are kept in the source evidence frame (IPC/drill mil-scale for
    a reference board) rather than re-projected, so downstream consumers can decide on a
    canonical unit once a board-origin transform is resolved.
    """

    id: str
    primitive_type: str
    x: float
    y: float
    net: str | None = None
    refdes: str | None = None
    pin: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass(slots=True)
class BoardDesign:
    id: str
    version: str
    title: str
    components: list[ComponentInstance] = field(default_factory=list)
    nets: list[Net] = field(default_factory=list)
    layers: list[BoardLayer] = field(default_factory=list)
    board_objects: list[BoardObject] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    confidence_summary: dict[str, float | str] = field(default_factory=dict)
