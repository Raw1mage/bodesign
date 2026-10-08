"""Tests for bodesign_c04_routing_gate (R-01..R-07).

R-07 fixtures replace the fixture's B.Cu fill with a dumbbell (two blocks + a straight neck of chosen width).

Fixture tests/fixtures/c04_routing_gate/routed.kicad_pcb: 30x20 mm, 2 copper layers, PWR/SIG/GND nets, PWR tracks 0.5 mm with
two vias on F.Cu<->B.Cu, one SIG track 0.2 mm, a GND B.Cu pour touched by TP1. Every negative control is ONE textual
mutation of that file (anchor must occur exactly once).
"""
import json
import os
import shutil
import tempfile
import unittest

from bodesign_eda_bridge import c04_routing as rt
from bodesign_eda_bridge.c04_gate import C04GateInputError
from bodesign_eda_bridge.c04_routing import c04_routing_gate

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "c04_routing_gate")
BOARD = os.path.join(FX, "routed.kicad_pcb")
CLASSES = {"Power": {"nets": ["PWR"], "min_track_width_mm": 0.5, "min_vias_per_transition": 2},
           "Sig": {"nets": ["SIG"], "min_track_width_mm": 0.2},
           "Gnd": {"nets": ["GND"], "min_track_width_mm": 0.2}}
KO = [{"name": "KO-1", "x": 10.6, "y": 4.0, "w": 2.0, "h": 2.0}]
SPEC = [os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/" + n)
        for n in ("btdongle_c04-v4.kicad_pcb", "btdongle_c04-v3.kicad_pcb", ".history/btdongle_c04-v3.kicad_pcb")]


def _text() -> str:
    with open(BOARD, encoding="utf-8") as fh:
        return fh.read()


def mutate(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"mutation anchor {old!r} found {text.count(old)}x"
    return text.replace(old, new)


VIA9 = '(via (at 9 8) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 1) (uuid "c04c0000-0000-4000-8000-000000000a01"))'
B02 = '(segment (start 4.5 6) (end 4.5 8) (width 0.5)'
B01 = '(segment (start 4.5 5) (end 4.5 6) (width 0.5)'
FILL = '(filled_polygon (layer "B.Cu") (pts (xy 16 9) (xy 29 9) (xy 29 19) (xy 16 19)))'
ZONE = '(zone (net 3) (net_name "GND")'
R2P2 = '(pad "2" smd rect (at 0.5 0) (size 0.6 0.6) (layers "F.Cu") (net 3 "GND")'
SEG45 = ('(segment (start 15.3 5.1) (end 16.3 6.1) (width 0.2) (layer "F.Cu") (net 3) '
         '(uuid "c04c0000-0000-4000-8000-000000000b98"))\n\t')


def dumbbell(half_neck: float) -> str:
    h = half_neck
    pts = [(16, 9), (20, 9), (20, 14 - h), (22, 14 - h), (22, 9), (29, 9), (29, 19), (22, 19), (22, 14 + h), (20, 14 + h), (20, 19), (16, 19)]
    return '(filled_polygon (layer "B.Cu") (pts ' + " ".join(f"(xy {x} {y})" for x, y in pts) + "))"


SEG30 = ('(segment (start 15.3 5.2) (end 16.166 5.7) (width 0.2) (layer "F.Cu") (net 3) '
         '(uuid "c04c0000-0000-4000-8000-000000000b99"))\n\t')


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache")
        os.makedirs(base, exist_ok=True)
        cls.root = tempfile.mkdtemp(prefix="c04rt-", dir=base)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def board(self, name: str, text: str) -> str:
        p = os.path.join(self.root, name + ".kicad_pcb")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def run_gate(self, path: str = BOARD, **kw):
        kw.setdefault("classes", CLASSES)
        return c04_routing_gate(path, **kw)


class PositiveControl(Base):
    def test_all_measured_gates_pass_and_ok(self):
        r = self.run_gate(keepouts=KO, keepout_margin_mm=0.4)
        for g in ("R-01", "R-02", "R-03", "R-04", "R-06", "R-07"):
            self.assertEqual(r["gates"][g]["status"], "pass", (g, r["gates"][g]))
            self.assertEqual(r["gates"][g]["offenders"], [], g)
        self.assertEqual(r["gates"]["R-05"]["status"], "unmeasured")
        self.assertTrue(r["ok"])
        # R-08 is unmeasured here: CLASSES declares no clearance_mm, and the fixture is routed (informational mode)
        self.assertEqual(r["unmeasured_gates"], ["R-05", "R-08"])
        self.assertEqual(r["gates"]["R-01"]["measured"]["segments_examined"], 6)
        self.assertGreater(r["gates"]["R-03"]["measured"]["endpoints_examined"], 0)
        self.assertEqual(r["gates"]["R-04"]["measured"]["zones_examined"][0]["islands"], 0)
        self.assertEqual(len(r["inputs"]["board_sha256"]), 64)

    def test_ok_false_while_r06_unmeasured(self):
        r = self.run_gate()
        self.assertEqual(r["gates"]["R-06"]["status"], "unmeasured")
        self.assertFalse(r["ok"])
        self.assertIn("R-06", r["unmeasured_gates"])

    def test_declared_pairs_pass_and_gate_ok(self):
        r = self.run_gate(keepouts=KO, keepout_margin_mm=0.4,
                          pairs=[{"a": "PWR", "b": "SIG", "max_len_mm": 20, "max_skew_mm": 20}])
        self.assertEqual(r["gates"]["R-05"]["status"], "pass")
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["gates"]["R-05"]["measured"]["pairs"][0]["len_a_mm"], 16.0, places=3)


class R01Width(Base):
    def test_narrow_power_track_fails_with_offender_fields(self):
        p = self.board("narrow", mutate(_text(), B02, B02.replace("0.5", "0.26")))
        g = self.run_gate(p)["gates"]["R-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(len(g["offenders"]), 1)
        o = g["offenders"][0]
        self.assertEqual((o["net"], o["class"], o["layer"], o["width"]), ("PWR", "Power", "F.Cu", 0.26))
        self.assertEqual(o["length"], 2.0)
        self.assertEqual(o["at"], [4.5, 6.0])

    def test_declared_escape_neck_is_listed_not_failed(self):
        p = self.board("neck", mutate(_text(), B01, B01.replace("0.5", "0.26")))
        g = self.run_gate(p, escape_exemptions=[{"ref": "R1", "max_length_mm": 1.0}])["gates"]["R-01"]
        self.assertEqual(g["status"], "pass", g["offenders"])
        self.assertEqual([n["ref"] for n in g["measured"]["exempt_necks"]], ["R1"])

    def test_undeclared_or_too_long_neck_still_fails(self):
        p = self.board("neck2", mutate(_text(), B01, B01.replace("0.5", "0.26")))
        self.assertEqual(self.run_gate(p)["gates"]["R-01"]["status"], "fail")
        g = self.run_gate(p, escape_exemptions=[{"ref": "R1", "max_length_mm": 0.5}])["gates"]["R-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["measured"]["exempt_necks"], [])

    def test_exemption_for_unknown_ref_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "refs not on the board"):
            self.run_gate(escape_exemptions=[{"ref": "ZZ9", "max_length_mm": 1.0}])


class R02Vias(Base):
    def test_single_via_transition_fails(self):
        p = self.board("onevia", mutate(_text(), VIA9, ""))
        g = self.run_gate(p)["gates"]["R-02"]
        self.assertEqual(g["status"], "fail")
        o = g["offenders"][0]
        self.assertEqual((o["net"], o["from"], o["to"], o["vias"], o["required"]), ("PWR", "F.Cu", "B.Cu", 1, 2))

    def test_no_class_declares_a_via_rule_is_unmeasured(self):
        cl = {k: {kk: vv for kk, vv in v.items() if kk != "min_vias_per_transition"} for k, v in CLASSES.items()}
        g = self.run_gate(classes=cl)["gates"]["R-02"]
        self.assertEqual(g["status"], "unmeasured")

    def test_class_rules_override_adds_via_rule(self):
        cl = {k: {kk: vv for kk, vv in v.items() if kk != "min_vias_per_transition"} for k, v in CLASSES.items()}
        p = self.board("onevia2", mutate(_text(), VIA9, ""))
        g = self.run_gate(p, classes=cl, class_rules={"Power": {"min_vias_per_transition": 2}})["gates"]["R-02"]
        self.assertEqual(g["status"], "fail")


class R03EntryAngle(Base):
    def test_30_degree_pad_entry_fails_with_angle(self):
        p = self.board("acid", mutate(_text(), ZONE, SEG30 + ZONE))
        g = self.run_gate(p)["gates"]["R-03"]
        self.assertEqual(g["status"], "fail")
        o = g["offenders"][0]
        self.assertEqual((o["ref"], o["pad"], o["net"], o["layer"]), ("R2", "2", "GND", "F.Cu"))
        self.assertAlmostEqual(o["angle"], 30.0, places=1)
        self.assertEqual(g["measured"]["teardrop_fixed"], [])

    def test_default_threshold_is_45_and_45_degree_entry_passes(self):
        self.assertEqual(rt.DEFAULT_ENTRY_ANGLE_DEG, 45.0)
        p = self.board("deg45", mutate(_text(), ZONE, SEG45 + ZONE))
        g = self.run_gate(p)["gates"]["R-03"]
        self.assertEqual(g["status"], "pass", g["offenders"])
        self.assertEqual(g["measured"]["min_entry_angle_deg"], 45.0)
        g2 = self.run_gate(p, min_entry_angle_deg=75)["gates"]["R-03"]
        self.assertEqual(g2["status"], "fail")
        self.assertAlmostEqual(g2["offenders"][0]["angle"], 45.0, places=1)

    def test_threshold_is_configurable(self):
        p = self.board("acid2", mutate(_text(), ZONE, SEG30 + ZONE))
        self.assertEqual(self.run_gate(p, min_entry_angle_deg=25)["gates"]["R-03"]["status"], "pass")

    def test_unsupported_pad_shape_is_unmeasured_not_pass(self):
        t = mutate(_text(), ZONE, SEG30 + ZONE)
        t = mutate(t, R2P2, R2P2.replace("smd rect", "smd trapezoid"))
        g = self.run_gate(self.board("trap", t))["gates"]["R-03"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("trapezoid", g["measured"]["unmeasured_endpoints"][0]["reason"])


class R04Islands(Base):
    ISL = '\n\t\t(filled_polygon (layer "B.Cu") (pts (xy 2 12) (xy 4 12) (xy 4 14) (xy 2 14)))'

    def test_stranded_island_fails_with_area_and_centroid(self):
        p = self.board("island", mutate(_text(), FILL, FILL + self.ISL))
        g = self.run_gate(p)["gates"]["R-04"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(len(g["offenders"]), 1)
        o = g["offenders"][0]
        self.assertEqual((o["net"], o["layer"]), ("GND", "B.Cu"))
        self.assertAlmostEqual(o["area_mm2"], 4.0, places=3)
        self.assertEqual(o["centroid"], [3.0, 13.0])

    def test_area_threshold_tolerates_small_island(self):
        p = self.board("island2", mutate(_text(), FILL, FILL + self.ISL))
        self.assertEqual(self.run_gate(p, max_island_area_mm2=5.0)["gates"]["R-04"]["status"], "pass")

    def test_unfilled_zone_is_unmeasured_never_pass(self):
        p = self.board("nofill", mutate(_text(), FILL, ""))
        g = self.run_gate(p)["gates"]["R-04"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("not filled", g["measured"]["unmeasured_items"][0]["reason"])


class R07PourNeck(Base):
    def test_pinched_neck_fails_with_fields(self):
        p = self.board("neck01", mutate(_text(), FILL, dumbbell(0.05)))
        g = self.run_gate(p)["gates"]["R-07"]
        self.assertEqual(g["status"], "fail", g)
        o = g["offenders"][0]
        self.assertEqual((o["net"], o["layer"], o["min_width"]), ("GND", "B.Cu", 0.2))
        self.assertAlmostEqual(o["neck_width"], 0.1, places=3)
        self.assertAlmostEqual(o["location"][1], 14.0, places=2)
        self.assertTrue(20.0 <= o["location"][0] <= 22.0)

    def test_same_fill_with_wide_neck_passes(self):
        p = self.board("neck03", mutate(_text(), FILL, dumbbell(0.15)))
        g = self.run_gate(p)["gates"]["R-07"]
        self.assertEqual(g["status"], "pass", g["offenders"])

    def test_threshold_follows_class_min_width(self):
        p = self.board("neckcls", mutate(_text(), FILL, dumbbell(0.15)))
        cl = {**CLASSES, "Gnd": {"nets": ["GND"], "min_track_width_mm": 0.5}}
        self.assertEqual(self.run_gate(p, classes=cl)["gates"]["R-07"]["status"], "fail")

    def test_fully_rectangular_fill_has_no_neck(self):
        g = self.run_gate()["gates"]["R-07"]
        self.assertEqual(g["status"], "pass")
        self.assertGreater(g["measured"]["zones_examined"][0]["edges"], 0)

    def test_unfilled_zone_is_unmeasured(self):
        g = self.run_gate(self.board("nofill7", mutate(_text(), FILL, "")))["gates"]["R-07"]
        self.assertEqual(g["status"], "unmeasured")

    def test_failing_neck_makes_ok_false(self):
        p = self.board("neck_ok", mutate(_text(), FILL, dumbbell(0.05)))
        self.assertFalse(self.run_gate(p, keepouts=KO, keepout_margin_mm=0.4)["ok"])


def _mini_board(pads: str, extra: str = "", at: str = "10 10") -> str:
    return ('(kicad_pcb\n\t(version 20241229)\n\t(generator "pcbnew")\n\t(layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))\n'
            '\t(net 0 "")\n\t(net 1 "GND")\n\t(net 2 "SIG")\n'
            f'\t(footprint "X:Y" (layer "F.Cu") (uuid "c04c0000-0000-4000-8000-0000000000e1") (at {at})\n'
            '\t\t(property "Reference" "U9" (at 0 -2 0) (layer "F.SilkS") (uuid "c04c0000-0000-4000-8000-0000000001e1") (effects (font (size 1 1) (thickness 0.15))))\n'
            f'{pads}\n\t)\n{extra}\n)\n')


CUSTOM = ('\t\t(pad "1" smd custom (at 0 0) (size 1.0 0.6) (layers "F.Cu") (net 1 "GND") (options (clearance outline) (anchor rect))\n'
          '\t\t\t(primitives (gr_poly (pts (xy 0 -0.3) (xy 1.0 -0.3) (xy 1.0 0.3) (xy 0 0.3)) (width 0) (fill yes)))\n'
          '\t\t\t(uuid "c04c0000-0000-4000-8000-0000000003e1"))')


def _seg(a: str, b: str) -> str:
    return f'\t(segment (start {a}) (end {b}) (width 0.2) (layer "F.Cu") (net 1) (uuid "c04c0000-0000-4000-8000-000000000be1"))'


class R03CustomPad(Base):
    def test_custom_pad_30_degree_entry_fails(self):
        # union outline right edge is x=1.0 (vertical); direction (0.5, 0.866) is 30 deg from it
        p = self.board("cust30", _mini_board(CUSTOM, _seg("10.95 9.75", "12.45 12.348")))
        g = self.run_gate(p)["gates"]["R-03"]
        self.assertEqual(g["status"], "fail", g)
        o = g["offenders"][0]
        self.assertEqual((o["ref"], o["pad"], o["net"]), ("U9", "1", "GND"))
        self.assertAlmostEqual(o["angle"], 30.0, delta=1.0)
        self.assertEqual(g["measured"]["unmeasured_endpoints"], [])

    def test_custom_pad_90_degree_entry_passes(self):
        p = self.board("cust90", _mini_board(CUSTOM, _seg("10.5 10", "13 10")))
        g = self.run_gate(p)["gates"]["R-03"]
        self.assertEqual(g["status"], "pass", g)
        self.assertEqual(g["measured"]["endpoints_examined"], 1)

    def test_stroke_primitive_custom_pad_is_unmeasured_not_pass(self):
        pad = CUSTOM.replace("(gr_poly (pts (xy 0 -0.3) (xy 1.0 -0.3) (xy 1.0 0.3) (xy 0 0.3)) (width 0) (fill yes))",
                             "(gr_line (start 0 0) (end 1 0) (width 0.1))")
        g = self.run_gate(self.board("custln", _mini_board(pad, _seg("10.5 10", "13 10"))))["gates"]["R-03"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("gr_line", g["measured"]["unmeasured_endpoints"][0]["reason"])


def _qfn_pads() -> str:
    out = []
    for i in range(6):
        net = '(net 2 "SIG")' if i % 2 else '(net 1 "GND")'
        out.append(f'\t\t(pad "{i + 1}" smd rect (at 0 {i * 0.5}) (size 0.825 0.25) (layers "F.Cu") {net} '
                   f'(uuid "c04c0000-0000-4000-8000-0000000005{i:02d}"))')
    return "\n".join(out)


class R08Escape(Base):
    CL = lambda self, w: {"Pw": {"nets": ["GND", "SIG"], "min_track_width_mm": w, "clearance_mm": 0.15}}

    def test_half_mm_class_on_half_mm_pitch_fails_pre_route(self):
        r = self.run_gate(self.board("qfn05", _mini_board(_qfn_pads())), classes=self.CL(0.5))
        g = r["gates"]["R-08"]
        self.assertEqual(g["status"], "fail", g)
        self.assertEqual(g["measured"]["mode"], "pre_route")
        self.assertTrue(g["measured"]["counts_toward_ok"])
        self.assertFalse(r["ok"])
        refs = {(o["ref"], o["pad"]) for o in g["offenders"]}
        self.assertEqual(refs, {("U9", "2"), ("U9", "3"), ("U9", "4"), ("U9", "5")})
        o = [x for x in g["offenders"] if x["pad"] == "3"][0]
        self.assertLess(o["max_feasible_width_mm"], 0.5)
        self.assertAlmostEqual(o["min_gap_mm"], o["max_feasible_width_mm"] + 0.3, places=3)
        self.assertEqual(o["exits_examined"], 4)  # 1 copper layer x 4 local sides

    def test_quarter_mm_class_is_feasible(self):
        g = self.run_gate(self.board("qfn025", _mini_board(_qfn_pads())), classes=self.CL(0.25))["gates"]["R-08"]
        self.assertEqual(g["status"], "pass", g["offenders"])
        self.assertTrue(g["measured"]["counts_toward_ok"])

    def test_routed_board_is_informational_and_not_in_ok(self):
        r = self.run_gate(self.board("qfnrt", _mini_board(_qfn_pads(), _seg("10 10", "12 10"))), classes=self.CL(0.5))
        g = r["gates"]["R-08"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["measured"]["mode"], "routed_informational")
        self.assertFalse(g["measured"]["counts_toward_ok"])
        self.assertNotIn("R-08", r["unmeasured_gates"])

    def test_class_without_clearance_is_unmeasured_never_pass(self):
        cl = {"Pw": {"nets": ["GND", "SIG"], "min_track_width_mm": 0.5}}
        g = self.run_gate(self.board("qfnnoc", _mini_board(_qfn_pads())), classes=cl)["gates"]["R-08"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("clearance_mm", g["measured"]["unmeasured_items"][0]["reason"])

    def test_clearance_comes_from_project_file_and_class_rules(self):
        pro = {"net_settings": {"classes": [{"name": "Default", "track_width": 0.5, "clearance": 0.15, "priority": 2147483647}]}}
        p = self.board("qfnpro", _mini_board(_qfn_pads()))
        with open(p[:-len(".kicad_pcb")] + ".kicad_pro", "w", encoding="utf-8") as fh:
            json.dump(pro, fh)
        self.assertEqual(c04_routing_gate(p)["gates"]["R-08"]["status"], "fail")
        ok = c04_routing_gate(p, class_rules={"Default": {"min_track_width_mm": 0.25}})
        self.assertEqual(ok["gates"]["R-08"]["status"], "pass")
        self.assertEqual(ok["classes"]["table"]["Default"]["clearance_mm"], 0.15)

    def test_unmodelled_pad_shape_is_unmeasured_item(self):
        t = _mini_board(_qfn_pads()).replace('(pad "1" smd rect', '(pad "1" smd trapezoid')
        g = self.run_gate(self.board("qfntz", t), classes=self.CL(0.25))["gates"]["R-08"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("trapezoid", g["measured"]["unmeasured_items"][0]["reason"])


class R05Pairs(Base):
    def test_absent_declaration_is_unmeasured(self):
        self.assertEqual(self.run_gate()["gates"]["R-05"]["status"], "unmeasured")

    def test_over_length_and_skew_fail(self):
        g = self.run_gate(pairs=[{"a": "PWR", "b": "SIG", "max_len_mm": 10, "max_skew_mm": 5}])["gates"]["R-05"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual({o["kind"] for o in g["offenders"]}, {"over_length", "skew"})

    def test_unknown_pair_net_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "not a net on the board"):
            self.run_gate(pairs=[{"a": "PWR", "b": "NOPE", "max_len_mm": 10, "max_skew_mm": 5}])

    def test_declared_failing_pair_makes_ok_false(self):
        r = self.run_gate(keepouts=KO, keepout_margin_mm=0.4,
                          pairs=[{"a": "PWR", "b": "SIG", "max_len_mm": 10, "max_skew_mm": 5}])
        self.assertFalse(r["ok"])


class R06KeepoutMargin(Base):
    def test_track_half_a_mm_from_keepout_fails_at_larger_margin(self):
        r = self.run_gate(keepouts=KO, keepout_margin_mm=0.6)
        g = r["gates"]["R-06"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual([(o["kind"], o["layer"]) for o in g["offenders"]], [("track", "F.Cu")])
        self.assertAlmostEqual(g["offenders"][0]["distance_mm"], 0.5, places=3)
        self.assertFalse(r["ok"])

    def test_margin_below_distance_passes(self):
        g = self.run_gate(keepouts=KO, keepout_margin_mm=0.4)["gates"]["R-06"]
        self.assertEqual(g["status"], "pass")
        self.assertEqual(g["measured"]["keepout_margin_mm"], 0.4)

    def test_owner_pads_exempt_and_listed_non_owner_pads_still_fail(self):
        ko = [{"name": "KO-R2", "x": 14.0, "y": 4.7, "w": 1.0, "h": 0.6}]
        own = self.run_gate(keepouts=[{**ko[0], "owner_ref": "R2"}], keepout_margin_mm=0.2)["gates"]["R-06"]
        self.assertNotIn("pad", {o["kind"] for o in own["offenders"]})
        self.assertIn("R2", {e["ref"] for e in own["measured"]["owner_exempt_pads"]})
        non = self.run_gate(keepouts=ko, keepout_margin_mm=0.2)["gates"]["R-06"]
        self.assertIn(("pad", "R2"), {(o["kind"], o["item"]["ref"]) for o in non["offenders"] if o["kind"] == "pad"})
        self.assertEqual(non["measured"]["owner_exempt_pads"], [])

    def test_fill_inside_margin_fails(self):
        g = self.run_gate(keepouts=[{"name": "KO-F", "x": 13.5, "y": 10.0, "w": 2.0, "h": 2.0}],
                          keepout_margin_mm=1.0)["gates"]["R-06"]
        self.assertIn("fill", {o["kind"] for o in g["offenders"]})

    def test_margin_required_with_keepouts(self):
        with self.assertRaisesRegex(C04GateInputError, "keepout_margin_mm is required"):
            self.run_gate(keepouts=KO)

    def test_unknown_owner_ref_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "owner_ref 'ZZ9' is not a footprint"):
            self.run_gate(keepouts=[{**KO[0], "owner_ref": "ZZ9"}], keepout_margin_mm=0.4)


class ClassResolutionAndInputs(Base):
    def test_no_class_source_raises_not_defaults(self):
        with self.assertRaisesRegex(C04GateInputError, "C04_ROUTING_CLASSES_MISSING"):
            c04_routing_gate(BOARD)

    def test_class_rules_unknown_class_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "unknown class"):
            self.run_gate(class_rules={"Nope": {"min_track_width_mm": 1}})

    def test_missing_board_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "C04_GATE_INPUT_NOT_FOUND"):
            c04_routing_gate(os.path.join(self.root, "absent.kicad_pcb"), classes=CLASSES)

    def test_sibling_project_file_supplies_classes_and_priority(self):
        pro = {"net_settings": {"classes": [
            {"name": "Default", "track_width": 0.2, "priority": 2147483647},
            {"name": "Power_High", "track_width": 0.5, "priority": 1}],
            "netclass_patterns": [{"netclass": "Power_High", "pattern": "PWR"}]}}
        p = self.board("withpro", _text())
        with open(p[:-len(".kicad_pcb")] + ".kicad_pro", "w", encoding="utf-8") as fh:
            json.dump(pro, fh)
        r = c04_routing_gate(p)
        self.assertIn("project file", r["classes"]["source"])
        self.assertEqual(r["gates"]["R-01"]["status"], "pass")
        self.assertEqual(r["classes"]["nets_without_class"], [])
        n = self.board("withpro2", mutate(_text(), B02, B02.replace("0.5", "0.26")))
        with open(n[:-len(".kicad_pcb")] + ".kicad_pro", "w", encoding="utf-8") as fh:
            json.dump(pro, fh)
        self.assertEqual(c04_routing_gate(n)["gates"]["R-01"]["status"], "fail")

    def test_input_board_is_not_mutated(self):
        before = _text()
        self.run_gate(keepouts=KO, keepout_margin_mm=0.4)
        self.assertEqual(before, _text())


class ServerRegistration(unittest.TestCase):
    def test_tool_registered(self):
        try:
            from services.mcp import server
        except Exception as e:
            self.skipTest(f"server.py not importable here: {type(e).__name__}")
        t = {x["name"]: x for x in server.TOOLS}
        self.assertIn("bodesign_c04_routing_gate", t)
        self.assertTrue(callable(t["bodesign_c04_routing_gate"]["handler"]))
        self.assertEqual(t["bodesign_c04_routing_gate"]["schema"]["required"], ["board_path"])
        out = t["bodesign_c04_routing_gate"]["handler"]({"board_path": BOARD})
        self.assertFalse(out["ok"])
        self.assertIn("C04_ROUTING_CLASSES_MISSING", out["error"])


_SPEC = next((p for p in SPEC if os.path.isfile(p)), None)


@unittest.skipUnless(_SPEC, "no btdongle c04 v3/v4 board on disk (Track A deliverable)")
class SpecimenShape(unittest.TestCase):
    def test_shape_only_never_a_verdict(self):
        r = c04_routing_gate(_SPEC, class_rules={"Power_High": {"min_vias_per_transition": 2}})
        self.assertEqual(set(r["gates"]), set(rt.GATE_IDS))
        for g in r["gates"].values():
            self.assertIn(g["status"], ("pass", "fail", "unmeasured"))
            self.assertEqual(set(g), {"status", "measured", "offenders"})
        self.assertEqual(len(r["inputs"]["board_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
