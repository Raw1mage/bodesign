import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_reverse_core import render_companion

REPO = Path("/home/pkcs12/projects/bodesign")
GEN_SCH = REPO / "plans/product_openmv_datasheet_kicad_source/generated/openmv_n6_subsystem/openmv_n6_subsystem.kicad_sch"
ROCKBOX_ART = REPO / "fixtures/private/rockbox/gerber/L1_top.art"
HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _pygerber_available() -> bool:
    try:
        import pygerber  # noqa: F401
        return True
    except ImportError:
        return False


class CompanionRenderTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-companion-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_unsupported_engineering_file_reports_clearly(self):
        result = render_companion(self.work / "board.DSN", self.work)
        self.assertEqual("unsupported", result.status)
        self.assertIn("originating tool", result.note)

    @unittest.skipUnless(HAS_KICAD_CLI and GEN_SCH.exists(), "kicad-cli or generated schematic not available")
    def test_schematic_renders_to_pdf(self):
        result = render_companion(GEN_SCH, self.work)
        self.assertEqual("rendered", result.status)
        self.assertEqual("kicad-cli", result.renderer)
        self.assertTrue(result.output.endswith(".pdf"))
        self.assertTrue(Path(result.output).exists())

    @unittest.skipUnless(ROCKBOX_ART.exists(), "Rockbox gerber fixture not present")
    def test_gerber_dispatches_to_pygerber(self):
        result = render_companion(ROCKBOX_ART, self.work)
        # Dispatch must be correct regardless of whether pygerber is in this interpreter.
        self.assertEqual("pygerber-raster", result.renderer)
        self.assertIn(result.status, {"rendered", "render-failed"})
        if _pygerber_available():
            self.assertEqual("rendered", result.status)
            self.assertTrue(result.output.endswith(".png"))
            self.assertTrue(Path(result.output).exists())


if __name__ == "__main__":
    unittest.main()
