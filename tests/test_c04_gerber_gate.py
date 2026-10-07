"""Tests for bodesign_c04_gerber_gate (GATE-C04-05 made measurable) and the GATE-05 delegation.

Fixtures: tests/fixtures/c04_gerber_gate/routed.kicad_pcb (30x20 mm, 2 layers, 3 SMD + 3 TH pads, 2 vias, tracks on
both layers, a GND zone on B.Cu). Gerbers + drill are exported NATIVELY by kicad-cli 9 at test time into a scratch
dir (setUpClass) and each negative control is a single textual mutation of those bytes.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from bodesign_eda_bridge import c04_gate as gate_mod
from bodesign_eda_bridge import c04_gerber as gg
from bodesign_eda_bridge.c04_gate import C04GateInputError, c04_placement_geometry_gate
from bodesign_eda_bridge.c04_gerber import c04_gerber_gate, parse_excellon, parse_rs274x

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "c04_gerber_gate")
ROUTED = os.path.join(FX, "routed.kicad_pcb")
PGFX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "c04_placement_gate")
HAVE_CLI = shutil.which("kicad-cli") is not None
KO_CLEAR = [{"name": "KO-clear", "x": 0.0, "y": 10.0, "w": 4.0, "h": 4.0}]
GERBERS_V3 = next((p for p in (os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/gerbers-v3"),) if os.path.isdir(p)), None)
SPEC_BOARD = next((p for p in (os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/btdongle_c04-v3.kicad_pcb"),) if os.path.isfile(p)), None)


def _scratch() -> str:
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="c04gg-", dir=base)


def export(board: str, out: str) -> None:
    os.makedirs(out, exist_ok=True)
    for cmd in (["pcb", "export", "gerbers", "--layers", "F.Cu,B.Cu,Edge.Cuts", "-o", out, board],
                ["pcb", "export", "drill", "-o", out + "/", "--format", "excellon", board]):
        r = subprocess.run(["kicad-cli", *cmd], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def mutate(path: str, old: str, new: str = "") -> None:
    with open(path, encoding="utf-8") as fh:
        t = fh.read()
    assert t.count(old) == 1, f"mutation anchor {old!r} found {t.count(old)}x in {path}"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(t.replace(old, new))


@unittest.skipUnless(HAVE_CLI, "kicad-cli absent: native gerber fixtures cannot be generated")
class GerberFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = _scratch()
        cls.base = os.path.join(cls.root, "base")
        export(ROUTED, cls.base)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def variant(self, name: str) -> str:
        d = os.path.join(self.root, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(self.base, d)
        return d

    def f(self, d: str, suffix: str) -> str:
        return os.path.join(d, "routed-" + suffix)

    def run_gate(self, d: str, keepouts=None, **kw):
        return c04_gerber_gate(ROUTED, d, KO_CLEAR if keepouts is None else keepouts, **kw)


class PositiveControl(GerberFixtureCase):
    def test_routed_export_passes_g01_g03(self):
        r = self.run_gate(self.base)
        self.assertTrue(r["ok"], json.dumps({g: v["offenders"] for g, v in r["gates"].items()})[:600])
        for g in ("G-01", "G-02", "G-03"):
            self.assertEqual(r["gates"][g]["status"], "pass", g)
        self.assertEqual(r["gates"]["G-04"]["status"], "unmeasured")

    def test_single_terminal_net_is_reported_not_failed(self):
        m = self.run_gate(self.base)["gates"]["G-02"]["measured"]
        self.assertEqual(m["single_terminal_nets"], [{"net": "SOLO", "terminal": "TP3.1"}])
        self.assertEqual(m["open_nets"], [])
        self.assertEqual(m["short_count"], 0)

    def test_measured_facts(self):
        r = self.run_gate(self.base)
        m1, m2 = r["gates"]["G-01"]["measured"], r["gates"]["G-02"]["measured"]
        self.assertEqual(m1["drills"], {"board": 5, "hits": 5, "missing": 0, "extra": 0, "slots_board": 0, "slots_file": 0})
        self.assertEqual(m1["drill_only_pads"], [])
        self.assertEqual(m1["edge_cuts"]["max_vertex_deviation_mm"], 0.0)
        self.assertEqual(m2["plated_hits"], 5)
        self.assertEqual(sorted(m2["layers_measured"]), ["B.Cu", "F.Cu"])
        self.assertEqual(r["method"]["connect_tol_mm"], 0.001)
        self.assertIn("gerber_files_sha256", r["inputs"])

    def test_inputs_are_not_mutated(self):
        before = {f: _sha(os.path.join(self.base, f)) for f in os.listdir(self.base)}
        self.run_gate(self.base)
        after = {f: _sha(os.path.join(self.base, f)) for f in os.listdir(self.base)}
        self.assertEqual(before, after)


class NegativeControls(GerberFixtureCase):
    def test_g02_open_track_deleted(self):
        d = self.variant("open")
        mutate(self.f(d, "F_Cu.gtl"), "X5500000Y-3000000D02*\nX25000000Y-3000000D01*\n")
        r = self.run_gate(d)
        g = r["gates"]["G-02"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["measured"]["open_nets"], ["N2"])
        o = [x for x in g["offenders"] if x["kind"] == "open"][0]
        self.assertEqual(o["net"], "N2")
        self.assertEqual(sorted(sum(o["components"], [])), ["R1.2", "TP1.1"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["gates"]["G-01"]["status"], "pass")  # parity unaffected by a missing draw

    def test_g02_short_bridge_added(self):
        d = self.variant("short")
        mutate(self.f(d, "F_Cu.gtl"), "X15500000Y-12000000D02*\nX25000000Y-12000000D01*\n",
               "X15500000Y-12000000D02*\nX25000000Y-12000000D01*\nX5500000Y-4000000D02*\nX4500000Y-5000000D01*\n")
        g = self.run_gate(d)["gates"]["G-02"]
        self.assertEqual(g["status"], "fail")
        shorts = [x for x in g["offenders"] if x["kind"] == "short"]
        self.assertEqual(len(shorts), 1)
        self.assertEqual(shorts[0]["nets"], ["N1", "N2"])

    def test_g01_pad_flash_removed(self):
        d = self.variant("parity")
        mutate(self.f(d, "F_Cu.gtl"), "X14500000Y-5000000D03*\n")
        g = self.run_gate(d)["gates"]["G-01"]
        self.assertEqual(g["status"], "fail")
        miss = [x for x in g["offenders"] if x["kind"] == "missing_flash"]
        self.assertEqual([(m["layer"], m["what"]) for m in miss], [("F.Cu", "R2.1")])

    def test_g01_extra_flash(self):
        d = self.variant("extra")
        mutate(self.f(d, "F_Cu.gtl"), "X5000000Y-17000000D03*\n", "X5000000Y-17000000D03*\nX9000000Y-17000000D03*\n")
        g = self.run_gate(d)["gates"]["G-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual([x["kind"] for x in g["offenders"]], ["extra_flash"])

    def test_g03_copper_in_keepout(self):
        for name, ko in (("f_track", {"name": "KO-trk", "x": 10.0, "y": 2.5, "w": 2.0, "h": 1.0}),
                         ("b_zone", {"name": "KO-zone", "x": 20.0, "y": 14.0, "w": 3.0, "h": 3.0, "layer": "B.Cu"})):
            g = self.run_gate(self.base, [ko])["gates"]["G-03"]
            self.assertEqual(g["status"], "fail", name) if False else None
        g1 = self.run_gate(self.base, [{"name": "KO-trk", "x": 10.0, "y": 2.5, "w": 2.0, "h": 1.0}])["gates"]["G-03"]
        self.assertEqual(g1["status"], "fail")
        self.assertEqual({o["layer"] for o in g1["offenders"]}, {"F.Cu"})
        g2 = self.run_gate(self.base, [{"name": "KO-zone", "x": 20.0, "y": 14.0, "w": 3.0, "h": 3.0, "layer": "B.Cu"}])["gates"]["G-03"]
        self.assertEqual(g2["status"], "fail")
        self.assertEqual({(o["layer"], o["kind"]) for o in g2["offenders"]}, {("B.Cu", "region")})

    def test_g03_layer_filter_excludes_other_layer(self):
        g = self.run_gate(self.base, [{"name": "KO", "x": 10.0, "y": 2.5, "w": 2.0, "h": 1.0, "layer": "B.Cu"}])["gates"]["G-03"]
        self.assertEqual(g["status"], "pass")

    def test_g03_empty_keepouts_unmeasured(self):
        self.assertEqual(self.run_gate(self.base, [])["gates"]["G-03"]["status"], "unmeasured")
        self.assertEqual(c04_gerber_gate(ROUTED, self.base)["gates"]["G-03"]["status"], "unmeasured")

    def test_drill_removed_gives_multilayer_open(self):
        d = self.variant("drill")
        mutate(self.f(d, "F_Cu.gtl").replace("routed-F_Cu.gtl", "routed.drl"), "X4.5Y-8.0\n")
        r = self.run_gate(d)
        self.assertEqual(r["gates"]["G-01"]["status"], "fail")
        self.assertIn("missing_drill", [x["kind"] for x in r["gates"]["G-01"]["offenders"]])
        g = r["gates"]["G-02"]
        self.assertEqual(g["status"], "fail")
        self.assertIn("N1", g["measured"]["open_nets"])
        self.assertIn("barrel_open", [x["kind"] for x in g["offenders"]])
        self.assertFalse(r["ok"])

    def test_outline_mismatch(self):
        d = self.variant("edge")
        mutate(self.f(d, "Edge_Cuts.gm1"), "X30000000Y0D01*", "X31000000Y0D01*")
        g = self.run_gate(d)["gates"]["G-01"]
        self.assertEqual(g["status"], "fail")
        self.assertIn("outline_mismatch", [x["kind"] for x in g["offenders"]])


    def test_unsupported_layer_is_unmeasured_never_pass(self):
        d = self.variant("unsup")
        mutate(self.f(d, "F_Cu.gtl"), "%LPD*%\n", "%LPD*%\n%LPC*%\n")
        r = self.run_gate(d)
        self.assertEqual(r["gates"]["G-02"]["status"], "unmeasured")
        self.assertEqual(r["gates"]["G-01"]["status"], "unmeasured")
        self.assertFalse(r["ok"])
        self.assertIn("clear polarity", json.dumps(r["gates"]["G-02"]["measured"]))

    def test_missing_copper_layer_file_fails_parity(self):
        d = self.variant("nolayer")
        os.remove(self.f(d, "B_Cu.gbl"))
        r = self.run_gate(d)
        self.assertIn("layer_file_missing", [x["kind"] for x in r["gates"]["G-01"]["offenders"]])
        self.assertNotEqual(r["gates"]["G-02"]["status"], "pass")
        self.assertFalse(r["ok"])


class RenderBinding(GerberFixtureCase):
    def render_dir(self, sidecar):
        h = os.path.join(self.root, "human")
        if os.path.isdir(h):
            shutil.rmtree(h)
        os.makedirs(h)
        with open(os.path.join(h, "05.c04-F.Cu-v1.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        if sidecar is not None:
            with open(os.path.join(h, "05.c04-F.Cu-v1.png.json"), "w", encoding="utf-8") as fh:
                fh.write(sidecar)
        return h

    def test_bound_png_passes(self):
        sha = _sha(self.f(self.base, "F_Cu.gtl"))
        h = self.render_dir(json.dumps({"gerber": "routed-F_Cu.gtl", "sha256": sha}))
        g = self.run_gate(self.base, human_dir=h)["gates"]["G-04"]
        self.assertEqual(g["status"], "pass", g)
        self.assertEqual(g["measured"]["bindings"][0]["gerber_files"], ["routed-F_Cu.gtl"])

    def test_no_sidecar_fails(self):
        g = self.run_gate(self.base, human_dir=self.render_dir(None))["gates"]["G-04"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0]["kind"], "no_sidecar")

    def test_unknown_sha_fails(self):
        h = self.render_dir(json.dumps({"gerber": "routed-F_Cu.gtl", "sha256": "0" * 64}))
        g = self.run_gate(self.base, human_dir=h)["gates"]["G-04"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0]["kind"], "sha_not_in_gerber_dir")

    def test_g04_does_not_gate_ok(self):
        h = self.render_dir(None)
        r = self.run_gate(self.base, human_dir=h)
        self.assertEqual(r["gates"]["G-04"]["status"], "fail")
        self.assertTrue(r["ok"])  # ok = G-01..G-03 only, as specified

    def test_placement_and_routed_pngs_are_out_of_scope_not_offenders(self):
        sha = _sha(self.f(self.base, "F_Cu.gtl"))
        h = self.render_dir(json.dumps({"gerber": "routed-F_Cu.gtl", "sha256": sha}))
        for n in ("01.c04-placement-v3.png", "01.c04-routed-v3.png"):
            with open(os.path.join(h, n), "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n")
        g = self.run_gate(self.base, human_dir=h)["gates"]["G-04"]
        self.assertEqual(g["status"], "pass", g)
        self.assertEqual(g["offenders"], [])
        self.assertEqual(g["measured"]["out_of_scope"], ["01.c04-placement-v3.png", "01.c04-routed-v3.png"])
        self.assertEqual(g["measured"]["pngs"], 1)

    def test_layer_png_without_sidecar_still_fails_next_to_out_of_scope(self):
        h = self.render_dir(None)
        with open(os.path.join(h, "01.c04-placement-v3.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        g = self.run_gate(self.base, human_dir=h)["gates"]["G-04"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual([o["png"] for o in g["offenders"]], ["05.c04-F.Cu-v1.png"])

    def test_inner_layer_and_composite_default_selected_and_configurable(self):
        h = self.render_dir(None)
        for n in ("06.c04-In1.Cu-v1.png", "07.c04-copper-composite-v1.png", "08.c04-top-copper-v1.png"):
            with open(os.path.join(h, n), "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n")
        g = self.run_gate(self.base, human_dir=h)["gates"]["G-04"]
        self.assertEqual(sorted(o["png"] for o in g["offenders"]),
                         ["05.c04-F.Cu-v1.png", "06.c04-In1.Cu-v1.png", "07.c04-copper-composite-v1.png"])
        self.assertEqual(g["measured"]["out_of_scope"], ["08.c04-top-copper-v1.png"])
        g2 = self.run_gate(self.base, human_dir=h, render_views=["top-copper"])["gates"]["G-04"]
        self.assertEqual([o["png"] for o in g2["offenders"]], ["08.c04-top-copper-v1.png"])


class Parsers(unittest.TestCase):
    HDR = "%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\nG01*\n"

    def test_region_and_draw_and_flash(self):
        t = (self.HDR + "%ADD10C,1.000000*%\n%ADD11R,2.000000X1.000000*%\nD10*\nX0Y0D02*\nX1000000Y0D01*\nD11*\n"
             "X5000000Y-1000000D03*\nG36*\nX0Y-5000000D02*\nX1000000Y-5000000D01*\nX1000000Y-6000000D01*\nG37*\nM02*\n")
        g = parse_rs274x(t)
        self.assertEqual(g["unsupported"], [])
        self.assertEqual([i["kind"] for i in g["items"]], ["draw", "flash", "region"])
        self.assertEqual(g["items"][1]["at"], (5.0, 1.0))  # y flipped into board frame

    def test_unsupported_markers(self):
        for body, needle in (("%LPC*%\n", "clear polarity"), ("%SRX2Y1I1.0J1.0*%\n", "step-and-repeat"), ("G74*\n", "G74"),
                             ("G91*\n", "incremental")):
            g = parse_rs274x(self.HDR + body + "M02*\n")
            self.assertTrue(any(needle in u for u in g["unsupported"]), (needle, g["unsupported"]))

    def test_draw_before_aperture_is_unsupported_not_guessed(self):
        g = parse_rs274x(self.HDR + "X0Y0D02*\nX1000000Y0D01*\nM02*\n")
        self.assertTrue(g["unsupported"])

    def test_arc_flatten_sagitta(self):
        pts = gg._flatten_arc((1.0, 0.0), (-1.0, 0.0), (0.0, 0.0), False)
        self.assertTrue(all(abs(((x * x + y * y) ** 0.5) - 1.0) < 1e-9 for x, y in pts))
        self.assertEqual(len(pts), 17)  # pi / (2*acos(1-0.005)) = 15.7 -> 16 chords

    def test_excellon_plating_and_unit(self):
        t = ("M48\nMETRIC\n; #@! TA.AperFunction,Plated,PTH,ViaDrill\nT1C0.300\n; #@! TA.AperFunction,NonPlated,NPTH\nT2C1.000\n%\n"
             "T1\nX1.0Y-2.0\nT2\nX3.0Y-4.0\nM30\n")
        d = parse_excellon(t)
        self.assertEqual([(h["x"], h["y"], h["dia"], h["plated"]) for h in d["hits"]],
                         [(1.0, 2.0, 0.3, True), (3.0, 4.0, 1.0, False)])

    def test_shape_distance_is_exact(self):
        a = ([(0.0, 0.0), (1.0, 0.0)], False, 0.1)
        b = ([(0.0, 0.5), (1.0, 0.5)], False, 0.1)
        self.assertAlmostEqual(gg.shape_distance(a, b, limit=0.5), 0.3, places=9)
        self.assertEqual(gg.shape_distance(a, b), float('inf'))  # beyond limit=0: culled, not measured


SLOT = os.path.join(FX, "slot.kicad_pcb")


@unittest.skipUnless(HAVE_CLI, "kicad-cli absent: native gerber fixtures cannot be generated")
class SlotAndNpthModelGaps(unittest.TestCase):
    """Real-board gaps found on btdongle v3: NPTH pads are drill-only (no flash), oval drills are routed slots."""

    @classmethod
    def setUpClass(cls):
        cls.root = _scratch()
        cls.base = os.path.join(cls.root, "base")
        export(SLOT, cls.base)
        with open(SLOT, encoding="utf-8") as fh:
            cls.board = fh.read()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def variant(self, name: str) -> str:
        d = os.path.join(self.root, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(self.base, d)
        return d

    def board_variant(self, name: str, old: str, new: str) -> str:
        assert self.board.count(old) == 1, old
        p = os.path.join(self.root, name + ".kicad_pcb")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(self.board.replace(old, new))
        return p

    def test_positive_slot_and_npth_pass(self):
        r = c04_gerber_gate(SLOT, self.base, KO_CLEAR)
        for g in ("G-01", "G-02", "G-03"):
            self.assertEqual(r["gates"][g]["status"], "pass", (g, r["gates"][g]["offenders"]))
        m1, m2 = r["gates"]["G-01"]["measured"], r["gates"]["G-02"]["measured"]
        self.assertEqual(m1["drill_only_pads"], ["H1.-"])
        self.assertEqual((m1["drills"]["slots_board"], m1["drills"]["slots_file"]), (1, 1))
        self.assertEqual(m1["unmodeled"], [])
        self.assertEqual(m2["unplated_hits"]["count"], 1)
        self.assertEqual(m2["unplated_hits"]["matched_board_npth_pads"], 1)
        self.assertEqual(m2["unplated_hits"]["unexplained"], [])

    def test_slot_hit_is_a_stadium_in_the_parser(self):
        with open(os.path.join(self.base, "slot.drl"), encoding="utf-8") as fh:
            d = parse_excellon(fh.read())
        s = [h for h in d["hits"] if h["slot"]]
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["plated"], True)
        self.assertAlmostEqual(s[0]["dia"], 0.6)
        ends = sorted(s[0]["slot"])
        self.assertAlmostEqual(ends[0][1], 11.7)
        self.assertAlmostEqual(ends[1][1], 12.3)

    def test_slot_drill_removed_gives_barrel_open(self):
        d = self.variant("noslot")
        mutate(os.path.join(d, "slot.drl"), "X8.0Y-11.7G85X8.0Y-12.3\nG05\n")
        r = c04_gerber_gate(SLOT, d, KO_CLEAR)
        self.assertEqual(r["gates"]["G-02"]["status"], "fail")
        o = [x for x in r["gates"]["G-02"]["offenders"] if x["kind"] == "barrel_open"]
        self.assertEqual([(x["terminal"], x["net"]) for x in o], [("J2.1", "SLOTN")])
        self.assertIn("SLOTN", r["gates"]["G-02"]["measured"]["open_nets"])
        self.assertEqual(r["gates"]["G-01"]["status"], "fail")
        self.assertIn("missing_drill", [x["kind"] for x in r["gates"]["G-01"]["offenders"]])
        self.assertFalse(r["ok"])

    def test_slot_replaced_by_round_hit_is_a_parity_failure(self):
        d = self.variant("roundslot")
        mutate(os.path.join(d, "slot.drl"), "X8.0Y-11.7G85X8.0Y-12.3\n", "X8.0Y-12.0\n")
        g = c04_gerber_gate(SLOT, d, KO_CLEAR)["gates"]["G-01"]
        self.assertEqual(g["status"], "fail")
        self.assertIn("missing_drill", [x["kind"] for x in g["offenders"]])

    def test_npth_pad_with_copper_but_no_flash_is_still_missing_flash(self):
        # Same ref H1, same drill, but the board now gives the NPTH pad a 2.4 mm annulus: gerber (exported from the
        # 1.8 mm board) has no flash there, so the rule must key on pad size/layers, not on the H prefix.
        b = self.board_variant("annulus", 'np_thru_hole circle (at 0 0) (size 1.8 1.8)', 'np_thru_hole circle (at 0 0) (size 2.4 2.4)')
        g = c04_gerber_gate(b, self.base, KO_CLEAR)["gates"]["G-01"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["measured"]["drill_only_pads"], [])
        mf = [x for x in g["offenders"] if x["kind"] == "missing_flash"]
        self.assertEqual(sorted(x["layer"] for x in mf), ["B.Cu", "F.Cu"])
        self.assertTrue(all(x["what"].startswith("H1.") for x in mf))

    def test_drill_only_rule_does_not_key_on_ref_prefix(self):
        b = self.board_variant("renamed", '(property "Reference" "H1"', '(property "Reference" "ZZ9"')
        g = c04_gerber_gate(b, self.base, KO_CLEAR)["gates"]["G-01"]
        self.assertEqual(g["status"], "pass", g["offenders"])
        self.assertEqual(g["measured"]["drill_only_pads"], ["ZZ9.-"])

    def test_extra_flash_on_a_drill_only_pad_is_still_detected(self):
        d = self.variant("npthflash")
        # give the NPTH location a copper flash in the gerber that the board does not call for
        with open(os.path.join(d, "slot-F_Cu.gtl"), encoding="utf-8") as fh:
            txt = fh.read()
        txt = txt.replace("M02*", "D10*\nX27000000Y-6000000D03*\nM02*")
        with open(os.path.join(d, "slot-F_Cu.gtl"), "w", encoding="utf-8") as fh:
            fh.write(txt)
        g = c04_gerber_gate(SLOT, d, KO_CLEAR)["gates"]["G-01"]
        self.assertIn("extra_flash", [x["kind"] for x in g["offenders"]])

    def test_unplated_hit_without_board_npth_is_a_finding(self):
        d = self.variant("rogue")
        mutate(os.path.join(d, "slot.drl"), "T4\nX27.0Y-6.0\n", "T4\nX27.0Y-6.0\nX20.0Y-18.0\n")
        g = c04_gerber_gate(SLOT, d, KO_CLEAR)["gates"]["G-02"]
        self.assertIn("unplated_hit_not_npth", [x["kind"] for x in g["offenders"]])
        self.assertEqual(len(g["measured"]["unplated_hits"]["unexplained"]), 1)

    def test_routed_slot_encoding_is_parsed_like_g85(self):
        t = ("M48\nMETRIC\n; #@! TA.AperFunction,Plated,PTH,ComponentDrill\nT1C0.600\n%\nG90\nT1\n"
             "G00X8.0Y-11.7\nM15\nG01X8.0Y-12.3\nM16\nM30\n")
        d = parse_excellon(t)
        self.assertEqual(d["unsupported"], [])
        self.assertEqual(len(d["hits"]), 1)
        self.assertIsNotNone(d["hits"][0]["slot"])
        self.assertEqual(parse_excellon("M48\nMETRIC\nT1C0.6\n%\nT1\nG00X1.0Y-1.0\nM15\nG02X2.0Y-2.0\nM16\nM30\n")["unsupported"],
                         ["routed arc slot (G02/G03)"])


class InputErrors(unittest.TestCase):
    def test_missing_gerber_dir(self):
        with self.assertRaises(C04GateInputError):
            c04_gerber_gate(ROUTED, "/nonexistent-gerber-dir", [])
        with self.assertRaises(C04GateInputError):
            c04_gerber_gate(ROUTED, None, [])

    def test_missing_board(self):
        with self.assertRaises(C04GateInputError):
            c04_gerber_gate("/nonexistent.kicad_pcb", os.path.dirname(ROUTED), [])

    def test_negative_tolerance_rejected(self):
        with self.assertRaises(C04GateInputError):
            c04_gerber_gate(ROUTED, FX, [], pad_tol_mm=-1)


@unittest.skipUnless(HAVE_CLI, "kicad-cli absent")
class Gate05Delegation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = _scratch()
        cls.gdir = os.path.join(cls.root, "g")
        export(os.path.join(PGFX, "positive.kicad_pcb"), cls.gdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def run_pg(self, **kw):
        ko = [{"name": "KO", "x": 0.0, "y": 10.0, "w": 4.0, "h": 4.0}]
        return c04_placement_geometry_gate(os.path.join(PGFX, "positive.kicad_pcb"), os.path.join(PGFX, "positive.net"), ko, **kw)

    def test_absent_gerber_dir_stays_unmeasured(self):
        r = self.run_pg()
        self.assertEqual(r["gates"]["GATE-C04-05"]["status"], "unmeasured")
        self.assertIn("GATE-C04-05", r["unmeasured_gates"])

    def test_unrouted_placement_board_never_passes_gate05(self):
        # positive.kicad_pcb is placed but has no tracks: the gerber bytes truly contain opens.
        r = self.run_pg(gerber_dir=self.gdir)
        g = r["gates"]["GATE-C04-05"]
        self.assertEqual(g["measured"]["delegated_to"], "bodesign_c04_gerber_gate")
        self.assertEqual(g["status"], "fail")
        self.assertIn("open", [o["kind"] for o in g["offenders"]])
        self.assertNotIn("GATE-C04-05", r["unmeasured_gates"])
        self.assertFalse(r["ok"])

    def test_delegated_pass_status_is_surfaced(self):
        fake = {"gates": {g: {"status": "pass", "measured": {}, "offenders": []} for g in ("G-01", "G-02", "G-03", "G-04")}}
        with mock.patch("bodesign_eda_bridge.c04_gerber.c04_gerber_gate", return_value=fake):
            r = self.run_pg(gerber_dir=self.gdir)
        self.assertEqual(r["gates"]["GATE-C04-05"]["status"], "pass")
        self.assertEqual(r["gates"]["GATE-C04-05"]["measured"]["sub_gate_status"]["G-02"], "pass")

    def test_delegated_fail_flips_ok(self):
        d = os.path.join(self.root, "bad")
        shutil.copytree(self.gdir, d)
        mutate(os.path.join(d, "positive-F_Cu.gtl"), "X4500000Y-5000000D03*\n")
        r = self.run_pg(gerber_dir=d)
        self.assertEqual(r["gates"]["GATE-C04-05"]["status"], "fail")
        self.assertIn("missing_flash", [o["kind"] for o in r["gates"]["GATE-C04-05"]["offenders"]])
        self.assertFalse(r["ok"])

    def test_delegated_unmeasured_blocks_ok(self):
        d = os.path.join(self.root, "unsup")
        shutil.copytree(self.gdir, d)
        mutate(os.path.join(d, "positive-F_Cu.gtl"), "%LPD*%\n", "%LPD*%\n%LPC*%\n")
        r = self.run_pg(gerber_dir=d)
        self.assertEqual(r["gates"]["GATE-C04-05"]["status"], "unmeasured")
        self.assertFalse(r["ok"])


class ServerRegistration(unittest.TestCase):
    def test_tool_registered(self):
        try:
            from services.mcp import server
        except Exception as e:  # server needs deps absent in some interpreters
            self.skipTest(f"server.py not importable here: {type(e).__name__}")
        t = {x["name"]: x for x in server.TOOLS}
        self.assertIn("bodesign_c04_gerber_gate", t)
        self.assertTrue(callable(t["bodesign_c04_gerber_gate"]["handler"]))
        self.assertIn("gerber_dir", t["bodesign_c04_placement_geometry_gate"]["schema"]["properties"])


@unittest.skipUnless(GERBERS_V3 and SPEC_BOARD, "gerbers-v3 + btdongle_c04-v3.kicad_pcb absent (Track A in flight)")
class SpecimenShape(unittest.TestCase):
    def test_shape_only(self):
        r = c04_gerber_gate(SPEC_BOARD, GERBERS_V3, [])
        self.assertEqual(set(r["gates"]), {"G-01", "G-02", "G-03", "G-04"})
        for g in r["gates"].values():
            self.assertIn(g["status"], ("pass", "fail", "unmeasured"))
            self.assertEqual(set(g), {"status", "measured", "offenders"})
        self.assertIn("board_sha256", r["inputs"])


if __name__ == "__main__":
    unittest.main()
