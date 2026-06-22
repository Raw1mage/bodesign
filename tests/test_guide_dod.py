"""GUIDE Definition-of-Done enforcement tests
(quality_readiness-enforces-guide-definition-of-done).

Covers: placeholder/fake-complete precision, the manifest checker (present /
missing / honest-status / conditional / all_of), c00 readiness fake-complete +
conditional-RF, per-stage manifest completeness, and the package roll-up.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import guide_dod
from bodesign_workflow_core import assess_c00_prd_readiness, assess_package_readiness

PRIVATE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class PlaceholderPrecisionTests(unittest.TestCase):
    def test_placeholders_flagged(self):
        for v in ["TBC", "TBD", "TODO", "N/A", "to be confirmed", "待補充", "未定", "", "   ", None, {}, []]:
            self.assertTrue(guide_dod.is_placeholder_value(v), f"{v!r} should be placeholder")

    def test_legit_values_not_flagged(self):
        # The exact false-positive corpus that must NOT trip (bare 待 in 待機/期待, etc.)
        for v in ["STM32N657L0 (4.2MB SRAM, 600 Gops Neural-ART)", "3.3V", "802.11 b/g/n",
                  "期待機制,待機電流 5uA", "USB-C PD", "CYW43439 Wi-Fi/BLE", {"rail": "VBAT"}, 5]:
            self.assertFalse(guide_dod.is_placeholder_value(v), f"{v!r} must NOT be a placeholder")

    def test_real_tbc_inside_long_value(self):
        self.assertTrue(guide_dod.is_placeholder_value(
            "STM32N657, octal NOR/PSRAM, microSD. MPNs/stock TBC (no DigiKey API)."))


class CheckerTests(unittest.TestCase):
    def setUp(self):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        self.t = Path(tempfile.mkdtemp(prefix="dod-", dir=PRIVATE))

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_empty_stage_all_missing_blocking(self):
        r = guide_dod.assess_guide_dod(self.t, "c05")
        self.assertFalse(r["dod_ok"])
        self.assertEqual(len(r["missing_blocking"]), 6)

    def _mk(self, *rels):
        for rel in rels:
            p = self.t / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")

    def test_complete_stage_green(self):
        # Manifests are project-root-relative: files live under <root>/C05-FW/.
        self._mk(*[f"C05-FW/{fn}" for fn in ["Functional_Spec.md", "Module_Architecture.md",
                   "State_Machine.md", "Task_Breakdown.md", "Pin_Map_Bridge.json", "Firmware_Build_Notes.md"]])
        r = guide_dod.assess_guide_dod(self.t, "c05")
        self.assertTrue(r["dod_ok"])
        self.assertEqual(r["missing_blocking"], [])

    def test_honest_status_override_not_blocking(self):
        self._mk(*[f"C02-ME/{fn}" for fn in ["Mechanical_Constraints.json", "Mechanical_Assumptions.md",
                   "Enclosure.scad", "Assembly_Notes.md", "Print_Settings.md", "Vendor_Handoff.md",
                   "SketchUp_Import_Guide.md"]])
        (self.t / "dod_status.json").write_text(json.dumps(
            {"enclosure_export": {"status": "not-run", "reason": "no OpenSCAD toolchain"}}))
        r = guide_dod.assess_guide_dod(self.t, "c02", conditions={"toolchain": True})
        statuses = {d["id"]: d["status"] for d in r["deliverables"]}
        self.assertEqual(statuses["enclosure_export"], "honest-status")
        self.assertTrue(r["dod_ok"])

    def test_conditional_skipped_when_unknown(self):
        self._mk("C06-Verification/Verification_Summary.json", "C06-Verification/Test_Plan.md",
                 "C06-Verification/Bring_Up_Checklist.md", "C06-Verification/analysis/cross_verify.json")
        r = guide_dod.assess_guide_dod(self.t, "c06")
        statuses = {d["id"]: d["status"] for d in r["deliverables"]}
        self.assertEqual(statuses["evt_findings"], "n-a")
        self.assertTrue(r["dod_ok"])

    def test_all_of_requires_every_file(self):
        self._mk("C04-Layout/Layout_Constraints.json")
        statuses = {d["id"]: d["status"] for d in guide_dod.assess_guide_dod(self.t, "c04")["deliverables"]}
        self.assertEqual(statuses["layout_placement"], "missing")  # Placement_Constraints.md absent
        self._mk("C04-Layout/Placement_Constraints.md")
        statuses2 = {d["id"]: d["status"] for d in guide_dod.assess_guide_dod(self.t, "c04")["deliverables"]}
        self.assertEqual(statuses2["layout_placement"], "present")


class AllManifestsLoadTest(unittest.TestCase):
    def test_every_stage_manifest_loads_with_guide_rows(self):
        for stage in ["c00", "c01", "c02", "c03", "c04", "c05", "c06", "c07"]:
            m = guide_dod.load_manifest(stage)
            self.assertIsNotNone(m, f"{stage} manifest missing")
            self.assertTrue(m["deliverables"])
            for d in m["deliverables"]:
                self.assertIn("guide_row", d, f"{stage}/{d.get('id')} missing guide_row (DD-1 sync)")
                self.assertTrue(d.get("any_of") or d.get("all_of"), f"{stage}/{d.get('id')} has no paths")


class C00ReadinessDodTests(unittest.TestCase):
    def setUp(self):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        self.t = Path(tempfile.mkdtemp(prefix="dod-c00-", dir=PRIVATE))
        self.c00 = self.t / "C00-PRD"
        self.c00.mkdir()

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def _write_state(self, fields, include_rf=False):
        state = {
            "schema": "bodesign.c00.answer_state.v1", "project_name": "x", "include_rf": include_rf,
            "allowed_states": ["missing", "drafted", "answered", "external-needed", "blocked", "accepted-risk"],
            "documents": {"Project_Requirements.md": {"sections": [
                {"id": "s1", "title": "S1", "fields": fields}]}},
        }
        (self.c00 / "answer_state.json").write_text(json.dumps(state), encoding="utf-8")
        for fn in ["Project_Requirements.md", "C00_Handoff_Report.md"]:
            (self.c00 / fn).write_text("x")

    def test_fake_complete_field_blocks(self):
        self._write_state({
            "a": {"value": "real answer 3.3V", "state": "answered"},
            "b": {"value": "MPNs TBC", "state": "answered"},
        })
        r = assess_c00_prd_readiness(self.t).to_dict()
        self.assertIn("b", r["fake_complete_fields"])
        self.assertNotIn("a", r["fake_complete_fields"])
        self.assertFalse(r["dod_ok"])

    def test_radio_part_without_include_rf_blocks(self):
        self._write_state({
            "parts": {"value": "MCU + CYW43439 Wi-Fi/BLE radio", "state": "answered"},
        }, include_rf=False)
        r = assess_c00_prd_readiness(self.t).to_dict()
        self.assertFalse(r["dod_ok"])
        self.assertTrue(any("RF appendix required" in w for w in r["warnings"]))

    def test_clean_state_is_dod_ok(self):
        self._write_state({"a": {"value": "5V 2A USB-C", "state": "answered"}}, include_rf=False)
        r = assess_c00_prd_readiness(self.t).to_dict()
        self.assertTrue(r["dod_ok"], r.get("warnings"))


class PerStageBaseAgreementTests(unittest.TestCase):
    """Regression for issue_20260623_guide_compliance_wrong_base_false_missing: the
    bundled guide_compliance block must resolve deliverables against the SAME base as
    the main readiness block (project root + stage folder), so a compliant stage is
    NOT a false RED, and the two blocks AGREE."""

    def setUp(self):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        self.t = Path(tempfile.mkdtemp(prefix="dod-base-", dir=PRIVATE))

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_c05_present_files_not_false_red_and_blocks_agree(self):
        from bodesign_workflow_core import assess_c05_fw_readiness
        c05 = self.t / "C05-FW"
        c05.mkdir()
        for fn in ["Functional_Spec.md", "Module_Architecture.md", "State_Machine.md",
                   "Task_Breakdown.md", "Pin_Map_Bridge.json", "Firmware_Build_Notes.md"]:
            (c05 / fn).write_text("x")
        r = assess_c05_fw_readiness(self.t).to_dict()
        # guide_compliance must NOT report present files as missing (the false RED bug)
        self.assertTrue(r["guide_compliance"]["dod_ok"], r["guide_compliance"]["missing_blocking"])
        self.assertEqual(r["guide_compliance"]["missing_blocking"], [])
        self.assertTrue(r["dod_ok"])
        # ...and it must AGREE with the main block (which sees the files present)
        self.assertIn("Functional_Spec", r["present_sections"])
        self.assertIn("Pin_Map_Bridge", r["present_sections"])

    def test_package_rollup_uses_project_root(self):
        from bodesign_workflow_core import assess_package_readiness
        c05 = self.t / "C05-FW"
        c05.mkdir()
        for fn in ["Functional_Spec.md", "Module_Architecture.md", "State_Machine.md",
                   "Task_Breakdown.md", "Pin_Map_Bridge.json", "Firmware_Build_Notes.md"]:
            (c05 / fn).write_text("x")
        r = assess_package_readiness(self.t).to_dict()
        self.assertIn("c05", r["guide_compliance"])
        self.assertNotIn("c05", r["dod_missing"])  # c05 fully present -> not flagged


if __name__ == "__main__":
    unittest.main()
