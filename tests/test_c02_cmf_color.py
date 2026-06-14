"""Phase 6: CMF single-colour render tests.

_resolve_cmf_color parsing (hex / named EN+中文 / RGB(A) / None / illegal) and the
voice extraction of cmf_color into gen_params. The render itself needs GL/trimesh
so the actual rasterise path is skipped on hosts without them; we verify colour
resolution and the C-array construction logic that feeds vertex_colors.

Sub-modules are loaded directly from file (importlib) to bypass the package
__init__, which on a bare host pulls in optional namespace packages
(bodesign_reverse_core/bodesign_design_ir) that are not installed. The modules
under test (model_render, c02_me_package) have only stdlib top-level imports.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load(mod_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass(slots=True) can resolve the module via
    # sys.modules during class processing (dataclasses._is_type).
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


_model_render = _load(
    "c02_model_render_under_test",
    "packages/eda-bridge/bodesign_eda_bridge/model_render.py",
)
_c02 = _load(
    "c02_me_package_under_test",
    "packages/workflow-core/bodesign_workflow_core/c02_me_package.py",
)


class ResolveCmfColorTests(unittest.TestCase):
    def setUp(self):
        self._resolve = _model_render._resolve_cmf_color

    def test_none_returns_none(self):
        self.assertIsNone(self._resolve(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._resolve(""))
        self.assertIsNone(self._resolve("   "))

    def test_hex_rrggbb(self):
        self.assertEqual(self._resolve("#FF8800"), (255, 136, 0, 255))

    def test_hex_rrggbbaa(self):
        self.assertEqual(self._resolve("#FF880080"), (255, 136, 0, 128))

    def test_hex_lowercase(self):
        self.assertEqual(self._resolve("#00ff00"), (0, 255, 0, 255))

    def test_hex_bad_length_returns_none(self):
        self.assertIsNone(self._resolve("#FFF"))
        self.assertIsNone(self._resolve("#FF88"))

    def test_hex_non_hex_returns_none(self):
        self.assertIsNone(self._resolve("#ZZZZZZ"))

    def test_named_en(self):
        self.assertEqual(self._resolve("white"), (245, 246, 248, 255))
        self.assertEqual(self._resolve("black"), (28, 30, 34, 255))

    def test_named_cjk(self):
        self.assertEqual(self._resolve("黑"), (28, 30, 34, 255))
        self.assertEqual(self._resolve("銀"), (200, 204, 209, 255))

    def test_named_case_insensitive(self):
        self.assertEqual(self._resolve("White"), (245, 246, 248, 255))
        self.assertEqual(self._resolve("BLUE"), self._resolve("blue"))

    def test_unknown_name_returns_none(self):
        self.assertIsNone(self._resolve("chartreuse"))
        self.assertIsNone(self._resolve("彩虹"))

    def test_rgb_tuple(self):
        self.assertEqual(self._resolve((10, 20, 30)), (10, 20, 30, 255))

    def test_rgba_tuple(self):
        self.assertEqual(self._resolve((10, 20, 30, 200)), (10, 20, 30, 200))

    def test_tuple_clamped(self):
        self.assertEqual(self._resolve((300, -5, 128)), (255, 0, 128, 255))

    def test_bad_tuple_len_returns_none(self):
        self.assertIsNone(self._resolve((1, 2)))
        self.assertIsNone(self._resolve((1, 2, 3, 4, 5)))

    def test_bad_tuple_values_returns_none(self):
        self.assertIsNone(self._resolve(("a", "b", "c")))


class CArrayConstructionTests(unittest.TestCase):
    """The render fills vertex colours from the resolved RGBA (or grey fallback)."""

    def test_default_grey_constant(self):
        self.assertEqual(_model_render._DEFAULT_ENCLOSURE_RGBA, (176, 180, 188, 255))

    def test_resolved_color_feeds_tile(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available on host")
        _resolve_cmf_color = _model_render._resolve_cmf_color
        _DEFAULT_ENCLOSURE_RGBA = _model_render._DEFAULT_ENCLOSURE_RGBA
        # color given -> tile uses resolved rgba
        rgba = _resolve_cmf_color("red")
        C = np.tile(list(rgba), (4, 1))
        self.assertEqual(C.shape, (4, 4))
        self.assertEqual(tuple(C[0]), (200, 60, 55, 255))
        # color None -> fallback grey
        rgba2 = _resolve_cmf_color(None) or _DEFAULT_ENCLOSURE_RGBA
        C2 = np.tile(list(rgba2), (4, 1))
        self.assertEqual(tuple(C2[0]), (176, 180, 188, 255))


class VoiceCmfExtractionTests(unittest.TestCase):
    def setUp(self):
        self._extract = _c02._extract_cmf_color

    def test_no_color_returns_none(self):
        self.assertIsNone(self._extract("一個 50x30 的盒子", {}))

    def test_named_cjk(self):
        self.assertEqual(self._extract("白色外殼", {}), "white")
        self.assertEqual(self._extract("我要黑色的盒子", {}), "black")

    def test_named_en(self):
        self.assertEqual(self._extract("a silver enclosure", {}), "silver")

    def test_hex_wins(self):
        self.assertEqual(self._extract("外殼用 #1A2B3C 顏色", {}), "#1A2B3C")

    def test_navy_beats_blue(self):
        # "深藍" must resolve to navy, not blue (longer keyword first)
        self.assertEqual(self._extract("深藍色機殼", {}), "navy")

    def test_answers_precedence(self):
        self.assertEqual(self._extract("白色盒子", {"cmf_color": "red"}), "red")

    def test_plan_intent_puts_color_in_gen_params(self):
        plan = _c02.plan_c02_intent("一個 60x40 的盒子，最高元件 12mm，白色外殼，壁厚 2mm，間隙 1mm")
        self.assertEqual(plan["gen_params"].get("cmf_color"), "white")

    def test_plan_intent_no_color_absent(self):
        plan = _c02.plan_c02_intent("一個 60x40 的盒子，最高元件 12mm，壁厚 2mm，間隙 1mm")
        self.assertNotIn("cmf_color", plan["gen_params"])


if __name__ == "__main__":
    unittest.main()
