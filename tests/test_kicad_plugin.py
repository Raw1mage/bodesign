import unittest

from bodesign_kicad_plugin import BODESIGN_PLUGIN_METADATA, PCBNEW_AVAILABLE, SidecarConfig, build_approved_patch_request, build_plugin_handshake_request, build_request_analysis_call, discover_project_context, open_dashboard_url


class KiCadPluginTests(unittest.TestCase):
    def test_imports_safely_regardless_of_kicad_pcbnew(self):
        # The plugin must import whether or not pcbnew is present; PCBNEW_AVAILABLE
        # is informational only and must never gate import or change the contract.
        self.assertIsInstance(PCBNEW_AVAILABLE, bool)
        self.assertIn("bodesign companion dashboard", BODESIGN_PLUGIN_METADATA["name"])
        self.assertIn("without replacing KiCad editors", BODESIGN_PLUGIN_METADATA["description"])

    def test_default_sidecar_urls(self):
        config = SidecarConfig("rockbox")

        self.assertEqual("http://127.0.0.1:8765/bodesign/projects/rockbox", config.dashboard_url)
        self.assertEqual("http://127.0.0.1:8765/bodesign/api/projects/rockbox/kicad-foundation", config.foundation_api_url)
        self.assertEqual("http://127.0.0.1:8765/bodesign/api/projects/rockbox/kicad-native-extension", config.native_extension_api_url)
        self.assertEqual("http://127.0.0.1:8765/bodesign/api/projects/rockbox/kicad-plugin-handshake", config.handshake_api_url)
        self.assertEqual("http://127.0.0.1:8765/bodesign/api/projects/rockbox/kicad-analysis-status", config.request_analysis_api_url)

    def test_discovers_project_context_from_kicad_paths(self):
        project_context = discover_project_context("/work/demo/eda/demo.kicad_pro")
        pcb_context = discover_project_context("/work/demo/eda/demo.kicad_pcb")

        self.assertEqual("demo", project_context.project_id)
        self.assertEqual("project", project_context.source_type)
        self.assertEqual("/work/demo/eda", project_context.project_root)
        self.assertEqual("pcb", pcb_context.source_type)

    def test_request_analysis_is_represented_not_executed(self):
        config = SidecarConfig("demo")
        context = discover_project_context("/work/demo/eda/demo.kicad_pro")
        call = build_request_analysis_call(config, context)

        self.assertEqual("POST", call["method"])
        self.assertIn("/kicad-analysis-status", call["endpoint"])
        self.assertEqual(".bodesign/analysis/kicad-happy", call["payload"]["analysis_root"])
        self.assertIn("drc", call["payload"]["requested_checks"])
        self.assertFalse(call["payload"]["approved_for_execution"])
        self.assertEqual("represented-not-executed", call["status"])

    def test_plugin_handshake_request_is_represented_not_sent(self):
        config = SidecarConfig("demo")
        context = discover_project_context("/work/demo/eda/demo.kicad_pcb")
        request = build_plugin_handshake_request(config, context)

        self.assertEqual("represented-not-sent", request.status)
        self.assertIn("/kicad-plugin-handshake", request.endpoint)
        self.assertEqual("demo", request.payload["project_id"])
        self.assertEqual("pcb", request.payload["source_type"])
        self.assertFalse(request.payload["approved_for_execution"])
        self.assertFalse(request.payload["approved_for_file_mutation"])
        self.assertIn("represent-approved-patch", request.payload["plugin_capabilities"])
        self.assertTrue(any("does not run KiCad" in warning for warning in request.warnings))

    def test_approved_patch_guard_blocks_unapproved_patch(self):
        config = SidecarConfig("demo")

        with self.assertRaises(ValueError):
            build_approved_patch_request(config, "candidate-1", approved_by_user=False)

    def test_approved_patch_request_is_represented_not_applied(self):
        config = SidecarConfig("demo")
        request = build_approved_patch_request(config, "candidate-1", approved_by_user=True)

        self.assertEqual("represented-not-applied", request.status)
        self.assertTrue(request.approved_by_user)
        self.assertIn("apply-approved-patch", request.endpoint)
        self.assertTrue(any("does not apply files" in warning for warning in request.warnings))
        self.assertEqual("http://127.0.0.1:8765/bodesign/projects/demo", open_dashboard_url(config))


if __name__ == "__main__":
    unittest.main()
