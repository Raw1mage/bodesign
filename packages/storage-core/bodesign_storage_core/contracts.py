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
