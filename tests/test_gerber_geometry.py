from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "packages" / "gerber-core"))

from bodesign_gerber_core import focus_svg_viewbox, normalize_allegro_gerber_source, parse_drill_file, parse_gerber_file, render_gerber_with_pygerber, render_geometry_svg


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

    def test_allegro_header_normalization_removes_pygerber_incompatible_codes(self):
        source = "%FSLAX25Y25*MOIN*%\n%IR0*IPPOS*OFA0B0*MIAV0*SF1.0B1.0*%\nM02*\n"

        normalized, removed_codes = normalize_allegro_gerber_source(source)

        self.assertIn("%FSLAX25Y25*%", normalized)
        self.assertNotIn("IR0", normalized)
        self.assertEqual(["IP", "IR", "MI", "OFA", "SF"], removed_codes)

    def test_pygerber_adapter_renders_normalized_rockbox_layer_when_available(self):
        gerber_path = REPO_ROOT / "fixtures" / "private" / "rockbox" / "gerber" / "L1_top.art"
        output_dir = REPO_ROOT / ".artifacts" / "tests" / "pygerber"

        result = render_gerber_with_pygerber(gerber_path, output_dir)

        if result.status != "rendered":
            self.skipTest(f"pygerber renderer unavailable: {result.warnings}")
        self.assertTrue(result.normalized)
        self.assertIn("IR", result.removed_extended_codes)
        self.assertIsNotNone(result.output_path)
        self.assertIn("<svg", Path(str(result.output_path)).read_text(encoding="utf-8", errors="ignore"))

    def test_focus_svg_viewbox_crops_empty_pygerber_extent(self):
        svg = '<svg width="158.0" height="199.0" viewBox="0 0 158 199"><defs></defs><use xlink:href="#d1" x="14" y="111" /><use xlink:href="#d1" x="72" y="160" /><path d="M25,120 L70,150 Z" /></svg>'

        focused = focus_svg_viewbox(svg)

        self.assertIn("viewBox=\"", focused)
        self.assertNotIn('viewBox="0 0 158 199"', focused)
        self.assertNotIn('width="158.0" height="199.0"', focused)


if __name__ == "__main__":
    unittest.main()
