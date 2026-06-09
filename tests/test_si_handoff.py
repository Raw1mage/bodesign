"""C04 Tier-3 SI constraint handoff emits a complete, honest pro-EDA package."""
import json, os, shutil, tempfile, unittest
from pathlib import Path

from bodesign_workflow_core import (
    NetClassConstraint, StackupSpec, emit_si_constraint_export,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class SiHandoffTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.out = Path(tempfile.mkdtemp(prefix="bodesign-si-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_emits_three_files_and_tbd_for_missing(self):
        ncs = [
            NetClassConstraint(name="DDR_DQ", nets=["DQ0", "DQ1"], kind="single_ended",
                               target_impedance_ohm=40, impedance_tol_pct=10,
                               length_match_group="DDR_BYTE0", length_match_tol_mm=0.1,
                               topology="fly_by", termination="ODT"),
            NetClassConstraint(name="USB_HS", nets=["DP", "DM"], kind="differential",
                               target_impedance_ohm=90, impedance_tol_pct=10),  # diff_skew_ps missing → TBD
        ]
        su = StackupSpec(layers=12, hdi_type="any-layer", finest_bga_pitch_mm=0.4, via_in_pad=True,
                         layer_map=[{"layer": 1, "type": "signal", "ref_plane": 2}], notes="iPhone-class")
        r = emit_si_constraint_export(
            project_name="phoneX", tier=3, stackup=su, net_classes=ncs, out_dir=self.out,
            placement_notes=["RF chip ≤30mm from antenna"], keepouts=["antenna zone all layers"],
        )
        # three files exist
        for p in (r.json_path, r.csv_path, r.md_path):
            self.assertTrue(Path(p).exists())
        # JSON is the source of truth, schema + tier + reason present
        payload = json.loads(Path(r.json_path).read_text())
        self.assertEqual(payload["schema"], "bodesign.si_constraints.v1")
        self.assertEqual(payload["feasibility_tier"], 3)
        self.assertEqual(len(payload["net_classes"]), 2)
        # honesty: missing diff skew is flagged TBD, not invented
        self.assertIn("USB_HS.diff_skew_ps", r.tbd)
        self.assertIn("USB_HS.diff_skew_ps", payload["tbd"])
        # CSV header + a data row
        csv_text = Path(r.csv_path).read_text()
        self.assertIn("net_class", csv_text.splitlines()[0])
        self.assertIn("DDR_DQ", csv_text)
        # MD maps to the EDA tools
        md = Path(r.md_path).read_text()
        self.assertIn("Allegro", md)
        self.assertIn("Xpedition", md)
        self.assertIn("TBD", md)

    def test_no_fabrication_when_clean(self):
        ncs = [NetClassConstraint(name="RF_50", kind="single_ended", target_impedance_ohm=50,
                                  impedance_tol_pct=10)]
        su = StackupSpec(layers=4, layer_map=[{"layer": 1}])
        r = emit_si_constraint_export(project_name="p", tier=2, stackup=su, net_classes=ncs, out_dir=self.out)
        self.assertEqual(r.tbd, [])  # nothing missing → no TBD


if __name__ == "__main__":
    unittest.main()
