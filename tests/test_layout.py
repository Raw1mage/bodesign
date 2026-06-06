import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import PCBNEW_AVAILABLE, emit_layout

FP_DIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
HAS_FP = (FP_DIR / "Resistor_SMD.pretty").exists()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

COMPONENTS = [
    {"ref": "R1", "footprint": "Resistor_SMD:R_0402_1005Metric"},
    {"ref": "C1", "footprint": "Capacitor_SMD:C_0402_1005Metric"},
    {"ref": "U1", "footprint": "NoSuch:Footprint_XYZ"},  # unresolved
]


@unittest.skipUnless(PCBNEW_AVAILABLE and HAS_FP, "pcbnew / KiCad footprints not available")
class LayoutTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-layout-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_emit_layout_places_and_renders(self):
        result = emit_layout(self.work, "demo_board", COMPONENTS, board_mm=(50, 40))

        self.assertEqual("ok", result.status)
        self.assertEqual(2, result.placed)  # R1 + C1 placed; U1 unresolved
        self.assertTrue(any("U1" in u for u in result.unresolved_footprints))
        self.assertTrue(Path(result.board_path).exists())
        # kicad-cli is present in this environment -> DRC + companion produced
        self.assertIsNotNone(result.drc_report)
        self.assertTrue(Path(result.drc_report).exists())
        self.assertIsNotNone(result.companion)
        self.assertTrue(result.companion.endswith(".svg"))
        self.assertTrue(Path(result.companion).exists())


if __name__ == "__main__":
    unittest.main()
