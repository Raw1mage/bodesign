import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from bodesign_workflow_core.drc_crop import (
    DrcViolationCoord,
    DrcVisualCrop,
    extract_drc_coordinates,
    render_svg_crop,
    render_png_crop,
    generate_drc_visual_crops,
    PIL_AVAILABLE,
)
from bodesign_eda_bridge.routing import drc_gate


class TestDrcCrop(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_drc_coordinates_from_dict_pos(self):
        violations = [
            {
                "type": "clearance",
                "description": "Clearance violation between Pad 1 and Track",
                "pos": {"x": 12.5, "y": 25.0},
            },
            {
                "type": "track_width",
                "description": "Track width violation",
                "coordinate": [10.0, 30.5],
            },
        ]
        coords = extract_drc_coordinates(violations)
        self.assertEqual(len(coords), 2)
        self.assertEqual(coords[0].violation_id, "DRC-001")
        self.assertEqual(coords[0].rule_type, "clearance")
        self.assertAlmostEqual(coords[0].x, 12.5)
        self.assertAlmostEqual(coords[0].y, 25.0)

        self.assertEqual(coords[1].violation_id, "DRC-002")
        self.assertAlmostEqual(coords[1].x, 10.0)
        self.assertAlmostEqual(coords[1].y, 30.5)

    def test_extract_drc_coordinates_from_items_and_regex(self):
        violations = [
            {
                "type": "clearance",
                "description": "Clearance between items",
                "items": [
                    {"pos": {"x": 20.0, "y": 40.0}},
                    {"pos": {"x": 30.0, "y": 50.0}},
                ],
            },
            {
                "type": "via_hole",
                "description": "Via hole violation at (15.2mm, 45.8mm)",
            },
            "Text report line: clearance violation @ (18.0, 22.0)",
        ]
        coords = extract_drc_coordinates(violations)
        self.assertEqual(len(coords), 3)

        # Average of items: (20+30)/2 = 25, (40+50)/2 = 45
        self.assertAlmostEqual(coords[0].x, 25.0)
        self.assertAlmostEqual(coords[0].y, 45.0)

        # Regex fallback from description
        self.assertAlmostEqual(coords[1].x, 15.2)
        self.assertAlmostEqual(coords[1].y, 45.8)

        # String line
        self.assertAlmostEqual(coords[2].x, 18.0)
        self.assertAlmostEqual(coords[2].y, 22.0)

    def test_render_svg_crop(self):
        coord = DrcViolationCoord(
            violation_id="DRC-001",
            rule_type="clearance",
            x=10.0,
            y=20.0,
            description="Clearance violation",
        )
        out_svg = self.out_dir / "crop_001.svg"
        render_svg_crop(coord, out_svg, window_mm=5.0)

        self.assertTrue(out_svg.exists())
        content = out_svg.read_text(encoding="utf-8")
        self.assertIn("<svg", content)
        self.assertIn('viewBox="7.5000 17.5000 5.0000 5.0000"', content)
        self.assertIn('fill="#ffcc00"', content)

    @unittest.skipUnless(PIL_AVAILABLE, "PIL / Pillow required for PNG rendering")
    def test_render_png_crop(self):
        from PIL import Image

        coord = DrcViolationCoord(
            violation_id="DRC-002",
            rule_type="short",
            x=15.0,
            y=25.0,
            description="Short circuit",
        )
        out_png = self.out_dir / "crop_002.png"
        render_png_crop(coord, out_png, window_mm=5.0, pixels_per_mm=100)

        self.assertTrue(out_png.exists())
        with Image.open(out_png) as img:
            self.assertEqual(img.size, (500, 500))
            self.assertEqual(img.mode, "RGBA")

    def test_generate_drc_visual_crops(self):
        violations = [
            {
                "type": "clearance",
                "description": "Clearance violation",
                "pos": {"x": 10.0, "y": 20.0},
            },
            {
                "type": "courtyard",
                "description": "Courtyard overlap",
                "pos": {"x": 30.0, "y": 40.0},
            },
        ]
        crops = generate_drc_visual_crops(
            violations,
            output_dir=self.out_dir,
            window_mm=5.0,
            preferred_format="svg",
        )
        self.assertEqual(len(crops), 2)
        for c in crops:
            self.assertTrue(Path(c.crop_file).exists())
            d = c.to_dict()
            self.assertIn("violation_id", d)
            self.assertIn("coordinate", d)
            self.assertIn("crop_file", d)

    @patch("bodesign_eda_bridge.routing._need_pcbnew")
    @patch("subprocess.run")
    def test_drc_gate_with_visual_crops(self, mock_subproc, mock_pcbnew):
        fake_drc = {
            "violations": [
                {
                    "type": "clearance",
                    "description": "Clearance violation",
                    "pos": {"x": 12.0, "y": 14.0},
                }
            ],
            "unconnected_items": [],
        }

        # Mock kicad-cli output by intercepting subprocess and writing json to rep file
        def fake_run(cmd, capture_output=True):
            rep_file = cmd[cmd.index("-o") + 1]
            Path(rep_file).write_text(json.dumps(fake_drc), encoding="utf-8")
            return MagicMock(returncode=0)

        mock_subproc.side_effect = fake_run

        crops_dir = self.out_dir / "crops"
        result = drc_gate(
            "/dummy/board.kicad_pcb",
            visual_crops_dir=str(crops_dir),
            crop_format="svg",
        )

        self.assertIn("visual_crops", result)
        self.assertEqual(len(result["visual_crops"]), 1)
        self.assertEqual(result["visual_crops"][0]["violation_id"], "DRC-001")
        self.assertTrue(Path(result["visual_crops"][0]["crop_file"]).exists())


if __name__ == "__main__":
    unittest.main()
