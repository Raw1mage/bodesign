# BR3 (2026-07-06): engine revision stamp. Content-hash of the core engine
# source files so "which copy is live" (host / engpatch / site-packages) is
# one-glance provable. compose_schematic prints it; sync_engine.sh verifies it.
import hashlib as _hashlib
from pathlib import Path as _Path


def _compute_engine_rev() -> str:
    h = _hashlib.sha256()
    here = _Path(__file__).parent
    for fn in ("composer.py", "kicad_emit.py", "fidelity.py", "render_qa.py"):
        fp = here / fn
        if fp.exists():
            h.update(fp.read_bytes())
    return h.hexdigest()[:12]


__engine_rev__ = _compute_engine_rev()

from .contracts import KiCadBridgePlan, KiCadNativeCapability, KiCadNativeExtensionContract, build_kicad_native_extension_contract, plan_kicad_bridge
from .kicad_emit import (
    EmitComponent,
    EmitNet,
    ErcClassification,
    KiCadValidationResult,
    SchematicEmitResult,
    classify_erc_report,
    emit_kicad_schematic,
    load_symbol,
    validate_kicad_schematic,
)
from .fidelity import FidelityError, FidelityReport, verify_partition_fidelity
from .render_qa import TextQAReport, qa_svg_text
from .kicad_symbol import KiCadSymbolEmitResult, KiCadSymbolPin, emit_kicad_symbol, emit_kicad_symbol_library_from_pin_table
from .bom_export import BomResult, export_bom, export_netlist
from .component_fetch import fetch_component, search_components
from .dxf_dwg import dwg_to_dxf, dxf_to_dwg
from .composer import ComposeResult, compose_schematic
from .fab import FabResult, emit_fab_outputs
from .layout import LayoutResult, PCBNEW_AVAILABLE, emit_layout
from .model_render import ModelRenderResult, render_board_model, render_enclosure_model
from .impedance import solve_impedance
from .pin_allocation import PinAllocation, PinAllocationRow, build_pin_allocation, render_pin_allocation_csv, render_pin_allocation_md
from .simulate import SimResult, simulate_schematic
from .pcb_verify import PcbVerifyResult, analyze_emc, analyze_thermal
from .skill_paths import analyzer_engine_status, resolve_skill
from .footprint_map import FootprintCandidate, PackageQuery, build_footprint_map, match_footprints
from .placement_rules import RULES as PLACEMENT_RULES, get_rule as get_placement_rule
from .preplace import PartGeom, PreplaceResult, preplace
from .routing import (
    autoroute,
    drc_gate,
    length_match_bus,
    net2pcb_board,
    pour_planes,
    resolve_connector_pads,
    si_check,
    si_status,
    via_in_pad,
    widen_bus_tracks,
)

__all__ = [
    "analyzer_engine_status",
    "resolve_skill",
    "fetch_component",
    "search_components",
    "autoroute",
    "drc_gate",
    "length_match_bus",
    "net2pcb_board",
    "PLACEMENT_RULES",
    "get_placement_rule",
    "PartGeom",
    "PreplaceResult",
    "preplace",
    "pour_planes",
    "resolve_connector_pads",
    "si_check",
    "si_status",
    "via_in_pad",
    "widen_bus_tracks",
    "BomResult",
    "ComposeResult",
    "EmitComponent",
    "EmitNet",
    "ErcClassification",
    "classify_erc_report",
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
    "solve_impedance",
    "simulate_schematic",
    "build_pin_allocation",
    "render_pin_allocation_csv",
    "render_pin_allocation_md",
    "SchematicEmitResult",
    "build_footprint_map",
    "build_kicad_native_extension_contract",
    "compose_schematic",
    "dwg_to_dxf",
    "dxf_to_dwg",
    "emit_fab_outputs",
    "export_bom",
    "export_netlist",
    "emit_kicad_symbol",
    "emit_layout",
    "render_board_model",
    "render_enclosure_model",
    "ModelRenderResult",
    "emit_kicad_schematic",
    "emit_kicad_symbol_library_from_pin_table",
    "load_symbol",
    "match_footprints",
    "plan_kicad_bridge",
    "validate_kicad_schematic",
    "__engine_rev__",
    "FidelityError",
    "FidelityReport",
    "verify_partition_fidelity",
    "TextQAReport",
    "qa_svg_text",
]
