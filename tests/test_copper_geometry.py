import unittest

from bodesign_gerber_core import (
    CopperGeometry,
    MissingGeometryError,
    build_copper_geometry,
    edge_to_edge,
    plane_coverage,
    point_to_copper,
)


class BuildCopperGeometryTests(unittest.TestCase):
    def test_tv1_build_tracks_pads_curve_flagged_excluded(self):
        geom = build_copper_geometry(
            tracks=[{"x1": 0, "y1": 0, "x2": 10, "y2": 0}],
            pads=[{"x": 5, "y": 5, "w": 2, "h": 2}],
            curves=[{"cx": 0, "cy": 0, "r": 2}],
        )
        self.assertEqual(len(geom.primitives), 3)
        # curve excluded from linear/distance math
        self.assertEqual(len(geom.curves()), 1)
        self.assertEqual(len(geom.linear()), 2)
        self.assertEqual(geom.curves()[0].coords, [])
        self.assertIsNotNone(geom.curves()[0].curve_params)

    def test_tv2_empty_input_fails_fast(self):
        with self.assertRaises(MissingGeometryError) as ctx:
            build_copper_geometry(tracks=[], pads=[], polygons=[])
        self.assertEqual(ctx.exception.reason, "zero_geometry")

    def test_curves_only_still_fails_fast(self):
        with self.assertRaises(MissingGeometryError) as ctx:
            build_copper_geometry(curves=[{"cx": 0, "cy": 0, "r": 1}])
        self.assertEqual(ctx.exception.reason, "zero_geometry")

    def test_deterministic_ids(self):
        a = build_copper_geometry(tracks=[{"x1": 0, "y1": 0, "x2": 1, "y2": 0}])
        b = build_copper_geometry(tracks=[{"x1": 0, "y1": 0, "x2": 1, "y2": 0}])
        self.assertEqual([p.id for p in a.primitives], [p.id for p in b.primitives])


class NetIslandTests(unittest.TestCase):
    def test_tv3_touching_merge_disjoint_separate(self):
        geom = build_copper_geometry(
            tracks=[
                {"x1": 0, "y1": 0, "x2": 1, "y2": 0},
                {"x1": 1, "y1": 0, "x2": 2, "y2": 0},  # touches first at (1,0)
                {"x1": 50, "y1": 50, "x2": 51, "y2": 50},  # disjoint
            ]
        )
        islands = {p.net_island for p in geom.linear()}
        self.assertEqual(len(islands), 2)


class EdgeToEdgeTests(unittest.TestCase):
    def _two_island_geom(self) -> CopperGeometry:
        return build_copper_geometry(
            tracks=[
                {"x1": 0, "y1": 0, "x2": 0, "y2": 10},
                {"x1": 3, "y1": 0, "x2": 3, "y2": 10},
            ]
        )

    def test_tv4_edge_to_edge_distance_and_provenance(self):
        geom = self._two_island_geom()
        a, b = geom.linear()[0].net_island, geom.linear()[1].net_island
        res = edge_to_edge(geom, a, b)
        self.assertIsNone(res.error)
        self.assertAlmostEqual(res.distance_mm, 3.0)
        self.assertTrue(res.provenance.primitive_refs)
        self.assertEqual(res.provenance.algorithm, "segment_min_distance")

    def test_tv5_byte_identical_repeat(self):
        geom = self._two_island_geom()
        a, b = geom.linear()[0].net_island, geom.linear()[1].net_island
        r1 = edge_to_edge(geom, a, b)
        r2 = edge_to_edge(geom, a, b)
        self.assertEqual(r1.distance_mm, r2.distance_mm)
        self.assertEqual(r1.provenance.primitive_refs, r2.provenance.primitive_refs)

    def test_tv7_empty_island_returns_error_not_zero(self):
        geom = self._two_island_geom()
        res = edge_to_edge(geom, "nonexistent_a", "nonexistent_b")
        self.assertIsNotNone(res.error)
        self.assertEqual(res.error.reason, "empty_primitive_set")
        self.assertIsNone(res.distance_mm)

    def test_tv8_skipped_curve_disclosed_in_provenance(self):
        geom = build_copper_geometry(
            tracks=[
                {"x1": 0, "y1": 0, "x2": 0, "y2": 10},
                {"x1": 3, "y1": 0, "x2": 3, "y2": 10},
            ],
            curves=[{"cx": 1, "cy": 1, "r": 0.5}],
        )
        a, b = geom.linear()[0].net_island, geom.linear()[1].net_island
        res = edge_to_edge(geom, a, b)
        self.assertTrue(res.provenance.skipped_curves)


class PointAndPlaneTests(unittest.TestCase):
    def test_tv6_point_to_copper_and_plane_coverage(self):
        geom = build_copper_geometry(
            tracks=[{"x1": 0, "y1": 0, "x2": 10, "y2": 0}],
            polygons=[{"points": [[0, 0], [10, 0], [10, 10], [0, 10]], "plane": True}],
        )
        pt = point_to_copper(geom, 0, 5)
        self.assertIsNone(pt.error)
        self.assertAlmostEqual(pt.distance_mm, 0.0)  # point on track's x=0 line vertically? nearest is (0,0)-(10,0)
        cov = plane_coverage(geom, 5, 5)
        self.assertIsNone(cov.error)
        self.assertTrue(cov.covered)

    def test_plane_coverage_outside(self):
        geom = build_copper_geometry(
            polygons=[{"points": [[0, 0], [10, 0], [10, 10], [0, 10]], "plane": True}]
        )
        cov = plane_coverage(geom, 50, 50)
        self.assertFalse(cov.covered)

    def test_plane_coverage_no_plane_returns_error(self):
        geom = build_copper_geometry(tracks=[{"x1": 0, "y1": 0, "x2": 1, "y2": 0}])
        cov = plane_coverage(geom, 5, 5)
        self.assertIsNotNone(cov.error)
        self.assertEqual(cov.error.reason, "empty_primitive_set")


class NoPcbnewTests(unittest.TestCase):
    def test_no_pcbnew_import(self):
        # copper_geometry must stay pure-python (no pcbnew). The global sys.modules
        # is contaminated by sibling tests that legitimately import pcbnew (layout),
        # so assert the invariant in a FRESH interpreter for true isolation.
        import subprocess
        import sys as _sys

        code = (
            "import sys\n"
            "import bodesign_gerber_core.copper_geometry as cg\n"
            "assert 'pcbnew' not in sys.modules, 'pcbnew imported transitively'\n"
            "assert 'pcbnew' not in cg.__dict__, 'pcbnew bound in module'\n"
        )
        proc = subprocess.run(
            [_sys.executable, "-c", code],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0,
                         f"copper_geometry pulled pcbnew: {proc.stderr.strip()}")


if __name__ == "__main__":
    unittest.main()
