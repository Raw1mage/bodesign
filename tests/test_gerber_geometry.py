from pathlib import Path
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "packages" / "gerber-core"))

from bodesign_gerber_core import GerberRenderResult, focus_svg_viewbox, normalize_allegro_gerber_source, parse_drill_file, parse_gerber_file, render_gerber_preview, render_gerber_with_pygerber, render_geometry_svg
from bodesign_shared import data_root

GERBER = data_root() / "fixtures" / "rockbox" / "gerber"
HAS_GERBER = (GERBER / "L1_top.art").exists()
_NEED = "gerber fixtures absent (set BODESIGN_DATA_DIR)"


class GerberGeometryTests(unittest.TestCase):
    @unittest.skipUnless(HAS_GERBER, _NEED)
    def test_rockbox_top_layer_parses_draws_flashes_and_apertures(self):
        gerber_path = GERBER / "L1_top.art"

        summary = parse_gerber_file(gerber_path, sample_limit=50)

        self.assertEqual("inch", summary.unit)
        self.assertGreaterEqual(len(summary.apertures), 40)
        self.assertGreater(summary.draw_count, 1000)
        self.assertGreater(summary.flash_count, 800)
        self.assertIsNotNone(summary.bounds.min_x)
        self.assertGreater(len(summary.sample_draws), 0)
        self.assertGreater(len(summary.sample_flashes), 0)

    @unittest.skipUnless(HAS_GERBER, _NEED)
    def test_rockbox_drill_parses_tools_and_hits(self):
        drill_path = GERBER / "ROCKBOX_V2-1-6.drl"

        summary = parse_drill_file(drill_path, sample_limit=50)

        self.assertEqual(789, summary.hit_count)
        self.assertEqual(4, len(summary.tools))
        self.assertEqual(809, summary.tools[1].quantity_hint)
        self.assertEqual("PLATED", summary.tools[0].plating)
        self.assertEqual("NON_PLATED", summary.tools[-1].plating)
        self.assertGreater(len(summary.sample_hits), 0)

    @unittest.skipUnless(HAS_GERBER, _NEED)
    def test_svg_preview_uses_real_geometry(self):
        gerber_path = GERBER / "L1_top.art"
        drill_path = GERBER / "ROCKBOX_V2-1-6.drl"

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

    @unittest.skipUnless(HAS_GERBER, _NEED)
    def test_pygerber_adapter_renders_normalized_rockbox_layer_when_available(self):
        gerber_path = GERBER / "L1_top.art"
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

    def test_gerber_preview_renders_selected_layer_through_pygerber_adapter(self):
        work = REPO_ROOT / ".artifacts" / "tests" / "gerber-preview-unit"
        work.mkdir(parents=True, exist_ok=True)
        gerber = work / "L1_top.art"
        gerber.write_text("M02*\n", encoding="utf-8")
        rendered = work / "L1_top.pygerber.png"
        rendered.write_bytes(b"png")

        with patch("bodesign_gerber_core.contracts.render_gerber_raster_with_pygerber",
                   return_value=GerberRenderResult(str(gerber), str(rendered), "pygerber-raster", "rendered")):
            result = render_gerber_preview(work, work / "preview.png", "layer", layer_glob="*.art")

        self.assertEqual("rendered", result["status"])
        self.assertEqual(str(work / "preview.png"), result["image"])
        self.assertEqual(str(gerber), result["rendered_layers"][0]["path"])
        self.assertEqual("pygerber-raster", result["rendered_layers"][0]["renderer"])

    def test_gerber_preview_reports_composite_mode_unavailable(self):
        result = render_gerber_preview(REPO_ROOT, REPO_ROOT / ".artifacts" / "tests" / "stack.png", "stack")

        self.assertEqual("render-unavailable", result["status"])
        self.assertIsNone(result["image"])
        self.assertEqual("unsupported-preview-mode", result["skipped"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
