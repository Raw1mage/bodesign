import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import generate_c02_openscad, plan_c02_intent
from bodesign_workflow_core.c02_me_package import (
    _build_enclosure_part,
    _render_openscad_source,
    _validate_corner_radius,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

try:
    import build123d as _b123d  # noqa: F401
    _HAS_BUILD123D = True
except Exception:
    _HAS_BUILD123D = False


_CONSTRAINTS = {
    "board_outline": {"width_mm": 60, "height_mm": 40},
    "component_heights": [{"ref": "U1", "height_mm": 15}],
    "mounting_holes": [{"x_mm": 4, "y_mm": 4, "diameter_mm": 2.5}],
    "connector_openings": [
        {"face": "east", "width_mm": 9, "height_mm": 3.5, "z_mm": 4},
    ],
}


class CornerRadiusValidationTests(unittest.TestCase):
    # case for the 60x40 board, wall=2 clearance=1 -> case 66x46, limit = 23
    def test_none_and_zero_are_square(self):
        self.assertEqual(_validate_corner_radius(None, 66.0, 46.0), 0.0)
        self.assertEqual(_validate_corner_radius(0, 66.0, 46.0), 0.0)
        self.assertEqual(_validate_corner_radius(0.0, 66.0, 46.0), 0.0)

    def test_positive_radius_passes(self):
        self.assertEqual(_validate_corner_radius(3, 66.0, 46.0), 3.0)
        # exactly half the smaller side is the boundary and is allowed
        self.assertEqual(_validate_corner_radius(23.0, 66.0, 46.0), 23.0)

    def test_negative_radius_raises(self):
        with self.assertRaises(ValueError):
            _validate_corner_radius(-1, 66.0, 46.0)

    def test_out_of_range_raises_not_clamped(self):
        # DD-2: an impossible radius fails fast rather than being silently clamped.
        with self.assertRaises(ValueError):
            _validate_corner_radius(30, 66.0, 46.0)


class OpenScadCornerRadiusTests(unittest.TestCase):
    def test_square_when_radius_absent(self):
        # backward compatible: None -> plain cube, no hull
        source = _render_openscad_source(_CONSTRAINTS, 2.0, 1.0, 1.0)
        self.assertIn("cube([case_width, case_height, case_depth])", source)
        self.assertNotIn("hull()", source)

    def test_square_when_radius_zero(self):
        source = _render_openscad_source(_CONSTRAINTS, 2.0, 1.0, 1.0, 0)
        self.assertIn("cube([case_width, case_height, case_depth])", source)
        self.assertNotIn("hull()", source)

    def test_rounded_uses_hull_of_four_cylinders(self):
        source = _render_openscad_source(_CONSTRAINTS, 2.0, 1.0, 1.0, 3)
        self.assertIn("hull()", source)
        # exactly four vertical corner cylinders
        self.assertEqual(source.count("cylinder(h=case_depth"), 4)
        # the plain outer cube must be gone (replaced by the hull)
        self.assertNotIn("cube([case_width, case_height, case_depth])", source)

    def test_rounding_preserves_cuts_and_posts(self):
        # the difference structure and the real connector/mounting geometry from the
        # previous round must NOT be filled in by the hull rounding.
        source = _render_openscad_source(_CONSTRAINTS, 2.0, 1.0, 1.0, 3)
        self.assertIn("module connector_cuts()", source)
        self.assertIn("connector_cuts();", source)  # still differenced from the shell
        self.assertIn("module mounting_posts()", source)
        self.assertIn("mounting_posts();", source)
        self.assertIn("east face", source)

    def test_out_of_range_radius_raises(self):
        with self.assertRaises(ValueError):
            _render_openscad_source(_CONSTRAINTS, 2.0, 1.0, 1.0, 30)

    def test_generate_openscad_passes_radius_through(self):
        base = PRIVATE_BASE
        base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="c02-radius-", dir=base))
        try:
            res = generate_c02_openscad(
                work, constraints=_CONSTRAINTS,
                wall_thickness_mm=2.0, clearance_mm=1.0, lid_clearance_mm=1.0,
                corner_radius_mm=3,
            )
            self.assertEqual(res.status, "source_generated")
            scad = (work / "C02-ME" / "Enclosure.scad").read_text(encoding="utf-8")
            self.assertIn("hull()", scad)
            self.assertEqual(scad.count("cylinder(h=case_depth"), 4)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class PlanIntentCornerRadiusTests(unittest.TestCase):
    _BASE = "我要一個 60x40 的盒子，最高元件 15mm，壁厚 2mm，間隙 1mm，蓋間隙 1mm"

    def _radius_ask_present(self, plan):
        # plan_c02_intent only surfaces the single top-ranked next_question, so to
        # assert the corner-radius ask exists we drive answers for the other
        # not-yet-provided fields until corner_radius becomes the top question, OR
        # accept it directly as next_question. Here we provide answers for the
        # secondary fields so the corner ask is the only one left.
        nq = plan.get("next_question")
        return bool(nq) and nq.get("key") == "corner_radius_mm"

    def test_rounding_keyword_without_radius_asks(self):
        # mentions rounding but gives no radius -> must ask, never guess (DD-2).
        # Provide every other optional field so the corner-radius ask ranks to the
        # top of next_question (mounting/heat/antenna/battery/environment otherwise
        # outrank it as earlier-registered open questions).
        answers = {
            "mounting_holes": "x=4,y=4,d=2.5",
            "heat_sources": "none",
            "antenna_keepouts": "none",
            "battery_envelope": "none",
            "environment_targets": "indoor",
            "connector_openings": "face=east, width_mm=9, height_mm=3.5, z_mm=4",
        }
        r = plan_c02_intent(self._BASE + "，要圓角", answers=answers)
        self.assertNotIn("corner_radius_mm", r["gen_params"])
        self.assertTrue(self._radius_ask_present(r),
                        f"expected corner_radius ask, got {r.get('next_question')}")

    def test_radius_in_text_is_extracted(self):
        r = plan_c02_intent(self._BASE + "，圓角 3mm")
        self.assertEqual(r["gen_params"].get("corner_radius_mm"), 3.0)
        # a provided radius is not re-asked
        nq = r.get("next_question")
        self.assertFalse(nq and nq.get("key") == "corner_radius_mm")

    def test_radius_via_answer(self):
        r = plan_c02_intent(self._BASE + "，要倒角", answers={"corner_radius_mm": "4mm"})
        self.assertEqual(r["gen_params"].get("corner_radius_mm"), 4.0)

    def test_no_rounding_mention_no_param_no_ask(self):
        r = plan_c02_intent(self._BASE)
        self.assertNotIn("corner_radius_mm", r["gen_params"])
        nq = r.get("next_question")
        self.assertFalse(nq and nq.get("key") == "corner_radius_mm")


@unittest.skipUnless(_HAS_BUILD123D, "build123d not installed on host")
class BuildPartCornerRadiusTests(unittest.TestCase):
    def test_square_part_builds(self):
        part = _build_enclosure_part(_CONSTRAINTS, 2.0, 1.0, 1.0)
        self.assertIsNotNone(part)
        self.assertGreater(part.volume, 0)

    def test_rounded_part_builds_and_is_smaller(self):
        # filleting the four vertical edges removes material, so the rounded part
        # must have strictly less volume than the square one.
        square = _build_enclosure_part(_CONSTRAINTS, 2.0, 1.0, 1.0)
        rounded = _build_enclosure_part(_CONSTRAINTS, 2.0, 1.0, 1.0, corner_radius_mm=3)
        self.assertIsNotNone(rounded)
        self.assertGreater(rounded.volume, 0)
        self.assertLess(rounded.volume, square.volume)

    def test_out_of_range_radius_raises(self):
        with self.assertRaises(ValueError):
            _build_enclosure_part(_CONSTRAINTS, 2.0, 1.0, 1.0, corner_radius_mm=30)


if __name__ == "__main__":
    unittest.main()
