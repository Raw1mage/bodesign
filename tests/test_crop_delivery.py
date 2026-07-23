"""Tests for crop_delivery: delivery-layer PNG cropping to ink bbox + margin.

Coverage:
  bbox detection  — synthetic image with a known ink rectangle, frame band ignored
  crop correctness— output size == bbox + margin, clamped to image bounds
  margin          — margin_pct expands the crop by the expected pixel count
  no-ink          — blank page emits an unchanged-size copy (never drops a page)
  batch           — *.superseded* skipped; all others cropped into out dir
"""
import os
import tempfile
import unittest

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

if _HAS_PIL:
    from bodesign_eda_bridge import crop_delivery


PAPER = 244  # KiCad off-white sheet luminance (matches ink_metrics convention)
INK = 20     # a clearly-darker ink pixel


def _make_page(w, h, ink_box, frame=True, paper=PAPER):
    """Grey page: paper background, an ink rectangle at ink_box=(x0,y0,x1,y1),
    optionally a thin frame hugging all four edges (the KiCad sheet frame)."""
    img = Image.new("L", (w, h), color=paper)
    px = img.load()
    x0, y0, x1, y1 = ink_box
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px[x, y] = INK
    if frame:
        for x in range(w):
            px[x, 0] = INK
            px[x, h - 1] = INK
        for y in range(h):
            px[0, y] = INK
            px[w - 1, y] = INK
    return img


@unittest.skipUnless(_HAS_PIL, "PIL not installed")
class DetectInkBboxTests(unittest.TestCase):
    def test_bbox_ignores_frame_band(self):
        # Ink rect well inside; frame lines on the edges must be ignored.
        img = _make_page(400, 300, (100, 80, 260, 210), frame=True)
        bbox = crop_delivery.detect_ink_bbox(img, edge_ignore_pct=3.0)
        self.assertIsNotNone(bbox)
        min_x, min_y, max_x, max_y = bbox
        # Frame ignored -> bbox is the interior rectangle, not (0,0,w-1,h-1).
        self.assertEqual((min_x, min_y, max_x, max_y), (100, 80, 260, 210))

    def test_blank_page_returns_none(self):
        img = Image.new("L", (200, 200), color=PAPER)
        self.assertIsNone(crop_delivery.detect_ink_bbox(img, edge_ignore_pct=3.0))


@unittest.skipUnless(_HAS_PIL, "PIL not installed")
class CropPngTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="croptest-")

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def test_crop_size_is_bbox_plus_margin(self):
        w, h = 400, 300
        ink = (100, 80, 260, 210)  # 161 x 131 content
        img = _make_page(w, h, ink, frame=True)
        in_p = self._path("in.png")
        img.save(in_p)
        out_p = self._path("out.png")
        margin_pct = 5.0
        r = crop_delivery.crop_png(in_p, out_p, margin_pct=margin_pct, edge_ignore_pct=3.0)

        margin = round(w * margin_pct / 100.0)  # 20 px
        exp_w = (ink[2] - ink[0] + 1) + 2 * margin  # 161 + 40 = 201
        exp_h = (ink[3] - ink[1] + 1) + 2 * margin  # 131 + 40 = 171
        self.assertEqual(r.crop_size, (exp_w, exp_h))
        # Output file exists and matches reported crop size.
        got = Image.open(out_p)
        self.assertEqual(got.size, (exp_w, exp_h))
        # Fill gain > 1: cropped image is denser than the original page.
        self.assertGreater(r.fill_gain, 1.0)

    def test_margin_clamps_at_image_edge(self):
        # Ink touching near the edge: crop must clamp, never exceed image bounds.
        w, h = 200, 200
        ink = (5, 5, 40, 40)
        img = _make_page(w, h, ink, frame=False)
        in_p = self._path("edge.png")
        img.save(in_p)
        out_p = self._path("edge_out.png")
        r = crop_delivery.crop_png(in_p, out_p, margin_pct=10.0, edge_ignore_pct=0.0)
        cw, ch = r.crop_size
        self.assertLessEqual(cw, w)
        self.assertLessEqual(ch, h)

    def test_blank_page_emits_full_copy(self):
        w, h = 150, 150
        img = Image.new("L", (w, h), color=PAPER)
        in_p = self._path("blank.png")
        img.save(in_p)
        out_p = self._path("blank_out.png")
        r = crop_delivery.crop_png(in_p, out_p, edge_ignore_pct=3.0)
        self.assertEqual(r.crop_size, (w, h))
        self.assertTrue(os.path.exists(out_p))

    def test_no_content_ink_cropped_away(self):
        # The ink rectangle must survive fully inside the crop (no content lost).
        w, h = 400, 300
        ink = (100, 80, 260, 210)
        img = _make_page(w, h, ink, frame=True)
        in_p = self._path("keep.png")
        img.save(in_p)
        out_p = self._path("keep_out.png")
        crop_delivery.crop_png(in_p, out_p, margin_pct=5.0, edge_ignore_pct=3.0)
        out = Image.open(out_p).convert("L")
        _lo, hi = out.getextrema()
        # The dark ink pixel value must still be present in the crop.
        self.assertLess(_lo, hi - 12)


@unittest.skipUnless(_HAS_PIL, "PIL not installed")
class CropBatchTests(unittest.TestCase):
    def test_batch_skips_superseded(self):
        tmp = tempfile.mkdtemp(prefix="cropbatch-")
        _make_page(300, 200, (50, 40, 150, 120), frame=True).save(os.path.join(tmp, "01_power.png"))
        _make_page(300, 200, (50, 40, 150, 120), frame=True).save(os.path.join(tmp, "02_core.png"))
        # A superseded file that must be skipped.
        _make_page(300, 200, (50, 40, 150, 120), frame=True).save(
            os.path.join(tmp, "06_product.superseded.png")
        )
        out_dir = os.path.join(tmp, "cropped")
        results = crop_delivery.crop_batch(tmp, out_dir, margin_pct=5.0, edge_ignore_pct=3.0)
        names = {os.path.basename(r.out_path) for r in results}
        self.assertEqual(names, {"01_power.png", "02_core.png"})
        self.assertFalse(os.path.exists(os.path.join(out_dir, "06_product.superseded.png")))


if __name__ == "__main__":
    unittest.main()
