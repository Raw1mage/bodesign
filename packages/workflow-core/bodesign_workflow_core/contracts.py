from dataclasses import dataclass, field
from pathlib import Path

from .design_review import review_gate_status
from .orchestration import (
    ORCH_REL_DIR,
    OrchestrationError,
    list_blockers,
    list_evidence_returns,
    list_work_packets,
)


@dataclass(slots=True)
class WorkflowStage:
    stage_id: str
    title: str
    status: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"stage_id": self.stage_id, "title": self.title, "status": self.status,
                "inputs": list(self.inputs), "outputs": list(self.outputs),
                "blockers": list(self.blockers)}


@dataclass(slots=True)
class ReferenceBoardWorkflowPlan:
    project_id: str
    board_design_id: str
    status: str
    orchestration_model: str
    stages: list[WorkflowStage] = field(default_factory=list)
    approval_gates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"project_id": self.project_id, "board_design_id": self.board_design_id,
                "status": self.status, "orchestration_model": self.orchestration_model,
                "stages": [s.to_dict() for s in self.stages],
                "approval_gates": list(self.approval_gates), "warnings": list(self.warnings)}


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
    project_folder: str | Path | None = None,
) -> ReferenceBoardWorkflowPlan:
    spatial_blocker = "Spatial Gerber/drill geometry fusion is pending."
    knowledge_blocker = "Component knowledge queue still has unresolved datasheet/pinout gaps."
    # G2/DD-4: design-review gate between propose-layout-intent and
    # deterministic-validation. Status derives from the persisted
    # DesignReviewRecord in the client project folder (REVIEW_MISSING /
    # REVIEW_REJECTED keep validation blocked; no silent pass-through).
    review_status, review_blockers = review_gate_status(project_folder)
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
            stage_id="design-review",
            title="Pre-implementation design review (scenario walkthrough + verdict)",
            status=review_status,
            inputs=["candidate design intent", "RequirementContracts", "skills/bodesign review methodology"],
            outputs=["DesignReviewRecord (subject, scenarios, counts, verdict)"],
            blockers=list(review_blockers),
        ),
        WorkflowStage(
            stage_id="deterministic-validation",
            title="Run deterministic validation",
            status="blocked",
            inputs=["candidate design", "KiCad bridge plan", "Gerber validation plan"],
            outputs=["DRC/ERC/export validation report"],
            blockers=["Native EDA execution remains behind an explicit adapter/approval boundary."]
                     + list(review_blockers),
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


# ── A1/DD-8: spine-derived workflow plan (single source of truth) ──────

# Which stage each downstream layer's open blockers / evidence map onto.
# C01/C02 (ID/ME) and C03 (mech constraints) gate the intent stage; C04
# (layout) gates validation; C05/C06 feed validation evidence.
_LAYER_STAGE: dict[str, str] = {
    "C01": "propose-layout-intent",
    "C02": "propose-layout-intent",
    "C03": "propose-layout-intent",
    "C04": "deterministic-validation",
    "C05": "deterministic-validation",
    "C06": "deterministic-validation",
}


def derive_workflow_plan(
    project_id: str,
    board_design_id: str,
    folder: str | Path,
    artifact_count: int = 0,
    component_count: int = 0,
    net_count: int = 0,
    knowledge_queue_count: int = 0,
    orchestration_model: str = "client-orchestrated-mcp-workflow",
) -> ReferenceBoardWorkflowPlan:
    """A1/DD-8: compute the reference-board workflow plan from `_orchestration/`
    spine state (work packets + blockers + evidence returns) plus the design-
    review record. The static `plan_reference_board_workflow()` stays as the
    stage TEMPLATE; this function fills status/blockers from spine truth.

    Explicit initialization policy: a missing `_orchestration/` directory is a
    `spine-not-initialized` blocker on every spine-derived stage — NEVER a
    silent fallback to the parameter-snapshot behaviour.
    """
    plan = plan_reference_board_workflow(
        project_id, board_design_id, artifact_count, component_count, net_count,
        knowledge_queue_count, orchestration_model, project_folder=folder,
    )

    root = Path(folder).expanduser().resolve()
    if not (root / ORCH_REL_DIR).exists():
        # DD-8: fail-fast surface, no fallback (SPINE_NOT_INITIALIZED).
        blocker = ("SPINE_NOT_INITIALIZED: orchestration spine not initialized for this project; "
                   "run workflow init first (no fallback to static plan)")
        for stage in plan.stages:
            if stage.stage_id in set(_LAYER_STAGE.values()):
                stage.status = "blocked"
                stage.blockers = [blocker]
        plan.status = "spine-not-initialized"
        plan.warnings = list(plan.warnings) + [blocker]
        return plan

    packets = list_work_packets(root)
    open_blockers = list_blockers(root, unresolved_only=True)
    evidence = list_evidence_returns(root)

    # Group spine state by the stage each source layer maps onto.
    stage_blockers: dict[str, list[str]] = {}
    for b in open_blockers:
        stage_id = _LAYER_STAGE.get(b.source_layer)
        if stage_id is None:
            raise OrchestrationError(
                f"SPINE_STATE_CORRUPT: blocker {b.blocker_id} has unmapped source layer {b.source_layer!r}"
            )
        stage_blockers.setdefault(stage_id, []).append(f"{b.blocker_id}: {b.summary}")
    stage_evidence: dict[str, list] = {}
    for ev in evidence:
        stage_id = _LAYER_STAGE.get(ev.source_layer)
        if stage_id is None:
            raise OrchestrationError(
                f"SPINE_STATE_CORRUPT: evidence {ev.evidence_id} has unmapped source layer {ev.source_layer!r}"
            )
        stage_evidence.setdefault(stage_id, []).append(ev)
    dispatched_stages = {_LAYER_STAGE[p.target_layer] for p in packets if p.target_layer in _LAYER_STAGE}

    for stage in plan.stages:
        if stage.stage_id not in set(_LAYER_STAGE.values()):
            continue  # non-spine stages keep template/gate-derived status
        spine_blockers = stage_blockers.get(stage.stage_id, [])
        # design-review gate blockers on validation are kept (G2 is not spine state).
        review_blockers = [b for b in stage.blockers if b.startswith("REVIEW_")]
        stage.blockers = review_blockers + spine_blockers
        if spine_blockers or review_blockers:
            stage.status = "blocked"
        elif any(ev.envelope.get("severity") in ("info", "minor") or ev.resolved
                 for ev in stage_evidence.get(stage.stage_id, [])):
            stage.status = "evidence-received"
        elif stage.stage_id in dispatched_stages:
            stage.status = "dispatched"
        else:
            stage.status = "pending-dispatch"

    open_count = len(open_blockers)
    plan.status = "blocked" if open_count else ("in-progress" if packets else "planned")
    return plan
