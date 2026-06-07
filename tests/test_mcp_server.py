import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


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

    def test_run_tool_c01_emit_and_readiness(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c01-", dir=PRIVATE_BASE))
        try:
            r = self.server.run_tool("bodesign_c01_emit_package", {
                "out_dir": str(work),
                "c00": "Battery camera product with microphone, BLE, USB-C, and LED status.",
                "answers": {"product_name": "MCP C01 POC", "form_archetype": "desktop sensor"},
            })
            self.assertTrue(r["ok"])
            self.assertTrue(r["result"]["readiness"]["usable"])
            self.assertTrue((work / "C01-ID" / "CMF" / "CMF_Direction.md").exists())

            readiness = self.server.run_tool("bodesign_c01_readiness", {"folder": str(work)})
            self.assertTrue(readiness["ok"])
            self.assertEqual(100, readiness["result"]["readiness_pct"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c01_generate_concept_image_requires_key(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c01-img-", dir=PRIVATE_BASE))
        try:
            with patch.dict(os.environ, {"BODESIGN_GOOGLE_API_KEY": "", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "BODESIGN_OPENCODE_ACCOUNTS_JSON": str(work / "missing-accounts.json")}, clear=False):
                result = self.server.run_tool("bodesign_c01_generate_concept_image", {
                    "out_dir": str(work),
                    "prompt": "compact desktop edge AI camera sensor",
                })
            self.assertFalse(result["ok"])
            self.assertIn("Google AI Studio API key", result["error"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c02_readiness_blocks_missing_board_outline(self):
        result = self.server.run_tool("bodesign_c02_readiness", {
            "constraints": {"component_heights": [{"ref": "J1", "height_mm": 8}]}
        })

        self.assertTrue(result["ok"])
        self.assertFalse(result["result"]["can_generate_cad_source"])
        self.assertIn("Board outline", result["result"]["next_step"])

    def test_run_tool_c02_readiness_accepts_minimum_source_constraints(self):
        result = self.server.run_tool("bodesign_c02_readiness", {
            "constraints": {
                "board_outline": {"width_mm": 80, "height_mm": 50},
                "component_heights": [{"ref": "U1", "height_mm": 4}],
            }
        })

        self.assertTrue(result["ok"])
        self.assertTrue(result["result"]["can_generate_cad_source"])
        self.assertFalse(result["result"]["can_create_printable_draft"])

    def test_run_tool_c02_emit_enclosure_package(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c02-", dir=PRIVATE_BASE))
        try:
            result = self.server.run_tool("bodesign_c02_emit_enclosure_package", {
                "out_dir": str(work),
                "constraints": {"component_heights": [{"ref": "J1", "height_mm": 8}]},
                "project_summary": "Desk AI sensor",
                "prototype_intent": "vendor RFQ package",
                "printer_profile": {"material": "PLA"},
            })

            self.assertTrue(result["ok"])
            self.assertEqual("package_emitted", result["result"]["status"])
            self.assertFalse(result["result"]["source_ready"])
            self.assertFalse(result["result"]["vendor_handoff_ready"])
            self.assertFalse(result["result"]["me_approved"])
            self.assertTrue((work / "C02-ME" / "Mechanical_Constraints.json").exists())
            self.assertTrue((work / "C02-ME" / "Vendor_Handoff.md").exists())
            self.assertFalse((work / "C02-ME" / "Enclosure.skp").exists())
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c02_generate_openscad_and_export_unavailable_stl(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c02-scad-", dir=PRIVATE_BASE))
        try:
            constraints = {
                "board_outline": {"width_mm": 80, "height_mm": 50},
                "component_heights": [{"ref": "J1", "height_mm": 8}],
            }
            source = self.server.run_tool("bodesign_c02_generate_openscad", {
                "out_dir": str(work),
                "constraints": constraints,
                "wall_thickness_mm": 2.0,
                "clearance_mm": 1.0,
                "lid_clearance_mm": 0.4,
            })

            self.assertTrue(source["ok"])
            self.assertEqual("source_generated", source["result"]["status"])
            self.assertTrue((work / "C02-ME" / "Enclosure.scad").exists())
            self.assertFalse(source["result"]["printable_draft_ready"])
            self.assertFalse(source["result"]["me_approved"])

            with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
                stl = self.server.run_tool("bodesign_c02_export_stl", {"out_dir": str(work)})
            self.assertTrue(stl["ok"])
            self.assertEqual("export_unavailable", stl["result"]["status"])
            self.assertFalse((work / "C02-ME" / "Enclosure.stl").exists())
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c02_export_skp_reports_unavailable(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c02-skp-", dir=PRIVATE_BASE))
        try:
            source = self.server.run_tool("bodesign_c02_generate_openscad", {
                "out_dir": str(work),
                "constraints": {
                    "board_outline": {"width_mm": 80, "height_mm": 50},
                    "component_heights": [{"ref": "J1", "height_mm": 8}],
                },
                "wall_thickness_mm": 2.0,
                "clearance_mm": 1.0,
                "lid_clearance_mm": 0.4,
            })
            self.assertTrue(source["ok"])

            result = self.server.run_tool("bodesign_c02_export_skp", {"out_dir": str(work)})

            self.assertTrue(result["ok"])
            self.assertEqual("skp_export_unavailable", result["result"]["status"])
            self.assertIsNone(result["result"]["skp_path"])
            self.assertFalse((work / "C02-ME" / "Enclosure.skp").exists())
            self.assertTrue((work / "C02-ME" / "SketchUp_Import_Guide.md").exists())
            self.assertFalse(result["result"]["me_approved"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c03_export_mechanical_constraints(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c03-", dir=PRIVATE_BASE))
        try:
            result = self.server.run_tool("bodesign_c03_export_mechanical_constraints", {
                "out_dir": str(work),
                "circuit": {
                    "components": [
                        {"ref": "J1", "value": "USB-C", "role": "connector", "height_mm": 3.2, "external": True},
                        {"ref": "U1", "value": "AI MCU", "height_mm": 1.4, "thermal_watts": 1.8},
                    ],
                    "battery_envelope": {"width_mm": 30, "height_mm": 40, "depth_mm": 6},
                },
            })

            self.assertTrue(result["ok"])
            self.assertEqual("mechanical_constraints_exported", result["result"]["status"])
            self.assertFalse(result["result"]["mechanical_approval"])
            self.assertTrue((work / "C03-EE" / "Mechanical_Constraint_Export.json").exists())
            self.assertIn("component_heights", result["result"]["c02_ready_keys"])
            self.assertNotIn("board_outline", result["result"]["constraints"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

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
        page = self.server._landing_html("/x/bodesign.sock", 8077, "en")
        for section in ("Install", "File model", "Circuit-design workflow", "Skill packages", "Endpoints"):
            self.assertIn(section, page)
        self.assertIn("/tools", page)
        self.assertIn("/idef0.svg", page)

    def test_landing_page_i18n_zh(self):
        page = self.server._landing_html("/x/bodesign.sock", 8077, "zh")
        for section in ("安裝與啟動", "檔案模型", "電路設計工作流", "編排的 skill 套件", "連線端點"):
            self.assertIn(section, page)
        self.assertIn('lang="zh-Hant"', page)
        # tool detail also localizes
        self.assertIn("參數", self.server._tool_detail_html("bodesign_emit_fab", "zh"))

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

    def test_skill_downloads_include_bundle_and_kicad(self):
        names = [fn for fn, _, _ in self.server._skill_downloads()]
        self.assertTrue(any(n.startswith("bodesign-eda") for n in names), "bundle missing")
        self.assertIn("kicad.tar.gz", names)
        page = self.server._landing_html("x", 8077, "en")
        self.assertIn("/skills/kicad.tar.gz", page)

    def test_build_server_when_mcp_available(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("mcp SDK not installed in this interpreter")
        server = self.server.build_server()
        self.assertEqual("bodesign", server.name)


if __name__ == "__main__":
    unittest.main()
