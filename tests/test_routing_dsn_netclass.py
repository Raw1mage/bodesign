"""BR_20260708: Specctra DSN net-class rule injection (pure text surgery, bare-host).

`build_dsn_with_netclasses` rewrites a KiCad-exported DSN's single global rule into
per-class rules so freerouting honours a tight BGA-escape width/clearance for escape
nets while other nets keep their own widths. These tests drive it directly (no pcbnew).
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

# Load routing.py in isolation (its module-level `import pcbnew` is guarded, but the
# package __init__ pulls kiutils-heavy siblings; load the single module directly).
_PKG = "bodesign_eda_bridge"
_ROOT = Path(__file__).resolve().parent.parent / "packages" / "eda-bridge" / _PKG
if _PKG not in sys.modules:
    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [str(_ROOT)]
    sys.modules[_PKG] = pkg
_spec = importlib.util.spec_from_file_location(f"{_PKG}.routing", str(_ROOT / "routing.py"))
routing = importlib.util.module_from_spec(_spec)
sys.modules[f"{_PKG}.routing"] = routing
_spec.loader.exec_module(routing)

build_dsn_with_netclasses = routing.build_dsn_with_netclasses
classify_autoroute_readiness = routing.classify_autoroute_readiness
classify_clearance_violation = routing.classify_clearance_violation

# Minimal KiCad-shaped DSN: um resolution, one global class, three nets.
_DSN = """(pcb board.dsn
  (parser (host_cad KiCad))
  (resolution um 10)
  (structure
    (rule (width 200) (clearance 200))
  )
  (network
    (net "WIFI_QSPI_D0" (pins U1-A1 U2-1))
    (net "HSE" (pins U1-B2 Y1-1))
    (net "GND" (pins U1-C3 C1-2))
    (class kicad_default
      "WIFI_QSPI_D0" "HSE" "GND"
      (circuit
        (use_via Via[0-1]_600:300_um)
      )
      (rule (width 200) (clearance 200))
    )
  )
)
"""


class DsnNetClassTests(unittest.TestCase):
    def test_bga_escape_class_gets_tight_rule(self):
        out = build_dsn_with_netclasses(
            _DSN,
            [{"name": "bga_escape", "width_mm": 0.1, "clearance_mm": 0.1,
              "match": ["WIFI_QSPI", "HSE"]}],
            default_width_mm=0.2, default_clearance_mm=0.2,
        )
        self.assertEqual(out["unit"], "um")
        self.assertEqual(out["total_nets"], 3)
        esc = next(c for c in out["classes"] if c["name"] == "bga_escape")
        # 0.1mm at um resolution = 100 um
        self.assertEqual(esc["width_dsn"], 100)
        self.assertEqual(esc["clearance_dsn"], 100)
        self.assertCountEqual(esc["nets"], ["WIFI_QSPI_D0", "HSE"])
        # GND falls through to the synthesized default class at 0.2mm = 200um
        self.assertEqual(out["default_class"]["nets"], ["GND"])
        self.assertEqual(out["default_class"]["width_dsn"], 200)
        # rewritten DSN carries both a tight and a default rule
        self.assertIn("(width 100)", out["dsn"])
        self.assertIn("(width 200)", out["dsn"])
        self.assertIn("(class bga_escape", out["dsn"])

    def test_first_class_claims_net_ordered(self):
        out = build_dsn_with_netclasses(
            _DSN,
            [{"name": "power", "width_mm": 0.3, "clearance_mm": 0.2, "match": ["GND"]},
             {"name": "catch_all", "width_mm": 0.15, "clearance_mm": 0.15, "match": ["WIFI", "HSE", "GND"]}],
        )
        power = next(c for c in out["classes"] if c["name"] == "power")
        catch = next(c for c in out["classes"] if c["name"] == "catch_all")
        self.assertEqual(power["nets"], ["GND"])          # first class claims GND
        self.assertNotIn("GND", catch["nets"])            # not double-claimed
        self.assertCountEqual(catch["nets"], ["WIFI_QSPI_D0", "HSE"])

    def test_via_token_preserved_for_fanout(self):
        out = build_dsn_with_netclasses(
            _DSN, [{"name": "bga_escape", "width_mm": 0.1, "clearance_mm": 0.1, "match": ["WIFI"]}])
        # the original use_via fanout token is carried into the rewritten class
        self.assertIn("Via[0-1]_600:300_um", out["dsn"])

    def test_empty_class_dropped_with_warning(self):
        out = build_dsn_with_netclasses(
            _DSN, [{"name": "nomatch", "width_mm": 0.1, "clearance_mm": 0.1, "match": ["ZZZ"]}])
        self.assertTrue(any("nomatch" in w for w in out["warnings"]))
        self.assertNotIn("(class nomatch", out["dsn"])
        # all nets land in default
        self.assertEqual(out["default_class"]["count"], 3)

    def test_missing_explicit_net_reported(self):
        out = build_dsn_with_netclasses(
            _DSN, [{"name": "c", "width_mm": 0.1, "clearance_mm": 0.1, "nets": ["DOES_NOT_EXIST"]}])
        self.assertIn("DOES_NOT_EXIST", out["missing_explicit_nets"])

    def test_no_resolution_fails_fast(self):
        with self.assertRaises(ValueError):
            build_dsn_with_netclasses("(pcb x (network (net \"A\" (pins U1-1))))",
                                      [{"name": "c", "width_mm": 0.1, "clearance_mm": 0.1, "match": ["A"]}])

    def test_unsupported_unit_fails_fast(self):
        bad = _DSN.replace("(resolution um 10)", "(resolution furlong 10)")
        with self.assertRaises(ValueError):
            build_dsn_with_netclasses(bad, [{"name": "c", "width_mm": 0.1, "clearance_mm": 0.1, "match": ["HSE"]}])


class AutorouteReadinessTests(unittest.TestCase):
    """BR_20260708 Ask #2: diagnostic route preflight names EXACTLY what is missing."""

    def _probe(self, **kw):
        base = {"jar_present": True, "java_present": True, "xvfb_present": True,
                "awt_headful": True, "display": False}
        base.update(kw)
        return base

    def test_all_present_is_ready(self):
        v = classify_autoroute_readiness(self._probe())
        self.assertTrue(v["ready"])
        self.assertEqual(v["missing"], [])

    def test_headless_jre_not_ready_even_with_xvfb(self):
        # the crash is the missing libawt_xawt.so, not the display
        v = classify_autoroute_readiness(self._probe(awt_headful=False))
        self.assertFalse(v["ready"])
        self.assertIn("full-JRE-libawt_xawt.so", v["missing"])
        self.assertTrue(any("HeadlessException" in r for r in v["remedy"]))

    def test_missing_jar_named(self):
        v = classify_autoroute_readiness(self._probe(jar_present=False))
        self.assertFalse(v["ready"])
        self.assertIn("freerouting.jar", v["missing"])

    def test_no_display_and_no_xvfb_flagged(self):
        v = classify_autoroute_readiness(self._probe(xvfb_present=False, display=False))
        self.assertFalse(v["ready"])
        self.assertIn("xvfb-run-or-DISPLAY", v["missing"])

    def test_real_display_substitutes_for_xvfb(self):
        v = classify_autoroute_readiness(self._probe(xvfb_present=False, display=True))
        self.assertTrue(v["ready"])

    def test_no_java_does_not_double_flag_awt(self):
        # awt check is gated on java_present, so a missing java yields one clean 'java' miss
        v = classify_autoroute_readiness(self._probe(java_present=False, awt_headful=False))
        self.assertIn("java", v["missing"])
        self.assertNotIn("full-JRE-libawt_xawt.so", v["missing"])


class ClearanceViolationClassifyTests(unittest.TestCase):
    """BR_20260708: package-intrinsic pad gaps split from true copper routing errors."""

    def _v(self, vtype, item_refs):
        return {"type": vtype,
                "items": [{"description": f"Pad {i+1} of {r}"} for i, r in enumerate(item_refs)]}

    def test_same_footprint_pad_gap_is_package_intrinsic(self):
        v = self._v("clearance", ["U_IMU", "U_IMU"])
        self.assertEqual(classify_clearance_violation(v), "package_intrinsic")

    def test_cross_part_clearance_is_copper(self):
        v = self._v("clearance", ["R1", "C2"])
        self.assertEqual(classify_clearance_violation(v), "copper")

    def test_non_clearance_copper_stays_copper(self):
        v = self._v("track_dangling", ["U1"])
        self.assertEqual(classify_clearance_violation(v), "copper")

    def test_silk_is_other(self):
        v = self._v("silk_overlap", ["R1", "R2"])
        self.assertEqual(classify_clearance_violation(v), "other")

    def test_pad_adjacency_false_forces_copper(self):
        # if caller declares this footprint has NO intrinsic gap, a same-ref clearance
        # is treated as a real copper error (no silent intrinsic pass)
        v = self._v("clearance", ["J1", "J1"])
        self.assertEqual(classify_clearance_violation(v, pad_adjacency={"J1": False}), "copper")


if __name__ == "__main__":
    unittest.main()
