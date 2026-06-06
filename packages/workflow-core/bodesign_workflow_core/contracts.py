from dataclasses import dataclass, field


@dataclass(slots=True)
class WorkflowStage:
    stage_id: str
    title: str
    status: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReferenceBoardWorkflowPlan:
    project_id: str
    board_design_id: str
    status: str
    orchestration_model: str
    stages: list[WorkflowStage] = field(default_factory=list)
    approval_gates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CandidateDiffItem:
    area: str
    status: str
    summary: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedDesignCandidateWorkspace:
    project_id: str
    candidate_id: str
    source_board_design_id: str
    status: str
    approval_state: str
    diff_summary: list[CandidateDiffItem] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    validation_gates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def plan_reference_board_workflow(
    project_id: str,
    board_design_id: str,
    artifact_count: int,
    component_count: int,
    net_count: int,
    knowledge_queue_count: int,
    orchestration_model: str = "client-orchestrated-mcp-workflow",
) -> ReferenceBoardWorkflowPlan:
    spatial_blocker = "Spatial Gerber/drill geometry fusion is pending."
    knowledge_blocker = "Component knowledge queue still has unresolved datasheet/pinout gaps."
    stages = [
        WorkflowStage(
            stage_id="ingest-sources",
            title="Ingest source artifacts",
            status="available" if artifact_count else "blocked",
            inputs=["project artifacts"],
            outputs=["classified artifacts", "evidence refs"],
            blockers=[] if artifact_count else ["No project artifacts are attached."],
        ),
        WorkflowStage(
            stage_id="resolve-knowledge",
            title="Resolve reusable component knowledge",
            status="needs-input" if knowledge_queue_count else "available",
            inputs=["component queue", "user-provided datasheets", "docxmcp source chunks"],
            outputs=["ComponentKnowledge records"],
            blockers=[knowledge_blocker] if knowledge_queue_count else [],
        ),
        WorkflowStage(
            stage_id="reconstruct-reference-ir",
            title="Reconstruct reference BoardDesign IR",
            status="partial" if component_count and net_count else "blocked",
            inputs=["placement", "IPC nets", "Gerber/drill summaries"],
            outputs=[board_design_id],
            blockers=[spatial_blocker],
        ),
        WorkflowStage(
            stage_id="propose-layout-intent",
            title="Propose subsystem and layout intent",
            status="blocked",
            inputs=["BoardDesign IR", "ComponentKnowledge"],
            outputs=["candidate design intent"],
            blockers=[spatial_blocker, knowledge_blocker],
        ),
        WorkflowStage(
            stage_id="deterministic-validation",
            title="Run deterministic validation",
            status="blocked",
            inputs=["candidate design", "KiCad bridge plan", "Gerber validation plan"],
            outputs=["DRC/ERC/export validation report"],
            blockers=["Native EDA execution remains behind an explicit adapter/approval boundary."],
        ),
        WorkflowStage(
            stage_id="user-approval",
            title="Request user approval before generated layout use",
            status="required",
            inputs=["validation report", "evidence diff"],
            outputs=["approval decision"],
            blockers=["Generated layout is not send-to-fab without explicit approval."],
        ),
    ]
    return ReferenceBoardWorkflowPlan(
        project_id=project_id,
        board_design_id=board_design_id,
        status="planned-with-blockers",
        orchestration_model=orchestration_model,
        stages=stages,
        approval_gates=[
            "External datasheet fetching requires explicit approval.",
            "Native KiCad/freerouting execution requires adapter-bound approval.",
            "Generated fabrication outputs require deterministic validation and user approval.",
        ],
        warnings=[
            "This workflow is a deterministic plan contract; it does not execute AI generation or native EDA tools yet.",
            "MVP cross-MCP document processing should be client-orchestrated across bodesign MCP and docxmcp.",
        ],
    )


def build_generated_design_candidate_workspace(
    project_id: str,
    source_board_design_id: str,
    candidate_id: str | None = None,
    component_count: int = 0,
    net_count: int = 0,
    artifact_count: int = 0,
) -> GeneratedDesignCandidateWorkspace:
    resolved_candidate_id = candidate_id or f"{project_id}-candidate-001"
    return GeneratedDesignCandidateWorkspace(
        project_id=project_id,
        candidate_id=resolved_candidate_id,
        source_board_design_id=source_board_design_id,
        status="draft-evidence-workspace",
        approval_state="not-approved",
        diff_summary=[
            CandidateDiffItem(
                area="source coverage",
                status="available" if artifact_count else "blocked",
                summary=f"{artifact_count} source artifacts are available for evidence comparison.",
                evidence_refs=["project-artifacts"] if artifact_count else [],
            ),
            CandidateDiffItem(
                area="component coverage",
                status="partial" if component_count else "blocked",
                summary=f"{component_count} reference components are available; generated component deltas are not produced yet.",
                evidence_refs=["BoardDesign.components"] if component_count else [],
            ),
            CandidateDiffItem(
                area="net coverage",
                status="partial" if net_count else "blocked",
                summary=f"{net_count} reference nets are available; generated netlist deltas are not produced yet.",
                evidence_refs=["BoardDesign.nets"] if net_count else [],
            ),
            CandidateDiffItem(
                area="layout output",
                status="blocked",
                summary="Generated placement/routing output is pending spatial IR and deterministic validation.",
                evidence_refs=[],
            ),
        ],
        evidence_refs=["BoardDesign IR", "component knowledge queue", "cross-probe evidence", "workflow approval gates"],
        validation_gates=[
            "Candidate must pass deterministic schema validation.",
            "Candidate must pass KiCad/DRC checks through an approved adapter workflow.",
            "Candidate must include source evidence diff before approval.",
            "Candidate is not send-to-fab without explicit user approval.",
        ],
        warnings=[
            "This workspace does not generate a new board layout yet.",
            "Approval state is explicit and defaults to not-approved.",
        ],
    )
