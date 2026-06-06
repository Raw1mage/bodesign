import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import compose_schematic, simulate_schematic

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_NGSPICE = shutil.which("ngspice") is not None
SKILLS = Path(os.environ.get("BODESIGN_SKILLS_HOME", Path.home() / ".claude" / "skills"))
HAS_SKILLS = (SKILLS / "kicad" / "scripts").is_dir() and (SKILLS / "spice" / "scripts").is_dir()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

DIVIDER = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "R2", "symbol": "Device:R", "value": "20k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
    ],
    "nets": [{"name": "VIN", "nodes": ["R1.1"]}, {"name": "VOUT", "nodes": ["R1.2", "R2.1"]}, {"name": "GND", "nodes": ["R2.2"]}],
}


class SimulateTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-sim-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_degrades_gracefully_without_skills(self):
        # bogus skill paths -> skipped, never raises
        result = simulate_schematic(self.work / "x.kicad_sch", self.work,
                                    kicad_skill=self.work / "nope", spice_skill=self.work / "nope")
        self.assertEqual("skipped-no-skills", result.status)
        self.assertTrue(result.warnings)

    @unittest.skipUnless(HAS_SYMBOLS and HAS_NGSPICE and HAS_SKILLS, "ngspice / kicad+spice skills / symbols not available")
    def test_simulates_divider_pass(self):
        sch = compose_schematic(self.work, "divider", DIVIDER, symbol_dirs=SYMBOL_DIR).emit.schematic_path
        result = simulate_schematic(sch, self.work)

        self.assertEqual("ok", result.status)
        self.assertGreaterEqual(result.passed, 1)
        self.assertEqual(0, result.failed)
        kinds = [r["type"] for r in result.results]
        self.assertIn("voltage_divider", kinds)
        vd = next(r for r in result.results if r["type"] == "voltage_divider")
        self.assertEqual("pass", vd["status"])


if __name__ == "__main__":
    unittest.main()
