import importlib
import json
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

    def test_run_tool_c01_next_question_and_update_answers(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c01-interact-", dir=PRIVATE_BASE))
        try:
            question = self.server.run_tool("bodesign_c01_next_question", {"folder": str(work)})
            self.assertTrue(question["ok"])
            self.assertEqual("form_archetype", question["result"]["target_field"])
            self.assertFalse(question["result"]["answer_state_exists"])

            update = self.server.run_tool("bodesign_c01_update_answers", {
                "folder": str(work),
                "c00": "Desk edge AI device with camera, mic, USB-C, and LED.",
                "answers": {
                    "form_archetype": "desktop sensor",
                    "usage_posture": "placed on desk",
                },
            })

            self.assertTrue(update["ok"])
            self.assertEqual("answers_updated", update["result"]["status"])
            self.assertFalse(update["result"]["human_approved"])
            self.assertEqual("primary_face", update["result"]["next_question"]["target_field"])
            self.assertTrue((work / "C01-ID" / "answer_state.json").exists())
            self.assertTrue((work / "C01-ID" / "Handoff_to_ID_Designer.md").exists())

            readiness = self.server.run_tool("bodesign_c01_readiness", {"folder": str(work)})
            self.assertTrue(readiness["ok"])
            self.assertFalse(readiness["result"]["usable"])
            self.assertEqual("C01-ID/answer_state.json", readiness["result"]["answer_state_path"])
            self.assertIn("primary_face", readiness["result"]["next_step"])
            self.assertFalse(readiness["result"]["human_approved"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_scaffold_prd(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c00-", dir=PRIVATE_BASE))
        try:
            result = self.server.run_tool("bodesign_c00_scaffold_prd", {
                "out_dir": str(work),
                "project_name": "MCP C00 POC",
                "include_rf": True,
            })

            self.assertTrue(result["ok"])
            self.assertEqual("scaffold_created", result["result"]["status"])
            self.assertFalse(result["result"]["readiness_computed"])
            self.assertFalse(result["result"]["prd_emitted"])
            self.assertFalse(result["result"]["human_approved"])
            self.assertTrue((work / "C00-PRD" / "Project_Requirements.md").exists())
            self.assertTrue((work / "C00-PRD" / "RF_Requirements.md").exists())
            state = json.loads((work / "C00-PRD" / "answer_state.json").read_text(encoding="utf-8"))
            self.assertIn("Project_Requirements.md", state["documents"])
            self.assertIn("RF_Requirements.md", state["documents"])
            self.assertEqual("missing", state["documents"]["Project_Requirements.md"]["sections"][0]["state"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_readiness_reports_blockers(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c00-ready-", dir=PRIVATE_BASE))
        try:
            scaffold = self.server.run_tool("bodesign_c00_scaffold_prd", {"out_dir": str(work)})
            self.assertTrue(scaffold["ok"])

            readiness = self.server.run_tool("bodesign_c00_readiness", {"folder": str(work)})

            self.assertTrue(readiness["ok"])
            self.assertEqual("blocked", readiness["result"]["status"])
            self.assertEqual(0, readiness["result"]["readiness_pct"])
            self.assertTrue(readiness["result"]["next_question"])
            self.assertFalse(readiness["result"]["prd_emitted"])
            self.assertFalse(readiness["result"]["human_approved"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_readiness_missing_state_is_data_error(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c00-missing-", dir=PRIVATE_BASE))
        try:
            result = self.server.run_tool("bodesign_c00_readiness", {"folder": str(work)})

            self.assertFalse(result["ok"])
            self.assertIn("answer_state.json", result["error"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_emit_prd_generates_markdown_without_approval(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c00-emit-", dir=PRIVATE_BASE))
        try:
            scaffold = self.server.run_tool("bodesign_c00_scaffold_prd", {"out_dir": str(work)})
            self.assertTrue(scaffold["ok"])

            result = self.server.run_tool("bodesign_c00_emit_prd", {"folder": str(work)})

            self.assertTrue(result["ok"])
            self.assertEqual("prd_markdown_emitted", result["result"]["status"])
            self.assertTrue(result["result"]["prd_emitted"])
            self.assertFalse(result["result"]["human_approved"])
            self.assertIn("C00-PRD/Project_Requirements.generated.md", result["result"]["files"])
            self.assertIn("C00-PRD/C00_Handoff_Report.md", result["result"]["files"])
            self.assertTrue((work / "C00-PRD" / "Project_Requirements.generated.md").exists())
            self.assertTrue((work / "C00-PRD" / "C00_Handoff_Report.md").exists())
            generated = (work / "C00-PRD" / "Project_Requirements.generated.md").read_text(encoding="utf-8")
            self.assertIn("{missing}", generated)
            self.assertIn("Human approved: false", generated)
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

    def test_run_tool_c02_export_step_reports_unavailable(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c02-step-", dir=PRIVATE_BASE))
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

            result = self.server.run_tool("bodesign_c02_export_step", {"out_dir": str(work)})

            self.assertTrue(result["ok"])
            self.assertEqual("step_export_unavailable", result["result"]["status"])
            self.assertIsNone(result["result"]["step_path"])
            self.assertFalse((work / "C02-ME" / "Enclosure.step").exists())
            self.assertTrue((work / "C02-ME" / "STEP_Draft_Handoff.md").exists())
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

    def test_run_tool_agent_registry(self):
        r = self.server.run_tool("bodesign_agent_registry", {})
        self.assertTrue(r["ok"])
        self.assertEqual([role["code"] for role in r["result"]["roles"]],
                         ["C00", "C01", "C02", "C03", "C04", "C05", "C06"])

    def test_run_tool_orchestration_roundtrip(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-orch-", dir=PRIVATE_BASE))
        try:
            d = self.server.run_tool("bodesign_dispatch_work_packet", {
                "folder": str(work), "target_layer": "C01",
                "objective": "Produce first-pass ID direction from PRD visual fields.",
                "sections": ["s05_id_me_requirements"]})
            self.assertTrue(d["ok"])
            packet_id = d["result"]["packet_id"]
            self.assertEqual(d["result"]["target_role"], "industrial_design")

            b = self.server.run_tool("bodesign_return_blocker", {
                "folder": str(work), "packet_id": packet_id, "severity": "decision",
                "summary": "Need primary face decision.",
                "question_for_user": "Which face is primary?",
                "affected_c00_fields": ["s05_id_me_requirements.primary_face"]})
            self.assertTrue(b["ok"])
            blocker_id = b["result"]["blocker_id"]

            open_blk = self.server.run_tool("bodesign_list_blockers", {"folder": str(work), "unresolved_only": True})
            self.assertEqual(len(open_blk["result"]["blockers"]), 1)

            g = self.server.run_tool("bodesign_ingest_blocker", {
                "folder": str(work), "blocker_id": blocker_id, "resolved_state": "answered",
                "decision": "Top face is primary."})
            self.assertTrue(g["ok"])
            self.assertTrue(g["result"]["resolved"])

            closed = self.server.run_tool("bodesign_list_blockers", {"folder": str(work), "unresolved_only": True})
            self.assertEqual(closed["result"]["blockers"], [])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_dispatch_to_c00_fails(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-orch2-", dir=PRIVATE_BASE))
        try:
            r = self.server.run_tool("bodesign_dispatch_work_packet",
                                     {"folder": str(work), "target_layer": "C00", "objective": "x"})
            self.assertFalse(r["ok"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_orchestration(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-loop-", dir=PRIVATE_BASE))
        try:
            # Empty -> the loop tells you to scaffold C00 first.
            tick = self.server.run_tool("bodesign_c00_orchestration_tick", {"folder": str(work)})
            self.assertTrue(tick["ok"])
            self.assertEqual(tick["result"]["kind"], "scaffold_c00")
            # Status board is read-only and well-formed.
            self.server.run_tool("bodesign_c00_scaffold_prd", {"out_dir": str(work), "project_name": "X"})
            board = self.server.run_tool("bodesign_c00_orchestration_status", {"folder": str(work)})
            self.assertTrue(board["ok"])
            self.assertEqual([l["code"] for l in board["result"]["layers"]],
                             ["C01", "C02", "C03", "C04", "C05", "C06"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_tool_groups_assigned(self):
        groups = {t["name"]: t["group"] for t in self.server.TOOLS}
        # C02 CAD generation/export tools belong to the mechanical worker group.
        for t in ("bodesign_c02_export_step", "bodesign_c02_export_stl",
                  "bodesign_c02_generate_openscad", "bodesign_c02_export_skp"):
            self.assertEqual(groups[t], "me")
        # Pure-python / core tools stay core.
        for t in ("bodesign_agent_registry", "bodesign_c02_readiness", "bodesign_c00_orchestration_tick"):
            self.assertEqual(groups[t], "core")

    def test_monolith_runs_everything_local(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"all"}
            for name in ("bodesign_c02_export_step", "bodesign_agent_registry"):
                self.assertEqual(self.server._route_tool(name)[0], "local")
        finally:
            self.server.SERVED_GROUPS = saved

    def test_core_without_worker_reports_unavailable(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"core"}
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BODESIGN_ME_WORKER_URL", None)
                decision, target = self.server._route_tool("bodesign_c02_export_step")
                self.assertEqual((decision, target), ("unavailable", "me"))
                # run_tool surfaces it as data, never a crash, never a fabricated STEP.
                r = self.server.run_tool("bodesign_c02_export_step", {"out_dir": "/x"})
                self.assertFalse(r["ok"])
                self.assertTrue(r["worker_unavailable"])
                # A core tool still runs locally.
                self.assertEqual(self.server._route_tool("bodesign_agent_registry")[0], "local")
        finally:
            self.server.SERVED_GROUPS = saved

    def test_core_with_worker_forwards(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"core"}
            with patch.dict(os.environ, {"BODESIGN_ME_WORKER_URL": "http://bodesign-me:8077"}):
                decision, target = self.server._route_tool("bodesign_c02_export_step")
                self.assertEqual(decision, "forward")
                self.assertEqual(target, "http://bodesign-me:8077")
                # run_tool forwards (patch the forwarder to avoid a live worker).
                with patch.object(self.server, "_forward_to_worker",
                                  return_value={"ok": True, "result": {"status": "step_exported"}}) as fwd:
                    r = self.server.run_tool("bodesign_c02_export_step", {"out_dir": "/x"})
                    fwd.assert_called_once()
                    self.assertEqual(r["result"]["status"], "step_exported")
        finally:
            self.server.SERVED_GROUPS = saved

    def test_me_worker_serves_me_tools_locally(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"me"}
            self.assertEqual(self.server._route_tool("bodesign_c02_export_step")[0], "local")
            # A core tool on the worker, with no core worker url, is unavailable (core never forwards core tools here).
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BODESIGN_CORE_WORKER_URL", None)
                self.assertEqual(self.server._route_tool("bodesign_agent_registry")[0], "unavailable")
        finally:
            self.server.SERVED_GROUPS = saved

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
