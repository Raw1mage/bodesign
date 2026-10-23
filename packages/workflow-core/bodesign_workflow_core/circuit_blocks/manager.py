"""
Manager and instantiation engine for Verified Circuit Blocks.

Handles block registration, parameter validation, refdes collision resolution,
netlist fragment merging, and spatial constraint extraction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from .library import get_core_circuit_blocks
from .schema import (
    BlockLayoutConstraint,
    BlockValidationError,
    CircuitBlockDefinition,
)


@dataclass(slots=True)
class InstantiatedComponent:
    refdes: str
    value: str
    package: str
    part_number: str | None
    lcsc_part: str | None
    description: str
    pin_connections: dict[str, str]  # pin_number -> resolved_net_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "refdes": self.refdes,
            "value": self.value,
            "package": self.package,
            "part_number": self.part_number,
            "lcsc_part": self.lcsc_part,
            "description": self.description,
            "pin_connections": dict(self.pin_connections),
        }


@dataclass(slots=True)
class AppliedBlockResult:
    block_id: str
    instance_id: str
    components: list[InstantiatedComponent]
    net_connections: dict[str, list[str]]  # net_name -> list of "REF.PIN"
    layout_constraints: list[BlockLayoutConstraint]
    bom_rows: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "instance_id": self.instance_id,
            "components": [c.to_dict() for c in self.components],
            "net_connections": {k: list(v) for k, v in self.net_connections.items()},
            "layout_constraints": [l.to_dict() for l in self.layout_constraints],
            "bom_rows": list(self.bom_rows),
        }


class CircuitBlockRegistry:
    """In-memory registry of certified circuit blocks."""

    def __init__(self, load_core: bool = True) -> None:
        self._blocks: dict[str, CircuitBlockDefinition] = {}
        if load_core:
            for b in get_core_circuit_blocks():
                self.register(b)

    def register(self, block: CircuitBlockDefinition) -> None:
        block.validate()
        self._blocks[block.block_id] = block

    def get(self, block_id: str) -> CircuitBlockDefinition:
        if block_id not in self._blocks:
            raise BlockValidationError(
                "BLOCK_NOT_FOUND",
                f"Circuit block '{block_id}' not found in registry. Available: {sorted(self._blocks.keys())}",
            )
        return self._blocks[block_id]

    def list_blocks(self) -> list[dict[str, Any]]:
        return [
            {
                "block_id": b.block_id,
                "name": b.name,
                "category": b.category,
                "description": b.description,
                "citation": b.datasheet_citation,
                "ports": [p.name for p in b.external_ports],
                "component_count": len(b.components),
            }
            for b in self._blocks.values()
        ]


def _next_refdes(prefix: str, used_refdes: set[str]) -> str:
    """Finds the lowest integer index N >= 1 such that f'{prefix}{N}' is not used."""
    n = 1
    while f"{prefix}{n}" in used_refdes:
        n += 1
    used_refdes.add(f"{prefix}{n}")
    return f"{prefix}{n}"


def apply_circuit_block(
    block_id: str,
    port_mapping: dict[str, str],
    instance_id: str = "inst1",
    used_refdes: set[str] | None = None,
    registry: CircuitBlockRegistry | None = None,
) -> AppliedBlockResult:
    """Instantiates a circuit block with caller's net mapping and refdes conflict avoidance."""
    reg = registry or CircuitBlockRegistry()
    block = reg.get(block_id)

    # 1. Validate Port Mapping
    required_ports = {p.name for p in block.external_ports if p.required}
    missing_ports = required_ports - set(port_mapping.keys())
    if missing_ports:
        raise BlockValidationError(
            "PORT_MAPPING_INCOMPLETE",
            f"Missing required port mappings for block '{block_id}': {sorted(missing_ports)}",
            {"missing_ports": sorted(missing_ports)},
        )

    # Internal nets are scoped per instance to prevent cross-instance short circuits
    resolved_nets: dict[str, str] = dict(port_mapping)
    for port in block.external_ports:
        if not port.required and port.name not in resolved_nets:
            resolved_nets[port.name] = f"NET_{instance_id}_{port.name}"

    for inet in block.internal_nets:
        resolved_nets[inet.name] = f"NET_{instance_id}_{inet.name}"

    ref_set = set(used_refdes or set())
    components_out: list[InstantiatedComponent] = []
    bom_rows_out: list[dict[str, Any]] = []
    net_connections: dict[str, list[str]] = {}

    # Map generic component prefix to assigned refdes list
    refdes_by_prefix: dict[str, list[str]] = {}

    for comp in block.components:
        assigned_ref = _next_refdes(comp.ref_prefix, ref_set)
        refdes_by_prefix.setdefault(comp.ref_prefix, []).append(assigned_ref)

        pin_conns: dict[str, str] = {}
        for pin_num, pin_net in comp.pins.items():
            resolved_net = resolved_nets[pin_net]
            pin_conns[pin_num] = resolved_net

            # Track node in netlist
            node_key = f"{assigned_ref}.{pin_num}"
            net_connections.setdefault(resolved_net, []).append(node_key)

        inst_comp = InstantiatedComponent(
            refdes=assigned_ref,
            value=comp.value,
            package=comp.package,
            part_number=comp.part_number,
            lcsc_part=comp.lcsc_part,
            description=comp.description,
            pin_connections=pin_conns,
        )
        components_out.append(inst_comp)

        bom_rows_out.append(
            {
                "Designator": assigned_ref,
                "Value": comp.value,
                "Footprint": comp.package,
                "MPN": comp.part_number or comp.value,
                "LCSC_Part": comp.lcsc_part or "",
                "Description": comp.description,
                "Status": "finalized" if comp.part_number else "design-ready",
            }
        )

    # Map layout constraints with actual refdes
    mapped_constraints: list[BlockLayoutConstraint] = []
    for constraint in block.layout_constraints:
        mapped_targets: list[str] = []
        for target in constraint.target_elements:
            if target in refdes_by_prefix:
                mapped_targets.extend(refdes_by_prefix[target])
            elif target in port_mapping:
                mapped_targets.append(port_mapping[target])
            else:
                mapped_targets.append(target)

        mapped_constraints.append(
            BlockLayoutConstraint(
                rule_type=constraint.rule_type,
                target_elements=mapped_targets,
                max_distance_mm=constraint.max_distance_mm,
                description=constraint.description,
            )
        )

    return AppliedBlockResult(
        block_id=block_id,
        instance_id=instance_id,
        components=components_out,
        net_connections=net_connections,
        layout_constraints=mapped_constraints,
        bom_rows=bom_rows_out,
    )
