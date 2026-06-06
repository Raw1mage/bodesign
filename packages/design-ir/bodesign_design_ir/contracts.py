from dataclasses import dataclass, field

from bodesign_shared import EvidenceRef


@dataclass(slots=True)
class ComponentInstance:
    refdes: str
    part_number: str | None = None
    footprint: str | None = None
    placement: dict[str, float | str] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass(slots=True)
class Net:
    name: str
    connected_pads: list[str] = field(default_factory=list)
    constraints: dict[str, str | float] = field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


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
    Rockbox) rather than re-projected, so downstream consumers can decide on a
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
