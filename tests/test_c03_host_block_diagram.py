import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import emit_c03_host_block_diagram


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

# TV1: aiguard-style host MODEL — center SoC + peripherals all four sides + reference_baseline.
TV1_MODEL = {
    "title": "aiguard Host Block Diagram",
    "center_part": {"name": "STM32N657L0H3Q", "mpn": "STM32N657L0H3Q", "type": "soc"},
    "peripherals": [
        {"name": "Octal Flash", "side": "left", "type": "memory", "bus": "XSPI1"},
        {"name": "PSRAM", "side": "left", "type": "memory", "bus": "XSPI2"},
        {"name": "microSD", "side": "left", "type": "connector", "bus": "SDMMC"},
        {"name": "Wi-Fi/BLE", "side": "top", "type": "rf", "bus": "SDIO"},
        {"name": "MIPI 5->1 mux", "side": "right", "type": "connector", "bus": "CSI"},
        {"name": "Touch OLED", "side": "right", "type": "connector", "bus": "I2C+SPI"},
        {"name": "USB-C", "side": "right", "type": "connector", "bus": "USB2"},
        {"name": "18650 power chain", "side": "bottom", "type": "power", "bus": "VSYS"},
    ],
    "reference_baseline": {
        "name": "OpenMV N6",
        "diffs": [
            "no Ethernet PHY",
            "5 module sockets via MIPI 5->1 mux",
            "18650 battery vs USB-only",
            "touch OLED added",
        ],
        "sourcing_gates": ["MIPI mux MPN pending", "18650 charger MPN pending"],
    },
}


class C03HostBlockDiagramTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c03-host-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _svg_text(self, result_dict) -> str:
        svg_abs = self.work / result_dict["svg_path"]
        return svg_abs.read_text(encoding="utf-8")

    # TV1: complete MODEL → five-layer host block SVG + reference-baseline rendered.
    def test_tv1_valid_full(self):
        result = emit_c03_host_block_diagram(self.work, TV1_MODEL).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertEqual(
            ["center", "peripherals", "buses", "legend", "annotations"],
            result["layers"],
        )
        self.assertEqual(8, result["peripherals_count"])
        self.assertEqual([], result["placeholders"])
        # reference_baseline echo present.
        self.assertEqual("OpenMV N6", result["reference_baseline"]["name"])
        self.assertEqual(4, result["reference_baseline"]["diffs_count"])
        self.assertEqual(2, result["reference_baseline"]["sourcing_gates_count"])
        svg = self._svg_text(result)
        for token in (
            "center-STM32N657L0H3Q",
            "peripheral-Octal Flash",
            "bus-Wi-Fi/BLE",
            "derived from OpenMV N6",
            "functional block diagram, not a netlist",
        ):
            self.assertIn(token, svg)

    # TV2: center_part missing name → fail-fast.
    def test_tv2_missing_center_name(self):
        model = {"center_part": {"mpn": "X"}, "peripherals": [{"name": "A", "side": "top"}]}
        result = emit_c03_host_block_diagram(self.work, model).to_dict()
        self.assertEqual("missing", result["status"])
        self.assertIn("center_part.name", result["missing_fields"])
        self.assertNotIn("svg_path", result)
        self.assertFalse(
            (self.work / "C03-EE" / "block" / "Host_Block_Diagram.svg").exists()
        )

    # TV3: peripherals empty → fail-fast.
    def test_tv3_empty_peripherals(self):
        model = {"center_part": {"name": "SoC"}, "peripherals": []}
        result = emit_c03_host_block_diagram(self.work, model).to_dict()
        self.assertEqual("missing", result["status"])
        self.assertIn("peripherals", result["missing_fields"])
        self.assertNotIn("svg_path", result)

    # TV4: peripheral side not in enum → fail-fast with invalid marker.
    def test_tv4_invalid_side(self):
        model = {"center_part": {"name": "SoC"}, "peripherals": [{"name": "A", "side": "northwest"}]}
        result = emit_c03_host_block_diagram(self.work, model).to_dict()
        self.assertEqual("missing", result["status"])
        self.assertIn("peripherals[0].side(invalid:northwest)", result["missing_fields"])
        self.assertNotIn("svg_path", result)

    # TV5: unknown peripheral type → named placeholder (dashed), not dropped.
    def test_tv5_unknown_type_placeholder(self):
        model = {
            "center_part": {"name": "SoC", "type": "soc"},
            "peripherals": [{"name": "Mystery", "side": "top", "type": "quantum-thing"}],
        }
        result = emit_c03_host_block_diagram(self.work, model).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertIn("Mystery", result["placeholders"])
        svg = self._svg_text(result)
        self.assertIn("(placeholder)", svg)
        self.assertIn("stroke-dasharray", svg)

    # TV6: same MODEL → byte-identical SVG (determinism, no RNG).
    def test_tv6_determinism(self):
        r1 = emit_c03_host_block_diagram(self.work, TV1_MODEL).to_dict()
        svg1 = self._svg_text(r1)
        work2 = Path(tempfile.mkdtemp(prefix="bodesign-c03-host2-", dir=PRIVATE_BASE))
        try:
            r2 = emit_c03_host_block_diagram(work2, TV1_MODEL).to_dict()
            svg2 = (work2 / r2["svg_path"]).read_text(encoding="utf-8")
        finally:
            shutil.rmtree(work2, ignore_errors=True)
        self.assertEqual(svg1, svg2)

    # TV7: absent reference_baseline → no derived-from block (no fabricated baseline).
    def test_tv7_no_reference_baseline(self):
        model = {
            "center_part": {"name": "SoC", "type": "soc"},
            "peripherals": [{"name": "USB-C", "side": "right", "type": "connector"}],
        }
        result = emit_c03_host_block_diagram(self.work, model).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertNotIn("reference_baseline", result)
        svg = self._svg_text(result)
        self.assertNotIn("derived from", svg)
        # honest boundary still present.
        self.assertIn("functional block diagram, not a netlist", svg)

    # TV8: all peripherals on one side → no crash/overflow (R1 edge case).
    def test_tv8_lopsided_sides(self):
        model = {
            "center_part": {"name": "SoC", "type": "soc"},
            "peripherals": [
                {"name": "P1", "side": "left", "type": "memory"},
                {"name": "P2", "side": "left", "type": "memory"},
                {"name": "P3", "side": "left", "type": "memory"},
                {"name": "P4", "side": "left", "type": "memory"},
                {"name": "P5", "side": "left", "type": "memory"},
            ],
        }
        result = emit_c03_host_block_diagram(self.work, model).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertEqual(5, result["peripherals_count"])
        svg = self._svg_text(result)
        for n in range(1, 6):
            self.assertIn(f"peripheral-P{n}", svg)

    # PPTX: emit_pptx without bridge → unavailable, never fabricated.
    def test_pptx_unavailable_without_bridge(self):
        result = emit_c03_host_block_diagram(self.work, TV1_MODEL, emit_pptx=True).to_dict()
        self.assertEqual("ok", result["status"])
        self.assertEqual("unavailable", result["pptx_status"])
        self.assertEqual([], [f for f in result["files"] if f.get("kind") == "pptx"])
        self.assertFalse(
            (self.work / "C03-EE" / "block" / "Host_Block_Diagram.pptx").exists()
        )

    # PNG gating mirror: cairosvg absent → png_rendered false and no phantom.
    def test_png_gated(self):
        try:
            import cairosvg  # noqa: F401
            has_cairo = True
        except Exception:
            has_cairo = False
        result = emit_c03_host_block_diagram(self.work, TV1_MODEL).to_dict()
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
            self.assertFalse(
                (self.work / "C03-EE" / "block" / "Host_Block_Diagram.png").exists()
            )


if __name__ == "__main__":
    unittest.main()
