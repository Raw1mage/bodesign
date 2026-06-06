import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import PCBNEW_AVAILABLE, emit_fab_outputs, emit_layout

FP_DIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
HAS_FP = (FP_DIR / "Resistor_SMD.pretty").exists()
HAS_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


@unittest.skipUnless(PCBNEW_AVAILABLE and HAS_FP and HAS_CLI, "pcbnew / footprints / kicad-cli not available")
class FabTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-fab-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_fab_outputs_from_generated_board(self):
        layout = emit_layout(self.work, "demo_board",
                             [{"ref": "R1", "footprint": "Resistor_SMD:R_0402_1005Metric"}],
                             board_mm=(40, 30))
        self.assertEqual("ok", layout.status)

        fab = emit_fab_outputs(layout.board_path, self.work / "fab", ("gerbers", "drill", "pos", "step", "pdf"))

        self.assertEqual("ok", fab.status)
        for fmt in ("gerbers", "drill", "pos", "step", "pdf"):
            self.assertIn(fmt, fab.outputs)
        # gerbers/drill are directories with content
        self.assertTrue(any(Path(fab.outputs["gerbers"]).iterdir()))
        self.assertTrue(Path(fab.outputs["step"]).exists())
        self.assertTrue(Path(fab.outputs["pdf"]).exists())

    def test_missing_board_fails_cleanly(self):
        fab = emit_fab_outputs(self.work / "nope.kicad_pcb", self.work / "fab")
        self.assertEqual("failed", fab.status)
        self.assertTrue(fab.warnings)


if __name__ == "__main__":
    unittest.main()
