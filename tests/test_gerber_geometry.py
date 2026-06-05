from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "packages" / "gerber-core"))

from bodesign_gerber_core import parse_drill_file, parse_gerber_file, render_geometry_svg


class GerberGeometryTests(unittest.TestCase):
    def test_rockbox_top_layer_parses_draws_flashes_and_apertures(self):
        gerber_path = REPO_ROOT / "fixtures" / "private" / "rockbox" / "gerber" / "L1_top.art"

        summary = parse_gerber_file(gerber_path, sample_limit=50)

        self.assertEqual("inch", summary.unit)
        self.assertGreaterEqual(len(summary.apertures), 40)
        self.assertGreater(summary.draw_count, 1000)
        self.assertGreater(summary.flash_count, 800)
        self.assertIsNotNone(summary.bounds.min_x)
        self.assertGreater(len(summary.sample_draws), 0)
        self.assertGreater(len(summary.sample_flashes), 0)

    def test_rockbox_drill_parses_tools_and_hits(self):
        drill_path = REPO_ROOT / "fixtures" / "private" / "rockbox" / "gerber" / "ROCKBOX_V2-1-6.drl"

        summary = parse_drill_file(drill_path, sample_limit=50)

        self.assertEqual(789, summary.hit_count)
        self.assertEqual(4, len(summary.tools))
        self.assertEqual(809, summary.tools[1].quantity_hint)
        self.assertEqual("PLATED", summary.tools[0].plating)
        self.assertEqual("NON_PLATED", summary.tools[-1].plating)
        self.assertGreater(len(summary.sample_hits), 0)

    def test_svg_preview_uses_real_geometry(self):
        gerber_path = REPO_ROOT / "fixtures" / "private" / "rockbox" / "gerber" / "L1_top.art"
        drill_path = REPO_ROOT / "fixtures" / "private" / "rockbox" / "gerber" / "ROCKBOX_V2-1-6.drl"

        svg = render_geometry_svg(parse_gerber_file(gerber_path, sample_limit=20), parse_drill_file(drill_path, sample_limit=20))

        self.assertIn("<svg", svg)
        self.assertIn("<line", svg)
        self.assertIn("<circle", svg)


if __name__ == "__main__":
    unittest.main()
