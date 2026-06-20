import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import emit_c03_partition_diagram


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

TV1_MODEL = {
    "title": "CCM/ECB 模組 Breakout",
    "boards": [
        {"name": "CCM", "role": "core", "tier": "compute", "modules": [
            {"name": "SoC", "type": "soc"},
            {"name": "LPDDR", "type": "memory"},
            {"name": "PMIC", "type": "power"},
        ]},
        {"name": "ECB", "role": "carrier", "tier": "expansion", "modules": [
            {"name": "USB-C", "type": "connector"},
            {"name": "Ethernet PHY", "type": "phy"},
        ]},
    ],
    "interconnect": [
        {"class": "PCIe", "signals": ["PERp", "PERn"], "dir": "bidir"},
        {"class": "Power", "signals": ["VSYS"], "dir": "core-to-carrier"},
    ],
}


class C03PartitionDiagramTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c03-part-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _svg_text(self, result_dict) -> str:
        svg_abs = self.work / result_dict["svg_path"]
        return svg_abs.read_text(encoding="utf-8")

    # TV1: complete MODEL → five-layer partition SVG.
    def test_tv1_complete_model_five_layers(self):
        result = emit_c03_partition_diagram(self.work, TV1_MODEL).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertEqual(["boards", "modules", "interconnect", "legend", "annotations"], result["layers"])
        self.assertEqual(2, result["boards_count"])
        self.assertEqual(5, result["modules_count"])
        self.assertEqual(2, result["interconnect_count"])
        self.assertEqual([], result["placeholders"])
        svg = self._svg_text(result)
        for group in ('id="board-CCM"', 'id="board-ECB"', 'id="module-CCM-1"', 'id="net-PCIe"'):
            self.assertIn(group, svg)

    # TV2: missing interconnect.dir → fail-fast.
    def test_tv2_missing_dir_fail_fast(self):
        model = {
            "boards": [{"name": "CCM", "role": "core", "modules": [{"name": "SoC", "type": "soc"}]}],
            "interconnect": [{"class": "PCIe", "signals": ["PERp"]}],
        }
        result = emit_c03_partition_diagram(self.work, model).to_dict()
        self.assertEqual("missing", result["status"])
        self.assertIn("interconnect[0].dir", result["missing_fields"])
        self.assertNotIn("svg_path", result)
        self.assertFalse((self.work / "C03-EE" / "partition" / "Partition_Breakout.svg").exists())

    # TV2b: missing board.role → fail-fast.
    def test_tv2b_missing_role_fail_fast(self):
        model = {
            "boards": [{"name": "CCM", "modules": [{"name": "SoC", "type": "soc"}]}],
            "interconnect": [{"class": "Power", "dir": "core-to-carrier"}],
        }
        result = emit_c03_partition_diagram(self.work, model).to_dict()
        self.assertEqual("missing", result["status"])
        self.assertIn("boards[0].role", result["missing_fields"])
        self.assertNotIn("svg_path", result)

    # TV3: uncovered module type → named placeholder (not silently dropped).
    def test_tv3_uncovered_type_placeholder(self):
        model = {
            "boards": [{"name": "CCM", "role": "core", "modules": [{"name": "Mystery", "type": "unobtanium"}]}],
            "interconnect": [{"class": "Power", "dir": "core-to-carrier"}],
        }
        result = emit_c03_partition_diagram(self.work, model).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertIn("Mystery", result["placeholders"])
        self.assertIn('id="module-CCM-1"', self._svg_text(result))

    # TV4: honest-boundary three notes always stamped.
    def test_tv4_honest_boundary_notes(self):
        result = emit_c03_partition_diagram(self.work, TV1_MODEL).to_dict()
        self.assertEqual(
            ["design partition, not fab pinout", "no RefDes.Pin→net", "no DRC-SI claim"],
            result["boundary"]["notes"],
        )
        svg = self._svg_text(result)
        for note in ("design partition, not fab pinout", "no RefDes.Pin", "no DRC-SI claim"):
            self.assertIn(note, svg)

    # TV5: same MODEL → byte-stable SVG (determinism, no RNG).
    def test_tv5_byte_stable(self):
        r1 = emit_c03_partition_diagram(self.work, TV1_MODEL).to_dict()
        svg1 = self._svg_text(r1)
        work2 = Path(tempfile.mkdtemp(prefix="bodesign-c03-part2-", dir=PRIVATE_BASE))
        try:
            r2 = emit_c03_partition_diagram(work2, TV1_MODEL).to_dict()
            svg2 = (work2 / r2["svg_path"]).read_text(encoding="utf-8")
        finally:
            shutil.rmtree(work2, ignore_errors=True)
        self.assertEqual(svg1, svg2)

    # TV6: cairosvg absent → png_rendered=false and PNG not listed (no phantom).
    def test_tv6_png_gated(self):
        try:
            import cairosvg  # noqa: F401
            has_cairo = True
        except Exception:
            has_cairo = False
        result = emit_c03_partition_diagram(self.work, TV1_MODEL).to_dict()
        self.assertEqual("ok", result["status"])
        png_files = [f for f in result["files"] if f.get("kind") == "png"]
        svg_files = [f for f in result["files"] if f.get("kind") == "svg"]
        self.assertTrue(svg_files)
        if has_cairo:
            self.assertTrue(result["png_rendered"])
            self.assertTrue(png_files)
        else:
            self.assertFalse(result["png_rendered"])
            self.assertEqual([], png_files)
            self.assertFalse((self.work / "C03-EE" / "partition" / "Partition_Breakout.png").exists())

    # TV7: >2 boards adaptive, non-overlapping.
    def test_tv7_multi_board(self):
        model = {
            "boards": [
                {"name": "CCM", "role": "core", "modules": [{"name": "SoC", "type": "soc"}]},
                {"name": "ECB", "role": "carrier", "modules": [{"name": "USB", "type": "connector"}]},
                {"name": "AUX", "role": "carrier", "modules": [{"name": "Sensor", "type": "sensor"}]},
            ],
            "interconnect": [{"class": "I2C", "dir": "bidir", "from_board": "CCM", "to_board": "AUX"}],
        }
        result = emit_c03_partition_diagram(self.work, model).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertEqual(3, result["boards_count"])
        svg = self._svg_text(result)
        for group in ('id="board-CCM"', 'id="board-ECB"', 'id="board-AUX"', 'id="net-I2C"'):
            self.assertIn(group, svg)

    # PPTX: emit_pptx without bridge → unavailable, never fabricated.
    def test_pptx_unavailable_without_bridge(self):
        result = emit_c03_partition_diagram(self.work, TV1_MODEL, emit_pptx=True).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertEqual("unavailable", result["pptx_status"])
        self.assertEqual([], [f for f in result["files"] if f.get("kind") == "pptx"])
        self.assertFalse((self.work / "C03-EE" / "partition" / "Partition_Breakout.pptx").exists())


if __name__ == "__main__":
    unittest.main()
