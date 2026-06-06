import importlib
import sys
import types
import unittest


class ApiRouteRegistrationTests(unittest.TestCase):
    def test_bodesign_routes_are_registered_without_fastapi_runtime(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        routes = {route.path for route in api_main.app.routes}

        self.assertIn("/", routes)
        self.assertIn("/bodesign", routes)
        self.assertIn("/bodesign/", routes)
        self.assertIn("/bodesign/projects/{project_id}", routes)
        self.assertIn("/bodesign/projects/{project_id}/artifacts/{artifact_id}", routes)
        self.assertIn("/bodesign/routes", routes)
        self.assertIn("/bodesign/health", routes)
        self.assertIn("/bodesign/api/routes", routes)
        self.assertIn("/bodesign/api/projects", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/artifacts", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/artifacts/{artifact_id}", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/geometry", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/storage-share", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/kicad-foundation", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/kicad-native-extension", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/kicad-plugin-handshake", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/cross-probe/{probe_id}", routes)
        self.assertIn("/bodesign/api/artifacts/detect", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/knowledge/queue", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/knowledge/external-fetch", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/knowledge/datasheets", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/eda/kicad/bridge-plan", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/workflow/reference-board", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/candidates/generated-design", routes)
        self.assertIn("/bodesign/api/projects/{project_id}/reports/design", routes)

    def test_bodesign_route_index_is_visible_without_fastapi_runtime(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        route_index = api_main.bodesign_route_index()
        route_registry = api_main.bodesign_route_registry()

        self.assertIn("bodesign visible routes", route_index)
        self.assertIn("/bodesign/", route_index)
        self.assertIn("/bodesign/api/routes", {route["path"] for route in route_registry["routes"]})

    def test_bodesign_viewer_has_file_workspace_tabs(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        html = api_main.bodesign_viewer()

        self.assertIn("KiCad companion dashboard", html)
        self.assertIn("Native KiCad remains the schematic/PCB editor", html)
        self.assertIn("Project Overview", html)
        self.assertIn("Schematic Status", html)
        self.assertIn("PCB Layout Status", html)
        self.assertIn("Libraries", html)
        self.assertIn("Datasheets/Docs", html)
        self.assertIn("Analysis", html)
        self.assertIn("Manufacturing Outputs", html)
        self.assertIn("Reports", html)
        self.assertIn("Candidate Review", html)
        self.assertIn('id="tab-overview"', html)
        self.assertIn('id="tab-schematic"', html)
        self.assertIn('id="tab-pcb"', html)
        self.assertIn('id="tab-manufacturing"', html)
        self.assertNotIn('for="tab-board">Board View</label>', html)
        self.assertNotIn('for="tab-gerber">Gerber Layers</label>', html)
        self.assertNotIn('for="tab-ipc">IPC / Nets</label>', html)
        self.assertIn("Rockbox reference board", html)
        self.assertIn("imported-fixture", html)
        self.assertIn("/bodesign/projects/rockbox", html)
        self.assertIn("grid-template-columns: 300px minmax(0, 1fr)", html)
        self.assertIn(".panels { flex: 0 0 100%", html)
        self.assertIn("table-layout: fixed", html)
        self.assertIn("Datasheets/Docs", api_main.bodesign_project_workspace("rockbox"))
        self.assertIn("Gerber Layers", html)
        self.assertIn("IPC-356 Nets", html)
        self.assertIn("Component / pinout inspector", html)
        self.assertIn("BoardDesign IR", html)
        self.assertIn("Candidate workspace", html)
        self.assertIn("Diff / evidence summary", html)
        self.assertIn("not-approved", html)
        self.assertIn("bodesign is a companion dashboard", html)
        self.assertIn("Native KiCad extension boundary", html)
        self.assertIn("kicad-action-plugin-plus-bodesign-mcp-sidecar", html)
        self.assertIn("browser-native schematic editor", html)
        self.assertIn("browser-native PCB layout editor", html)
        self.assertIn("Third-party raster Gerber render", html)
        self.assertIn("Default view", html)
        self.assertIn("pygerber-raster", html)
        self.assertIn("raster-view", html) if "data:image/png;base64" in html else self.assertIn("Raster render unavailable", html)
        self.assertIn("Raster view is the default", html)
        self.assertIn("Browser-level zoom is intentionally left to the image viewer", html)
        self.assertIn("Toggle placement overlay", html)
        self.assertIn('data-overlay-toggle="components"', html)
        self.assertIn("show-components", html)
        self.assertNotIn("const svgX = original[0]", html)
        self.assertNotIn("overlay.style.transform", html)
        self.assertNotIn("addEventListener('wheel'", html)
        self.assertNotIn("addEventListener('pointerdown'", html)
        self.assertNotIn("<svg", html)
        self.assertIn("geometry-canvas", html)
        self.assertIn("component-overlay", html)
        self.assertIn("component-marker", html)
        self.assertIn('data-category="major"', html)
        self.assertIn('data-overlay-toggle="testpoints"', html)
        self.assertIn("Toggle test points", html)
        self.assertIn("U401", html)
        self.assertIn("MDBT53-P1M", html)
        self.assertIn("Component / pinout inspector", html)
        self.assertIn("IPC pin/net evidence", html)
        self.assertIn("Component-Net fusion preview", html)
        self.assertIn("Component-Net fusion evidence", html)
        self.assertIn("coverage:", html)
        self.assertIn("cross-probe/U401", html)
        self.assertIn("Probe", html)
        self.assertIn("L1_top.art", html)
        self.assertIn("ROCKBOX_V2-1-6.drl", html)
        self.assertIn("KiCad native foundation status", html)
        self.assertIn("foundation-fixture-ready", html)
        self.assertIn("KiCad source detection", html)
        self.assertIn("eda/rockbox/rockbox.kicad_pro", html)
        self.assertIn("eda/rockbox/rockbox.kicad_sch", html)
        self.assertIn("eda/rockbox/rockbox.kicad_pcb", html)
        self.assertIn("Human-facing folder taxonomy", html)
        self.assertIn("KiCad Happy hidden analysis cache", html)
        self.assertIn(".bodesign/analysis/kicad-happy", html)
        self.assertIn("track_in_git", html)
        self.assertIn("Detected manufacturing outputs", html)
        self.assertIn("Real client folder browsing is not wired yet", html)
        self.assertIn("scoped-client-storage-share", html)

    def test_project_api_lists_imported_rockbox_project(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        projects = api_main.list_projects()

        self.assertEqual("rockbox", projects[0]["id"])
        self.assertEqual("imported-fixture", projects[0]["status"])
        self.assertIn("viewer_url", projects[0])

    def test_project_artifact_api_and_viewer_expose_rockbox_files(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        artifacts = api_main.list_project_artifacts("rockbox")
        artifact = artifacts[0]
        artifact_detail = api_main.get_project_artifact("rockbox", artifact["id"])
        artifact_html = api_main.bodesign_artifact_viewer("rockbox", artifact["id"])

        self.assertGreater(len(artifacts), 0)
        self.assertEqual("rockbox", artifact["project_id"])
        self.assertIn("viewer_url", artifact)
        self.assertIn("preview", artifact_detail)
        self.assertIn(str(artifact["filename"]), artifact_html)
        self.assertIn("Preview", artifact_html)

    def test_project_geometry_api_exposes_gerber_and_drill_summary(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        geometry = api_main.get_project_geometry("rockbox")

        self.assertIn(geometry["status"], {"pygerber-raster-preview", "raster-render-unavailable"})
        self.assertEqual("L1_top.art", geometry["gerber"]["filename"])
        self.assertEqual("ROCKBOX_V2-1-6.drl", geometry["drill"]["filename"])
        self.assertIn(geometry["raster_renderer"]["status"], {"rendered", "render-failed"})
        self.assertIn("fusion_summary", geometry)
        self.assertGreater(geometry["fusion_summary"]["total_components"], 100)
        self.assertGreater(geometry["fusion_summary"]["mapped_components"], 100)
        self.assertGreater(geometry["fusion_summary"]["coverage_ratio"], 0.5)
        self.assertNotIn("svg", geometry)
        self.assertGreater(geometry["gerber"]["draw_count"], 1000)
        self.assertEqual(789, geometry["drill"]["hit_count"])

    def test_project_storage_share_manifest_is_client_owned_and_scoped(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        manifest = api_main.get_project_storage_share("rockbox")

        self.assertEqual("ready", manifest["status"])
        self.assertEqual("client", manifest["durable_owner"])
        self.assertEqual("client-owned-local-folder", manifest["storage_model"])
        self.assertEqual(".bodesign", manifest["hidden_workspace"])
        self.assertEqual([], manifest["validation_errors"])
        self.assertIn("disposable", manifest["cache_policy"])
        self.assertIn("scoped", manifest["save_back_mode"])
        self.assertIn("client", manifest["conflict_policy"])
        self.assertIn("eda", {folder["role"] for folder in manifest["human_facing_folders"]})
        self.assertIn("outputs", {folder["role"] for folder in manifest["human_facing_folders"]})
        self.assertTrue(all(folder["visibility"] == "human-facing" for folder in manifest["human_facing_folders"]))
        self.assertTrue(all(folder["path"].startswith(".bodesign/") for folder in manifest["machine_workspaces"]))
        self.assertIn("project-read", {scope["scope_id"] for scope in manifest["read_scopes"]})
        self.assertIn("mcp-save-back", {scope["scope_id"] for scope in manifest["write_scopes"]})
        self.assertNotEqual("server", manifest["durable_owner"])
        taxonomy = manifest["folder_taxonomy"]
        self.assertIn("eda/rockbox/rockbox.kicad_pro", taxonomy["kicad_sources"]["project"])
        self.assertIn("eda/rockbox/rockbox.kicad_sch", taxonomy["kicad_sources"]["schematic"])
        self.assertIn("eda/rockbox/rockbox.kicad_pcb", taxonomy["kicad_sources"]["pcb"])
        self.assertIn("outputs", taxonomy["roles"])
        self.assertTrue(any(artifact["artifact_type"] in {"gerber", "drill"} for artifact in taxonomy["output_artifacts"]))
        self.assertIn(".bodesign/analysis/kicad-happy/manifest.json", taxonomy["hidden_paths"])
        self.assertFalse(any(path.startswith(".bodesign/") for paths in taxonomy["roles"].values() for path in paths))
        kicad_happy_cache = manifest["kicad_happy_cache"]
        self.assertEqual(".kicad-happy.json", kicad_happy_cache["config_path"])
        self.assertEqual(".bodesign/analysis/kicad-happy", kicad_happy_cache["analysis_root"])
        self.assertEqual("hidden-mcp-analysis-cache", kicad_happy_cache["mode"])
        self.assertFalse(kicad_happy_cache["track_in_git"])
        self.assertTrue(all(artifact["path"].startswith(".bodesign/analysis/kicad-happy/") for artifact in kicad_happy_cache["artifact_paths"]))
        self.assertIn("manifest", {artifact["category"] for artifact in kicad_happy_cache["artifact_paths"]})
        self.assertIn("drc", {artifact["category"] for artifact in kicad_happy_cache["artifact_paths"]})
        self.assertIn("thermal", {artifact["category"] for artifact in kicad_happy_cache["artifact_paths"]})

    def test_project_kicad_foundation_summarizes_storage_taxonomy_and_gates(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        foundation = api_main.get_project_kicad_foundation("rockbox")

        self.assertEqual("foundation-fixture-ready", foundation["status"])
        self.assertEqual("client", foundation["storage_owner"])
        self.assertEqual("client-owned-local-folder", foundation["storage_model"])
        self.assertEqual(".bodesign", foundation["hidden_workspace"])
        self.assertTrue(foundation["safe_save_back"]["requires_client_approval"])
        self.assertEqual("scoped-client-storage-share", foundation["safe_save_back"]["mode"])
        self.assertIn("eda/rockbox/rockbox.kicad_pro", foundation["kicad_sources"]["project"])
        self.assertIn("eda/rockbox/rockbox.kicad_sch", foundation["kicad_sources"]["schematic"])
        self.assertIn("eda/rockbox/rockbox.kicad_pcb", foundation["kicad_sources"]["pcb"])
        self.assertIn("libraries", foundation["taxonomy_roles"])
        self.assertTrue(any(artifact["artifact_type"] in {"gerber", "drill"} for artifact in foundation["output_artifacts"]))
        self.assertEqual(".bodesign/analysis/kicad-happy", foundation["kicad_happy_cache"]["analysis_root"])
        self.assertFalse(foundation["kicad_happy_cache"]["track_in_git"])
        self.assertIn("gerber-to-design-source", foundation["blocked_pipelines"])
        self.assertIn("datasheet-reference-to-design-source", foundation["blocked_pipelines"])
        self.assertTrue(any("Real client folder browsing is not wired yet" in blocker for blocker in foundation["blockers"]))
        self.assertTrue(any("Safe save-back" in blocker for blocker in foundation["blockers"]))
        self.assertTrue(any("Browser-native schematic/PCB editing" in blocker for blocker in foundation["blockers"]))
        native_extension = foundation["native_extension"]
        self.assertEqual("contract-ready", native_extension["status"])
        self.assertEqual("kicad-action-plugin-plus-bodesign-mcp-sidecar", native_extension["integration_model"])
        self.assertIn("KiCad native application owns schematic editor", native_extension["native_editor_owner"])
        self.assertIn("browser-native schematic editor", native_extension["blocked_browser_features"])

    def test_project_kicad_native_extension_exposes_plugin_sidecar_contract(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        extension = api_main.get_project_kicad_native_extension("rockbox")

        self.assertEqual("contract-ready", extension["status"])
        self.assertEqual("kicad-action-plugin-plus-bodesign-mcp-sidecar", extension["integration_model"])
        self.assertIn("KiCad native application owns schematic editor", extension["native_editor_owner"])
        self.assertIn("Companion dashboard", extension["bodesign_role"])
        self.assertTrue(any(capability["capability_id"] == "apply-approved-patch" and capability["owner"] == "kicad-plugin" for capability in extension["capabilities"]))
        self.assertIn("browser-native schematic editor", extension["blocked_browser_features"])
        self.assertIn("browser-native PCB layout editor", extension["blocked_browser_features"])

    def test_project_kicad_plugin_handshake_is_fail_safe(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        handshake = api_main.get_project_kicad_plugin_handshake("rockbox")

        self.assertEqual("sidecar-handshake-ready", handshake["status"])
        self.assertTrue(handshake["sidecar_available"])
        self.assertEqual("kicad-action-plugin-plus-bodesign-mcp-sidecar", handshake["integration_model"])
        self.assertEqual("/bodesign/projects/rockbox", handshake["urls"]["dashboard"])
        self.assertEqual("/bodesign/api/projects/rockbox/kicad-foundation", handshake["urls"]["foundation"])
        self.assertIn("request-analysis-plan", handshake["approved_capabilities"])
        self.assertIn("represent-approved-patch", handshake["approved_capabilities"])
        self.assertIn("mutate-kicad-files-without-user-approval", handshake["blocked_capabilities"])
        self.assertFalse(handshake["approval_policy"]["approved_for_execution"])
        self.assertFalse(handshake["approval_policy"]["approved_for_file_mutation"])
        self.assertIn("approved-patch-only", handshake["approval_policy"]["patch_application"])
        self.assertEqual("contract-ready", handshake["native_extension_status"])
        self.assertEqual("foundation-fixture-ready", handshake["foundation_status"])
        self.assertTrue(any("does not run KiCad" in warning for warning in handshake["warnings"]))

    def test_project_cross_probe_links_components_nets_and_artifacts(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        component_probe = api_main.get_project_cross_probe("rockbox", "U401")
        net_name = component_probe["nets"][0]["net"]
        net_probe = api_main.get_project_cross_probe("rockbox", net_name)
        artifact_probe = api_main.get_project_cross_probe("rockbox", "l1-top-art")

        self.assertEqual("component", component_probe["kind"])
        self.assertEqual("U401", component_probe["component"]["refdes"])
        self.assertGreater(len(component_probe["nets"]), 0)
        self.assertIn("artifacts", component_probe)
        self.assertEqual("net", net_probe["kind"])
        self.assertGreater(len(net_probe["components"]), 0)
        self.assertGreaterEqual(net_probe["net"]["pad_count"], len(net_probe["components"]))
        self.assertEqual("artifact", artifact_probe["kind"])
        self.assertEqual("L1_top.art", artifact_probe["artifact"]["filename"])
        self.assertGreater(len(artifact_probe["related_artifacts"]), 0)

    def test_project_component_knowledge_queue_exposes_reusable_parts(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        queue = api_main.get_component_knowledge_queue("rockbox")

        self.assertEqual("queued", queue["status"])
        self.assertGreater(queue["total_items"], 20)
        self.assertIn("component:mdbt53-p1m", {item["reusable_key"] for item in queue["items"]})
        self.assertIn("knowledge_gaps", queue["items"][0])

    def test_external_datasheet_fetch_is_blocked_by_policy_gate(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        response = api_main.request_external_datasheet_fetch("rockbox", {"part_number": "MDBT53-P1M"})

        self.assertEqual("blocked-policy-gate", response["status"])
        self.assertFalse(response["external_fetch_enabled"])
        self.assertTrue(response["requires_user_approval"])
        self.assertIn("docxmcp-derived source chunks", response["allowed_inputs"])

    def test_kicad_bridge_plan_api_uses_plugin_submodule_posture(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        response = api_main.plan_project_kicad_bridge("rockbox", {"board_design_id": "rockbox-board-design"})

        self.assertEqual("plugin-submodule-auto-workflow", response["integration_posture"])
        self.assertEqual("not-executed", response["execution_status"])
        self.assertIn("adapter", response["adapter_boundary"].lower())
        self.assertTrue(any(output.endswith(".kicad_pcb") for output in response["planned_outputs"]))

    def test_reference_board_workflow_plan_is_client_orchestrated_and_gated(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        response = api_main.plan_project_reference_board_workflow("rockbox", {"board_design_id": "rockbox-board-design"})

        self.assertEqual("planned-with-blockers", response["status"])
        self.assertEqual("client-orchestrated-mcp-workflow", response["orchestration_model"])
        stage_ids = {stage["stage_id"] for stage in response["stages"]}
        self.assertIn("ingest-sources", stage_ids)
        self.assertIn("resolve-knowledge", stage_ids)
        self.assertIn("deterministic-validation", stage_ids)
        self.assertTrue(any("docxmcp" in warning for warning in response["warnings"]))
        self.assertTrue(any("approval" in gate.lower() for gate in response["approval_gates"]))

    def test_generated_design_candidate_workspace_is_not_approved_by_default(self):
        install_fastapi_stub()
        sys.modules.pop("services.api.main", None)

        api_main = importlib.import_module("services.api.main")
        response = api_main.get_generated_design_candidate_workspace("rockbox")

        self.assertEqual("draft-evidence-workspace", response["status"])
        self.assertEqual("not-approved", response["approval_state"])
        self.assertEqual("rockbox-board-design", response["source_board_design_id"])
        self.assertTrue(any(item["area"] == "layout output" for item in response["diff_summary"]))
        self.assertTrue(any("send-to-fab" in gate for gate in response["validation_gates"]))


def install_fastapi_stub() -> None:
    fastapi_module = types.ModuleType("fastapi")
    responses_module = types.ModuleType("fastapi.responses")

    class Route:
        def __init__(self, path: str, method: str) -> None:
            self.path = path
            self.method = method

    class FastAPI:
        def __init__(self, *args, **kwargs) -> None:
            self.routes = []

        def get(self, path: str, **kwargs):
            return self._register(path, "GET")

        def post(self, path: str, **kwargs):
            return self._register(path, "POST")

        def _register(self, path: str, method: str):
            def decorator(function):
                self.routes.append(Route(path, method))
                return function

            return decorator

    class HTMLResponse:
        pass

    class RedirectResponse:
        def __init__(self, url: str) -> None:
            self.url = url

    fastapi_module.FastAPI = FastAPI
    responses_module.HTMLResponse = HTMLResponse
    responses_module.RedirectResponse = RedirectResponse
    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.responses"] = responses_module


if __name__ == "__main__":
    unittest.main()
