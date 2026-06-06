import importlib
import unittest


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.server = importlib.import_module("services.mcp.server")

    def test_registry_is_well_formed(self):
        names = [t["name"] for t in self.server.TOOLS]
        self.assertEqual(len(names), len(set(names)), "tool names must be unique")
        self.assertGreaterEqual(len(names), 10)
        for t in self.server.TOOLS:
            self.assertTrue(t["name"].startswith("bodesign_"))
            self.assertTrue(callable(t["handler"]))
            self.assertIn("type", t["schema"])
            self.assertTrue(t["description"])

    def test_run_tool_plan_design_intent(self):
        r = self.server.run_tool("bodesign_plan_design_intent",
                                 {"spec": "STM32N6 NPU + WiFi + camera + USB-C charging + 18650 battery"})
        self.assertTrue(r["ok"])
        self.assertEqual("needs-clarification", r["result"]["status"])
        self.assertTrue(r["result"]["subsystems"])

    def test_unknown_tool_is_data_not_exception(self):
        r = self.server.run_tool("nope", {})
        self.assertIn("error", r)
        self.assertIn("unknown tool", r["error"])

    def test_handler_error_is_captured(self):
        # missing required "folder" -> KeyError captured as data, not raised
        r = self.server.run_tool("bodesign_ingest_project", {})
        self.assertFalse(r["ok"])
        self.assertIn("error", r)

    def test_landing_page_has_guide_sections(self):
        page = self.server._landing_html("/x/bodesign.sock", 8077)
        for section in ("Install", "File model", "Circuit-design workflow", "Skill packages", "Endpoints"):
            self.assertIn(section, page)
        self.assertIn("/tools", page)

    def test_tools_index_links_every_tool(self):
        idx = self.server._tools_index_html()
        for t in self.server.TOOLS:
            self.assertIn(f'/tools/{t["name"]}', idx)

    def test_tool_detail_shows_full_schema(self):
        detail = self.server._tool_detail_html("bodesign_compose_schematic")
        self.assertIn("inputSchema", detail)
        self.assertIn("tools/call", detail)
        self.assertIn("bodesign_compose_schematic", detail)
        self.assertIn("Unknown tool", self.server._tool_detail_html("nope_not_a_tool"))

    def test_build_server_when_mcp_available(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("mcp SDK not installed in this interpreter")
        server = self.server.build_server()
        self.assertEqual("bodesign", server.name)


if __name__ == "__main__":
    unittest.main()
