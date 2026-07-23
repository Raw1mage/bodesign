"""M1 單元測試：ScaleContext 傳播（scale-coherence spec TV-1/TV-2/TV-4）。

驗收：
- TV-1 scale=4.5 生成符號後無殘留未縮放常數（pin length=22.86、text 1.27×4.5）。
- TV-2 scale=1.0 恆等：generic/pin-table path 與 legacy 硬編碼 byte-identical。
- TV-4 CCM path 缺 scale 時 require_scale_context 顯式 raise SCALE_CONTEXT_MISSING。
"""

import re
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.kicad_symbol import (
    KiCadSymbolPin,
    emit_kicad_symbol,
    _generic_symbol_library,
    _PIN_LENGTH,
)
from bodesign_eda_bridge.occupancy import (
    ScaleContext,
    ScaleContextMissing,
    require_scale_context,
)


_SIZE_RE = re.compile(r"\(size ([0-9.]+) ([0-9.]+)\)")
_LEN_RE = re.compile(r"\(length ([0-9.]+)\)")

# 8-pin DIP-ish generic part (numeric <=24 → two-column mirror, no BGA parse issues).
_PINS = [
    KiCadSymbolPin(number=str(i + 1), name=n, kind="passive")
    for i, n in enumerate(
        ["VDD", "GND", "PA0", "PA1", "NRST", "BOOT0", "SWDIO", "SWCLK"]
    )
]


class TestScaleContext(unittest.TestCase):
    def test_from_pitch_derives_page_scale(self):
        ctx = ScaleContext.from_pitch(11.43)
        self.assertEqual(ctx.page_scale, 4.5)
        self.assertEqual(ctx.pin_pitch_mm, 11.43)
        self.assertEqual(ctx.pin_length_mm, 22.86)   # 5.08 × 4.5
        self.assertEqual(ctx.text_height_mm, 5.715)  # 1.27 × 4.5

    def test_identity_scale(self):
        ctx = ScaleContext(page_scale=1.0)
        self.assertEqual(ctx.pin_length_mm, 5.08)
        self.assertEqual(ctx.text_height_mm, 1.27)

    def test_nonpositive_scale_raises(self):
        with self.assertRaises(ValueError):
            ScaleContext(page_scale=0.0)
        with self.assertRaises(ValueError):
            ScaleContext(page_scale=-1.0)


class TestTV1ScalePropagation(unittest.TestCase):
    """TV-1: scale=4.5 生成後無殘留未縮放常數。"""

    def _lib(self, scale):
        return _generic_symbol_library(
            "TESTIC", _PINS, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc", scale=scale,
        )

    def test_pin_length_scaled(self):
        lib = self._lib(4.5)
        lengths = {float(m) for m in _LEN_RE.findall(lib)}
        # every pin graphic length must be 22.86, never the legacy 5.08.
        self.assertEqual(lengths, {22.86}, f"pin lengths: {lengths}")
        self.assertNotIn(5.08, lengths)

    def test_no_residual_unscaled_text(self):
        lib = self._lib(4.5)
        sizes = {float(a) for a, _b in _SIZE_RE.findall(lib)}
        # every text height must be 5.715 (1.27×4.5); zero residual 1.27.
        self.assertNotIn(1.27, sizes, f"residual 1.27 text sizes present: {sizes}")
        self.assertIn(5.715, sizes)

    def test_property_text_also_scaled(self):
        # the 159-residual bug was refdes/value/footprint/datasheet property text
        # staying at 1.27. Assert Reference/Value property blocks are 5.715.
        lib = self._lib(4.5)
        for prop in ("Reference", "Value", "Footprint", "Datasheet"):
            block = re.search(
                rf'\(property "{prop}".*?\(size ([0-9.]+)', lib, re.DOTALL
            )
            self.assertIsNotNone(block, f"{prop} property missing")
            self.assertEqual(float(block.group(1)), 5.715, f"{prop} not scaled")


class TestTV2ByteIdentity(unittest.TestCase):
    """TV-2: scale=1.0 恆等（零打擊半徑護欄）。"""

    def test_generic_scale1_matches_default(self):
        # scale=1.0 explicit must equal the legacy default (no scale arg) byte-for-byte.
        default = _generic_symbol_library(
            "TESTIC", _PINS, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc",
        )
        scaled1 = _generic_symbol_library(
            "TESTIC", _PINS, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc", scale=1.0,
        )
        self.assertEqual(default, scaled1)

    def test_scale1_pin_length_is_legacy(self):
        lib = _generic_symbol_library(
            "TESTIC", _PINS, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc", scale=1.0,
        )
        lengths = {float(m) for m in _LEN_RE.findall(lib)}
        self.assertEqual(lengths, {_PIN_LENGTH})  # 5.08

    def test_emit_kicad_symbol_default_path(self):
        # public API (no scale arg) must still emit legacy 5.08 / 1.27 output.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.kicad_sym"
            emit_kicad_symbol(
                "TESTIC",
                [{"number": str(i + 1), "name": n, "type": "S"}
                 for i, n in enumerate(["VDD", "GND", "PA0", "PA1"])],
                p, datasheet="ds",
            )
            text = p.read_text()
        self.assertIn("(length 5.08)", text)
        self.assertIn("(size 1.27 1.27)", text)


class TestTV4ScaleContextMissing(unittest.TestCase):
    """TV-4: CCM path 缺 scale fail-loud。"""

    def test_require_none_raises(self):
        with self.assertRaises(ScaleContextMissing) as cm:
            require_scale_context(None, "build_u1_variant")
        self.assertIn("SCALE_CONTEXT_MISSING", str(cm.exception))
        self.assertIn("build_u1_variant", str(cm.exception))

    def test_require_present_passes_through(self):
        ctx = ScaleContext.from_pitch(11.43)
        self.assertIs(require_scale_context(ctx, "build_u1_variant"), ctx)


class TestTV3BodyWidthReverseSolve(unittest.TestCase):
    """TV-3: body 寬由縮放後 pin-name 字寬反解（DD-2）。

    左右排 pin-name 向本體內延伸；body 寬必須 >= 左最長字寬 + 右最長字寬 + gap，
    否則兩排 name 對撞在中線（113×318 瘦高病的根因）。
    """

    _RECT_RE = re.compile(
        r"\(rectangle\s*\(start (-?[0-9.]+) (-?[0-9.]+)\)\s*\(end (-?[0-9.]+) (-?[0-9.]+)\)",
        re.DOTALL,
    )
    # long left names + long right names, DIP-ish so half go left, half go right.
    _LONG = [
        KiCadSymbolPin(number=str(i + 1), name=n, kind="passive")
        for i, n in enumerate(
            # first 3 -> left column, last 3 -> right column (numeric <=24 mirror)
            ["VSSAPMUPD", "VDDSMPSVS", "VREFBUFOUT",
             "PA0OTGFSDM", "PC13WKUP01", "PH0OSCIN32"]
        )
    ]

    def _body_width(self, lib):
        m = self._RECT_RE.search(lib)
        self.assertIsNotNone(m, "no body rectangle found")
        x0, _y0, x1, _y1 = (float(v) for v in m.groups())
        return abs(x1 - x0)

    def test_body_width_spans_both_name_columns(self):
        scale = 4.5
        lib = _generic_symbol_library(
            "U1", self._LONG, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc", scale=scale,
        )
        width = self._body_width(lib)
        # left column longest = "VREFBUFOUT" (10), right column longest depends on
        # mirror split; conservatively require the body to hold the two widest
        # names + a centre gap, all at scaled char width (1.05 * scale).
        char_w = 1.05 * scale
        # left = names[:3], right = reversed(names[3:]); longest of each column
        left_max = max(len(n) for n in ["VSSAPMUPD", "VDDSMPSVS", "VREFBUFOUT"])
        right_max = max(len(n) for n in ["PA0OTGFSDM", "PC13WKUP01", "PH0OSCIN32"])
        min_span = (left_max + right_max) * char_w
        self.assertGreaterEqual(
            width, min_span,
            f"body width {width} < name span {min_span} (thin-tall regression)",
        )

    def test_left_right_name_boxes_do_not_overlap(self):
        scale = 4.5
        lib = _generic_symbol_library(
            "U1", self._LONG, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc", scale=scale,
        )
        half_w = self._body_width(lib) / 2.0
        char_w = 1.05 * scale
        # left names run +x from -half_w; right names run -x from +half_w.
        left_reach = -half_w + max(len(n) for n in ["VSSAPMUPD", "VDDSMPSVS", "VREFBUFOUT"]) * char_w
        right_reach = half_w - max(len(n) for n in ["PA0OTGFSDM", "PC13WKUP01", "PH0OSCIN32"]) * char_w
        self.assertLessEqual(
            left_reach, right_reach,
            f"left name reach {left_reach} overshoots right {right_reach} (collision)",
        )

    def test_scale1_still_widens_for_long_names_not_scale(self):
        # DD-2 is a correctness fix, not a scale change: even at scale=1.0 a body
        # with very long names must be wide enough to hold them. This intentionally
        # departs from legacy byte-identity for the draftsman path (documented).
        lib = _generic_symbol_library(
            "U1", self._LONG, footprint_filter="*", datasheet="ds",
            evidence="ev", description="desc", scale=1.0,
        )
        width = self._body_width(lib)
        left_max = max(len(n) for n in ["VSSAPMUPD", "VDDSMPSVS", "VREFBUFOUT"])
        right_max = max(len(n) for n in ["PA0OTGFSDM", "PC13WKUP01", "PH0OSCIN32"])
        self.assertGreaterEqual(width, (left_max + right_max) * 1.05)


class TestM4IntraSymbolTextOverlapGate(unittest.TestCase):
    """M4-1 / TV-5: intra-symbol 文字互疊閘（同 owner 不豁免、真縮放 box）。"""

    def _ledger(self):
        from bodesign_eda_bridge.occupancy import OccupancyLedger
        return OccupancyLedger()

    def test_same_owner_text_overlap_detected(self):
        from bodesign_eda_bridge.occupancy import LedgerRect
        led = self._ledger()
        # two pin-name boxes on the SAME symbol U1 that geometrically overlap
        led.try_reserve(LedgerRect(0, 0, 10, 10, "U1", "pin_extent"))
        led.try_reserve(LedgerRect(5, 5, 15, 15, "U1", "pin_extent"))
        self.assertEqual(len(led.intra_symbol_text_overlaps()), 1)

    def test_cross_owner_text_not_flagged(self):
        from bodesign_eda_bridge.occupancy import LedgerRect
        led = self._ledger()
        led.try_reserve(LedgerRect(0, 0, 10, 10, "U1", "pin_extent"))
        led.try_reserve(LedgerRect(5, 5, 15, 15, "U2", "pin_extent"))
        # cross-owner overlap is a label/body adjacency concern, NOT intra-symbol
        self.assertEqual(len(led.intra_symbol_text_overlaps()), 0)

    def test_non_text_kind_ignored(self):
        from bodesign_eda_bridge.occupancy import LedgerRect
        led = self._ledger()
        # same owner, overlapping, but kind=body (structural coexistence, not text)
        led.try_reserve(LedgerRect(0, 0, 10, 10, "U1", "body"))
        led.try_reserve(LedgerRect(5, 5, 15, 15, "U1", "pin_extent"))
        # only pin_extent↔pin_extent counts; body↔pin_extent same-owner is exempt
        self.assertEqual(len(led.intra_symbol_text_overlaps()), 0)

    def test_assert_raises_intra_symbol_text_overlap(self):
        from bodesign_eda_bridge.occupancy import LedgerRect, IntraSymbolTextOverlap
        led = self._ledger()
        led.try_reserve(LedgerRect(0, 0, 10, 10, "U1", "pin_extent"))
        led.try_reserve(LedgerRect(5, 5, 15, 15, "U1", "pin_extent"))
        with self.assertRaises(IntraSymbolTextOverlap) as cm:
            led.assert_no_intra_symbol_text_overlap()
        self.assertIn("TEXT_OVERLAP_INTRA_SYMBOL", str(cm.exception))

    def test_assert_passes_when_clear(self):
        from bodesign_eda_bridge.occupancy import LedgerRect
        led = self._ledger()
        led.try_reserve(LedgerRect(0, 0, 10, 10, "U1", "pin_extent"))
        led.try_reserve(LedgerRect(20, 20, 30, 30, "U1", "pin_extent"))
        self.assertEqual(led.assert_no_intra_symbol_text_overlap(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
