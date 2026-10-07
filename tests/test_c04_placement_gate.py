"""Tests for bodesign_c04_placement_geometry_gate (GATE-C04-01..05).

Fixtures are synthetic (tests/fixtures/c04_placement_gate/). The positive board is a 20x20 mm
outline with R1 (5,5), R2 (10,5), C1 (15,15), each with a 2.0x1.2 mm courtyard.
Negative controls are single-edit variants of it, one per gate.
"""
import os
import shutil
import unittest
from unittest import mock

from bodesign_eda_bridge import c04_gate as gate_mod
from bodesign_eda_bridge.c04_gate import C04GateInputError, c04_placement_geometry_gate

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "c04_placement_gate")
POS = os.path.join(FX, "positive.kicad_pcb")
NET = os.path.join(FX, "positive.net")
# keepout well away from every part (nearest is C1 courtyard at x>=14)
KO_CLEAR = [{"name": "KO-01", "x": 0.0, "y": 10.0, "w": 4.0, "h": 4.0}]
SPECIMEN = next((p for p in (os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/btdongle_c04-v1.kicad_pcb"),
                             os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/.history/btdongle_c04-v1.kicad_pcb"))
                 if os.path.isfile(p)), os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/btdongle_c04-v1.kicad_pcb"))

HAVE_CLI = shutil.which("kicad-cli") is not None


def run(board=POS, keepouts=None, **kw):
    return c04_placement_geometry_gate(board, NET, KO_CLEAR if keepouts is None else keepouts, **kw)


class PositiveControl(unittest.TestCase):
    @unittest.skipUnless(HAVE_CLI, "kicad-cli absent: GATE-C04-02 cannot be measured here")
    def test_all_measured_gates_pass(self):
        r = run()
        self.assertTrue(r["ok"], r)
        for g in ("GATE-C04-01", "GATE-C04-02", "GATE-C04-03", "GATE-C04-04"):
            self.assertEqual(r["gates"][g]["status"], "pass", (g, r["gates"][g]))
            self.assertEqual(r["gates"][g]["offenders"], [], g)
        self.assertEqual(r["gates"]["GATE-C04-01"]["measured"]["counts"], {"missing": 0, "extra": 0, "mismatch": 0})
        # R1 courtyard centreline x in [4,6]; edge at x=0 -> 4.0 minus the 0.045 pcbnew courtyard outset
        self.assertAlmostEqual(r["gates"]["GATE-C04-04"]["measured"]["min_margin_mm"], 4.0 - 0.045, places=3)

    def test_output_shape_and_hashes(self):
        r = run()
        self.assertEqual(set(r["gates"]), set(gate_mod.GATE_IDS))
        for g in r["gates"].values():
            self.assertIn(g["status"], ("pass", "fail", "unmeasured"))
            self.assertIn("measured", g)
            self.assertIn("offenders", g)
        self.assertEqual(len(r["inputs"]["board_sha256"]), 64)
        self.assertEqual(len(r["inputs"]["netlist_sha256"]), 64)

    def test_edge_margin_default_is_040(self):
        self.assertEqual(run()["gates"]["GATE-C04-04"]["measured"]["edge_margin_mm"], 0.40)


class Gate05AlwaysUnmeasured(unittest.TestCase):
    def test_literal_unmeasured_even_when_everything_else_passes(self):
        r = run()
        g = r["gates"]["GATE-C04-05"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertTrue(g["measured"]["placement_only"])
        self.assertIn("GATE-C04-05", r["unmeasured_gates"])

    def test_ok_never_implies_copper_parity(self):
        self.assertIn("never implies copper connectivity", run()["scope"])


class Gate01Parity(unittest.TestCase):
    def test_missing_ref_fails(self):
        g = run(os.path.join(FX, "missing_ref.kicad_pcb"))["gates"]["GATE-C04-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["measured"]["missing"], ["C1"])
        self.assertEqual(g["measured"]["counts"]["missing"], 1)
        self.assertIn({"ref": "C1", "kind": "missing_ref"}, g["offenders"])

    def test_extra_pad_net_fails(self):
        g = run(os.path.join(FX, "extra_pad_net.kicad_pcb"))["gates"]["GATE-C04-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual([m["kind"] for m in g["measured"]["mismatch"]], ["extra_pad_net"])
        self.assertEqual((g["measured"]["mismatch"][0]["ref"], g["measured"]["mismatch"][0]["pad"]), ("R1", "3"))

    def test_net_mismatch_fails(self):
        with open(POS) as fh:
            txt = fh.read()
        a = '(net 1 "N1") (uuid "c04a0000-0000-4000-8000-0000000003f1")'
        self.assertIn(a, txt)
        bad = self._write("netmis.kicad_pcb", txt.replace(a, '(net 3 "GND") (uuid "c04a0000-0000-4000-8000-0000000003f1")'))
        g = run(bad)["gates"]["GATE-C04-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["measured"]["mismatch"][0]["kind"], "net_mismatch")
        self.assertEqual(g["measured"]["mismatch"][0]["netlist_net"], "N1")

    def test_expected_ref_count_mismatch_fails_and_match_passes(self):
        self.assertEqual(run(expected_ref_count=3)["gates"]["GATE-C04-01"]["status"], "pass")
        g = run(expected_ref_count=45)["gates"]["GATE-C04-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0], {"kind": "ref_count", "expected": 45, "board": 3})

    def _write(self, name, text):
        d = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or FX, "c04_gate_tests")
        os.makedirs(d, mode=0o700, exist_ok=True)
        p = os.path.join(d, name)
        with open(p, "w") as fh:
            fh.write(text)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        return p


class Gate02Courtyard(unittest.TestCase):
    def test_cli_absent_is_unmeasured_never_pass(self):
        with mock.patch.object(gate_mod, "_find_kicad_cli", return_value=None):
            r = run()
        g = r["gates"]["GATE-C04-02"]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("kicad-cli", g["measured"]["reason"])
        self.assertFalse(r["ok"], "ok must not be true while GATE-C04-02 is unmeasured")
        self.assertIn("GATE-C04-02", r["unmeasured_gates"])

    @unittest.skipUnless(HAVE_CLI, "kicad-cli absent")
    def test_overlapping_courtyards_fail(self):
        with open(POS) as fh:
            txt = fh.read()
        # move R2 on top of R1 (both 2.0 mm wide courtyards, 1 mm apart)
        bad = txt.replace("(at 10 5)", "(at 6 5)")
        d = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or FX, "c04_gate_tests")
        os.makedirs(d, mode=0o700, exist_ok=True)
        p = os.path.join(d, "overlap.kicad_pcb")
        with open(p, "w") as fh:
            fh.write(bad)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        g = run(p)["gates"]["GATE-C04-02"]
        self.assertEqual(g["status"], "fail")
        self.assertGreaterEqual(g["measured"]["courtyards_overlap"], 1)

    def test_unusable_cli_output_is_unmeasured(self):
        fake = mock.Mock(returncode=1, stderr="boom", stdout="")
        with mock.patch.object(gate_mod, "_find_kicad_cli", return_value="/bin/true"), \
             mock.patch.object(gate_mod.subprocess, "run", return_value=fake):
            g = gate_mod.gate_courtyard(POS)
        self.assertEqual(g["status"], "unmeasured")


class Gate03Keepout(unittest.TestCase):
    def test_part_inside_keepout_fails_with_offenders(self):
        ko = [{"name": "KO-01", "x": 4.0, "y": 4.0, "w": 3.0, "h": 3.0}]  # swallows R1
        g = run(keepouts=ko)["gates"]["GATE-C04-03"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual({o["ref"] for o in g["offenders"]}, {"R1"})
        self.assertEqual({o["kind"] for o in g["offenders"]}, {"pad", "courtyard", "footprint"})
        self.assertEqual({o["keepout"] for o in g["offenders"]}, {"KO-01"})

    def test_clear_keepout_passes(self):
        self.assertEqual(run()["gates"]["GATE-C04-03"]["status"], "pass")

    def test_empty_keepouts_is_unmeasured_not_vacuous_pass(self):
        g = run(keepouts=[])["gates"]["GATE-C04-03"]
        self.assertEqual(g["status"], "unmeasured")

    def test_layer_filter_skips_other_side(self):
        ko = [{"name": "KO-B", "x": 4.0, "y": 4.0, "w": 3.0, "h": 3.0, "layer": "B.Cu"}]
        self.assertEqual(run(keepouts=ko)["gates"]["GATE-C04-03"]["status"], "pass")


class Gate04EdgeMargin(unittest.TestCase):
    def test_courtyard_at_02mm_from_edge_fails(self):
        g = run(os.path.join(FX, "edge_close.kicad_pcb"))["gates"]["GATE-C04-04"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual([o["ref"] for o in g["offenders"]], ["C1"])
        self.assertAlmostEqual(g["measured"]["min_margin_mm"], 0.2 - 0.045, places=3)
        self.assertEqual(g["measured"]["min_margin_ref"], "C1")
        self.assertEqual(g["offenders"][0]["kind"], "margin_below_required")

    def test_same_board_passes_with_smaller_margin(self):
        g = run(os.path.join(FX, "edge_close.kicad_pcb"), edge_margin_mm=0.1)["gates"]["GATE-C04-04"]
        self.assertEqual(g["status"], "pass")

    def test_part_outside_outline_reports_negative_margin(self):
        with open(POS) as fh:
            txt = fh.read()
        d = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or FX, "c04_gate_tests")
        os.makedirs(d, mode=0o700, exist_ok=True)
        p = os.path.join(d, "outside.kicad_pcb")
        with open(p, "w") as fh:
            fh.write(txt.replace("(at 15 15)", "(at 25 15)"))
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        g = run(p)["gates"]["GATE-C04-04"]
        self.assertEqual(g["status"], "fail")
        self.assertLess(g["measured"]["min_margin_mm"], 0)


class FailFast(unittest.TestCase):
    def test_missing_keepouts_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "keepouts is required"):
            c04_placement_geometry_gate(POS, NET, None)

    def test_incomplete_keepout_lists_gap(self):
        with self.assertRaisesRegex(C04GateInputError, r"keepouts\[0\] missing 'h'"):
            c04_placement_geometry_gate(POS, NET, [{"name": "K", "x": 0, "y": 0, "w": 1}])

    def test_missing_files_raise(self):
        with self.assertRaisesRegex(C04GateInputError, "board_path"):
            c04_placement_geometry_gate("/nonexistent/x.kicad_pcb", NET, KO_CLEAR)
        with self.assertRaisesRegex(C04GateInputError, "netlist_path"):
            c04_placement_geometry_gate(POS, "", KO_CLEAR)

    def test_board_without_outline_or_courtyard_raises(self):
        with open(POS) as fh:
            txt = fh.read()
        no_edge = "\n".join(l for l in txt.splitlines() if "Edge.Cuts\")" not in l or "gr_rect" not in l)
        d = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or FX, "c04_gate_tests")
        os.makedirs(d, mode=0o700, exist_ok=True)
        p = os.path.join(d, "noedge.kicad_pcb")
        with open(p, "w") as fh:
            fh.write(no_edge)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        with self.assertRaisesRegex(C04GateInputError, "Edge.Cuts outline has 0"):
            run(p)

    def test_bad_margin_raises(self):
        with self.assertRaisesRegex(C04GateInputError, "edge_margin_mm"):
            run(edge_margin_mm=-1)


class ServerRegistration(unittest.TestCase):
    def test_tool_registered_with_required_fields(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bodesign_server_c04", os.path.join(os.path.dirname(FX), "..", "services", "mcp", "server.py"))
        # the server module is imported by test_mcp_server the same way; reuse its loader if present
        try:
            srv = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(srv)
        except Exception as e:  # pragma: no cover - environment specific
            self.skipTest(f"server module not importable here: {e}")
        t = {x["name"]: x for x in srv.TOOLS}["bodesign_c04_placement_geometry_gate"]
        self.assertEqual(t["schema"]["required"], ["board_path", "netlist_path", "keepouts"])
        out = t["handler"]({"board_path": POS, "netlist_path": NET})
        self.assertFalse(out["ok"])
        self.assertIn("keepouts is required", out["error"])


@unittest.skipUnless(os.path.isfile(SPECIMEN), "btdongle specimen not landed (Track A in flight)")
class SpecimenShape(unittest.TestCase):
    """Runs the gate on the Track A specimen; asserts SHAPE only, never a verdict."""

    def test_shape_only(self):
        net = os.path.splitext(SPECIMEN)[0] + ".net"
        if not os.path.isfile(net):
            net = NET  # no paired netlist next to the specimen: parity verdict is irrelevant to shape
        try:
            r = c04_placement_geometry_gate(SPECIMEN, net, [{"name": "KO-01", "x": 0, "y": 0, "w": 14.0, "h": 9.0}])
        except C04GateInputError as e:
            # an explicit fail-fast error is a legal shape for an incomplete board
            self.assertIn("C04_GATE_", str(e))
            return
        self.assertEqual(set(r["gates"]), set(gate_mod.GATE_IDS))
        for g in r["gates"].values():
            self.assertIn(g["status"], ("pass", "fail", "unmeasured"))
        self.assertEqual(r["gates"]["GATE-C04-05"]["status"], "unmeasured")
        self.assertEqual(len(r["inputs"]["board_sha256"]), 64)


# ----------------------------------------------------------------------- GATE-C04-06 / 07
def _fx(name):
    return os.path.join(FX, name)


def _g(name, gate, **kw):
    return run(_fx(name), **kw)["gates"][gate]


class Gate06Silk(unittest.TestCase):
    G = "GATE-C04-06"

    def test_positive_passes_with_text_examined(self):
        g = _g("positive.kicad_pcb", self.G)
        self.assertEqual(g["status"], "pass", g)
        self.assertEqual(g["measured"]["texts_examined"], 3)
        self.assertEqual(g["measured"]["unmeasured_items"], [])

    def test_silk_on_pad_fails_with_pad_and_courtyard_offenders(self):
        g = _g("silk_on_pad.kicad_pcb", self.G)
        self.assertEqual(g["status"], "fail")
        kinds = {(o["ref"], o["against_ref"], o["kind"]) for o in g["offenders"]}
        self.assertIn(("R1", "R1", "pad"), kinds)
        # ruling: text over its OWN pads is an offender; text in its OWN courtyard is excluded but reported
        self.assertNotIn(("R1", "R1", "courtyard"), kinds)
        self.assertEqual(g["measured"]["own_courtyard_contained"]["refs"], ["R1"])
        self.assertEqual(g["measured"]["own_courtyard_contained"]["count"], 1)
        for o in g["offenders"]:
            self.assertLess(o["clearance_mm"], 0.15)

    def test_silk_on_neighbour_courtyard_fails(self):
        g = _g("silk_on_neighbour_courtyard.kicad_pcb", self.G)
        self.assertEqual(g["status"], "fail")
        self.assertEqual([(o["ref"], o["against_ref"], o["kind"]) for o in g["offenders"]], [("R1", "R2", "courtyard")])

    def test_rotated_text_is_handled_not_skipped(self):
        # same anchor, angle 90: R1's rotated text box reaches R2's courtyard; its unrotated twin does not.
        g = _g("rotated_text.kicad_pcb", self.G)
        self.assertEqual(g["status"], "fail", g)
        self.assertEqual(g["measured"]["texts_examined"], 3)
        self.assertEqual([(o["ref"], o["against_ref"], o["kind"]) for o in g["offenders"]], [("R1", "R2", "courtyard")])
        with open(_fx("rotated_text.kicad_pcb"), encoding="utf-8") as fh:
            twin = fh.read().replace("(at 5 -1.75 90)", "(at 5 -1.75 0)")
        board = gate_mod.load_board(twin)
        self.assertEqual(gate_mod.gate_silk(board, 0.15, gate_mod.DEFAULT_REF_TEXT_LAYERS)["status"], "pass")

    def test_b_side_text_collides_with_b_side_pads_and_clear_twin_passes(self):
        g = _g("b_side_text.kicad_pcb", self.G)
        self.assertEqual(g["status"], "fail")
        self.assertTrue(all(o["text_layer"] == "B.SilkS" for o in g["offenders"]))
        self.assertEqual(_g("b_side_clear.kicad_pcb", self.G)["status"], "pass")

    def test_b_side_text_ignores_front_side_copper(self):
        # same-side rule: B text over F-only pads is not a collision
        s = open(POS, encoding="utf-8").read().replace(
            '(property "Reference" "R1" (at 0 -2.2 0) (layer "F.SilkS")', '(property "Reference" "R1" (at 0 0 0) (layer "B.SilkS")')
        board = gate_mod.load_board(s)
        g = gate_mod.gate_silk(board, 0.15, gate_mod.DEFAULT_REF_TEXT_LAYERS)
        self.assertEqual(g["status"], "pass", g["offenders"])

    def test_unmodelled_glyph_is_unmeasured_item_not_skipped(self):
        s = open(POS, encoding="utf-8").read().replace('"Reference" "R1"', '"Reference" "R~1"')
        g = gate_mod.gate_silk(gate_mod.load_board(s), 0.15, gate_mod.DEFAULT_REF_TEXT_LAYERS)
        self.assertEqual(g["status"], "unmeasured")
        self.assertEqual([i["ref"] for i in g["measured"]["unmeasured_items"]], ["R~1"])
        self.assertEqual(g["measured"]["texts_examined"], 2)

    def test_missing_text_geometry_fails_fast_naming_the_ref(self):
        s = open(POS, encoding="utf-8").read().replace("(effects (font (size 1 1) (thickness 0.15)))", "", 1)
        with self.assertRaises(C04GateInputError) as cm:
            gate_mod.gate_silk(gate_mod.load_board(s), 0.15, gate_mod.DEFAULT_REF_TEXT_LAYERS)
        self.assertIn("R1", str(cm.exception))
        self.assertIn("C04_GATE_SILK_GEOMETRY", str(cm.exception))

    def test_no_visible_text_on_layers_is_unmeasured_not_pass(self):
        r = run(ref_text_layers=["B.SilkS"])
        g = r["gates"][self.G]
        self.assertEqual(g["status"], "unmeasured")
        self.assertIn("reason", g["measured"])

    def test_clearance_param_changes_verdict(self):
        self.assertEqual(_g("positive.kicad_pcb", self.G, silk_clearance_mm=0.15)["status"], "pass")
        self.assertEqual(_g("positive.kicad_pcb", self.G, silk_clearance_mm=5.0)["status"], "fail")


class Gate07CourtyardGap(unittest.TestCase):
    G = "GATE-C04-07"

    def test_positive_passes_and_reports_smallest_three(self):
        g = _g("positive.kicad_pcb", self.G)
        self.assertEqual(g["status"], "pass")
        st = g["measured"]["smallest_three"]
        self.assertEqual(len(st), 3)
        self.assertEqual(st, sorted(st, key=lambda e: e["distance_mm"]))
        self.assertAlmostEqual(st[0]["distance_mm"], 3.0 - 2 * 0.045, places=3)

    def test_gap_020_fails_with_the_pair(self):
        g = _g("courtyard_gap_020.kicad_pcb", self.G)
        self.assertEqual(g["status"], "fail")
        self.assertEqual([(o["ref"], o["against_ref"]) for o in g["offenders"]], [("R1", "R2")])
        self.assertAlmostEqual(g["offenders"][0]["distance_mm"], 0.20, places=3)
        self.assertEqual(g["measured"]["smallest_three"][0]["refs"], ["R1", "R2"])

    def test_threshold_param(self):
        self.assertEqual(_g("courtyard_gap_020.kicad_pcb", self.G, courtyard_gap_mm=0.15)["status"], "pass")

    def test_polygon_not_aabb_for_a_non_rectangular_courtyard(self):
        # L-shaped courtyard: bounding boxes are 0.5 mm apart in x, the polygons are 2.5 mm apart.
        def block(ref, ox, pts):
            lines = "".join(
                '(fp_line (start %s %s) (end %s %s) (stroke (width 0.05) (type default)) (layer "F.CrtYd")) ' % (
                    pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]) for i in range(len(pts)))
            return ('(footprint "X:Y" (layer "F.Cu") (at %s 0) (property "Reference" "%s" (at 0 0 0) (layer "F.Fab") '
                    '(effects (font (size 1 1) (thickness 0.15)))) %s (pad "1" smd rect (at 0 0) (size 0.2 0.2) '
                    '(layers "F.Cu")))' % (ox, ref, lines))
        L = [(-3, -3), (3, -3), (3, -2), (-2, -2), (-2, 3), (-3, 3)]
        sq = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        text = ('(kicad_pcb (gr_rect (start -20 -20) (end 20 20) (layer "Edge.Cuts")) ' + block("A", 0, L)
                + block("B", 3.5, [(a - 0.0, b + 2.5) for a, b in sq]) + ')')
        text = text.replace('(at 3.5 0)', '(at 3.5 0)')
        board = gate_mod.load_board(text)
        g = gate_mod.gate_courtyard_gap(board, 0.25)
        boxes = [fp["courtyard"] for fp in board["footprints"]]
        self.assertGreater(gate_mod._bbox_gap(boxes[0], boxes[1]) + 1e-9, -1)  # sanity: function runs
        d = g["measured"]["smallest_three"][0]["distance_mm"]
        # B courtyard spans x 3..4, y 2..3; A's L spans x<=3 only for y<=-2 or x<=-2 -> nearest A point (3,-2): 4.0 away.
        self.assertGreater(d, 3.5)
        self.assertEqual(g["status"], "pass")


class Gate04PolygonModel(unittest.TestCase):
    def test_outset_is_part_of_the_model_and_declared(self):
        g = _g("positive.kicad_pcb", "GATE-C04-04")
        self.assertAlmostEqual(g["measured"]["min_margin_mm"], 4.0 - 0.045, places=3)
        self.assertEqual(g["measured"]["aabb_fallback_refs"], [])
        self.assertIn("polygon", g["measured"]["model"])

    def test_edge_close_still_fails(self):
        g = _g("edge_close.kicad_pcb", "GATE-C04-04")
        self.assertEqual(g["status"], "fail")
        self.assertAlmostEqual(g["offenders"][0]["margin_mm"], 0.2 - 0.045, places=3)


class OkSemantics(unittest.TestCase):
    @unittest.skipUnless(HAVE_CLI, "kicad-cli absent")
    def test_ok_requires_06_and_07(self):
        self.assertTrue(run()["ok"])
        self.assertFalse(run(_fx("silk_on_pad.kicad_pcb"))["ok"])
        self.assertFalse(run(_fx("courtyard_gap_020.kicad_pcb"))["ok"])


# ------------------------------------------------------- r1 / r2 specimen calibration (skip if absent)
_OUT = os.path.expanduser("~/products/bodesign/outputs/btdongle_ms")


def _first(*names):
    for n in names:
        for d in (_OUT, os.path.join(_OUT, ".history"), os.path.join(_OUT, ".history", "editable-history")):
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


R1 = _first("btdongle_c04-v1.kicad_pcb")
R2 = _first("btdongle_c04-v2.kicad_pcb")
REVIEW23 = ["SW2", "C10", "C12", "R12", "U1", "C4", "D2", "D5", "J1", "R4"]
KO01 = [{"name": "KO-01", "x": 0, "y": 0, "w": 14.0, "h": 9.0}]


@unittest.skipUnless(R1, "btdongle r1 specimen not on disk (checked outputs/ and .history/)")
class R1Calibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 06/07/04 do not read the netlist; the fixture net only satisfies the signature (GATE-01 is not asserted).
        cls.r = c04_placement_geometry_gate(R1, NET, KO01)

    def test_gate06_fails_and_catches_at_least_6_of_10_review23_refs(self):
        g = self.r["gates"]["GATE-C04-06"]
        self.assertEqual(g["status"], "fail")
        caught = [x for x in REVIEW23 if x in g["measured"]["offending_refs"]]
        self.assertGreaterEqual(len(caught), 6, caught)
        self.assertEqual(g["measured"]["texts_examined"], 45)

    def test_gate07_fails_with_c1_f1_at_0130(self):
        g = self.r["gates"]["GATE-C04-07"]
        self.assertEqual(g["status"], "fail")
        pair = [o for o in g["offenders"] if {o["ref"], o["against_ref"]} == {"C1", "F1"}]
        self.assertEqual(len(pair), 1, g["offenders"])
        self.assertAlmostEqual(pair[0]["distance_mm"], 0.130, places=3)

    def test_gate04_polygon_margin_matches_producer_0400(self):
        m = self.r["gates"]["GATE-C04-04"]["measured"]
        self.assertAlmostEqual(m["min_margin_mm"], 0.400, places=3)
        self.assertEqual(m["min_margin_ref"], "SW1")


@unittest.skipUnless(R2, "btdongle r2 not landed (btdongle_c04-v2.kicad_pcb)")
class R2Passes(unittest.TestCase):
    def test_gates_06_07_pass_on_r2(self):
        r = c04_placement_geometry_gate(R2, NET, KO01)
        for g in ("GATE-C04-06", "GATE-C04-07"):
            self.assertEqual(r["gates"][g]["status"], "pass", (g, r["gates"][g]["offenders"][:5], r["gates"][g]["measured"].get("unmeasured_items")))


if __name__ == "__main__":
    unittest.main()
