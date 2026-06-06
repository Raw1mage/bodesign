import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import (
    PCBNEW_AVAILABLE,
    analyze_emc,
    analyze_thermal,
    compose_schematic,
    emit_layout,
)

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
FP_DIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_FP = (FP_DIR / "Resistor_SMD.pretty").exists()
HAS_CLI = shutil.which("kicad-cli") is not None
SKILLS = Path(os.environ.get("BODESIGN_SKILLS_HOME", Path.home() / ".claude" / "skills"))
HAS_KICAD_SKILL = (SKILLS / "kicad" / "scripts").is_dir()
HAS_EMC_SKILL = (SKILLS / "emc" / "scripts").is_dir()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

SPEC = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
        {"ref": "R2", "symbol": "Device:R", "value": "20k", "footprint": "Resistor_SMD:R_0402_1005Metric"},
    ],
    "nets": [{"name": "VIN", "nodes": ["R1.1"]}, {"name": "VOUT", "nodes": ["R1.2", "R2.1"]}, {"name": "GND", "nodes": ["R2.2"]}],
}
FOOTPRINTS = [{"ref": "R1", "footprint": "Resistor_SMD:R_0402_1005Metric"},
              {"ref": "R2", "footprint": "Resistor_SMD:R_0402_1005Metric"}]


class PcbVerifyTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-emc-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_emc_degrades_without_skills(self):
        r = analyze_emc(self.work / "s.kicad_sch", self.work / "b.kicad_pcb", self.work,
                        kicad_skill=self.work / "nope", emc_skill=self.work / "nope")
        self.assertEqual("skipped-no-skills", r.status)

    @unittest.skipUnless(HAS_SYMBOLS and HAS_FP and HAS_CLI and PCBNEW_AVAILABLE and HAS_KICAD_SKILL and HAS_EMC_SKILL,
                         "kicad/emc skills, pcbnew, footprints, kicad-cli required")
    def test_emc_and_thermal_on_generated_board(self):
        sch = compose_schematic(self.work, "divider", SPEC, symbol_dirs=SYMBOL_DIR).emit.schematic_path
        board = emit_layout(self.work, "divider", FOOTPRINTS, board_mm=(30, 20)).board_path

        emc = analyze_emc(sch, board, self.work / "emc")
        self.assertEqual("ok", emc.status)
        self.assertGreaterEqual(emc.finding_count, 1)        # EMC analyzer flags real risks
        self.assertIn("error", emc.by_severity)              # no ground plane -> error

        thermal = analyze_thermal(sch, board, self.work / "thermal")
        self.assertEqual("ok", thermal.status)
        self.assertIn("thermal_score", thermal.summary)


if __name__ == "__main__":
    unittest.main()
