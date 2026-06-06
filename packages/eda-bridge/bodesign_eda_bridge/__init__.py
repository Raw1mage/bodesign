from .contracts import KiCadBridgePlan, KiCadNativeCapability, KiCadNativeExtensionContract, build_kicad_native_extension_contract, plan_kicad_bridge
from .kicad_emit import (
    EmitComponent,
    EmitNet,
    KiCadValidationResult,
    SchematicEmitResult,
    emit_kicad_schematic,
    load_symbol,
    validate_kicad_schematic,
)
from .kicad_symbol import KiCadSymbolEmitResult, KiCadSymbolPin, emit_kicad_symbol, emit_kicad_symbol_library_from_pin_table
from .bom_export import BomResult, export_bom, export_netlist
from .composer import ComposeResult, compose_schematic
from .fab import FabResult, emit_fab_outputs
from .layout import LayoutResult, PCBNEW_AVAILABLE, emit_layout
from .pin_allocation import PinAllocation, PinAllocationRow, build_pin_allocation, render_pin_allocation_csv, render_pin_allocation_md
from .simulate import SimResult, simulate_schematic
from .pcb_verify import PcbVerifyResult, analyze_emc, analyze_thermal
from .footprint_map import FootprintCandidate, PackageQuery, build_footprint_map, match_footprints

__all__ = [
    "BomResult",
    "ComposeResult",
    "EmitComponent",
    "EmitNet",
    "FabResult",
    "FootprintCandidate",
    "KiCadBridgePlan",
    "KiCadNativeCapability",
    "KiCadNativeExtensionContract",
    "KiCadSymbolEmitResult",
    "KiCadSymbolPin",
    "KiCadValidationResult",
    "LayoutResult",
    "PCBNEW_AVAILABLE",
    "PackageQuery",
    "PcbVerifyResult",
    "PinAllocation",
    "PinAllocationRow",
    "SimResult",
    "analyze_emc",
    "analyze_thermal",
    "simulate_schematic",
    "build_pin_allocation",
    "render_pin_allocation_csv",
    "render_pin_allocation_md",
    "SchematicEmitResult",
    "build_footprint_map",
    "build_kicad_native_extension_contract",
    "compose_schematic",
    "emit_fab_outputs",
    "export_bom",
    "export_netlist",
    "emit_kicad_symbol",
    "emit_layout",
    "emit_kicad_schematic",
    "emit_kicad_symbol_library_from_pin_table",
    "load_symbol",
    "match_footprints",
    "plan_kicad_bridge",
    "validate_kicad_schematic",
]
