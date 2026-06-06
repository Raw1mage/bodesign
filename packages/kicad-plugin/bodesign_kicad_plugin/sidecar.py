from dataclasses import dataclass, field
from pathlib import PurePath


DEFAULT_BODESIGN_BASE_URL = "http://127.0.0.1:8765/bodesign"


@dataclass(slots=True)
class SidecarConfig:
    project_id: str
    base_url: str = DEFAULT_BODESIGN_BASE_URL
    project_source: str = "kicad-action-plugin"

    @property
    def dashboard_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/projects/{self.project_id}"

    @property
    def foundation_api_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/projects/{self.project_id}/kicad-foundation"

    @property
    def native_extension_api_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/projects/{self.project_id}/kicad-native-extension"

    @property
    def handshake_api_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/projects/{self.project_id}/kicad-plugin-handshake"

    @property
    def request_analysis_api_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/projects/{self.project_id}/kicad-analysis-status"


@dataclass(slots=True)
class KiCadProjectContext:
    project_id: str
    project_path: str
    project_root: str
    source_type: str
    source: str = "kicad-action-plugin"
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ApprovedPatchRequest:
    project_id: str
    candidate_id: str
    approved_by_user: bool
    endpoint: str
    status: str = "represented-not-applied"
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PluginHandshakeRequest:
    project_id: str
    endpoint: str
    payload: dict[str, object]
    status: str = "represented-not-sent"
    warnings: list[str] = field(default_factory=list)


def discover_project_context(kicad_path: str, project_id: str | None = None) -> KiCadProjectContext:
    path = PurePath(kicad_path)
    suffix = path.suffix.lower()
    source_type = {
        ".kicad_pro": "project",
        ".kicad_sch": "schematic",
        ".kicad_pcb": "pcb",
    }.get(suffix, "unknown")
    inferred_project_id = project_id or path.stem or "unknown-kicad-project"
    warnings = []
    if source_type == "unknown":
        warnings.append("Path is not a recognized KiCad .kicad_pro/.kicad_sch/.kicad_pcb source.")
    return KiCadProjectContext(
        project_id=inferred_project_id,
        project_path=str(path),
        project_root=str(path.parent) if str(path.parent) != "." else "",
        source_type=source_type,
        warnings=warnings,
    )


def open_dashboard_url(config: SidecarConfig) -> str:
    return config.dashboard_url


def build_request_analysis_call(config: SidecarConfig, context: KiCadProjectContext) -> dict[str, object]:
    return {
        "method": "POST",
        "endpoint": config.request_analysis_api_url,
        "payload": {
            "project_id": config.project_id,
            "project_source": config.project_source,
            "kicad_project_path": context.project_path,
            "source_type": context.source_type,
            "requested_checks": ["kicad-happy-analysis", "drc", "erc", "dfm", "emc", "thermal"],
            "analysis_root": ".bodesign/analysis/kicad-happy",
            "approved_for_execution": False,
        },
        "status": "represented-not-executed",
        "warnings": ["This scaffold builds the request only; it does not run KiCad, DRC, ERC, or write files."],
    }


def build_plugin_handshake_request(config: SidecarConfig, context: KiCadProjectContext) -> PluginHandshakeRequest:
    return PluginHandshakeRequest(
        project_id=config.project_id,
        endpoint=config.handshake_api_url,
        payload={
            "project_id": config.project_id,
            "project_source": config.project_source,
            "kicad_project_path": context.project_path,
            "kicad_project_root": context.project_root,
            "source_type": context.source_type,
            "plugin_capabilities": ["open-dashboard", "request-analysis", "represent-approved-patch"],
            "approved_for_execution": False,
            "approved_for_file_mutation": False,
        },
        warnings=["Handshake is represented only; it does not run KiCad, DRC, ERC, or mutate project files."],
    )


def build_approved_patch_request(config: SidecarConfig, candidate_id: str, approved_by_user: bool) -> ApprovedPatchRequest:
    endpoint = f"{config.base_url.rstrip('/')}/api/projects/{config.project_id}/candidates/{candidate_id}/apply-approved-patch"
    if not approved_by_user:
        raise ValueError("approved_by_user is required before representing a KiCad-native patch request")
    return ApprovedPatchRequest(
        project_id=config.project_id,
        candidate_id=candidate_id,
        approved_by_user=True,
        endpoint=endpoint,
        warnings=["Patch request is represented for KiCad-native/client-approved application; this scaffold does not apply files."],
    )
