import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bodesign_workflow_core import assess_c02_constraint_readiness, emit_c02_enclosure_package, export_c02_skp, export_c02_step, export_c02_stl, generate_c02_openscad


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class C02MePackageTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c02-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_missing_constraints_block_cad_source(self):
        readiness = assess_c02_constraint_readiness({})

        self.assertEqual("brief_ready", readiness.readiness_level)
        self.assertFalse(readiness.can_generate_cad_source)
        self.assertFalse(readiness.can_create_printable_draft)
        self.assertIn("Board outline", readiness.next_step)
        statuses = {item.key: item.status for item in readiness.items}
        self.assertEqual("missing", statuses["board_outline"])
        self.assertEqual("missing", statuses["component_heights"])

    def test_board_and_heights_allow_source_not_printable_output(self):
        readiness = assess_c02_constraint_readiness({
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8.5}],
        })

        self.assertTrue(readiness.can_generate_cad_source)
        self.assertFalse(readiness.can_place_openings)
        self.assertFalse(readiness.can_create_printable_draft)
        self.assertEqual("brief_ready", readiness.readiness_level)
        self.assertIn("connector", readiness.next_step.lower())

    def test_useful_constraints_become_source_ready(self):
        readiness = assess_c02_constraint_readiness({
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "U1", "height_mm": 4.2}],
            "mounting_holes": [{"x_mm": 5, "y_mm": 5, "diameter_mm": 2.5}],
            "connector_openings": [{"name": "USB-C", "edge": "right"}],
            "heat_sources": [{"ref": "U1", "watts": 1.5}],
            "antenna_keepouts": [{"area": "top-right"}],
        })

        self.assertEqual("source_ready", readiness.readiness_level)
        self.assertTrue(readiness.can_generate_cad_source)
        self.assertTrue(readiness.can_place_openings)
        self.assertFalse(readiness.can_create_printable_draft)

    def test_reads_constraints_from_c02_folder(self):
        constraints_dir = self.work / "C02-ME"
        constraints_dir.mkdir(parents=True)
        (constraints_dir / "Mechanical_Constraints.json").write_text(json.dumps({
            "board_outline": {"width_mm": 40, "height_mm": 20},
            "component_heights": [{"ref": "J1", "height_mm": 6}],
        }), encoding="utf-8")

        readiness = assess_c02_constraint_readiness(folder=self.work)

        self.assertTrue(readiness.can_generate_cad_source)

    def test_emit_enclosure_package_preserves_pending_constraints(self):
        result = emit_c02_enclosure_package(
            self.work,
            constraints={"component_heights": [{"ref": "J1", "height_mm": 8}]},
            project_summary="Desk sensor prototype",
            prototype_intent="fit-check enclosure",
            printer_profile={"material": "PLA", "nozzle_mm": 0.4},
        )

        self.assertEqual("package_emitted", result.status)
        self.assertFalse(result.to_dict()["source_ready"])
        self.assertFalse(result.to_dict()["printable_draft_ready"])
        self.assertFalse(result.to_dict()["me_approved"])
        expected = {
            "C02-ME/Mechanical_Constraints.json",
            "C02-ME/Mechanical_Assumptions.md",
            "C02-ME/Assembly_Notes.md",
            "C02-ME/Print_Settings.md",
            "C02-ME/Vendor_Handoff.md",
            "C02-ME/SketchUp_Import_Guide.md",
        }
        self.assertEqual(expected, set(result.files))
        constraints = json.loads((self.work / "C02-ME" / "Mechanical_Constraints.json").read_text(encoding="utf-8"))
        pending = constraints["constraint_status"]["pending"]
        self.assertTrue(any(item["key"] == "board_outline" and item["status"] == "engineering_pending" for item in pending))
        self.assertFalse((self.work / "C02-ME" / "Enclosure.stl").exists())
        self.assertIn("skp_export_unavailable", (self.work / "C02-ME" / "SketchUp_Import_Guide.md").read_text(encoding="utf-8"))

    def test_generate_openscad_requires_board_outline_and_heights(self):
        result = generate_c02_openscad(self.work, constraints={"component_heights": [{"ref": "J1", "height_mm": 8}]})

        self.assertEqual("source_blocked", result.status)
        self.assertIsNone(result.source_path)
        self.assertFalse((self.work / "C02-ME" / "Enclosure.scad").exists())

    def test_generate_openscad_writes_source_from_explicit_constraints(self):
        emit_c02_enclosure_package(self.work, constraints={
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8}],
            "mounting_holes": [{"x_mm": 5, "y_mm": 5, "diameter_mm": 2.5}],
            "connector_openings": [{"name": "USB-C", "edge": "right"}],
        })

        missing_dimensions = generate_c02_openscad(self.work)
        self.assertEqual("source_blocked", missing_dimensions.status)
        self.assertIn("must be explicit", missing_dimensions.message)

        result = generate_c02_openscad(self.work, wall_thickness_mm=2.0, clearance_mm=1.0, lid_clearance_mm=0.4)

        self.assertEqual("source_generated", result.status)
        self.assertTrue(result.to_dict()["source_ready"])
        self.assertFalse(result.to_dict()["printable_draft_ready"])
        self.assertFalse(result.to_dict()["me_approved"])
        source = (self.work / "C02-ME" / "Enclosure.scad").read_text(encoding="utf-8")
        self.assertIn("board_width = 80", source)
        self.assertIn("max_component_height = 8", source)
        self.assertIn("USB-C", source)

    def test_export_stl_reports_unavailable_without_openscad(self):
        emit_c02_enclosure_package(self.work, constraints={
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8}],
        })
        generate_c02_openscad(self.work, wall_thickness_mm=2.0, clearance_mm=1.0, lid_clearance_mm=0.4)

        with patch("bodesign_workflow_core.c02_me_package.shutil.which", return_value=None):
            result = export_c02_stl(self.work, openscad_bin=None)

        self.assertEqual("export_unavailable", result.status)
        self.assertFalse((self.work / "C02-ME" / "Enclosure.stl").exists())
        self.assertFalse(result.to_dict()["printable_draft_ready"])

    def test_export_skp_reports_unavailable_and_updates_import_guide(self):
        emit_c02_enclosure_package(self.work, constraints={
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8}],
        })
        generate_c02_openscad(self.work, wall_thickness_mm=2.0, clearance_mm=1.0, lid_clearance_mm=0.4)

        result = export_c02_skp(self.work)

        self.assertEqual("skp_export_unavailable", result.status)
        self.assertIsNone(result.skp_path)
        self.assertEqual("C02-ME/Enclosure.scad", result.source_path)
        self.assertFalse((self.work / "C02-ME" / "Enclosure.skp").exists())
        guide = (self.work / "C02-ME" / "SketchUp_Import_Guide.md").read_text(encoding="utf-8")
        self.assertIn("No `C02-ME/Enclosure.skp` file was generated", guide)
        self.assertIn("C02-ME/Enclosure.scad", guide)
        self.assertFalse(result.to_dict()["me_approved"])

    def test_export_step_reports_unavailable_and_writes_handoff(self):
        emit_c02_enclosure_package(self.work, constraints={
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8}],
        })
        generate_c02_openscad(self.work, wall_thickness_mm=2.0, clearance_mm=1.0, lid_clearance_mm=0.4)

        result = export_c02_step(self.work)

        self.assertEqual("step_export_unavailable", result.status)
        self.assertIsNone(result.step_path)
        self.assertEqual("C02-ME/Enclosure.scad", result.source_path)
        self.assertFalse((self.work / "C02-ME" / "Enclosure.step").exists())
        handoff = (self.work / "C02-ME" / "STEP_Draft_Handoff.md").read_text(encoding="utf-8")
        self.assertIn("No `C02-ME/Enclosure.step` file was generated", handoff)
        self.assertIn("FreeCAD", handoff)
        self.assertIn("CadQuery", handoff)
        self.assertFalse(result.to_dict()["me_approved"])


if __name__ == "__main__":
    unittest.main()
