"""Isolated unit tests for promoted engine seams in kicad_emit.py (Phase 1.2).

Tests isolated functionality of:
- _record_run
- _other_net_segments
- _segments_of
- _guard_route
- _route_clears_ledger
- _assert_no_cross_net_junction
- _place_local_label
- _route_clears_points
"""

import unittest

from bodesign_eda_bridge.occupancy import LedgerRect, OccupancyLedger
from bodesign_eda_bridge.kicad_emit import (
    _assert_no_cross_net_junction,
    _guard_route,
    _other_net_segments,
    _place_local_label,
    _record_run,
    _route_clears_ledger,
    _route_clears_points,
    _segments_of,
    _ROUTE_GUARD_KINDS,
    _PERPENDICULAR_OK_KINDS,
)


class RecordRunTests(unittest.TestCase):
    def test_record_run_accuracy_and_append(self):
        runs = []
        # 3-4-5 right triangle -> hypot is 5.0 mm
        entry = _record_run(0.0, 0.0, 3.0, 4.0, "VCC", runs)
        self.assertEqual(entry, {"net": "VCC", "len_mm": 5.0})
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0], {"net": "VCC", "len_mm": 5.0})

    def test_record_run_horizontal_vertical_zero(self):
        runs = []
        # Horizontal run
        e1 = _record_run(10.0, 5.0, 25.5, 5.0, "CLK", runs)
        self.assertEqual(e1["len_mm"], 15.5)

        # Vertical run
        e2 = _record_run(10.0, 5.0, 10.0, 12.2, "DATA", runs)
        self.assertEqual(e2["len_mm"], 7.2)

        # Zero length run
        e3 = _record_run(10.0, 10.0, 10.0, 10.0, "NC", runs)
        self.assertEqual(e3["len_mm"], 0.0)

        self.assertEqual(len(runs), 3)

    def test_record_run_optional_runs_list(self):
        # When wire_runs is None or omitted, entry is still returned without error
        entry = _record_run(0.0, 0.0, 1.0, 1.0, "TEST", None)
        self.assertEqual(entry["net"], "TEST")
        self.assertEqual(entry["len_mm"], 1.4142)


class SegmentsHelperTests(unittest.TestCase):
    def test_segments_of(self):
        wp = [(0.0, 0.0), (10.0, 0.0), (10.0, 20.0)]
        segs = _segments_of(wp)
        self.assertEqual(segs, [((0.0, 0.0), (10.0, 0.0)), ((10.0, 0.0), (10.0, 20.0))])

    def test_segments_of_degenerate(self):
        self.assertEqual(_segments_of([]), [])
        self.assertEqual(_segments_of([(5.0, 5.0)]), [])

    def test_other_net_segments(self):
        registry = {
            "NET_A": [((0.0, 0.0), (10.0, 0.0))],
            "NET_B": [((20.0, 0.0), (30.0, 0.0))],
            "NET_C": [((40.0, 0.0), (50.0, 0.0))],
        }
        others_a = _other_net_segments("NET_A", registry)
        self.assertEqual(len(others_a), 2)
        self.assertIn(((20.0, 0.0), (30.0, 0.0)), others_a)
        self.assertIn(((40.0, 0.0), (50.0, 0.0)), others_a)

        # Querying a net not in registry returns all segments
        others_unknown = _other_net_segments("NET_X", registry)
        self.assertEqual(len(others_unknown), 3)


class RouteClearsPointsTests(unittest.TestCase):
    def test_route_clears_points_positive(self):
        wp = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        avoid = {(5.0, 5.0), (20.0, 20.0)}
        self.assertTrue(_route_clears_points(wp, avoid))

    def test_route_clears_points_vertex_hit_negative(self):
        wp = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        avoid = {(10.0, 0.0)}
        self.assertFalse(_route_clears_points(wp, avoid))

    def test_route_clears_points_midspan_crossing_allowed(self):
        # BR_20260905 §4.2: a segment passing across a pin point mid-span
        # without placing a VERTEX on it does not connect in KiCad.
        wp = [(0.0, 0.0), (10.0, 0.0)]
        avoid = {(5.0, 0.0)}  # directly on line, but NOT a waypoint vertex
        self.assertTrue(_route_clears_points(wp, avoid))

    def test_route_clears_points_empty_avoid(self):
        wp = [(0.0, 0.0), (10.0, 0.0)]
        self.assertTrue(_route_clears_points(wp, None))
        self.assertTrue(_route_clears_points(wp, []))


class RouteClearsLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = OccupancyLedger()

    def test_route_clears_ledger_clean(self):
        self.ledger.try_reserve(LedgerRect(100.0, 100.0, 110.0, 110.0, "U1", "body"))
        wp = [(0.0, 0.0), (50.0, 0.0)]
        self.assertTrue(_route_clears_ledger(wp, ledger=self.ledger))

    def test_route_clears_ledger_foreign_net_blocked(self):
        # Horizontal wire rect owned by NET_FOREIGN
        self.ledger.try_reserve(LedgerRect(0.0, 9.8, 30.0, 10.2, "NET_FOREIGN", "wire"))
        # Candidate wire along y=10.0
        wp = [(0.0, 10.0), (30.0, 10.0)]
        self.assertFalse(_route_clears_ledger(wp, net_name="NET_LOCAL", ledger=self.ledger))

    def test_route_clears_ledger_own_net_exempt(self):
        # Round 7: wire rect owned by the net's OWN name must not block later segments of same net
        self.ledger.try_reserve(LedgerRect(0.0, 9.8, 30.0, 10.2, "NET_LOCAL", "wire"))
        wp = [(0.0, 10.0), (30.0, 10.0)]
        self.assertTrue(_route_clears_ledger(wp, net_name="NET_LOCAL", ledger=self.ledger))

    def test_route_clears_ledger_host_refs_exempt(self):
        # Pin extent owned by host component U1
        self.ledger.try_reserve(LedgerRect(10.0, 10.0, 15.0, 15.0, "U1", "pin_extent"))
        wp = [(10.0, 12.0), (20.0, 12.0)]
        # Exemption via endpoint_refs
        self.assertTrue(_route_clears_ledger(wp, endpoint_refs=["U1"], ledger=self.ledger))
        # Non-exempt component ref blocks
        self.assertFalse(_route_clears_ledger(wp, endpoint_refs=["U2"], kinds=frozenset({"pin_extent"}), ledger=self.ledger))

    def test_route_clears_ledger_perpendicular_crossing_allowed(self):
        # Round 8: perpendicular crossing of existing wire is allowed
        self.ledger.try_reserve(LedgerRect(0.0, 9.9, 40.0, 10.1, "NET_HORIZ", "wire"))
        # Vertical route crossing at x=20.0
        wp = [(20.0, 0.0), (20.0, 30.0)]
        self.assertTrue(_route_clears_ledger(
            wp,
            net_name="NET_VERT",
            ledger=self.ledger,
            perpendicular_ok_kinds=_PERPENDICULAR_OK_KINDS,
        ))

    def test_route_clears_ledger_label_crossing_rejected(self):
        # Label text box is keepout regardless of angle
        self.ledger.try_reserve(LedgerRect(15.0, 8.0, 25.0, 12.0, "NET_HORIZ", "label"))
        wp = [(20.0, 0.0), (20.0, 30.0)]
        self.assertFalse(_route_clears_ledger(wp, net_name="NET_VERT", ledger=self.ledger))


class CrossNetJunctionAssertionTests(unittest.TestCase):
    def test_assert_no_cross_net_junction_clean(self):
        # Junction on its OWN net's wire -> valid
        junctions = [(10.0, 10.0, "NET_A")]
        registry = {"NET_A": [((0.0, 10.0), (20.0, 10.0))]}
        # Should not raise
        _assert_no_cross_net_junction(junctions, registry)

    def test_assert_no_cross_net_junction_empty(self):
        # Empty junctions or empty registry -> no-op
        _assert_no_cross_net_junction([], {})
        _assert_no_cross_net_junction(None, None)

    def test_assert_no_cross_net_junction_short_detected_batch(self):
        # Junction of NET_A lands on wire of NET_B -> SHORT
        junctions = [(10.0, 10.0, "NET_A")]
        registry = {
            "NET_A": [((10.0, 0.0), (10.0, 10.0))],
            "NET_B": [((0.0, 10.0), (20.0, 10.0))],
        }
        with self.assertRaises(ValueError) as ctx:
            _assert_no_cross_net_junction(junctions, registry)
        self.assertIn("CROSS_NET_JUNCTION_SHORT", str(ctx.exception))
        self.assertIn("'NET_A'", str(ctx.exception))
        self.assertIn("'NET_B'", str(ctx.exception))

    def test_assert_no_cross_net_junction_single_pt_signature(self):
        # Testing the (junction_pt, net_name, junction_registry) signature
        registry = {"NET_B": [((0.0, 10.0), (20.0, 10.0))]}
        with self.assertRaises(ValueError) as ctx:
            _assert_no_cross_net_junction((10.0, 10.0), "NET_A", registry)
        self.assertIn("CROSS_NET_JUNCTION_SHORT", str(ctx.exception))


class GuardRouteTests(unittest.TestCase):
    def test_guard_route_clean_untouched(self):
        base_wp = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        registry = {"OTHER_NET": [((50.0, 50.0), (60.0, 50.0))]}
        guarded, jogged = _guard_route("NET_1", base_wp, fusion_registry=registry)
        self.assertEqual(guarded, base_wp)
        self.assertFalse(jogged)

    def test_guard_route_collinear_collision_jogs(self):
        # NET_1 wants horizontal line y=10.0 from x=0 to 20
        base_wp = [(0.0, 10.0), (20.0, 10.0)]
        # OTHER_NET already has a wire along y=10.0 from x=5 to 15
        registry = {"OTHER_NET": [((5.0, 10.0), (15.0, 10.0))]}

        guarded, jogged = _guard_route("NET_1", base_wp, fusion_registry=registry)
        self.assertTrue(jogged)
        self.assertIsNotNone(guarded)
        # Endpoints must remain preserved
        self.assertEqual(guarded[0], base_wp[0])
        self.assertEqual(guarded[-1], base_wp[-1])
        # Intermediate segment moved off y=10.0
        self.assertNotEqual(guarded[1][1], 10.0)

    def test_guard_route_unroutable_returns_none(self):
        base_wp = [(0.0, 10.0), (20.0, 10.0)]
        # Force extra_ok predicate to reject all candidates
        guarded, jogged = _guard_route("NET_1", base_wp, extra_ok=lambda wp: False)
        self.assertIsNone(guarded)
        self.assertFalse(jogged)

    def test_guard_route_with_obstacles(self):
        base_wp = [(0.0, 0.0), (20.0, 20.0)]
        # Obstacle squarely in the middle
        obstacles = [(5.0, 15.0, 5.0, 15.0)]
        guarded, jogged = _guard_route("NET_1", base_wp, obstacles=obstacles)
        self.assertIsNotNone(guarded)


class PlaceLocalLabelTests(unittest.TestCase):
    def setUp(self):
        self.ledger = OccupancyLedger()

    def test_place_local_label_clean(self):
        blocks = []
        boxes = []
        keepouts = []
        downgrades = []
        wp = [(0.0, 20.0), (30.0, 20.0)]

        cx, cy, box, downgraded = _place_local_label(
            "SPI_CLK", 10.0, 20.0, wp, self.ledger,
            local_label_boxes=boxes,
            label_blocks=blocks,
            text_keepout_boxes=keepouts,
            label_local_downgrades=downgrades,
        )
        self.assertFalse(downgraded)
        self.assertEqual(len(blocks), 1)
        self.assertIn("SPI_CLK", blocks[0])
        self.assertEqual(len(boxes), 1)
        self.assertEqual(len(downgrades), 0)

    def test_place_local_label_nudge_on_collision(self):
        blocks = []
        boxes = []
        keepouts = []
        downgrades = []
        wp = [(0.0, 20.0), (30.0, 20.0)]

        # Place first label at 10.0, 20.0
        _place_local_label(
            "SIG_A", 10.0, 20.0, wp, self.ledger,
            local_label_boxes=boxes,
            label_blocks=blocks,
            text_keepout_boxes=keepouts,
            label_local_downgrades=downgrades,
        )
        # Attempt to place second label at SAME coordinate
        cx, cy, box, downgraded = _place_local_label(
            "SIG_B", 10.0, 20.0, wp, self.ledger,
            local_label_boxes=boxes,
            label_blocks=blocks,
            text_keepout_boxes=keepouts,
            label_local_downgrades=downgrades,
        )
        self.assertFalse(downgraded)
        # It must nudge along the wire away from (10.0, 20.0)
        self.assertNotEqual(cx, 10.0)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(len(boxes), 2)

    def test_place_local_label_downgrade_when_fully_blocked(self):
        blocks = []
        boxes = []
        keepouts = []
        downgrades = []
        wp = [(0.0, 20.0), (30.0, 20.0)]

        # Reserve a huge ledger rect that covers all points along the wire
        self.ledger.try_reserve(LedgerRect(-10.0, 10.0, 50.0, 30.0, "OBSTACLE", "label"))

        cx, cy, box, downgraded = _place_local_label(
            "TRAPPED", 10.0, 20.0, wp, self.ledger,
            local_label_boxes=boxes,
            label_blocks=blocks,
            text_keepout_boxes=keepouts,
            label_local_downgrades=downgrades,
        )
        self.assertTrue(downgraded)
        # Downgrade places at far endpoint wp[-1] = (30.0, 20.0)
        self.assertEqual((cx, cy), (30.0, 20.0))
        self.assertEqual(len(downgrades), 1)
        self.assertEqual(downgrades[0]["net"], "TRAPPED")


if __name__ == "__main__":
    unittest.main()
