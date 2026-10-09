import importlib
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

# Landing plane (plan mcp_r13, task 6.1): the Bucket-2 verbs are no longer MCP
# tools — their functional coverage now runs through gate.py's in-process
# handlers, mirroring how agents invoke them on the host.
REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE_SPEC = importlib.util.spec_from_file_location(
    "bodesign_landing_gate_for_mcp_tests", REPO_ROOT / "skills" / "bodesign" / "scripts" / "gate.py")
GATE = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(GATE)


def _seed_refs(work: Path, stage: str = "C01-ID") -> None:
    """Minimal 01_refs/ SSOT so the refs-first emit gate passes (DD-7).

    ``01_refs/`` is a PER-STAGE bucket (stage-structure.md); ``work`` is the
    product root, so the SSOT lands under the owning stage.
    """
    refs = work / stage / "01_refs"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "owner_brief.md").write_text(
        "# Owner brief\n\nDecomposed from the owner authority source.\n",
        encoding="utf-8",
    )


def run_landing(verb: str, args: dict) -> dict:
    """Run a landed verb through gate.py's handler, with run_tool-shaped output."""
    try:
        return {"ok": True, "result": GATE._jsonable(GATE.HANDLERS[verb](args))}
    except Exception as error:
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.server = importlib.import_module("services.mcp.server")

    def test_multisheet_engine_schema(self):
        schema = self.server.TOOLS_BY_NAME["bodesign_emit_multisheet"]["schema"]
        properties = schema["properties"]
        self.assertEqual(properties["layout_engine"]["enum"], ["elk-layered"])
        for key, kind in (("layout_engine", "string"),
                          ("engine_placement_models", "array"),
                          ("engine_spacing_overrides", "object"),
                          ("engine_orientation_sets", "object"),
                          ("engine_outline_refs", "array")):
            self.assertEqual(properties[key]["type"], kind)
            self.assertNotIn(key, schema["required"])

    def test_multisheet_engine_argument_precedence(self):
        from unittest.mock import Mock
        engine = {"layout_engine": "elk-layered", "engine_placement_models": ["R0"],
                  "engine_spacing_overrides": {"spacing.nodeNode": "12"},
                  "engine_orientation_sets": {"R1": ["identity"]},
                  "engine_outline_refs": []}
        for mode in ("spec", "top-level", "both", "mixed", "legacy"):
            with self.subTest(mode=mode):
                spec = {"components": [], "nets": []}
                args = {"out_dir": "unused", "project_name": "test", "spec": spec}
                if mode in ("spec", "both", "mixed"):
                    spec.update(engine)
                if mode in ("top-level", "both"):
                    args.update(engine)
                if mode == "both":
                    spec["layout_engine"] = "conflicting-engine"
                    spec["engine_placement_models"] = ["conflicting-model"]
                if mode == "mixed":
                    args["engine_outline_refs"] = []
                    spec["engine_outline_refs"] = ["R1"]
                original = dict(spec)
                result = Mock(leaf_paths={}, leaf_results={})
                result.to_dict.return_value = {"engine_reports": {}}
                with patch("bodesign_eda_bridge.hierarchical.emit_multisheet", return_value=result) as emit:
                    out = self.server._h_emit_multisheet(args)
                forwarded_spec = emit.call_args.args[2]
                sources = {}
                for key, value in engine.items():
                    if key in args:
                        self.assertEqual(emit.call_args.kwargs[key], value)
                        self.assertNotIn(key, forwarded_spec)
                        sources[key] = "top-level"
                    elif key in original:
                        self.assertEqual(forwarded_spec[key], original[key])
                        self.assertNotIn(key, emit.call_args.kwargs)
                        sources[key] = "spec"
                self.assertEqual(out["engine_arg_source"], sources)
                self.assertEqual(spec, original, "caller spec must not be mutated")
                self.assertTrue(out["ok"])

    def test_tool_detail_status_is_404_for_an_unknown_tool(self):
        # BR_20260730 round 4 (D6). Round 3 fixed this status but left the
        # decision inside the run_http closure, unreachable by any test:
        # reverting `else 404` to `else 200` left the whole suite green, which
        # is an unguarded fix. This is the guard.
        self.assertEqual(404, self.server.tool_detail_status("nosuchtool"))
        self.assertEqual(404, self.server.tool_detail_status(""))
        self.assertEqual(404, self.server.tool_detail_status("../mcp.json"))

    def test_tool_detail_status_is_200_for_every_real_tool(self):
        # Accepting control: a guard that answered 404 for everything would
        # pass the negative test above while breaking the whole page.
        for tool in self.server.TOOLS:
            self.assertEqual(200, self.server.tool_detail_status(tool["name"]),
                             f"{tool['name']} is registered but its page 404s")

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
        r = run_landing("plan_design_intent",
                                 {"spec": "STM32N6 NPU + WiFi + camera + USB-C charging + 18650 battery"})
        self.assertTrue(r["ok"])
        self.assertEqual("needs-clarification", r["result"]["status"])
        self.assertTrue(r["result"]["subsystems"])

    def test_run_tool_c01_emit_and_readiness(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c01-", dir=PRIVATE_BASE))
        _seed_refs(work)
        try:
            r = run_landing("c01_emit_package", {
                "out_dir": str(work),
                "c00": "Battery camera product with microphone, BLE, USB-C, and LED status.",
                "answers": {"product_name": "MCP C01 POC", "form_archetype": "desktop sensor"},
            })
            self.assertTrue(r["ok"])
            self.assertTrue(r["result"]["readiness"]["usable"])
            self.assertTrue((work / "C01-ID" / "CMF" / "CMF_Direction.md").exists())

            readiness = run_landing("c01_readiness", {"folder": str(work)})
            self.assertTrue(readiness["ok"])
            self.assertEqual(100, readiness["result"]["readiness_pct"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c01_next_question_and_update_answers(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c01-interact-", dir=PRIVATE_BASE))
        _seed_refs(work)
        try:
            question = run_landing("c01_next_question", {"folder": str(work)})
            self.assertTrue(question["ok"])
            self.assertEqual("form_archetype", question["result"]["target_field"])
            self.assertFalse(question["result"]["answer_state_exists"])

            update = run_landing("c01_update_answers", {
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

            readiness = run_landing("c01_readiness", {"folder": str(work)})
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
            result = run_landing("c00_scaffold_prd", {
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
            scaffold = run_landing("c00_scaffold_prd", {"out_dir": str(work)})
            self.assertTrue(scaffold["ok"])

            readiness = run_landing("c00_readiness", {"folder": str(work)})

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
            result = run_landing("c00_readiness", {"folder": str(work)})

            self.assertFalse(result["ok"])
            self.assertIn("answer_state.json", result["error"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_emit_prd_generates_markdown_without_approval(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-c00-emit-", dir=PRIVATE_BASE))
        try:
            scaffold = run_landing("c00_scaffold_prd", {"out_dir": str(work)})
            self.assertTrue(scaffold["ok"])

            result = run_landing("c00_emit_prd", {"folder": str(work)})

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
        result = run_landing("c02_readiness", {
            "constraints": {"component_heights": [{"ref": "J1", "height_mm": 8}]}
        })

        self.assertTrue(result["ok"])
        self.assertFalse(result["result"]["can_generate_cad_source"])
        self.assertIn("Board outline", result["result"]["next_step"])

    def test_run_tool_c02_readiness_accepts_minimum_source_constraints(self):
        result = run_landing("c02_readiness", {
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
        _seed_refs(work, stage="C02-ME")
        try:
            result = run_landing("c02_emit_enclosure_package", {
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
            source = run_landing("c02_generate_openscad", {
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
            source = run_landing("c02_generate_openscad", {
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
            source = run_landing("c02_generate_openscad", {
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
            result = run_landing("c03_export_mechanical_constraints", {
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
        r = run_landing("agent_registry", {})
        self.assertTrue(r["ok"])
        self.assertEqual([role["code"] for role in r["result"]["roles"]],
                         ["C00", "C01", "C02", "C03", "C04", "C05", "C06"])

    def test_run_tool_orchestration_roundtrip(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-orch-", dir=PRIVATE_BASE))
        try:
            d = run_landing("dispatch_work_packet", {
                "folder": str(work), "target_layer": "C01",
                "objective": "Produce first-pass ID direction from PRD visual fields.",
                "sections": ["s05_id_me_requirements"]})
            self.assertTrue(d["ok"])
            packet_id = d["result"]["packet_id"]
            self.assertEqual(d["result"]["target_role"], "industrial_design")

            b = run_landing("return_blocker", {
                "folder": str(work), "packet_id": packet_id, "severity": "decision",
                "summary": "Need primary face decision.",
                "question_for_user": "Which face is primary?",
                "affected_c00_fields": ["s05_id_me_requirements.primary_face"]})
            self.assertTrue(b["ok"])
            blocker_id = b["result"]["blocker_id"]

            open_blk = run_landing("list_blockers", {"folder": str(work), "unresolved_only": True})
            self.assertEqual(len(open_blk["result"]["blockers"]), 1)

            g = run_landing("ingest_blocker", {
                "folder": str(work), "blocker_id": blocker_id, "resolved_state": "answered",
                "decision": "Top face is primary."})
            self.assertTrue(g["ok"])
            self.assertTrue(g["result"]["resolved"])

            closed = run_landing("list_blockers", {"folder": str(work), "unresolved_only": True})
            self.assertEqual(closed["result"]["blockers"], [])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_dispatch_to_c00_fails(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-orch2-", dir=PRIVATE_BASE))
        try:
            r = run_landing("dispatch_work_packet",
                            {"folder": str(work), "target_layer": "C00", "objective": "x"})
            self.assertFalse(r["ok"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_run_tool_c00_orchestration(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-mcp-loop-", dir=PRIVATE_BASE))
        try:
            # Empty -> the loop tells you to scaffold C00 first.
            tick = run_landing("c00_orchestration_tick", {"folder": str(work)})
            self.assertTrue(tick["ok"])
            self.assertEqual(tick["result"]["kind"], "scaffold_c00")
            # Status board is read-only and well-formed.
            run_landing("c00_scaffold_prd", {"out_dir": str(work), "project_name": "X"})
            board = run_landing("c00_orchestration_status", {"folder": str(work)})
            self.assertTrue(board["ok"])
            self.assertEqual([l["code"] for l in board["result"]["layers"]],
                             ["C01", "C02", "C03", "C04", "C05", "C06"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_tool_groups_assigned(self):
        groups = {t["name"]: t["group"] for t in self.server.TOOLS}
        # C02 CAD export tools belong to the mechanical worker group
        # (c02_generate_openscad landed — pure text generation runs on the host).
        for t in ("bodesign_c02_export_step", "bodesign_c02_export_stl", "bodesign_c02_export_skp"):
            self.assertEqual(groups[t], "me")
        # Electronics-engineering tools (KiCad/ngspice) belong to the ee worker group.
        for t in ("bodesign_compose_schematic", "bodesign_emit_layout", "bodesign_simulate",
                  "bodesign_analyze_emc", "bodesign_export_bom", "bodesign_render_companion",
                  "bodesign_widen_bus_tracks", "bodesign_length_match_bus"):
            self.assertEqual(groups[t], "ee")
        # emit_doc stays core: there is NO bodesign-docs worker — docx/pdf rendering is
        # delegated to docxmcp (which already ships LibreOffice). emit_doc gates gracefully.
        self.assertEqual(groups["bodesign_emit_doc"], "core")
        # Remaining core tools stay core.
        for t in ("bodesign_stage_dir", "bodesign_mcp_call", "bodesign_spice_model_card",
                  "bodesign_vault_query", "bodesign_render_gerber_preview"):
            self.assertEqual(groups[t], "core")

    # DD-3 borderline: the render-only path landed in gate.py, but the container
    # KEEPS this registered tool for the assemble path (docxmcp bridge).
    BORDERLINE_KEPT = {"c00_emit_prd_docx"}

    def test_landed_tools_removed_from_registry(self):
        """6.1/AC-7: no landed verb is still registered as an MCP tool — except the
        DD-3 borderline keeps, which stay registered for their container-only path."""
        names = {t["name"] for t in self.server.TOOLS}
        for verb in self.server.LANDED_VERBS:
            if verb in self.BORDERLINE_KEPT:
                self.assertIn(f"bodesign_{verb}", names,
                              f"{verb}: borderline keep must stay registered (assemble path)")
                continue
            self.assertNotIn(f"bodesign_{verb}", names)

    def test_landed_verbs_mirror_gate_registry(self):
        """Drift guard: server.LANDED_VERBS is 1:1 with gate.py's VERBS table."""
        self.assertEqual(set(self.server.LANDED_VERBS), set(GATE.VERBS))

    def test_removed_tool_call_returns_typed_tool_landed(self):
        """R3/AC-7: EVERY gate.py verb, called as its former MCP tool name, returns
        the typed TOOL_LANDED envelope (data-schema.json ToolLandedError) with the
        verb inside landing_command — never an anonymous unknown-tool error.
        Borderline keeps (still registered) dispatch normally instead."""
        for verb in sorted(GATE.VERBS):
            if verb in self.BORDERLINE_KEPT:
                self.assertIn(f"bodesign_{verb}", self.server.TOOLS_BY_NAME)
                continue
            r = self.server.run_tool(f"bodesign_{verb}", {"folder": "/x"})
            self.assertFalse(r["ok"], f"{verb}: expected ok=false")
            self.assertEqual(r["error"], "TOOL_LANDED", f"{verb}: wrong error code")
            self.assertIn(f"gate.py {verb} --repo", r["landing_command"],
                          f"{verb}: landing_command must carry the verb")

    # The converged registry, by NAME (6.4/AC-7). Historically this test asserted only
    # `len(TOOLS) == 55`, which was BOTH stale and blunt (BR_20260729 §J side-finding):
    #   * stale — it shipped red at 8fd59b0 (56 != 55) and nobody noticed, because the
    #     full host suite was never run; a later addition took it to 57, still red. A
    #     permanently-red assertion carries no signal, exactly like a permanently-green one.
    #   * blunt — a count cannot see a RENAME or a swap (drop one tool, add another and it
    #     stays green), so the check was weakest against the change most likely to break
    #     a client: a tool the caller names disappearing.
    # An explicit name set makes every add / remove / rename fail loudly and self-describe.
    EXPECTED_TOOLS = {
        "bodesign_analyze_emc", "bodesign_analyze_thermal", "bodesign_analyzer_selfcheck",
        "bodesign_apply_pad_intrinsic_overrides", "bodesign_ato_build", "bodesign_autoroute",
        "bodesign_autoroute_preflight", "bodesign_bga_escape_capacity",
        "bodesign_c00_emit_prd_docx", "bodesign_c00_prd_gate", "bodesign_c01_generate_concept_image",
        "bodesign_c02_export_skp", "bodesign_c02_export_step", "bodesign_c02_export_stl",
        "bodesign_c02_project_svg", "bodesign_c02_render_enclosure", "bodesign_c03_presentation_gate",
        "bodesign_c02_voice_to_design", "bodesign_c04_placement_geometry_gate", "bodesign_c04_board_manifest", "bodesign_c04_gerber_gate", "bodesign_c04_routing_gate", "bodesign_c02_mesh_gate", "bodesign_c02_chain_check", "bodesign_c02_view_coverage", "bodesign_c01_scene_gate", "bodesign_cache_close", "bodesign_cache_export",
        "bodesign_cache_provision", "bodesign_check_c03", "bodesign_clean_micro_stubs",
        "bodesign_component_fetch", "bodesign_component_search", "bodesign_compose_schematic",
        "bodesign_dwg_to_dxf", "bodesign_dxf_to_dwg", "bodesign_emit_doc", "bodesign_emit_fab",
        "bodesign_emit_layout", "bodesign_emit_symbol", "bodesign_export_bom",
        "bodesign_export_netlist", "bodesign_init", "bodesign_kb_get", "bodesign_kb_query",
        "bodesign_layout_drc_gate", "bodesign_length_match_bus", "bodesign_mcp_call",
        "bodesign_placement_preflight", "bodesign_pour_planes", "bodesign_prd_bom_crosscheck",
        "bodesign_render_board_model", "bodesign_render_companion",
        "bodesign_render_gerber_preview", "bodesign_route_net2pcb", "bodesign_si_check",
        "bodesign_simulate", "bodesign_spice_model_card", "bodesign_stage_dir",
        "bodesign_vault_diagnostics", "bodesign_vault_ingest", "bodesign_vault_query",
        "bodesign_vault_queue", "bodesign_vault_spec_check", "bodesign_via_in_pad",
        "bodesign_widen_bus_tracks", "bodesign_workspace_inspect",
    }

    def test_converged_registry_tool_count(self):
        """The registry matches EXPECTED_TOOLS exactly — no additions, removals or renames.

        assertSetEqual names the delta in both directions, so a failure says WHICH tool
        appeared or vanished instead of leaving a reader to diff two integers.
        """
        names = {t["name"] for t in self.server.TOOLS}
        self.assertSetEqual(names, self.EXPECTED_TOOLS)
        # No duplicate registrations: TOOLS_BY_NAME would silently collapse them, so a
        # double-registered tool is invisible to the set comparison above.
        self.assertEqual(len(self.server.TOOLS), len(names),
                         "duplicate tool name in TOOLS")
        # borderline / infrastructure keeps (design.md DD-3):
        for kept in ("bodesign_c00_emit_prd_docx", "bodesign_c02_voice_to_design",
                     "bodesign_spice_model_card", "bodesign_stage_dir", "bodesign_mcp_call",
                     "bodesign_cache_provision", "bodesign_cache_export", "bodesign_cache_close"):
            self.assertIn(kept, names)

    def test_landed_impedance_solve_is_structured(self):
        result = run_landing("impedance_solve", {
            "stackup": {"dielectric_height_mm": 0.18, "er": 4.2},
            "targets": {"se50": {"impedance_ohm": 50}},
        })

        self.assertTrue(result["ok"])
        self.assertIn("se50", result["result"]["classes"])
        self.assertIn("width_mm", result["result"]["classes"]["se50"])
        self.assertIn("actual_ohm", result["result"]["classes"]["se50"])
        self.assertIn("ps_per_mm", result["result"]["classes"]["se50"])

        missing = run_landing("impedance_solve", {"stackup": {"er": 4.2}, "targets": {"se50": 50}})
        self.assertFalse(missing["ok"])
        self.assertIn("dielectric_height_mm", missing["error"])

    def test_widen_bus_tracks_schema_and_core_routing(self):
        spec = self.server.TOOLS_BY_NAME["bodesign_widen_bus_tracks"]

        self.assertEqual(spec["group"], "ee")
        self.assertEqual(spec["schema"]["required"], ["in_path", "out_path", "nets", "target_mm"])
        self.assertIn("clearance_mm", spec["schema"]["properties"])
        self.assertIn("in_path", self.server.PATH_ARG_KEYS)
        self.assertIn("out_path", self.server.PATH_ARG_KEYS)
        self.assertIn("report_path", self.server.PATH_ARG_KEYS)

    def test_length_match_bus_schema_and_core_routing(self):
        spec = self.server.TOOLS_BY_NAME["bodesign_length_match_bus"]

        self.assertEqual(spec["group"], "ee")
        self.assertEqual(spec["schema"]["required"], ["in_path", "out_path", "nets", "budget_ps", "ps_per_mm"])
        self.assertIn("report_path", spec["schema"]["properties"])
        self.assertIn("clearance_mm", spec["schema"]["properties"])
        self.assertIn("in_path", self.server.PATH_ARG_KEYS)
        self.assertIn("out_path", self.server.PATH_ARG_KEYS)

    def test_route_net2pcb_exposes_connector_pinmap_override(self):
        # H1: the connector pin map must be a reachable caller input (no silent J1 gating).
        spec = self.server.TOOLS_BY_NAME["bodesign_route_net2pcb"]
        self.assertEqual(spec["group"], "ee")
        self.assertIn("connectors", spec["schema"]["properties"])
        self.assertIn("applied_pinmaps", spec["description"])
        self.assertIn("unmapped_connectors", spec["description"])

    def test_si_check_exposes_driver_load_and_threshold_overrides(self):
        # H2: rdrv/cload/edge/thresholds must be reachable inputs, not hidden defaults.
        spec = self.server.TOOLS_BY_NAME["bodesign_si_check"]
        self.assertEqual(spec["group"], "ee")
        for k in ("rdrv", "cload", "edge_ns", "overshoot_pass_pct", "overshoot_warn_pct"):
            self.assertIn(k, spec["schema"]["properties"])

    def test_render_gerber_preview_schema_and_core_unavailable_mode(self):
        spec = self.server.TOOLS_BY_NAME["bodesign_render_gerber_preview"]

        self.assertEqual(spec["group"], "core")
        self.assertEqual(spec["schema"]["required"], ["gerber_dir", "out_path", "mode"])
        self.assertIn("drill_dir", spec["schema"]["properties"])
        self.assertIn("layer_glob", spec["schema"]["properties"])
        self.assertIn("gerber_dir", self.server.PATH_ARG_KEYS)
        self.assertIn("drill_dir", self.server.PATH_ARG_KEYS)

        result = self.server.run_tool("bodesign_render_gerber_preview", {
            "gerber_dir": str(Path(__file__).resolve().parents[1]),
            "out_path": str(Path(__file__).resolve().parents[1] / ".artifacts" / "tests" / "mcp-stack.png"),
            "mode": "stack",
        })
        self.assertTrue(result["ok"])
        self.assertEqual("render-unavailable", result["result"]["status"])
        self.assertEqual("unsupported-preview-mode", result["result"]["skipped"][0]["reason"])

    def test_ee_tool_routes_to_ee_worker(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"core"}
            with patch.dict(os.environ, {"BODESIGN_EE_WORKER_URL": "http://bodesign-ee:8077"}):
                decision, target = self.server._route_tool("bodesign_compose_schematic")
                self.assertEqual((decision, target), ("forward", "http://bodesign-ee:8077"))
                decision, target = self.server._route_tool("bodesign_widen_bus_tracks")
                self.assertEqual((decision, target), ("forward", "http://bodesign-ee:8077"))
                decision, target = self.server._route_tool("bodesign_length_match_bus")
                self.assertEqual((decision, target), ("forward", "http://bodesign-ee:8077"))
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BODESIGN_EE_WORKER_URL", None)
                for name in ("bodesign_compose_schematic", "bodesign_widen_bus_tracks", "bodesign_length_match_bus"):
                    decision, target = self.server._route_tool(name)
                    self.assertEqual((decision, target), ("unavailable", "ee"))
        finally:
            self.server.SERVED_GROUPS = saved

    def test_monolith_runs_everything_local(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"all"}
            for name in ("bodesign_c02_export_step", "bodesign_stage_dir"):
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
                self.assertEqual(self.server._route_tool("bodesign_stage_dir")[0], "local")
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

    @unittest.skipUnless(importlib.util.find_spec("httpx"),
                         "httpx not installed (worker-forwarding is worker-only; "
                         "monolith/unittest env legitimately lacks it per AGENTS.md §4)")
    def test_configured_worker_unreachable_reports_starting(self):
        # Worker URL set but nothing listening -> retryable "starting", NOT permanent unavailable.
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"core"}
            with patch.dict(os.environ, {"BODESIGN_ME_WORKER_URL": "http://127.0.0.1:1"}):
                r = self.server.run_tool("bodesign_c02_export_step", {"out_dir": "/x"})
                self.assertFalse(r["ok"])
                self.assertTrue(r["worker_starting"])
                self.assertNotIn("worker_unavailable", r)
                self.assertEqual(r["group"], "me")
                self.assertGreater(r["retry_after_seconds"], 0)
        finally:
            self.server.SERVED_GROUPS = saved

    def test_unconfigured_worker_is_unavailable_not_starting(self):
        saved = self.server.SERVED_GROUPS
        try:
            self.server.SERVED_GROUPS = {"core"}
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BODESIGN_ME_WORKER_URL", None)
                r = self.server.run_tool("bodesign_c02_export_step", {"out_dir": "/x"})
                self.assertTrue(r["worker_unavailable"])
                self.assertNotIn("worker_starting", r)  # deliberate slim deployment: do not retry
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
                self.assertEqual(self.server._route_tool("bodesign_stage_dir")[0], "unavailable")
        finally:
            self.server.SERVED_GROUPS = saved

    def test_handler_error_is_captured(self):
        # missing required "symbol_name" -> KeyError captured as data, not raised
        r = self.server.run_tool("bodesign_emit_symbol", {})
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

    def test_socket_level_list_and_call_smoke(self):
        """T10: real MCP JSON-RPC roundtrip through the actual server process.

        Spawns ``server.py --transport stdio`` as a subprocess and drives it with
        the official MCP client (initialize -> list_tools -> call_tool). Proves the
        new C04 tools are reachable through the real protocol path, that the pure
        core tool returns a structured result, and that an EE-group board tool fails
        fast (never fabricates success) when no worker can run pcbnew here. Skipped
        unless the MCP SDK is installed (host interpreter has no socket transport).
        """
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("mcp SDK not installed in this interpreter")
        import asyncio
        import sys
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        repo = Path(self.server.__file__).resolve().parents[2]
        pkgs = ["services/mcp", "packages/workflow-core", "packages/eda-bridge",
                "packages/gerber-core", "packages/reverse-core", "packages/me-bridge",
                "packages/shared"]
        expected_tools = {"bodesign_widen_bus_tracks", "bodesign_length_match_bus",
                          "bodesign_render_gerber_preview"}

        async def roundtrip():
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(str(repo / p) for p in pkgs)
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(repo / "services/mcp/server.py"), "--transport", "stdio"],
                env=env,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual("bodesign", init.serverInfo.name)

                    listed = await session.list_tools()
                    names = {t.name for t in listed.tools}
                    self.assertTrue(expected_tools <= names,
                                    f"C04 tools missing from list_tools: {expected_tools - names}")
                    # landed verbs are NOT listed (v0.2.0 surface convergence)
                    self.assertNotIn("bodesign_impedance_solve", names)
                    self.assertNotIn("bodesign_c00_readiness", names)

                    # a landed name called through the real protocol → typed TOOL_LANDED
                    res = await session.call_tool("bodesign_impedance_solve", {
                        "stackup": {"dielectric_height_mm": 0.1, "er": 4.2},
                        "targets": [{"name": "se50", "impedance_ohm": 50, "kind": "single"}],
                    })
                    env_payload = json.loads(res.content[0].text)
                    self.assertFalse(env_payload.get("ok"), env_payload)
                    self.assertEqual("TOOL_LANDED", env_payload["error"])
                    self.assertIn("gate.py impedance_solve", env_payload["landing_command"])

                    res2 = await session.call_tool("bodesign_widen_bus_tracks", {
                        "in_path": "/nonexistent/none.kicad_pcb",
                        "out_path": str(PRIVATE_BASE / "none.out.kicad_pcb"),
                        "nets": ["D0"], "target_mm": 0.2,
                    })
                    env2 = json.loads(res2.content[0].text)
                    self.assertFalse(env2.get("ok"),
                                     f"EE board tool must not fabricate success: {env2}")

        asyncio.run(roundtrip())


if __name__ == "__main__":
    unittest.main()
