# BR3 (2026-07-06): engine revision stamp. Content-hash of the core engine
# source files so "which copy is live" (host / engpatch / site-packages) is
# one-glance provable. compose_schematic prints it; sync_engine.sh verifies it.
import hashlib as _hashlib
from pathlib import Path as _Path


def _compute_engine_rev() -> str:
    h = _hashlib.sha256()
    here = _Path(__file__).parent
    for fn in ("composer.py", "kicad_emit.py", "fidelity.py", "render_qa.py", "block_drafter.py"):
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
from .fidelity import (FidelityError, FidelityInputError, FidelityReport,
                       verify_netlist_fidelity, verify_partition_fidelity)
from .design_suggest import (PIN_CLASSES, SUGGEST_STATUSES,
                             DesignSuggestInputError, design_suggest)
from .render_qa import TextQAReport, qa_svg_text
from .readability_gate import ScoredSubjectError, readability_gate
# block_drafter / block_qa are LAZY (PEP 562, see __getattr__ at the bottom):
# they import kiutils, which the schematic/routing side of this package does not
# need. Importing them eagerly made `from bodesign_eda_bridge import
# compose_schematic` fail with ModuleNotFoundError: kiutils on any host without
# the drafting extras — composer.py itself imports only stdlib. That is the same
# defect BR_20260730 F1 fixed in workflow-core (a stdlib-only gate made
# unreachable by a sibling's heavy dependency), found here because the N1/N2
# tests below could not import composer on a bare host.
from .kicad_symbol import KiCadSymbolEmitResult, KiCadSymbolPin, emit_kicad_symbol, emit_kicad_symbol_library_from_pin_table
from .bom_export import BomResult, export_bom, export_netlist
from .component_fetch import fetch_component, fetch_components, search_components
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
from .preplace import (
    PartGeom,
    PreplaceResult,
    compute_utilization,
    count_overlap_pairs,
    overlap_pair_details,
    preplace,
)
from .routing import (
    DEFAULT_AUTOROUTE_PASSES,
    apply_pad_intrinsic_overrides,
    autoroute,
    autoroute_preflight,
    build_dsn_with_netclasses,
    classify_autoroute_readiness,
    classify_clearance_violation,
    clean_micro_stubs,
    drc_gate,
    length_match_bus,
    net2pcb_board,
    placement_preflight,
    pour_planes,
    resolve_connector_pads,
    router_via_budget,
    si_check,
    si_status,
    via_in_pad,
    widen_bus_tracks,
)
from .c04_gate import C04GateInputError, c04_placement_geometry_gate
from .c04_manifest import c04_board_manifest
from .c04_gerber import c04_gerber_gate
from .c04_routing import c04_routing_gate
from .c02_mesh_gate import C02MeshInputError, c02_mesh_gate
from .c02_chain import C02ChainInputError, c02_chain_check, c02_view_coverage
from .c01_scene_gate import C01SceneInputError, c01_scene_gate
from .c00_prd_gate import C00PrdInputError, c00_prd_gate

__all__ = [
    "C00PrdInputError",
    "c00_prd_gate",
    "C01SceneInputError",
    "c01_scene_gate",
    "DEFAULT_AUTOROUTE_PASSES",
    "analyzer_engine_status",
    "resolve_skill",
    "fetch_component",
    "fetch_components",
    "search_components",
    "autoroute",
    "autoroute_preflight",
    "build_dsn_with_netclasses",
    "apply_pad_intrinsic_overrides",
    "classify_autoroute_readiness",
    "classify_clearance_violation",
    "clean_micro_stubs",
    "drc_gate",
    "length_match_bus",
    "net2pcb_board",
    "router_via_budget",
    "PLACEMENT_RULES",
    "get_placement_rule",
    "PartGeom",
    "PreplaceResult",
    "compute_utilization",
    "count_overlap_pairs",
    "overlap_pair_details",
    "preplace",
    "placement_preflight",
    "pour_planes",
    "resolve_connector_pads",
    "si_check",
    "si_status",
    "via_in_pad",
    "widen_bus_tracks",
    "c04_placement_geometry_gate",
    "c04_board_manifest",
    "c04_gerber_gate",
    "c04_routing_gate",
    "c02_mesh_gate",
    "c02_chain_check",
    "c02_view_coverage",
    "C02ChainInputError",
    "C02MeshInputError",
    "C04GateInputError",
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
    "FidelityInputError",
    "FidelityReport",
    "verify_partition_fidelity",
    # WP4 netlist-only gate. Exported at package level because gate.py's verb
    # registry declares (module, callable) pairs and tests/test_landing_gate.py
    # resolves every one of them by getattr -- a registry row naming a callable
    # this package does not expose is a false declaration, not a lazy import.
    "verify_netlist_fidelity",
    # WP5 pin-class suggestion router (DD-02).
    "design_suggest",
    "DesignSuggestInputError",
    "PIN_CLASSES",
    "SUGGEST_STATUSES",
    "TextQAReport",
    "qa_svg_text",
    # WP6 form-axis readability gate. Exported for the same reason
    # verify_netlist_fidelity is: gate.py's registry declares (module, callable)
    # pairs and tests/test_landing_gate.py resolves each by getattr, so a row
    # naming a callable this package does not expose is a false declaration.
    "readability_gate",
    "ScoredSubjectError",
    "PinoutBlock",
    "draw_block",
    "BlockQAVerdict",
    "qa_block",
    "qa_loop",
]

# ---------------------------------------------------------------------------
# Lazy attribute resolution (PEP 562) for the kiutils-dependent drafting side.
#
# BR_20260730b: `composer` and the routing/gate modules import only stdlib, but
# an eager `from .block_drafter import ...` at module scope made the WHOLE
# package unimportable without kiutils. A caller asking for compose_schematic
# paid for a dependency it never used — the F1 shape (BR_20260730), one package
# over.
#
# Deliberately NOT a try/except ImportError that degrades to None: a missing
# name must still raise, and asking for draw_block without kiutils must still
# report the real ModuleNotFoundError. This defers the import, it does not
# swallow it — no silent fallback.
_LAZY_SUBMODULE_ATTRS = {
    "PinoutBlock": ".block_drafter",
    "draw_block": ".block_drafter",
    "BlockQAVerdict": ".block_qa",
    "qa_block": ".block_qa",
    "qa_loop": ".block_qa",
}


def __getattr__(name: str):
    module = _LAZY_SUBMODULE_ATTRS.get(name)
    if module is None:
        # Preserve normal semantics: a genuinely unknown attribute is an
        # AttributeError, not a confusing ImportError from a guessed module.
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module, __name__), name)
    globals()[name] = value  # resolve once; subsequent access is a plain lookup
    return value


def __dir__() -> list:
    return sorted(set(globals()) | set(_LAZY_SUBMODULE_ATTRS))
