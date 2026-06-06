from dataclasses import dataclass, field


@dataclass(slots=True)
class KiCadBridgePlan:
    project_id: str
    board_design_id: str
    integration_posture: str
    adapter_boundary: str
    plugin_mode: str = "submodule-or-plugin"
    planned_outputs: list[str] = field(default_factory=list)
    planned_checks: list[str] = field(default_factory=list)
    execution_status: str = "not-executed"
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KiCadNativeCapability:
    capability_id: str
    owner: str
    trigger_surface: str
    description: str
    requires_user_approval: bool = True


@dataclass(slots=True)
class KiCadNativeExtensionContract:
    project_id: str
    integration_model: str
    native_editor_owner: str
    sidecar_boundary: str
    bodesign_role: str
    capabilities: list[KiCadNativeCapability] = field(default_factory=list)
    blocked_browser_features: list[str] = field(default_factory=list)
    handoff_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def plan_kicad_bridge(project_id: str, board_design_id: str, integration_posture: str = "plugin-submodule-auto-workflow") -> KiCadBridgePlan:
    return KiCadBridgePlan(
        project_id=project_id,
        board_design_id=board_design_id,
        integration_posture=integration_posture,
        adapter_boundary="BoardDesign IR -> KiCad adapter -> optional KiCad plugin/submodule runtime",
        planned_outputs=[
            f"outputs/{project_id}/kicad/{board_design_id}.kicad_pcb",
            f"outputs/{project_id}/kicad/{board_design_id}.kicad_sch",
            f"outputs/{project_id}/kicad/{board_design_id}.bridge-report.json",
        ],
        planned_checks=[
            "schema-validate BoardDesign IR before export",
            "export KiCad project files through adapter boundary",
            "run KiCad DRC/ERC only inside approved plugin/submodule workflow",
            "re-import generated KiCad/Gerber outputs and compare against IR before fabrication use",
        ],
        warnings=[
            "This spike does not execute KiCad or freerouting yet.",
            "KiCad integration may become an automatic workflow plugin/submodule, but remains behind the adapter boundary.",
            "Generated fabrication outputs still require deterministic validation and user approval.",
        ],
    )


def build_kicad_native_extension_contract(project_id: str) -> KiCadNativeExtensionContract:
    return KiCadNativeExtensionContract(
        project_id=project_id,
        integration_model="kicad-action-plugin-plus-bodesign-mcp-sidecar",
        native_editor_owner="KiCad native application owns schematic editor, PCB editor, canvas, libraries, DRC, and ERC.",
        sidecar_boundary="KiCad plugin/action <-> bodesign MCP/API sidecar <-> client-owned project folder",
        bodesign_role="Companion dashboard for evidence, document management, AI workflow, candidate review, and approved patch/save-back.",
        capabilities=[
            KiCadNativeCapability("open-project-context", "kicad-plugin", "KiCad Action Plugin", "Open the active KiCad project context in bodesign without copying durable files."),
            KiCadNativeCapability("request-analysis", "bodesign-sidecar", "KiCad plugin or Web dashboard", "Run bodesign/KiCad Happy analysis into hidden .bodesign cache and return evidence summaries."),
            KiCadNativeCapability("review-candidate", "bodesign-web", "bodesign Candidate Review", "Review AI-generated diffs, evidence, validation gates, and approval state before any edit is applied."),
            KiCadNativeCapability("apply-approved-patch", "kicad-plugin", "KiCad Action Plugin", "Apply user-approved schematic/PCB/library edits through KiCad-native APIs or client-applied patches."),
            KiCadNativeCapability("sync-status", "bodesign-sidecar", "MCP/API", "Round-trip analysis status, trust summaries, warnings, and candidate outcomes back to bodesign."),
        ],
        blocked_browser_features=[
            "browser-native schematic editor",
            "browser-native PCB layout editor",
            "browser KiCad canvas clone",
            "server-side direct KiCad file mutation without user approval",
            "send-to-fab export without KiCad validation and approval",
        ],
        handoff_paths=[
            "KiCad Action Plugin invokes /bodesign/api/projects/{project_id}/kicad-native-extension",
            "bodesign Web links users back to native KiCad for edit/canvas/DRC/ERC actions",
            "approved candidate patches are applied by KiCad plugin or client-applied patch workflow",
        ],
        warnings=[
            "bodesign Web is not a KiCad-native editor.",
            "Native KiCad remains the authoritative editing and validation surface.",
            "The current implementation defines the contract only; it does not install or execute a KiCad plugin yet.",
        ],
    )
