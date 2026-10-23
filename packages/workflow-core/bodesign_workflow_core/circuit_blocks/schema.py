"""
Schema definition for Verified Circuit Blocks.

Encapsulates dual-aspect engineering contracts:
1. Electrical connectivity: schematic symbols, footprints, BOM attributes, mandated passives.
2. Physical spatial layout: maximum decoupling distances, TVS connector proximity, differential routing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class BlockValidationError(Exception):
    """Raised when circuit block definition or instantiation fails schema validation."""
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.details = details or {}


@dataclass(slots=True)
class BlockPort:
    name: str
    direction: str  # in, out, power, ground, bidirectional
    description: str = ""
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "description": self.description,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockPort:
        return cls(
            name=data["name"],
            direction=data["direction"],
            description=data.get("description", ""),
            required=data.get("required", True),
        )


@dataclass(slots=True)
class BlockComponent:
    ref_prefix: str  # e.g. "R", "C", "U", "D", "L"
    value: str
    package: str
    part_number: str | None = None
    lcsc_part: str | None = None  # Optional LCSC Part Number mapping (e.g. C12345)
    description: str = ""
    mandatory: bool = True
    # Pin number -> internal or port net name
    # e.g. {"1": "IN", "2": "GND", "3": "EN", "4": "NC", "5": "OUT"}
    pins: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_prefix": self.ref_prefix,
            "value": self.value,
            "package": self.package,
            "part_number": self.part_number,
            "lcsc_part": self.lcsc_part,
            "description": self.description,
            "mandatory": self.mandatory,
            "pins": dict(self.pins),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockComponent:
        return cls(
            ref_prefix=data["ref_prefix"],
            value=data["value"],
            package=data["package"],
            part_number=data.get("part_number"),
            lcsc_part=data.get("lcsc_part"),
            description=data.get("description", ""),
            mandatory=data.get("mandatory", True),
            pins=dict(data.get("pins", {})),
        )


@dataclass(slots=True)
class BlockInternalNet:
    name: str
    net_role: str = "signal"  # power, ground, signal, differential, high_current

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "net_role": self.net_role}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockInternalNet:
        return cls(name=data["name"], net_role=data.get("net_role", "signal"))


@dataclass(slots=True)
class BlockLayoutConstraint:
    rule_type: str  # max_distance_to_pin, max_trace_length, proximity_to_connector, differential_pair
    target_elements: list[str]  # e.g. ["C_DECOUPLE", "U_IC"]
    max_distance_mm: float | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "target_elements": list(self.target_elements),
            "max_distance_mm": self.max_distance_mm,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockLayoutConstraint:
        return cls(
            rule_type=data["rule_type"],
            target_elements=list(data.get("target_elements", [])),
            max_distance_mm=data.get("max_distance_mm"),
            description=data.get("description", ""),
        )


@dataclass(slots=True)
class CircuitBlockDefinition:
    block_id: str
    name: str
    category: str  # interface, power, protection, clock, mcu
    description: str
    datasheet_citation: str  # Must cite datasheet section/standard (no ungrounded blocks)
    external_ports: list[BlockPort]
    components: list[BlockComponent]
    internal_nets: list[BlockInternalNet] = field(default_factory=list)
    layout_constraints: list[BlockLayoutConstraint] = field(default_factory=list)
    mandated_passives: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "datasheet_citation": self.datasheet_citation,
            "external_ports": [p.to_dict() for p in self.external_ports],
            "components": [c.to_dict() for c in self.components],
            "internal_nets": [n.to_dict() for n in self.internal_nets],
            "layout_constraints": [l.to_dict() for l in self.layout_constraints],
            "mandated_passives": list(self.mandated_passives),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CircuitBlockDefinition:
        return cls(
            block_id=data["block_id"],
            name=data["name"],
            category=data["category"],
            description=data.get("description", ""),
            datasheet_citation=data.get("datasheet_citation", "UNGROUNDED"),
            external_ports=[BlockPort.from_dict(p) for p in data.get("external_ports", [])],
            components=[BlockComponent.from_dict(c) for c in data.get("components", [])],
            internal_nets=[BlockInternalNet.from_dict(n) for n in data.get("internal_nets", [])],
            layout_constraints=[BlockLayoutConstraint.from_dict(l) for l in data.get("layout_constraints", [])],
            mandated_passives=list(data.get("mandated_passives", [])),
        )

    def validate(self) -> None:
        """Validates that block definition conforms to schema invariants."""
        if not self.block_id or not self.name:
            raise BlockValidationError("BLOCK_SCHEMA_INVALID", "block_id and name must be non-empty.")

        if not self.datasheet_citation or self.datasheet_citation == "UNGROUNDED":
            raise BlockValidationError(
                "BLOCK_CITATION_MISSING",
                f"Circuit block '{self.block_id}' must provide a verified datasheet_citation (天條 4).",
            )

        port_names = {p.name for p in self.external_ports}
        internal_net_names = {n.name for n in self.internal_nets}
        all_nets = port_names | internal_net_names

        for comp in self.components:
            for pin_num, pin_net in comp.pins.items():
                if pin_net not in all_nets:
                    raise BlockValidationError(
                        "BLOCK_NET_UNRESOLVED",
                        f"Component '{comp.ref_prefix}' pin '{pin_num}' connects to unknown net '{pin_net}'. "
                        f"Must be one of external ports or internal nets: {sorted(all_nets)}",
                    )
