"""Router via authorisation vs ball pitch (BR_20260729 §K).

The lock that cost a consumer four rounds: on an 8-layer board with 4 signal
layers, `bga_escape_capacity` reported `blocking:false` with a 1.7x capacity
margin — but that margin multiplies by `len(signal_layers)`, which PRESUMES the
router can change layer. It changes layer by opening a via, and it may only open
the one its Default netclass authorises. That was 0.6mm against a 0.5mm ball
pitch: zero edge-to-edge gap, so no via could be opened inside the grid and the
inner layers were unreachable. Symptom: B.Cu carrying 10% of segments, 282 vias
all F.Cu-B.Cu through-hole, and a netclass width experiment that "did nothing"
because every class inherited the same 0.6mm via.

Two independent facts had to be visible and were not:
  * what the ROUTER may create (netclass rule) — vs what is already on the board
    (via-in-pad geometry). via_in_pad writes objects and never touches the rule,
    so 168 0.3mm vias coexisted with a 0.6mm authorisation.
  * whether a `use_via` override names a padstack the DSN actually DECLARES —
    freerouting silently ignores an unknown one, indistinguishable from success.

Pure-function tests run on the host; board-level ones need pcbnew and skip.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MOD = _REPO / "packages/eda-bridge/bodesign_eda_bridge/routing.py"
_spec = importlib.util.spec_from_file_location("_routing_via_under_test", _MOD)
_routing = importlib.util.module_from_spec(_spec)
sys.modules["_routing_via_under_test"] = _routing
_spec.loader.exec_module(_routing)

_build = _routing.build_dsn_with_netclasses

_DSN = """(pcb test
  (resolution um 10)
  (structure
    (layer F.Cu (type signal))
    (layer B.Cu (type signal))
  )
  (library
    (padstack "Via[0-7]_600:300_um" (shape (circle F.Cu 600)))
    (padstack "Via[0-7]_300:150_um" (shape (circle F.Cu 300)))
  )
  (network
    (net "+3V3" (pins U1-A1 U1-A2))
    (net "USB_DP" (pins U1-B1 J1-1))
    (net "BOOT0" (pins U1-C1))
    (class kicad_default "+3V3" USB_DP BOOT0
      (circuit
        (use_via "Via[0-7]_600:300_um")
      )
      (rule
        (width 2000)
        (clearance 2000)
      )
    )
  )
)
"""


class ViaOverridePerClass(unittest.TestCase):
    """The per-class `via` key existed but was undocumented and unreported."""

    def test_named_class_via_override_is_emitted_and_reported(self):
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": '"Via[0-7]_300:150_um"'}])
        self.assertIn('(use_via "Via[0-7]_300:150_um")', out["dsn"])
        self.assertEqual(out["used_vias"]["escape"], '"Via[0-7]_300:150_um"')
        esc = next(c for c in out["classes"] if c["name"] == "escape")
        self.assertEqual(esc["via"], '"Via[0-7]_300:150_um"')

    def test_without_override_class_inherits_the_harvested_via(self):
        """Back-compat: the board's own via is preserved when nothing is asked for."""
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116,
                             "clearance_mm": 0.15, "match": ["USB"]}])
        self.assertEqual(out["used_vias"]["escape"], '"Via[0-7]_600:300_um"')


class DefaultClassCanBeGivenAVia(unittest.TestCase):
    """The fall-through class was the one that could NOT be overridden.

    Named classes each accepted a `via`; the synthesized default was stranded on
    the harvested value. The nets nobody claims are exactly the ones a caller
    forgets — on the recorded board that was BOOT0/NRST/SWCLK/SWDIO, which sit in
    the BGA interior and would have needed the small via most.
    """

    def test_default_via_reaches_the_fall_through_class(self):
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": '"Via[0-7]_300:150_um"'}],
                     default_via='"Via[0-7]_300:150_um"')
        self.assertEqual(out["default_class"]["via"], '"Via[0-7]_300:150_um"')
        self.assertEqual(out["used_vias"]["kicad_default"], '"Via[0-7]_300:150_um"')
        # both classes now authorise the small via
        self.assertEqual(out["dsn"].count('(use_via "Via[0-7]_300:150_um")'), 2)

    def test_default_class_still_inherits_when_default_via_omitted(self):
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": '"Via[0-7]_300:150_um"'}])
        self.assertEqual(out["default_class"]["via"], '"Via[0-7]_600:300_um"')

    def test_named_override_does_not_leak_into_the_default_class(self):
        """Discrimination: a per-class override must not silently become global."""
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": '"Via[0-7]_300:150_um"'}])
        self.assertNotEqual(out["default_class"]["via"], '"Via[0-7]_300:150_um"')


class UndeclaredViaIsReported(unittest.TestCase):
    """freerouting IGNORES a use_via naming an unknown padstack — silently.

    Without this check, a typo'd override is indistinguishable from a honoured
    one: the DSN contains the line, freerouting drops it, and the caller reads
    the unchanged routing result as "the via was not the bottleneck".
    """

    def test_typo_is_named_in_warnings_and_undeclared_vias(self):
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": '"Via[0-7]_250:100_um"'}])
        self.assertIn('"Via[0-7]_250:100_um"', out["undeclared_vias"])
        self.assertTrue(any("undeclared via padstack" in w for w in out["warnings"]))
        self.assertTrue(any("IGNORES" in w for w in out["warnings"]))

    def test_declared_vias_lists_what_this_dsn_offers(self):
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116,
                             "clearance_mm": 0.15, "match": ["USB"]}])
        self.assertEqual(out["declared_vias"],
                         ["Via[0-7]_300:150_um", "Via[0-7]_600:300_um"])

    def test_a_valid_override_produces_no_undeclared_warning(self):
        """Reverse discrimination: the check must be SILENT on a correct name.

        A warning that fires on every override would be noise and get ignored,
        which is how the real signal gets lost.
        """
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": '"Via[0-7]_300:150_um"'}],
                     default_via='"Via[0-7]_300:150_um"')
        self.assertEqual(out["undeclared_vias"], [])
        self.assertFalse(any("undeclared" in w for w in out["warnings"]))

    def test_quoting_does_not_change_the_verdict(self):
        """A caller writing the name bare must not be told it is undeclared."""
        out = _build(_DSN, [{"name": "escape", "width_mm": 0.116, "clearance_mm": 0.15,
                             "match": ["USB"], "via": "Via[0-7]_300:150_um"}])
        self.assertEqual(out["undeclared_vias"], [])


try:
    import pcbnew  # noqa: F401
    _HAVE_PCBNEW = True
except Exception:
    _HAVE_PCBNEW = False


@unittest.skipUnless(_HAVE_PCBNEW, "pcbnew unavailable on host — run in the ee worker")
class RouterViaBudgetOnRealBoard(unittest.TestCase):
    """The board-level half: what may the router open, and does it fit the grid?"""

    def _board(self):
        import pcbnew
        for p in ("/work/experiments/aiguard_c04/ccm8_pin_vip.kicad_pcb",
                  str(_REPO / "experiments/aiguard_c04/ccm8_pin_vip.kicad_pcb")):
            if Path(p).exists():
                return pcbnew.LoadBoard(p)
        self.skipTest("aiguard fixture board not present in this worker")

    def test_reports_rule_not_geometry(self):
        """The recorded board: 0.3mm vias present, 0.6mm authorised.

        These are different facts and both must be visible; reading only the
        geometry would say "small vias exist, all good".
        """
        b = self._board()
        rep = _routing.router_via_budget(b, 0.5)
        self.assertEqual(rep["router_via_mm"], 0.6)
        self.assertFalse(rep["fits_in_ball_grid"])
        self.assertEqual(rep["via_gap_mm"], -0.1)
        self.assertIn("0.3", rep["existing_via_mm_counts"])
        self.assertFalse(rep["router_via_matches_existing"])

    def test_fits_when_pitch_exceeds_the_authorised_via(self):
        """Reverse discrimination: a coarse-pitch part must NOT be flagged.

        Without this, a check that always reports "does not fit" would look like
        it were working while carrying no information.
        """
        b = self._board()
        rep = _routing.router_via_budget(b, 1.0)
        self.assertTrue(rep["fits_in_ball_grid"])
        self.assertEqual(rep["via_gap_mm"], 0.4)


if __name__ == "__main__":
    unittest.main()
