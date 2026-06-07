import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    assess_c04_layout_readiness,
    emit_c04_layout_package,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_C01 = {
    "schema": "bodesign.c01.interface_constraints.v1",
    "exposed_components": [{"ref": "U1", "kind": "display"}],
    "downstream_targets": {"C04": ["preferred component faces", "placement keepouts"]},
}
_C03 = {
    "constraints": {
        "component_heights": [{"ref": "U1", "height_mm": 1.2}],
        "connector_openings": [{"ref": "J1", "type": "usb-c"}],
        "heat_sources": [{"ref": "U2", "watts": 1.5}],
        "antenna_keepouts": [{"area": "top-left"}],
        "battery_envelope": {"type": "18650"},
        "esd_emc_notes": ["protect USB lines"],
    }
}


class C04LayoutTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c04-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_emit_merges_c01_c03_and_leaves_board_pending(self):
        res = emit_c04_layout_package(self.work, c01=_C01, c03=_C03)
        self.assertIn("C04-Layout/Layout_Constraints.json", res.files)
        c = res.constraints
        self.assertEqual(c["schema"], "bodesign.c04.layout_constraints.v1")
        self.assertTrue(c["component_heights"])
        self.assertTrue(c["connector_edge_openings"])
        self.assertEqual(c["placement_intent"], ["preferred component faces", "placement keepouts"])
        # Layout-owned items stay pending and unfabricated.
        pending_items = {p["item"] for p in res.pending}
        self.assertIn("board_outline", pending_items)
        self.assertIn("placement_coordinates", pending_items)
        # No board/Gerber/approval claims.
        rd = res.readiness.to_dict()
        self.assertFalse(rd["board_ready"])
        self.assertFalse(rd["gerber_ready"])
        self.assertFalse(rd["layout_approval"])
        self.assertEqual(rd["status"], "layout_constraints_drafted")

    def test_readiness_without_upstream_is_blocked_not_fabricated(self):
        res = emit_c04_layout_package(self.work, c01=None, c03=None)
        self.assertEqual(res.readiness.status, "blocked")
        self.assertEqual(res.readiness.present_groups, [])

    def test_auto_loads_upstream_from_folder(self):
        # Drop the C01 + C03 exports where the emitter auto-discovers them.
        (self.work / "C01-ID").mkdir(parents=True, exist_ok=True)
        (self.work / "C01-ID" / "Interface_Constraints.json").write_text(json.dumps(_C01), encoding="utf-8")
        (self.work / "C03-EE").mkdir(parents=True, exist_ok=True)
        (self.work / "C03-EE" / "Mechanical_Constraint_Export.json").write_text(json.dumps(_C03), encoding="utf-8")
        res = emit_c04_layout_package(self.work)
        self.assertTrue(res.constraints["source"]["from_c01"])
        self.assertTrue(res.constraints["source"]["from_c03"])
        self.assertIn("component_heights", res.readiness.present_groups)

    def test_readiness_missing_before_emit(self):
        rd = assess_c04_layout_readiness(self.work)
        self.assertEqual(rd.status, "missing")
        self.assertFalse(rd.constraints_present)


if __name__ == "__main__":
    unittest.main()
