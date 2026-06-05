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
