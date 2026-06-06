from dataclasses import dataclass, field


@dataclass(slots=True)
class StorageFolderRole:
    role: str
    path: str
    visibility: str
    purpose: str
    writable: bool


@dataclass(slots=True)
class StorageShareScope:
    scope_id: str
    paths: list[str]
    permissions: list[str]
    owner: str


@dataclass(slots=True)
class StorageShareManifest:
    project_id: str
    project_root: str
    durable_owner: str
    storage_model: str
    hidden_workspace: str
    cache_policy: str
    save_back_mode: str
    conflict_policy: str
    human_facing_folders: list[StorageFolderRole] = field(default_factory=list)
    machine_workspaces: list[StorageFolderRole] = field(default_factory=list)
    read_scopes: list[StorageShareScope] = field(default_factory=list)
    write_scopes: list[StorageShareScope] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectPathClassification:
    path: str
    role: str
    artifact_type: str
    visibility: str


@dataclass(slots=True)
class ProjectFolderTaxonomy:
    roles: dict[str, list[str]] = field(default_factory=dict)
    kicad_sources: dict[str, list[str]] = field(default_factory=dict)
    output_artifacts: list[ProjectPathClassification] = field(default_factory=list)
    hidden_paths: list[str] = field(default_factory=list)
    unclassified_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KiCadHappyArtifactPath:
    category: str
    path: str
    visibility: str
    purpose: str


@dataclass(slots=True)
class KiCadHappyCacheMapping:
    config_path: str
    analysis_root: str
    mode: str
    track_in_git: bool
    cache_policy: str
    artifact_paths: list[KiCadHappyArtifactPath] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectTreeNode:
    role: str
    path: str
    kind: str
    visibility: str
    source_count: int
    sample_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HiddenWorkspaceSummary:
    path: str
    visibility: str
    source_count: int
    cache_policy: str
    categories: list[str] = field(default_factory=list)
    sample_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectTreeBrowseContract:
    project_id: str
    durable_owner: str
    access_mode: str
    storage_model: str
    project_root: str
    folder_nodes: list[ProjectTreeNode] = field(default_factory=list)
    hidden_workspace: HiddenWorkspaceSummary | None = None
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectRegistryLinks:
    dashboard: str
    storage_share: str
    project_tree: str
    kicad_foundation: str
    kicad_native_extension: str
    kicad_plugin_handshake: str


@dataclass(slots=True)
class ProjectRecord:
    project_id: str
    display_name: str
    durable_owner: str
    folder_handle_status: str
    access_mode: str
    storage_model: str
    project_root: str
    links: ProjectRegistryLinks
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectRegistry:
    status: str
    durable_owner: str
    access_mode: str
    records: list[ProjectRecord] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FolderOpenRequest:
    request_id: str
    project_id: str
    durable_owner: str
    access_mode: str
    approval_state: str
    requested_permissions: list[str] = field(default_factory=list)
    read_scopes: list[StorageShareScope] = field(default_factory=list)
    write_scopes: list[StorageShareScope] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    post_grant_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SaveBackProposal:
    proposal_id: str
    project_id: str
    target_scope: str
    target_path: str
    operation_intent: str
    application_mode: str
    approval_state: str
    conflict_policy: str
    direct_mcp_mutation_blocked: bool
    evidence_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CacheConflictStatus:
    project_id: str
    cache_authority: str
    source_authority: str
    freshness_state: str
    conflict_policy: str
    silent_resolution_blocked: bool
    source_revision_anchors: list[str] = field(default_factory=list)
    cache_entries: list[HiddenWorkspaceSummary] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceChunkItem:
    source_path: str
    target_path: str
    provenance_anchor: str
    content_kind: str
    cache_state: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceChunkMaterialization:
    project_id: str
    source_authority: str
    target_workspace: str
    materialization_mode: str
    approval_state: str
    direct_server_copy_blocked: bool
    chunk_items: list[SourceChunkItem] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KiCadAnalysisEvidenceOutput:
    category: str
    target_path: str
    cache_state: str
    purpose: str


@dataclass(slots=True)
class KiCadAnalysisStatus:
    project_id: str
    request_id: str
    orchestration_mode: str
    approval_state: str
    run_state: str
    analysis_root: str
    direct_server_execution_blocked: bool
    requested_checks: list[str] = field(default_factory=list)
    expected_outputs: list[KiCadAnalysisEvidenceOutput] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KiCadAnalysisEvidenceArtifact:
    artifact_id: str
    category: str
    path: str
    cache_state: str
    source_anchor: str
    purpose: str


@dataclass(slots=True)
class KiCadAnalysisEvidenceManifest:
    project_id: str
    manifest_id: str
    analysis_root: str
    source_authority: str
    cache_authority: str
    freshness_state: str
    access_mode: str
    direct_filesystem_browse_blocked: bool
    artifacts: list[KiCadAnalysisEvidenceArtifact] = field(default_factory=list)
    source_anchors: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_default_storage_share_manifest(project_id: str, project_root: str | None = None) -> StorageShareManifest:
    root = project_root or f"client://projects/{project_id}"
    hidden_workspace = ".bodesign"
    human_folders = [
        StorageFolderRole("docs", "docs/", "human-facing", "Datasheets, app notes, reference designs, and incoming documents.", True),
        StorageFolderRole("inputs", "inputs/", "human-facing", "Incoming source packages and user-provided evidence.", True),
        StorageFolderRole("eda", "eda/", "human-facing", "KiCad project, schematic, PCB, and project settings.", True),
        StorageFolderRole("libraries", "libraries/", "human-facing", "Project-local symbols, footprints, 3D models, and vendor libraries.", True),
        StorageFolderRole("outputs", "outputs/", "human-facing", "Reviewed Gerbers, drill files, BOM, position files, PDFs, STEP, and releases.", True),
        StorageFolderRole("reports", "reports/", "human-facing", "Human-readable analysis, reconstruction, validation, and review reports.", True),
    ]
    machine_workspaces = [
        StorageFolderRole("analysis-cache", f"{hidden_workspace}/analysis/", "hidden-system", "Analyzer runs, manifests, trust summaries, diffs, and render evidence.", True),
        StorageFolderRole("source-chunks", f"{hidden_workspace}/sources/", "hidden-system", "PDF/text/table chunks with provenance anchors.", True),
        StorageFolderRole("ir-cache", f"{hidden_workspace}/ir/", "hidden-system", "Normalized IR snapshots and reconstruction evidence.", True),
        StorageFolderRole("render-cache", f"{hidden_workspace}/render/", "hidden-system", "Disposable raster/render artifacts and previews.", True),
        StorageFolderRole("workflow-state", f"{hidden_workspace}/workflow/", "hidden-system", "Client-orchestrated workflow state and approval checkpoints.", True),
    ]
    return StorageShareManifest(
        project_id=project_id,
        project_root=root,
        durable_owner="client",
        storage_model="client-owned-local-folder",
        hidden_workspace=hidden_workspace,
        cache_policy="mcp-cache-disposable-not-authoritative",
        save_back_mode="scoped-client-storage-share",
        conflict_policy="client-detects-conflicts-before-accepting-mcp-writes",
        human_facing_folders=human_folders,
        machine_workspaces=machine_workspaces,
        read_scopes=[StorageShareScope("project-read", ["docs/", "inputs/", "eda/", "libraries/", "outputs/", "reports/", f"{hidden_workspace}/"], ["read"], "client")],
        write_scopes=[StorageShareScope("mcp-save-back", [f"{hidden_workspace}/", "reports/", "outputs/"], ["write", "patch"], "client-approved")],
        warnings=[
            "The MCP server is not the durable content owner.",
            "Machine-only intermediate files stay under the hidden .bodesign workspace.",
            "Writes require scoped client storage-share approval or client-applied patches.",
        ],
    )


def validate_storage_share_manifest(manifest: StorageShareManifest) -> list[str]:
    errors: list[str] = []
    if manifest.durable_owner != "client":
        errors.append("durable_owner must be client")
    if not manifest.hidden_workspace.startswith("."):
        errors.append("hidden_workspace must be hidden")
    if "disposable" not in manifest.cache_policy:
        errors.append("cache_policy must mark MCP cache as disposable")
    if not manifest.read_scopes:
        errors.append("at least one read scope is required")
    return errors


def classify_project_folder_taxonomy(paths: list[str], hidden_workspace: str = ".bodesign") -> ProjectFolderTaxonomy:
    normalized_paths = sorted({_normalize_relative_path(path) for path in paths if _normalize_relative_path(path)})
    roles: dict[str, list[str]] = {role: [] for role in ["docs", "inputs", "eda", "libraries", "outputs", "reports"]}
    kicad_sources: dict[str, list[str]] = {"project": [], "schematic": [], "pcb": []}
    output_artifacts: list[ProjectPathClassification] = []
    hidden_paths: list[str] = []
    unclassified_paths: list[str] = []

    hidden_prefix = hidden_workspace.strip("/") + "/"
    for path in normalized_paths:
        if path == hidden_workspace or path.startswith(hidden_prefix):
            hidden_paths.append(path)
            continue
        role = _human_role_for_path(path)
        if role is None:
            unclassified_paths.append(path)
            continue
        roles.setdefault(role, []).append(path)
        source_type = _kicad_source_type(path)
        if source_type is not None:
            kicad_sources[source_type].append(path)
        output_type = _output_artifact_type(path) if role == "outputs" else None
        if output_type is not None:
            output_artifacts.append(ProjectPathClassification(path, role, output_type, "human-facing"))

    warnings: list[str] = []
    if not kicad_sources["project"]:
        warnings.append("No KiCad .kicad_pro file detected under the human-facing project tree.")
    if not kicad_sources["schematic"]:
        warnings.append("No KiCad .kicad_sch schematic detected under the human-facing project tree.")
    if not kicad_sources["pcb"]:
        warnings.append("No KiCad .kicad_pcb layout detected under the human-facing project tree.")
    if hidden_paths:
        warnings.append("Hidden .bodesign machine workspace paths were excluded from human-facing taxonomy classification.")

    return ProjectFolderTaxonomy(roles, kicad_sources, output_artifacts, hidden_paths, unclassified_paths, warnings)


def build_kicad_happy_cache_mapping(hidden_workspace: str = ".bodesign", visible_analysis_opt_in: bool = False) -> KiCadHappyCacheMapping:
    analysis_root = "analysis" if visible_analysis_opt_in else f"{hidden_workspace.strip('/')}/analysis/kicad-happy"
    visibility = "human-facing-opt-in" if visible_analysis_opt_in else "hidden-system"
    mode = "visible-compatibility-analysis" if visible_analysis_opt_in else "hidden-mcp-analysis-cache"
    artifact_specs = [
        ("manifest", "manifest.json", "Analyzer run manifest and source file index."),
        ("analyzer-json", "analyzer.json", "Structured KiCad analyzer findings."),
        ("trust-summary", "trust-summary.json", "Evidence trust rollup for analyzer outputs."),
        ("diffs", "diffs/prior-run.json", "Prior-run comparison and regression evidence."),
        ("renders", "renders/board.svg", "Rendered schematic or PCB evidence figures."),
        ("report-figures", "figures/report-overview.svg", "Figures consumed by design review reports."),
        ("drc", "drc/results.json", "KiCad DRC evidence."),
        ("erc", "erc/results.json", "KiCad ERC evidence."),
        ("dfm", "dfm/results.json", "DFM evidence and manufacturing risk checks."),
        ("emc", "emc/results.json", "EMC evidence and pre-compliance findings."),
        ("thermal", "thermal/results.json", "Thermal analysis evidence."),
    ]
    artifact_paths = [
        KiCadHappyArtifactPath(category, f"{analysis_root}/{relative_path}", visibility, purpose)
        for category, relative_path, purpose in artifact_specs
    ]
    warnings = [
        ".kicad-happy.json is a compatibility configuration file, not MCP-owned durable storage.",
    ]
    if visible_analysis_opt_in:
        warnings.append("Visible analysis/ output is opt-in for engineers already using KiCad Happy directly.")
    else:
        warnings.append("Default MCP-run KiCad Happy outputs stay hidden under .bodesign/analysis/kicad-happy/.")
    return KiCadHappyCacheMapping(
        config_path=".kicad-happy.json",
        analysis_root=analysis_root,
        mode=mode,
        track_in_git=False,
        cache_policy="mcp-cache-disposable-not-authoritative",
        artifact_paths=artifact_paths,
        warnings=warnings,
    )


def build_project_tree_browse_contract(project_id: str, paths: list[str], manifest: StorageShareManifest | None = None) -> ProjectTreeBrowseContract:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    taxonomy = classify_project_folder_taxonomy(paths, storage_manifest.hidden_workspace)
    folder_nodes = [
        ProjectTreeNode(
            role=folder.role,
            path=folder.path,
            kind="human-facing-folder",
            visibility=folder.visibility,
            source_count=len(taxonomy.roles.get(folder.role, [])),
            sample_paths=taxonomy.roles.get(folder.role, [])[:8],
        )
        for folder in storage_manifest.human_facing_folders
    ]
    hidden_categories = sorted({path.split("/", 3)[1] if "/" in path else storage_manifest.hidden_workspace for path in taxonomy.hidden_paths})
    hidden_summary = HiddenWorkspaceSummary(
        path=storage_manifest.hidden_workspace,
        visibility="hidden-system-summary",
        source_count=len(taxonomy.hidden_paths),
        cache_policy=storage_manifest.cache_policy,
        categories=hidden_categories,
        sample_paths=taxonomy.hidden_paths[:8],
    )
    return ProjectTreeBrowseContract(
        project_id=project_id,
        durable_owner=storage_manifest.durable_owner,
        access_mode="read-only-fixture-backed",
        storage_model=storage_manifest.storage_model,
        project_root=storage_manifest.project_root,
        folder_nodes=folder_nodes,
        hidden_workspace=hidden_summary,
        blockers=[
            "Real client folder handles are not wired yet; this tree is derived from manifest and fixture evidence.",
            "Save-back/edit operations are blocked until scoped client approval and conflict checks exist.",
            "The sidecar must not browse arbitrary server filesystem paths outside declared storage-share scope.",
        ],
        warnings=[
            "Project content remains client-owned; bodesign only presents a scoped evidence tree.",
            "Hidden .bodesign internals are summarized, not exposed as root-level user folders.",
        ],
    )


def build_project_registry(project_ids: list[str], display_names: dict[str, str] | None = None) -> ProjectRegistry:
    names = display_names or {}
    records = [build_project_record(project_id, names.get(project_id)) for project_id in sorted(project_ids)]
    return ProjectRegistry(
        status="project-registry-fixture-ready",
        durable_owner="client",
        access_mode="read-only-fixture-backed",
        records=records,
        blockers=[
            "Real client folder handles are not granted yet; registry records are fixture-backed metadata.",
            "Save-back/edit operations require scoped client approval and conflict checks.",
        ],
        warnings=[
            "The registry is not a server-owned durable file store.",
            "Project source files remain under client control.",
        ],
    )


def build_project_record(project_id: str, display_name: str | None = None) -> ProjectRecord:
    manifest = build_default_storage_share_manifest(project_id)
    base_path = f"/bodesign/api/projects/{project_id}"
    return ProjectRecord(
        project_id=project_id,
        display_name=display_name or project_id,
        durable_owner=manifest.durable_owner,
        folder_handle_status="fixture-not-granted",
        access_mode="read-only-fixture-backed",
        storage_model=manifest.storage_model,
        project_root=manifest.project_root,
        links=ProjectRegistryLinks(
            dashboard=f"/bodesign/projects/{project_id}",
            storage_share=f"{base_path}/storage-share",
            project_tree=f"{base_path}/project-tree",
            kicad_foundation=f"{base_path}/kicad-foundation",
            kicad_native_extension=f"{base_path}/kicad-native-extension",
            kicad_plugin_handshake=f"{base_path}/kicad-plugin-handshake",
        ),
        blockers=[
            "Client folder handle is not granted; project is fixture-backed metadata only.",
            "MCP-side mutation is blocked until approved save-back semantics exist.",
        ],
        warnings=["Project record is an index/evidence pointer, not durable server-owned content."],
    )


def build_folder_open_request(project_id: str, manifest: StorageShareManifest | None = None) -> FolderOpenRequest:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    return FolderOpenRequest(
        request_id=f"folder-open-{project_id}",
        project_id=project_id,
        durable_owner=storage_manifest.durable_owner,
        access_mode="no-server-filesystem-access",
        approval_state="needs-client-grant/not-approved",
        requested_permissions=["read-project-tree", "read-kicad-sources", "read-documents", "represent-client-approved-save-back"],
        read_scopes=storage_manifest.read_scopes,
        write_scopes=storage_manifest.write_scopes,
        blockers=[
            "Client folder handle has not been granted; the MCP must not scan arbitrary server filesystem paths.",
            "File mutation and save-back are blocked until the client grants scoped access and approves conflict policy.",
            "Native KiCad editing remains outside this request and must go through the approved plugin/sidecar workflow.",
        ],
        post_grant_actions=[
            "refresh-project-registry",
            "refresh-storage-share",
            "refresh-project-tree",
            "refresh-kicad-foundation",
        ],
        warnings=[
            "This is a represented client-side folder handle request, not a server filesystem operation.",
            "Durable project files remain client-owned after approval.",
        ],
    )


def build_save_back_proposals(project_id: str, manifest: StorageShareManifest | None = None) -> list[SaveBackProposal]:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    return [
        SaveBackProposal(
            proposal_id=f"save-back-{project_id}-analysis-report",
            project_id=project_id,
            target_scope="mcp-save-back",
            target_path="reports/bodesign-analysis-summary.md",
            operation_intent="create-or-update-report",
            application_mode="client-applied/native-kicad-plugin",
            approval_state="not-approved",
            conflict_policy=storage_manifest.conflict_policy,
            direct_mcp_mutation_blocked=True,
            evidence_refs=[
                f"/bodesign/api/projects/{project_id}/kicad-foundation",
                f"/bodesign/api/projects/{project_id}/project-tree",
            ],
            warnings=[
                "This proposal is represented only; the MCP does not write client files directly.",
                "Client or native KiCad plugin must apply the patch after explicit approval and conflict checks.",
            ],
            next_actions=[
                "review-proposal-evidence",
                "approve-client-applied-patch",
                "client-checks-conflicts",
                "apply-through-client-or-native-kicad-plugin",
                "refresh-project-tree",
            ],
        )
    ]


def build_cache_conflict_status(project_id: str, paths: list[str] | None = None, manifest: StorageShareManifest | None = None) -> CacheConflictStatus:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    taxonomy = classify_project_folder_taxonomy(paths or [], storage_manifest.hidden_workspace)
    cache_categories = sorted({path.split("/", 3)[1] if "/" in path else storage_manifest.hidden_workspace for path in taxonomy.hidden_paths})
    cache_entries = [
        HiddenWorkspaceSummary(
            path=storage_manifest.hidden_workspace,
            visibility="hidden-system-summary",
            source_count=len(taxonomy.hidden_paths),
            cache_policy=storage_manifest.cache_policy,
            categories=cache_categories,
            sample_paths=taxonomy.hidden_paths[:8],
        )
    ]
    return CacheConflictStatus(
        project_id=project_id,
        cache_authority="disposable-mcp-cache",
        source_authority="client-owned-folder",
        freshness_state="fixture-stale/needs-client-refresh",
        conflict_policy="explicit-user-resolution",
        silent_resolution_blocked=True,
        source_revision_anchors=[
            f"client-folder-handle:{project_id}:not-granted",
            f"storage-share:{project_id}:manifest-fixture",
            f"project-tree:{project_id}:fixture-taxonomy",
        ],
        cache_entries=cache_entries,
        required_actions=[
            "refresh-from-client-folder",
            "invalidate-disposable-mcp-cache",
            "review-save-back-proposals",
            "require-user-conflict-resolution",
        ],
        blockers=[
            "Client folder handle is not granted; cache freshness cannot be verified against authoritative source files.",
            "MCP cache is disposable and must not be treated as authoritative project storage.",
            "Conflicts require explicit user/client resolution; silent resolution is blocked.",
        ],
        warnings=[
            "No filesystem scan, cache deletion, or conflict resolution is performed by this status contract.",
            "Refresh actions must be driven by client-owned source anchors.",
        ],
    )


def build_source_chunk_materialization(project_id: str, manifest: StorageShareManifest | None = None) -> SourceChunkMaterialization:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    target_workspace = f"{storage_manifest.hidden_workspace}/sources"
    return SourceChunkMaterialization(
        project_id=project_id,
        source_authority="client-owned-folder",
        target_workspace=target_workspace,
        materialization_mode="client-applied/docxmcp-orchestration",
        approval_state="not-approved/needs-client-grant",
        direct_server_copy_blocked=True,
        chunk_items=[
            SourceChunkItem(
                source_path="docs/reference-datasheet.pdf",
                target_path=f"{target_workspace}/docs/reference-datasheet/chunks.jsonl",
                provenance_anchor="doc://docs/reference-datasheet.pdf#page=1..n",
                content_kind="pdf-source-chunks",
                cache_state="represented-not-materialized",
                evidence_refs=[
                    f"/bodesign/api/projects/{project_id}/project-tree",
                    f"/bodesign/api/projects/{project_id}/cache-conflict-status",
                ],
            ),
            SourceChunkItem(
                source_path="inputs/reference-notes.txt",
                target_path=f"{target_workspace}/inputs/reference-notes/chunks.jsonl",
                provenance_anchor="doc://inputs/reference-notes.txt#line=1..n",
                content_kind="text-source-chunks",
                cache_state="represented-not-materialized",
                evidence_refs=[
                    f"/bodesign/api/projects/{project_id}/storage-share",
                    f"/bodesign/api/projects/{project_id}/folder-open-request",
                ],
            ),
        ],
        blockers=[
            "Client folder handle is not granted; source chunks cannot be materialized durably.",
            "docxmcp/client orchestration must provide provenance-preserving chunks before storage.",
            "Direct server-side copy of client documents into MCP-owned storage is blocked.",
        ],
        next_actions=[
            "grant-client-folder-handle",
            "run-docxmcp-client-side-decomposition",
            "review-source-chunk-provenance",
            "client-materializes-hidden-source-chunks",
            "refresh-cache-conflict-status",
        ],
        warnings=[
            "This contract represents source chunk materialization only; it does not read or copy files.",
            "Durable source chunks remain under client-owned hidden .bodesign/sources/ storage.",
        ],
    )


def build_kicad_analysis_status(project_id: str, manifest: StorageShareManifest | None = None, cache_mapping: KiCadHappyCacheMapping | None = None) -> KiCadAnalysisStatus:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    mapping = cache_mapping or build_kicad_happy_cache_mapping(storage_manifest.hidden_workspace)
    output_categories = {"manifest", "analyzer-json", "trust-summary", "diffs", "renders", "drc", "erc", "dfm", "emc", "thermal"}
    expected_outputs = [
        KiCadAnalysisEvidenceOutput(
            category=artifact.category,
            target_path=artifact.path,
            cache_state="represented-not-run",
            purpose=artifact.purpose,
        )
        for artifact in mapping.artifact_paths
        if artifact.category in output_categories
    ]
    return KiCadAnalysisStatus(
        project_id=project_id,
        request_id=f"kicad-analysis-{project_id}",
        orchestration_mode="native-kicad-plugin/client-orchestrated-kicad-happy",
        approval_state="not-approved/needs-client-grant",
        run_state="represented-not-run",
        analysis_root=mapping.analysis_root,
        direct_server_execution_blocked=True,
        requested_checks=["kicad-happy-analysis", "drc", "erc", "dfm", "emc", "thermal", "trust-summary", "prior-run-diff"],
        expected_outputs=expected_outputs,
        evidence_refs=[
            f"/bodesign/api/projects/{project_id}/kicad-foundation",
            f"/bodesign/api/projects/{project_id}/kicad-plugin-handshake",
            f"/bodesign/api/projects/{project_id}/cache-conflict-status",
        ],
        blockers=[
            "Client folder handle is not granted; analysis cannot be anchored to authoritative KiCad source revisions.",
            "User has not approved native KiCad/KiCad Happy execution.",
            "bodesign server must not run KiCad, DRC, ERC, or analyzer subprocesses directly.",
            "Analysis evidence cache is disposable and must not be treated as authoritative project source.",
        ],
        next_actions=[
            "grant-client-folder-handle",
            "approve-native-kicad-analysis-run",
            "run-analysis-through-kicad-plugin-or-client",
            "materialize-evidence-under-hidden-analysis-cache",
            "refresh-cache-conflict-status",
        ],
        warnings=[
            "This contract represents KiCad analysis request/status only; it does not execute native tools.",
            "Expected evidence outputs target hidden .bodesign analysis cache under client control.",
        ],
    )


def build_kicad_analysis_evidence_manifest(project_id: str, manifest: StorageShareManifest | None = None, cache_mapping: KiCadHappyCacheMapping | None = None) -> KiCadAnalysisEvidenceManifest:
    storage_manifest = manifest or build_default_storage_share_manifest(project_id)
    mapping = cache_mapping or build_kicad_happy_cache_mapping(storage_manifest.hidden_workspace)
    source_anchors = [
        f"{storage_manifest.project_root}/eda/{project_id}/{project_id}.kicad_pro",
        f"{storage_manifest.project_root}/eda/{project_id}/{project_id}.kicad_sch",
        f"{storage_manifest.project_root}/eda/{project_id}/{project_id}.kicad_pcb",
    ]
    artifact_categories = {"manifest", "analyzer-json", "trust-summary", "diffs", "renders", "report-figures", "drc", "erc", "dfm", "emc", "thermal"}
    artifacts = [
        KiCadAnalysisEvidenceArtifact(
            artifact_id=f"{project_id}-{artifact.category}",
            category=artifact.category,
            path=artifact.path,
            cache_state="represented-not-materialized",
            source_anchor=source_anchors[0],
            purpose=artifact.purpose,
        )
        for artifact in mapping.artifact_paths
        if artifact.category in artifact_categories
    ]
    return KiCadAnalysisEvidenceManifest(
        project_id=project_id,
        manifest_id=f"kicad-analysis-evidence-{project_id}",
        analysis_root=mapping.analysis_root,
        source_authority="client-owned-kicad-project",
        cache_authority="disposable-mcp-evidence-cache",
        freshness_state="fixture-stale/needs-client-refresh",
        access_mode="manifest-index-only/no-raw-filesystem-browse",
        direct_filesystem_browse_blocked=True,
        artifacts=artifacts,
        source_anchors=source_anchors,
        blockers=[
            "Client has not materialized KiCad Happy evidence outputs under the hidden analysis cache.",
            "bodesign server must not browse raw hidden folders or read arbitrary analysis files.",
            "Analysis evidence cache is disposable and must be refreshed from client-owned KiCad source anchors.",
        ],
        next_actions=[
            "approve-native-kicad-analysis-run",
            "materialize-evidence-via-kicad-plugin-or-client",
            "refresh-analysis-evidence-manifest",
            "review-trust-summary-and-drc-erc-evidence",
        ],
        warnings=[
            "This manifest is an evidence index only; it does not execute KiCad or read hidden cache files.",
            "Durable schematic/PCB sources remain in the client-owned KiCad project folder.",
        ],
    )


def _normalize_relative_path(path: str) -> str:
    return path.strip().replace("\\", "/").lstrip("/").rstrip("/")


def _human_role_for_path(path: str) -> str | None:
    first_segment = path.split("/", 1)[0].lower()
    if first_segment in {"docs", "inputs", "eda", "libraries", "outputs", "reports"}:
        return first_segment
    return None


def _kicad_source_type(path: str) -> str | None:
    lower_path = path.lower()
    if lower_path.endswith(".kicad_pro"):
        return "project"
    if lower_path.endswith(".kicad_sch"):
        return "schematic"
    if lower_path.endswith(".kicad_pcb"):
        return "pcb"
    return None


def _output_artifact_type(path: str) -> str | None:
    lower_path = path.lower()
    suffix_map = {
        ".gbr": "gerber",
        ".ger": "gerber",
        ".gtl": "gerber",
        ".gbl": "gerber",
        ".gto": "gerber",
        ".gbo": "gerber",
        ".drl": "drill",
        ".xln": "drill",
        ".bom.csv": "bom",
        ".csv": "table",
        ".pos": "position",
        ".step": "step-3d",
        ".stp": "step-3d",
        ".pdf": "pdf",
        ".zip": "release-package",
    }
    for suffix, artifact_type in suffix_map.items():
        if lower_path.endswith(suffix):
            return artifact_type
    return None
