try:
    import pcbnew  # type: ignore
except ImportError:
    pcbnew = None

from .sidecar import SidecarConfig, build_plugin_handshake_request, discover_project_context, open_dashboard_url

PCBNEW_AVAILABLE = pcbnew is not None


if PCBNEW_AVAILABLE:
    KiCadActionPluginBase = pcbnew.ActionPlugin
else:
    class KiCadActionPluginBase:
        def register(self) -> None:
            return None


BODESIGN_PLUGIN_METADATA = {
    "name": "bodesign companion dashboard",
    "category": "bodesign",
    "description": "Open bodesign evidence, analysis, and candidate review from native KiCad without replacing KiCad editors.",
    "show_toolbar_button": True,
}


class BodesignActionPlugin(KiCadActionPluginBase):
    def defaults(self) -> None:
        self.name = BODESIGN_PLUGIN_METADATA["name"]
        self.category = BODESIGN_PLUGIN_METADATA["category"]
        self.description = BODESIGN_PLUGIN_METADATA["description"]
        self.show_toolbar_button = BODESIGN_PLUGIN_METADATA["show_toolbar_button"]

    def Run(self) -> dict[str, object] | None:
        if not PCBNEW_AVAILABLE:
            return {
                "status": "pcbnew-unavailable",
                "dashboard_url": open_dashboard_url(SidecarConfig("unknown-kicad-project")),
                "warnings": ["KiCad pcbnew is unavailable; plugin scaffold imported in sidecar/test mode only."],
            }
        board = pcbnew.GetBoard()
        board_path = str(board.GetFileName()) if board else "unknown.kicad_pcb"
        context = discover_project_context(board_path)
        config = SidecarConfig(context.project_id)
        handshake = build_plugin_handshake_request(config, context)
        return {"status": "dashboard-ready", "dashboard_url": open_dashboard_url(config), "handshake_endpoint": handshake.endpoint, "project_context": context}
