import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import compose_schematic, export_bom, export_netlist

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

SPEC = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "R2", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "C1", "symbol": "Device:C", "value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric"},
    ],
    "nets": [{"name": "MID", "nodes": ["R1.2", "R2.1", "C1.1"]}, {"name": "GND", "nodes": ["R2.2", "C1.2"]}],
}


@unittest.skipUnless(HAS_SYMBOLS and HAS_CLI, "KiCad symbols / kicad-cli not available")
class BomExportTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-bom-", dir=PRIVATE_BASE))
        self.sch = compose_schematic(self.work, "bom_demo", SPEC, symbol_dirs=SYMBOL_DIR).emit.schematic_path

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_export_bom_groups_by_value(self):
        result = export_bom(self.sch, self.work, group_by="Value")
        self.assertEqual("ok", result.status)
        self.assertTrue(Path(result.csv_path).exists())
        self.assertEqual(2, result.line_count)  # 10k (R1,R2) + 100nF (C1)
        text = Path(result.csv_path).read_text()
        self.assertIn('"R1,R2"', text)  # grouped refs
        self.assertIn('"2"', text)      # quantity
        self.assertIn("MPN", text)      # MPN column present

    def test_export_netlist(self):
        result = export_netlist(self.sch, self.work)
        self.assertEqual("ok", result.status)
        self.assertTrue(Path(result.netlist_path).exists())

    def test_missing_schematic_fails_cleanly(self):
        result = export_bom(self.work / "nope.kicad_sch", self.work)
        self.assertEqual("failed", result.status)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
