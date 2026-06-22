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
# Recognize BOTH the legacy ~/.claude/skills layout AND the bundled/env-pointed
# container layout (BODESIGN_*_SKILL → /opt/bodesign-engines/...). Checking only the
# legacy path is what let the cross-engine-import regression slip past CI.
from bodesign_eda_bridge import resolve_skill
HAS_KICAD_SKILL = resolve_skill("kicad", "BODESIGN_KICAD_SKILL") is not None
HAS_EMC_SKILL = resolve_skill("emc", "BODESIGN_EMC_SKILL") is not None
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


class EngineEnvTests(unittest.TestCase):
    """Regression for the cross-engine import bug: the emc analyzer imports
    kicad_utils from the kicad engine, so analyze_emc must run the emc subprocess
    with the kicad scripts dir on PYTHONPATH. Host-runnable (no engines needed)."""

    def test_engine_env_prepends_kicad_scripts(self):
        from bodesign_eda_bridge.pcb_verify import _engine_env
        kicad_scripts = Path("/opt/bodesign-engines/bodesign/engines/kicad/scripts")
        env = _engine_env(kicad_scripts)
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep)[0], str(kicad_scripts))

    def test_engine_env_preserves_existing_pythonpath(self):
        from bodesign_eda_bridge.pcb_verify import _engine_env
        prev = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = "/already/here"
        try:
            env = _engine_env(Path("/k/scripts"))
            parts = env["PYTHONPATH"].split(os.pathsep)
            self.assertEqual(parts[0], "/k/scripts")
            self.assertIn("/already/here", parts)
        finally:
            if prev is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prev


if __name__ == "__main__":
    unittest.main()
