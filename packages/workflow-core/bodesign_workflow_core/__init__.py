from .substate_machine import (
    A2ARole,
    C03State,
    C04State,
    ControlViolationError,
    GateVerdict,
    GovernanceError,
    InvalidReceiptError,
    SelfApprovalProhibitedError,
    StateReceipt,
    StateTransitionBlockedError,
    SubstateMachine,
    mint_receipt,
)
from .blocker_hub import (
    BlockerHub,
    BlockerRecord,
    BlockerStatus,
)
from .circuit_blocks import (
    AppliedBlockResult,
    BlockComponent,
    BlockInternalNet,
    BlockLayoutConstraint,
    BlockPort,
    BlockValidationError,
    CircuitBlockDefinition,
    CircuitBlockRegistry,
    InstantiatedComponent,
    apply_circuit_block,
    get_core_circuit_blocks,
)
from .tidy import (
    BoundingBox,
    FootprintSilkRecord,
    PadGeometry,
    Point2D,
    distribute_passives,
    has_silk_pad_overlap,
    normalize_silk_rotation,
    snap_components,
    snap_coord,
    snap_point,
    tidy_all_footprints,
    tidy_footprint_silk,
    tidy_kicad_pcb,
    tidy_kicad_pcb_content,
)
from .contracts import CandidateDiffItem, GeneratedDesignCandidateWorkspace, ReferenceBoardWorkflowPlan, WorkflowStage, build_generated_design_candidate_workspace, derive_workflow_plan, plan_reference_board_workflow
from .agent_registry import (
    AgentRegistry,
    AgentRegistryError,
    AgentRole,
    load_agent_registry,
)
from .orchestration import (
    BlockerReturn,
    IngestResult,
    OrchestrationError,
    WorkPacket,
    dispatch_work_packet,
    get_blocker,
    get_work_packet,
    ingest_blocker,
    list_blockers,
    list_work_packets,
    return_blocker,
)
from .mode_contracts import (
    C01ModeEntry,
    enter_c01_mode,
    layer_relevant_prd_sections,
)
from .c00_orchestration import (
    Board,
    LayerBoard,
    NextAction,
    c00_orchestration_status,
    c00_orchestration_tick,
)
from .c04_layout_constraints import (
    C04LayoutReadiness,
    C04LayoutResult,
    assess_c04_layout_readiness,
    emit_c04_layout_package,
)
from .c04_placement_gate import (
    PlacementApprovalResult,
    PlacementReviewResult,
    assess_c04_placement_approval,
    emit_c04_placement_review,
)
from .c05_fw_spec import (
    C05FwReadiness,
    C05FwResult,
    assess_c05_fw_readiness,
    scaffold_c05_fw_spec,
)
from .c06_test_plan import (
    C06Readiness,
    C06Result,
    assemble_c06_test_plan,
    assess_c06_readiness,
)
from .gap_report import (
    EvidenceArtifactSummary,
    GapItem,
    ResolvedFact,
    SourceGapReport,
    collect_source_gap_report,
    render_gap_report_markdown,
)
from .orchestration import (
    EVIDENCE_RETURN_SCHEMA,
    EvidenceReturn,
    get_evidence_return,
    ingest_evidence,
    list_evidence_returns,
    return_evidence,
)
from .validation_evidence import (
    VALIDATION_EVIDENCE_SCHEMA,
    ValidationEvidence,
    ValidationEvidenceError,
    ValidationFinding,
    wrap_validation_evidence,
)
# BR_20260730 F1: `.checkers` is NOT eagerly imported.
# checkers/registry.py -> copper_clearance.py needs `bodesign_design_ir` (PCB IR,
# only present in the ee worker). Importing it here made every symbol in this
# package — including the pure-python, zero-dependency CSV gates like check_c03 —
# unreachable from a consumer repo that has no ee environment. A consumer facing
# `ModuleNotFoundError: bodesign_design_ir` on `from bodesign_workflow_core import
# check_c03` hand-writes its own gate instead (that fork then drifts and issues
# verdicts contradicting this package's). The capability existed; it was
# unreachable from where the caller actually stood.
# Resolved lazily via module __getattr__ (PEP 562) so `from bodesign_workflow_core
# import CheckerError` still works unchanged for callers that DO have the ee deps,
# and fails with the real ModuleNotFoundError only when a checker is actually used.
# name -> submodule that owns it. Every entry here is a symbol whose defining
# submodule imports an EXTERNAL bodesign_* package at module level, so importing
# it eagerly would drag that dependency into every consumer of this package.
# Derived from an audit of all eager submodules (BR_20260730): exactly two
# offenders exist — `checkers` (bodesign_design_ir, bodesign_gerber_core via
# copper_clearance) and `package_readiness` (bodesign_reverse_core).
# tests/test_workflow_core_reachability.py re-derives that audit from source and
# fails if a THIRD eager offender appears, so this map cannot silently go stale.
_LAZY_EXTERNAL_DEP_EXPORTS = {
    "CheckerError": "checkers",
    "check_board_edge_keepout": "checkers",
    "check_decoupling_pdn": "checkers",
    "guard_tier": "checkers",
    "DeliverableStatus": "package_readiness",
    "PackageReadiness": "package_readiness",
    "assess_package_readiness": "package_readiness",
    "render_readiness_markdown": "package_readiness",
}


def __getattr__(name: str):
    """PEP 562 lazy resolution for exports whose module needs an ee-only package.

    BR_20260730 F1. Resolution is deferred, NOT suppressed: a caller that actually
    uses one of these still gets the real ModuleNotFoundError, naming the missing
    package. This is removal of an unnecessary eager coupling, not a fallback.
    """
    owner = _LAZY_EXTERNAL_DEP_EXPORTS.get(name)
    if owner is not None:
        import importlib

        mod = importlib.import_module(f".{owner}", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXTERNAL_DEP_EXPORTS))
from .root_cause import (
    ROOT_CAUSE_SCHEMA,
    RootCauseError,
    RootCauseReport,
    load_root_cause_reports,
    record_root_cause,
)
from .reference_crosscheck import (
    DIFF_DIMENSIONS,
    CrossCheckDiff,
    CrossCheckDiffItem,
    CrossCheckError,
    crosscheck_diff,
)
from .design_review import (
    DESIGN_REVIEW_SCHEMA,
    REVIEW_VERDICTS,
    DesignReviewError,
    DesignReviewRecord,
    ReviewScenario,
    load_design_review,
    record_design_review,
    review_gate_status,
)
from .requirement_planning import (
    ORACLE_TOOLS,
    VERIFICATION_STATUSES,
    ClarifyingQuestion,
    DesignIntentPlan,
    ExtractedRequirement,
    SubsystemPlan,
    plan_design_intent,
    requirement_passfail_table,
)
from .evidence_sourcing import (
    MatchedDocument,
    PartEvidence,
    build_design_evidence_manifest,
    extract_part_candidates,
    scan_corpus_for_part,
)
# BR_20260730 F1 (2nd eager offender): package_readiness.py:18 imports
# `bodesign_reverse_core` at module level, so eager-importing it here re-broke the
# consumer-reachability this fix exists to restore. Same lazy treatment as
# `.checkers` above — see _LAZY_EXTERNAL_DEP_EXPORTS.
from .feasibility import (
    FeasibilityVerdict,
    classify_product_feasibility,
)
from .si_handoff import (
    NetClassConstraint,
    SiHandoffResult,
    StackupSpec,
    emit_si_constraint_export,
)
from .c00_prd_template import (
    C00EmitResult,
    C00PrdRubric,
    C00PrdTemplate,
    C00ReadinessResult,
    C00ScaffoldResult,
    C00TemplateError,
    C00UpdateResult,
    assess_c00_prd_readiness,
    c00_update_answers,
    emit_c00_prd_markdown,
    load_c00_prd_rubric,
    load_c00_prd_template,
    scaffold_c00_prd_package,
)
from .prd_bom_crosscheck import (
    CrosscheckResult,
    Verdict,
    prd_bom_crosscheck,
)
from .check_c03 import (
    CheckC03Result,
    RowFinding,
    check_c03,
)
from .c00_prd_docx import (
    C00DocxArchitecture,
    C00DocxArchitectureError,
    C00DocxPackage,
    C00DocxRenderResult,
    load_c00_docx_architecture,
    render_c00_prd_docx_package,
)
from .c01_id_template import (
    C01IdRubric,
    C01IdTemplate,
    C01TemplateError,
    load_c01_id_rubric,
    load_c01_id_template,
    validate_c01_outputs_binding,
)
from .c01_id_package import (
    BucketResult,
    C01AnswerUpdateResult,
    C01ConceptImageResult,
    C01NextQuestionResult,
    C01PackageArtifact,
    C01PackageReadiness,
    C01PackageResult,
    C01PromptArtifactsResult,
    C01ReferenceCuesResult,
    assess_c01_package_readiness,
    c01_add_reference_image,
    c01_confirm_reference_cue,
    c01_next_question,
    c01_update_answers,
    emit_c01_concept_prompts,
    emit_c01_cmf_package,
    emit_c01_id_visual_package,
    emit_c01_rockbox_package,
    emit_c01_uiux_package,
    generate_c01_concept_image,
)
from .c02_me_package import (
    C02ConstraintItem,
    C02ConstraintReadiness,
    C02FieldBinding,
    C02OpenScadResult,
    C02PackageResult,
    C02SkpExportResult,
    C02StepExportResult,
    C02StlExportResult,
    assess_c02_constraint_readiness,
    emit_c02_enclosure_package,
    export_c02_projection_svg,
    export_c02_skp,
    export_c02_step,
    export_c02_stl,
    generate_c02_openscad,
    plan_c02_intent,
    voice_to_design,
)
from .c03_mechanical_constraints import (
    C03MechanicalConstraintResult,
    export_c03_mechanical_constraints,
)
from .c03_partition_diagram import (
    EmitPartitionResult,
    PartitionModel,
    emit_c03_partition_diagram,
)
from .c03_host_block_diagram import (
    EmitHostBlockResult,
    HostBlockModel,
    emit_c03_host_block_diagram,
)
from .reference_crosscheck import (
    ReferenceCheck,
    crosscheck_nets,
    extract_schematic_net_labels,
    reference_nets_from_component_knowledge,
    render_crosscheck_markdown,
)
from .refs_gate import (
    REFS_ANCHOR_MISSING,
    REFS_MANIFEST_INVALID,
    REFS_SSOT_MISSING,
    RefsGateError,
    RefsManifest,
    RefsSource,
    ingest_refs,
    require_refs,
)
from .upstream_constraints import (
    CONNECTOR_FACE_CONFLICT,
    CONSTRAINT_SCHEMA_INVALID,
    UPSTREAM_CONSTRAINT_MISSING,
    ConnectorPlacement,
    FaceLayout,
    UpstreamConstraintError,
    assert_face_frozen,
    parse_face_layout,
    require_upstream_constraints,
    solve_face_placement,
    placement_to_coords,
)
from .board_surgery import (
    BOARD_SURGERY_UNSAFE_PATH,
    CASTELLATION_SPEC_INVALID,
    SAFE_PATH,
    UNSAFE_PATHS,
    BoardSurgeryError,
    CastellatedPad,
    CastellationRequest,
    assert_safe_surgery_path,
    build_castellation,
    parse_castellation_request,
)
from .dod_traceback import (
    DOD_TRACEBACK_FAILED,
    DOD_TRACEBACK_SCHEMA,
    TracebackReport,
    dod_refs_traceback,
)

__all__ = [
    "AgentRegistry",
    "AgentRegistryError",
    "AgentRole",
    "BlockerReturn",
    "Board",
    "C01ModeEntry",
    "LayerBoard",
    "NextAction",
    "CandidateDiffItem",
    "C00EmitResult",
    "C00PrdRubric",
    "C00PrdTemplate",
    "C00ReadinessResult",
    "C00ScaffoldResult",
    "C00TemplateError",
    "C00UpdateResult",
    "C01AnswerUpdateResult",
    "C01ConceptImageResult",
    "C01IdRubric",
    "C01IdTemplate",
    "C01NextQuestionResult",
    "C01PackageArtifact",
    "C01PackageReadiness",
    "C01PackageResult",
    "C01PromptArtifactsResult",
    "C01ReferenceCuesResult",
    "C01TemplateError",
    "C04LayoutReadiness",
    "C04LayoutResult",
    "C05FwReadiness",
    "C05FwResult",
    "C06Readiness",
    "C06Result",
    "C02ConstraintItem",
    "C02ConstraintReadiness",
    "C02OpenScadResult",
    "C02PackageResult",
    "C02SkpExportResult",
    "C02StepExportResult",
    "C02StlExportResult",
    "C03MechanicalConstraintResult",
    "ClarifyingQuestion",
    "DeliverableStatus",
    "DesignIntentPlan",
    "PackageReadiness",
    "ReferenceCheck",
    "CrosscheckResult",
    "CheckC03Result",
    "RowFinding",
    "check_c03",
    "Verdict",
    "assess_c00_prd_readiness",
    "prd_bom_crosscheck",
    "assess_package_readiness",
    "assess_c01_package_readiness",
    "assess_c02_constraint_readiness",
    "FeasibilityVerdict",
    "classify_product_feasibility",
    "NetClassConstraint",
    "StackupSpec",
    "SiHandoffResult",
    "emit_si_constraint_export",
    "crosscheck_nets",
    "c00_update_answers",
    "emit_c00_prd_markdown",
    "extract_schematic_net_labels",
    "reference_nets_from_component_knowledge",
    "render_crosscheck_markdown",
    "render_readiness_markdown",
    "EvidenceArtifactSummary",
    "ExtractedRequirement",
    "GapItem",
    "GeneratedDesignCandidateWorkspace",
    "MatchedDocument",
    "PartEvidence",
    "ReferenceBoardWorkflowPlan",
    "ResolvedFact",
    "SourceGapReport",
    "SubsystemPlan",
    "WorkflowStage",
    "build_design_evidence_manifest",
    "build_generated_design_candidate_workspace",
    "collect_source_gap_report",
    "c01_add_reference_image",
    "c01_confirm_reference_cue",
    "c01_next_question",
    "c01_update_answers",
    "extract_part_candidates",
    "BucketResult",
    "emit_c01_concept_prompts",
    "emit_c01_cmf_package",
    "emit_c01_id_visual_package",
    "emit_c01_rockbox_package",
    "emit_c01_uiux_package",
    "emit_c02_enclosure_package",
    "export_c02_projection_svg",
    "export_c02_skp",
    "export_c02_step",
    "export_c02_stl",
    "export_c03_mechanical_constraints",
    "generate_c01_concept_image",
    "generate_c02_openscad",
    "IngestResult",
    "OrchestrationError",
    "WorkPacket",
    "c00_orchestration_status",
    "c00_orchestration_tick",
    "dispatch_work_packet",
    "enter_c01_mode",
    "get_blocker",
    "get_work_packet",
    "ingest_blocker",
    "layer_relevant_prd_sections",
    "list_blockers",
    "list_work_packets",
    "return_blocker",
    "assess_c04_layout_readiness",
    "emit_c04_layout_package",
    "PlacementApprovalResult",
    "PlacementReviewResult",
    "assess_c04_placement_approval",
    "emit_c04_placement_review",
    "assess_c05_fw_readiness",
    "scaffold_c05_fw_spec",
    "assess_c06_readiness",
    "assemble_c06_test_plan",
    "load_agent_registry",
    "load_c00_prd_rubric",
    "load_c00_prd_template",
    "load_c01_id_rubric",
    "load_c01_id_template",
    "validate_c01_outputs_binding",
    "plan_design_intent",
    "plan_reference_board_workflow",
    "render_gap_report_markdown",
    "scaffold_c00_prd_package",
    "scan_corpus_for_part",
    "CheckerError",
    "check_board_edge_keepout",
    "check_decoupling_pdn",
    "guard_tier",
    "RefsGateError",
    "RefsManifest",
    "RefsSource",
    "REFS_SSOT_MISSING",
    "REFS_ANCHOR_MISSING",
    "REFS_MANIFEST_INVALID",
    "ingest_refs",
    "require_refs",
    "UpstreamConstraintError",
    "ConnectorPlacement",
    "FaceLayout",
    "UPSTREAM_CONSTRAINT_MISSING",
    "CONNECTOR_FACE_CONFLICT",
    "CONSTRAINT_SCHEMA_INVALID",
    "assert_face_frozen",
    "parse_face_layout",
    "require_upstream_constraints",
    "solve_face_placement",
    "placement_to_coords",
    "BoardSurgeryError",
    "CastellatedPad",
    "CastellationRequest",
    "BOARD_SURGERY_UNSAFE_PATH",
    "CASTELLATION_SPEC_INVALID",
    "SAFE_PATH",
    "UNSAFE_PATHS",
    "assert_safe_surgery_path",
    "build_castellation",
    "parse_castellation_request",
    "TracebackReport",
    "DOD_TRACEBACK_FAILED",
    "DOD_TRACEBACK_SCHEMA",
    "dod_refs_traceback",
    "C03State",
    "C04State",
    "A2ARole",
    "SubstateMachine",
    "StateReceipt",
    "GateVerdict",
    "mint_receipt",
    "GovernanceError",
    "StateTransitionBlockedError",
    "SelfApprovalProhibitedError",
    "ControlViolationError",
    "InvalidReceiptError",
    "BlockerHub",
    "BlockerRecord",
    "BlockerStatus",
    "BlockComponent",
    "BlockInternalNet",
    "BlockLayoutConstraint",
    "BlockPort",
    "BlockValidationError",
    "CircuitBlockDefinition",
    "get_core_circuit_blocks",
    "AppliedBlockResult",
    "CircuitBlockRegistry",
    "InstantiatedComponent",
    "apply_circuit_block",
    "BoundingBox",
    "Point2D",
    "snap_components",
    "snap_coord",
    "snap_point",
    "distribute_passives",
    "FootprintSilkRecord",
    "PadGeometry",
    "has_silk_pad_overlap",
    "normalize_silk_rotation",
    "tidy_all_footprints",
    "tidy_footprint_silk",
    "tidy_kicad_pcb",
    "tidy_kicad_pcb_content",
]
