import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import assess_c05_fw_readiness, scaffold_c05_fw_spec

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_SOFTWARE = {
    "functions": ["BLE telemetry", "step counting"],
    "modes": ["idle", "active", "charging"],
    "interactions": ["single button", "RGB LED status"],
}
_PIN_MAP = {"rows": [
    {"ref": "U1", "pin": "PA0", "net": "BTN", "is_mcu": True},
    {"ref": "U1", "pin": "PA1", "net": "LED_R", "is_mcu": True},
    {"ref": "J1", "pin": "1", "net": "VBUS", "is_mcu": False},
]}


class C05FwSpecTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c05-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_scaffold_writes_spec_docs_and_pin_bridge_no_code(self):
        res = scaffold_c05_fw_spec(self.work, software=_SOFTWARE, pin_map=_PIN_MAP)
        for rel in ("C05-FW/Functional_Spec.md", "C05-FW/Pin_Map_Bridge.json", "C05-FW/State_Machine.md"):
            self.assertIn(rel, res.files)
        # Bridges only the MCU pins.
        self.assertEqual(len(res.pin_bridge["signals"]), 2)
        self.assertEqual(res.pin_bridge["signals"][0]["responsibility"], "TBD by FW team (init/direction/driver/ISR).")
        rd = res.readiness.to_dict()
        self.assertFalse(rd["firmware_code"])
        self.assertTrue(rd["fw_team_owned"])
        self.assertEqual(rd["status"], "fw_spec_drafted")
        self.assertTrue(rd["functional_present"])
        self.assertTrue(rd["pin_bridge_present"])

    def test_functional_spec_embeds_prd_functions(self):
        scaffold_c05_fw_spec(self.work, software=_SOFTWARE, pin_map=_PIN_MAP)
        text = (self.work / "C05-FW" / "Functional_Spec.md").read_text()
        self.assertIn("BLE telemetry", text)
        self.assertIn("FW team owns the firmware code", text)

    def test_empty_inputs_stay_skeleton_not_fabricated(self):
        res = scaffold_c05_fw_spec(self.work)
        self.assertEqual(res.pin_bridge["signals"], [])
        self.assertEqual(res.readiness.status, "blocked")
        self.assertFalse(res.readiness.functional_present)
        self.assertFalse(res.readiness.pin_bridge_present)

    def test_readiness_missing_before_scaffold(self):
        rd = assess_c05_fw_readiness(self.work)
        self.assertEqual(rd.status, "missing")

    def test_pin_bridge_accepts_plain_row_list(self):
        res = scaffold_c05_fw_spec(self.work, pin_map=_PIN_MAP["rows"])
        self.assertEqual(len(res.pin_bridge["signals"]), 2)


if __name__ == "__main__":
    unittest.main()
