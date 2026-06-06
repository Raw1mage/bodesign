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

    def test_build_server_when_mcp_available(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("mcp SDK not installed in this interpreter")
        server = self.server.build_server()
        self.assertEqual("bodesign", server.name)


if __name__ == "__main__":
    unittest.main()
