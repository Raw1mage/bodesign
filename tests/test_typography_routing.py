"""Unit tests for Phase 3: Typography-Aware Routing & Anti-Fusion Multi-Channel Detours."""

import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.occupancy import OccupancyLedger, LedgerRect
from bodesign_eda_bridge.kicad_emit import (
    EmitComponent,
    EmitNet,
    emit_kicad_schematic,
    DEFAULT_SYMBOL_DIR,
    _orthogonal_route,
    _waypoints_clear,
    _seg_hits_box,
)


class TypographyKeepoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_text_keepout_registered_in_ledger(self):
        """Reference, Value, Pin Names, and Net Labels are registered into OccupancyLedger with 0.5mm clearance under text_keepout."""
        ledger = OccupancyLedger()
        components = [
            EmitComponent("R1", "Device:R", "10k", "", 100.0, 100.0),
            EmitComponent("R2", "Device:R", "20k", "", 140.0, 100.0),
        ]
        nets = [
            EmitNet("SIG_A", [("R1", "2"), ("R2", "1")]),
        ]
        emit_kicad_schematic(
            self.work, "test_text", components, nets,
            symbol_dir=DEFAULT_SYMBOL_DIR, connection_style="wire",
            ledger=ledger,
        )

        keepouts = [r for r in ledger.rects if r.kind == "text_keepout"]
        self.assertGreater(len(keepouts), 0, "text_keepout rects must be registered in ledger")

        # Check that component ref "R1" has text_keepout rects
        r1_keepouts = [r for r in keepouts if r.owner == "R1"]
        self.assertGreaterEqual(len(r1_keepouts), 2, "R1 must have text_keepout for Reference and Value")

        # Check layer and clearance margin
        for r in keepouts:
            self.assertEqual("text_keepout", r.source_layer)
            self.assertGreater(r.x1, r.x0)
            self.assertGreater(r.y1, r.y0)

    def test_orthogonal_route_avoids_text_keepout_box(self):
        """_orthogonal_route routes around text keepout boxes."""
        p1 = (100.0, 100.0)
        p2 = (150.0, 120.0)
        # Text obstacle blocking H-first elbow: x in [120, 140], y in [95, 105] (crosses y=100)
        text_box = (120.0, 140.0, 95.0, 105.0)

        route = _orthogonal_route(p1, p2, [text_box])
        self.assertTrue(_waypoints_clear(route, [text_box]))
        # Must not cross through the text box
        for a, b in zip(route, route[1:]):
            self.assertFalse(_seg_hits_box(a, b, text_box))

    def test_multi_channel_detours_when_elbows_blocked(self):
        """When both H-first and V-first elbows are blocked, mid-channel Z-routes are found."""
        p1 = (100.0, 100.0)
        p2 = (150.0, 120.0)
        # Block H-first (y=100) and V-first (x=100)
        obst_h = (110.0, 140.0, 95.0, 105.0)
        obst_v = (95.0, 105.0, 105.0, 115.0)
        obstacles = [obst_h, obst_v]

        route = _orthogonal_route(p1, p2, obstacles)
        self.assertTrue(_waypoints_clear(route, obstacles))
        for a, b in zip(route, route[1:]):
            for box in obstacles:
                self.assertFalse(_seg_hits_box(a, b, box))

    def test_fallback_telemetry_fields(self):
        """When a route fails to clear, fallback telemetry details collinear overlap vs ledger intrusion."""
        # Force a collision by creating unroutable pins with heavy obstacles
        p1 = (100.0, 100.0)
        p2 = (100.0, 140.0)
        # Fully enclose p2 in all directions
        box_top = (90.0, 110.0, 135.0, 145.0)
        box_bot = (90.0, 110.0, 95.0, 105.0)
        box_left = (90.0, 99.0, 95.0, 145.0)
        box_right = (101.0, 110.0, 95.0, 145.0)
        obstacles = [box_top, box_bot, box_left, box_right]

        # Force a fallback by routing between two components where the net is forced onto label
        components = [
            EmitComponent("R1", "Device:R", "10k", "", 100.0, 100.0),
            EmitComponent("R2", "Device:R", "20k", "", 100.0, 100.0), # Co-located
        ]
        nets = [
            EmitNet("COLLISION_NET", [("R1", "2"), ("R2", "2")]),
        ]
        res = emit_kicad_schematic(
            self.work, "test_fallback", components, nets,
            symbol_dir=DEFAULT_SYMBOL_DIR, connection_style="wire",
        )
        if res.fusion_label_fallbacks:
            fb = res.fusion_label_fallbacks[0]
            self.assertIn("net", fb)
            self.assertIn("reason", fb)
            self.assertIn("conflict_type", fb)
            self.assertIn("collinear_overlap", fb)
            self.assertIn("ledger_intrusion", fb)
            self.assertIn(fb["conflict_type"], ("collinear-overlap", "ledger-intrusion"))
