import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import export_c03_mechanical_constraints


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class C03MechanicalConstraintTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c03-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_exports_explicit_circuit_constraints_without_mechanical_approval(self):
        result = export_c03_mechanical_constraints(self.work, {
            "components": [
                {"ref": "J1", "value": "USB-C", "role": "connector", "height_mm": 3.2, "edge": "right", "external": True},
                {"ref": "U1", "value": "AI MCU", "height_mm": 1.4, "thermal_watts": 1.8},
                {"ref": "ANT1", "role": "antenna", "height_mm": 1.0, "preferred_area": "top-right"},
            ],
            "battery_envelope": {"width_mm": 30, "height_mm": 40, "depth_mm": 6},
            "esd_emc_notes": ["USB-C shield needs ESD/mechanical grounding review."],
        })

        self.assertEqual("mechanical_constraints_exported", result.status)
        self.assertFalse(result.to_dict()["mechanical_approval"])
        self.assertTrue((self.work / "C03-EE" / "Mechanical_Constraint_Export.json").exists())
        constraints = result.constraints
        self.assertEqual(3, len(constraints["component_heights"]))
        self.assertEqual("J1", constraints["connector_openings"][0]["ref"])
        self.assertEqual("U1", constraints["heat_sources"][0]["ref"])
        self.assertEqual("ANT1", constraints["antenna_keepouts"][0]["ref"])
        self.assertNotIn("board_outline", constraints)

    def test_records_pending_missing_c03_mechanical_data(self):
        result = export_c03_mechanical_constraints(self.work, {"components": [{"ref": "U1", "value": "MCU"}]})

        pending_keys = {item["key"] for item in result.pending}
        self.assertIn("component_heights", pending_keys)
        self.assertIn("component_height_refs", pending_keys)
        self.assertIn("connector_openings", pending_keys)
        payload = json.loads((self.work / "C03-EE" / "Mechanical_Constraint_Export.json").read_text(encoding="utf-8"))
        self.assertFalse(payload["approval"]["mechanical_approval"])


if __name__ == "__main__":
    unittest.main()
