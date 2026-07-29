"""BGA escape-capacity gate (BR_20260729 §H).

These lock the parts of the model that a future refactor could silently shift:
the rail/signal split, the "only blocking when nothing else can work" rule, and
the fact that the verdict reports the basis it was computed from.

The pure-geometry parts run anywhere; the board-level ones need pcbnew and skip
without it (host has no pcbnew — run inside the ee worker for full coverage).
"""
import importlib.util
import sys
import unittest
from pathlib import Path

# Load routing.py DIRECTLY rather than via `bodesign_eda_bridge`: the package
# __init__ imports block_drafter -> kiutils, which the host does not have, so a
# plain import would fail to collect this file. Skipping the whole module on that
# ImportError would report "0 tests, OK" — 0 coverage masquerading as clean, the
# very thing BR_20260729 L10 exists to stop. routing.py has no module-level
# relative imports (its `from .preplace import` calls live inside functions), so
# it loads standalone and the pure-geometry tests run everywhere.
_REPO = Path(__file__).resolve().parents[1]
_MOD = _REPO / "packages/eda-bridge/bodesign_eda_bridge/routing.py"
_spec = importlib.util.spec_from_file_location("_routing_under_test", _MOD)
_routing = importlib.util.module_from_spec(_spec)
sys.modules["_routing_under_test"] = _routing
_spec.loader.exec_module(_routing)

_is_power_net = _routing._is_power_net


class RailClassification(unittest.TestCase):
    """Calibrated against aiguard U1, where getting this wrong moved the budget by 7."""

    def test_plain_rails(self):
        for n in ("GND", "AGND", "DGND", "PGND", "VSS", "VCC", "VBAT", "VSYS"):
            self.assertTrue(_is_power_net(n), n)

    def test_numeric_rails_with_optional_sign(self):
        for n in ("+3V3", "+1V8", "3V3", "5V", "+12V"):
            self.assertTrue(_is_power_net(n), n)

    def test_suffixed_rails_are_still_rails(self):
        # VDDA is the analog rail: 6 balls on U1. Misreading it as signal inflated
        # the escape need from 167 to 172.
        for n in ("VDDA", "VDDCORE", "AVDD", "DVDD"):
            self.assertTrue(_is_power_net(n), n)

    def test_signal_suffix_beats_the_rail_stem(self):
        # VBUS_DET mentions a rail but is a detect line — 1 ball on U1, and
        # counting it as a rail under-reported the need.
        for n in ("VBUS_DET", "VSYS_SENSE", "VDD_EN", "VBAT_MON", "VCC_PG"):
            self.assertFalse(_is_power_net(n), n)

    def test_ordinary_signals(self):
        for n in ("USB_DP", "SD1_CLK", "HSE_IN", "GPIO_SPARE6", "PWR_EN",
                  "unconnected-(U1-PDR_ON-PadA1)"):
            self.assertFalse(_is_power_net(n), n)

    def test_empty_is_not_a_rail(self):
        self.assertFalse(_is_power_net(""))


def _has_pcbnew() -> bool:
    try:
        import pcbnew  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_pcbnew(), "needs pcbnew (run in the ee worker)")
class AgainstTheRealBoard(unittest.TestCase):
    """Anchored to the aiguard C04 board that motivated the gate."""

    BOARD = "/work/experiments/aiguard_c04/ccm_det_f.kicad_pcb"
    FANNED = "/work/experiments/aiguard_c04/ccm_det_f_vip.kicad_pcb"

    def _u1(self, res):
        return next(p for p in res["parts"] if p["ref"] == "U1")

    def setUp(self):
        import os
        if not os.path.exists(self.BOARD):
            self.skipTest("aiguard fixture board not present")
        from bodesign_eda_bridge.routing import bga_escape_capacity
        self.fn = bga_escape_capacity

    def test_reproduces_the_167_vs_144_shortfall(self):
        u1 = self._u1(self.fn(self.BOARD))
        self.assertEqual(u1["signal_balls"], 167)
        self.assertEqual(u1["perimeter_channels"], 72)
        self.assertEqual(u1["capacity"], 144)
        self.assertTrue(u1["blocking"])

    def test_power_planes_do_not_count_as_signal_layers(self):
        res = self.fn(self.BOARD)
        self.assertEqual(res["copper_layers"], ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
        self.assertEqual(res["signal_layers"], ["F.Cu", "B.Cu"])
        self.assertEqual(res["power_layers"], ["In1.Cu", "In2.Cu"])

    def test_fanout_alone_does_not_clear_it_when_inner_layers_are_planes(self):
        # The instructive case: 128 vias exist, but they land on power planes.
        u1 = self._u1(self.fn(self.FANNED))
        self.assertGreater(u1["fanout_vias"], 0)
        self.assertEqual(u1["inner_signal_layers"], [])
        self.assertFalse(u1["has_escape_route"])
        self.assertTrue(u1["blocking"])

    def test_fanout_via_count_uses_the_shared_extent_not_the_silkscreen_bbox(self):
        # BR_20260729 §E regression: with fp.GetBoundingBox() the silkscreen frame
        # swept in neighbours' vias and U2/U3 (24 pads each) both reported 29.
        res = self.fn(self.FANNED)
        for ref in ("U2", "U3"):
            p = next(x for x in res["parts"] if x["ref"] == ref)
            self.assertLess(p["fanout_vias"], 5, f"{ref} swept in neighbours' vias")

    def test_coarse_pitch_parts_are_not_blocked(self):
        res = self.fn(self.BOARD)
        for ref in ("U2", "U3"):
            p = next(x for x in res["parts"] if x["ref"] == ref)
            self.assertFalse(p["blocking"], f"{ref} 1.0mm pitch has room")

    def test_verdict_reports_how_it_classified(self):
        u1 = self._u1(self.fn(self.BOARD))
        self.assertEqual(u1["classification"], "heuristic")
        self.assertIn("VDDA", u1["power_nets"])
        self.assertIn("USB_DP", u1["signal_nets"])

    def test_caller_can_override_the_rail_list(self):
        res = self.fn(self.BOARD, power_nets=["GND", "+1V8", "+3V3", "VDDA"])
        u1 = self._u1(res)
        self.assertEqual(u1["classification"], "caller_supplied")
        self.assertEqual(u1["signal_balls"], 167)

    def test_blocking_part_gets_an_action_not_just_a_refusal(self):
        u1 = self._u1(self.fn(self.BOARD))
        self.assertGreaterEqual(u1["suggested_signal_layers"], 3)
        self.assertIn("re-placing will not fix this", u1["reason"])

    def test_optimistic_traces_per_gap_is_used_but_the_computed_one_is_reported(self):
        # At 0.22mm gap the nominal rules give 0, which would fail every fine-pitch
        # board on paper. The gate uses 1 and shows its work instead.
        u1 = self._u1(self.fn(self.BOARD))
        self.assertEqual(u1["traces_per_gap_used"], 1)
        self.assertEqual(u1["traces_per_gap_computed"], 0)

    def test_explicit_traces_per_gap_is_honoured(self):
        u1 = self._u1(self.fn(self.BOARD, traces_per_gap=2))
        self.assertEqual(u1["capacity"], 72 * 2 * 2)
        self.assertFalse(u1["blocking"], "288 >= 167")

    def test_optimistic_floor_is_flagged_as_an_advisory(self):
        # round=12: `computed 0` was already in the payload, but a caller kept two rings
        # on the surface and lost 50 minutes of routing before deriving what it meant.
        u1 = self._u1(self.fn(self.BOARD, track_mm=0.116, clearance_mm=0.15))
        self.assertEqual(u1["traces_per_gap_computed"], 0)
        self.assertEqual(u1["traces_per_gap_used"], 1)
        text = " ".join(u1["advisories"])
        self.assertIn("surface_escape_infeasible", text)
        self.assertIn("0.416mm", text, "must show the width the rules actually need")
        self.assertIn("0.22mm", text, "must show the gap it is compared against")

    def test_advisory_does_not_prescribe_a_ring_count(self):
        # Fewer surface rings is only viable if the inner layers have the capacity,
        # which this gate does not evaluate — it must not read as an instruction.
        u1 = self._u1(self.fn(self.BOARD, track_mm=0.116, clearance_mm=0.15))
        text = " ".join(u1["advisories"])
        self.assertIn("only viable if", text)
        self.assertNotIn("keep_rings=1", text)

    def test_advisory_is_silent_when_the_rules_actually_fit(self):
        u1 = self._u1(self.fn(self.BOARD, track_mm=0.03, clearance_mm=0.03))
        self.assertGreaterEqual(u1["traces_per_gap_computed"], u1["traces_per_gap_used"])
        self.assertNotIn("advisories", u1)

    def test_advisory_never_flips_the_verdict(self):
        # The optimistic floor is what keeps this gate from refusing boards fabs
        # build every day; the advisory explains it, it does not enforce it.
        res = self.fn(self.BOARD, track_mm=0.116, clearance_mm=0.15)
        u1 = self._u1(res)
        self.assertTrue(u1["blocking"], "4-layer shortfall stands on its own merits")
        self.assertIn("re-placing will not fix this", u1["reason"])
        self.assertTrue(res["advisories"], "top level aggregates per-part advisories")


@unittest.skipUnless(_has_pcbnew(), "needs pcbnew (run in the ee worker)")
class BoardLoading(unittest.TestCase):
    """BR_20260729 §H: pcbnew.LoadBoard returns None for a missing path instead of
    raising, and the next pcbnew call dereferences that null BOARD* — the worker dies
    with SIGSEGV (exit 139), so the caller sees a dropped connection, not an error.
    Measured: LoadBoard('ccm8_vip.kicad_pcb') -> None, ExportSpecctraDSN(None, dsn) -> 139.
    """

    BOARD = "/work/experiments/aiguard_c04/ccm_det_f.kicad_pcb"

    def setUp(self):
        self.load = _routing._load_board

    def test_missing_path_raises_instead_of_returning_none(self):
        with self.assertRaises(FileNotFoundError) as cm:
            self.load("definitely_not_a_board.kicad_pcb")
        self.assertIn("BOARD_NOT_FOUND", str(cm.exception))

    def test_error_shows_where_a_relative_path_resolved_to(self):
        # The trigger in the wild: a caller passes a path relative to THEIR cwd,
        # which resolves against the worker's. Naming both ends the guesswork.
        import os
        with self.assertRaises(FileNotFoundError) as cm:
            self.load("ccm8_vip.kicad_pcb")
        msg = str(cm.exception)
        self.assertIn(os.path.abspath("ccm8_vip.kicad_pcb"), msg)
        self.assertIn(os.getcwd(), msg)

    def test_unreadable_board_is_refused_rather_than_handed_on_as_null(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as fh:
            fh.write("not a kicad board\n")
            junk = fh.name
        try:
            with self.assertRaises((RuntimeError, Exception)) as cm:
                self.load(junk)
            self.assertNotIsInstance(cm.exception, FileNotFoundError)
        finally:
            import os
            os.unlink(junk)

    def test_a_real_board_still_loads(self):
        import os
        if not os.path.exists(self.BOARD):
            self.skipTest("aiguard fixture board not present")
        board = self.load(self.BOARD)
        self.assertIsNotNone(board)
        self.assertGreater(len(board.GetFootprints()), 0)

    def test_no_call_site_bypasses_the_guard(self):
        # A future call site added with the raw API reintroduces the segfault, so
        # assert the module holds no direct uses outside the helper itself.
        src = _MOD.read_text().splitlines()
        helper = [i for i, ln in enumerate(src) if ln.startswith("def _load_board")][0]
        end = next(i for i, ln in enumerate(src[helper + 1:], helper + 1)
                   if ln and not ln[0].isspace())
        outside = [f"{i + 1}: {ln.strip()}" for i, ln in enumerate(src)
                   if "pcbnew.LoadBoard(" in ln and not (helper <= i < end)]
        self.assertEqual(outside, [], "use _load_board() — raw LoadBoard segfaults on None")


if __name__ == "__main__":
    unittest.main(verbosity=2)
