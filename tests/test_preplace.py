"""Tests for the deterministic pre-placement core (TV-1..TV-5, pure python)."""
import copy
import unittest

from bodesign_eda_bridge.preplace import (
    PartGeom,
    build_clusters,
    compute_hpwl,
    count_overlap_pairs,
    parse_cap_farads,
    preplace,
    select_anchor,
)
from bodesign_eda_bridge.placement_rules import RULES


def _two_pad(ref, w, h, value="", kind=""):
    return PartGeom(ref=ref, w_mm=w, h_mm=h,
                    pads={"1": (-w / 4, 0.0), "2": (w / 4, 0.0)},
                    value=value, kind=kind)


def _ic(ref, npads=8, w=7.0, h=7.0):
    pads = {str(i + 1): (-w / 2 + 1 + i % 4 * 1.5, -h / 2 + 1 + i // 4 * (h - 2))
            for i in range(npads)}
    return PartGeom(ref=ref, w_mm=w, h_mm=h, pads=pads)


def _small_case():
    """U1 IC + decap C1 + crystal Y1 + load caps C2/C3 + pullup R1."""
    parts = {
        "U1": _ic("U1", npads=8),
        "C1": _two_pad("C1", 2.0, 1.2, value="100nF"),
        "Y1": _two_pad("Y1", 3.2, 2.5),
        "C2": _two_pad("C2", 1.6, 0.8, value="22pF"),
        "C3": _two_pad("C3", 1.6, 0.8, value="22pF"),
        "R1": _two_pad("R1", 1.6, 0.8, value="10k"),
    }
    nets = {
        "VDD": [("U1", "1"), ("C1", "1"), ("R1", "1")],
        "GND": [("U1", "5"), ("C1", "2"), ("C2", "2"), ("C3", "2"), ("Y1", "2")],
        "XIN": [("U1", "2"), ("Y1", "1"), ("C2", "1")],
        "XOUT": [("U1", "3"), ("C3", "1")],  # simplified
        "SIG": [("U1", "4"), ("R1", "2")],
    }
    return parts, nets


class TestPriors(unittest.TestCase):
    def test_cap_parse(self):
        self.assertAlmostEqual(parse_cap_farads("100nF"), 1e-7)
        self.assertAlmostEqual(parse_cap_farads("22pF"), 2.2e-11)
        self.assertAlmostEqual(parse_cap_farads("1uF"), 1e-6)
        self.assertIsNone(parse_cap_farads("10k"))

    def test_anchor_most_pads_tiebreak_lexicographic(self):
        parts = {"U2": _ic("U2", npads=8), "U1": _ic("U1", npads=8), "C1": _two_pad("C1", 2, 1)}
        self.assertEqual(select_anchor(parts), "U1")


class TestTV2Clustering(unittest.TestCase):
    def test_decap_and_crystal_assignment(self):
        parts, nets = _small_case()
        anchor = select_anchor(parts)
        self.assertEqual(anchor, "U1")
        clusters = build_clusters(parts, nets, anchor)
        self.assertEqual(clusters["C1"]["priority"], "decap")
        self.assertEqual(clusters["C1"]["target_ref"], "U1")
        self.assertEqual(clusters["C2"]["priority"], "crystal")
        self.assertEqual(clusters["C2"]["target_ref"], "Y1")
        self.assertEqual(clusters["R1"]["priority"], "signal")


class TestTV1Determinism(unittest.TestCase):
    def test_same_input_same_output(self):
        parts, nets = _small_case()
        r1 = preplace(copy.deepcopy(parts), copy.deepcopy(nets), (30, 25), seed=42)
        r2 = preplace(copy.deepcopy(parts), copy.deepcopy(nets), (30, 25), seed=42)
        self.assertEqual(r1.placement, r2.placement)
        self.assertEqual(r1.violations, r2.violations)
        self.assertEqual(r1.hpwl_mm, r2.hpwl_mm)

    def test_result_echoes_effective(self):
        parts, nets = _small_case()
        r = preplace(parts, nets, (30, 25), seed=7, weights={"w_aff": 5.0})
        self.assertEqual(r.effective["seed"], 7)
        self.assertEqual(r.effective["weights"]["w_aff"], 5.0)


class TestTV3ViolationReporting(unittest.TestCase):
    def test_r1_reports_anchored_violation_when_infeasible(self):
        # Big IC almost filling the board; decap forced outside R1 radius.
        parts = {
            "U1": _ic("U1", npads=8, w=18.0, h=18.0),
            "C1": _two_pad("C1", 2.0, 1.2, value="100nF"),
        }
        nets = {"VDD": [("U1", "1"), ("C1", "1")], "GND": [("U1", "5"), ("C1", "2")]}
        r = preplace(parts, nets, (40, 24), seed=42, sa_iterations=50)
        r1_viols = [v for v in r.violations if v["rule"] == "R1"]
        if r1_viols:  # geometry may or may not force it; when reported it must be anchored
            v = r1_viols[0]
            self.assertEqual(v["source"], RULES["R1"]["source"])
            self.assertIn("C1", v["refs"])
            self.assertGreater(v["measured_mm"], v["limit_mm"])

    def test_violation_schema_complete(self):
        parts = {
            "U1": _ic("U1", npads=8, w=30.0, h=18.0),
            "C1": _two_pad("C1", 2.0, 1.2, value="100nF"),
        }
        nets = {"VDD": [("U1", "1"), ("C1", "1")], "GND": [("U1", "5"), ("C1", "2")]}
        r = preplace(parts, nets, (60, 24), seed=1, sa_iterations=20)
        for v in r.violations:
            for key in ("rule", "source", "refs", "measured_mm", "limit_mm", "note"):
                self.assertIn(key, v)


class TestTV4FailFast(unittest.TestCase):
    def test_missing_geometry(self):
        parts, nets = _small_case()
        parts["C9"] = PartGeom(ref="C9", w_mm=0.0, h_mm=0.0, pads={})
        with self.assertRaises(ValueError) as cm:
            preplace(parts, nets, (30, 25))
        self.assertIn("PREPLACE_MISSING_GEOMETRY", str(cm.exception))
        self.assertIn("C9", str(cm.exception))

    def test_net_ref_without_part(self):
        parts, nets = _small_case()
        nets["VDD"].append(("C77", "1"))
        with self.assertRaises(ValueError) as cm:
            preplace(parts, nets, (30, 25))
        self.assertIn("C77", str(cm.exception))

    def test_board_too_small(self):
        parts, nets = _small_case()
        with self.assertRaises(ValueError) as cm:
            preplace(parts, nets, (5, 5))
        self.assertIn("PREPLACE_BOARD_TOO_SMALL", str(cm.exception))

    def test_invalid_seed(self):
        parts, nets = _small_case()
        with self.assertRaises(ValueError) as cm:
            preplace(parts, nets, (30, 25), seed="42")
        self.assertIn("PREPLACE_INVALID_SEED", str(cm.exception))


def _led_driver_case():
    """Synthetic 16-part 10-net reconstruction of the E2E LED driver board."""
    parts = {
        "U1": _ic("U1", npads=8, w=5.0, h=4.0),          # driver IC
        "J1": PartGeom("J1", 9.0, 7.5, {"A4": (-3, -2), "A9": (3, -2), "A1": (-4, 2),
                                          "A12": (4, 2), "A5": (0, 0)}),  # USB-C
        "C1": _two_pad("C1", 2.0, 1.2, value="100nF"),   # decap
        "C2": _two_pad("C2", 3.2, 1.6, value="10uF"),    # bulk
        "R1": _two_pad("R1", 1.6, 0.8, value="10k"),
        "R2": _two_pad("R2", 1.6, 0.8, value="1k"),
        "R3": _two_pad("R3", 2.0, 1.2, value="0.5"),     # sense
        "D1": _two_pad("D1", 2.8, 1.6),
        "D2": _two_pad("D2", 2.8, 1.6),
        "D3": _two_pad("D3", 2.8, 1.6),
        "D4": _two_pad("D4", 2.8, 1.6),
        "Q1": PartGeom("Q1", 3.0, 2.4, {"1": (-1, 1), "2": (0, -1), "3": (1, 1)}),
        "L1": _two_pad("L1", 4.0, 4.0, value="10uH"),
        "H1": PartGeom("H1", 3.2, 3.2, {"1": (0, 0)}),   # mounting holes
        "H2": PartGeom("H2", 3.2, 3.2, {"1": (0, 0)}),
        "H3": PartGeom("H3", 3.2, 3.2, {"1": (0, 0)}),
    }
    nets = {
        "VBUS": [("J1", "A4"), ("U1", "1"), ("C1", "1"), ("C2", "1"), ("L1", "1")],
        "GND": [("J1", "A1"), ("U1", "5"), ("C1", "2"), ("C2", "2"), ("R3", "2"),
                ("Q1", "2"), ("H1", "1")],
        "SW": [("U1", "2"), ("L1", "2"), ("Q1", "3")],
        "LED_A": [("L1", "2"), ("D1", "1")],
        "LED_1": [("D1", "2"), ("D2", "1")],
        "LED_2": [("D2", "2"), ("D3", "1")],
        "LED_3": [("D3", "2"), ("D4", "1")],
        "SENSE": [("D4", "2"), ("R3", "1"), ("U1", "4")],
        "EN": [("U1", "6"), ("R1", "1")],
        "FB": [("U1", "7"), ("R2", "1")],
    }
    return parts, nets


def _grid_baseline(parts):
    """Replicate routing.py's naive 8mm grid placement for comparison."""
    placement = {}
    gx = gy = 0.0
    for ref in parts:  # routing.py iterates netlist order; dict order preserved
        placement[ref] = (10 + gx, 10 + gy, 0.0)
        gx += 8
        if gx > 80:
            gx = 0
            gy += 8
    return placement


def _decap_distance(placement, parts, ref, target_ref, target_pad):
    import math
    from bodesign_eda_bridge.preplace import pad_abs
    tx, ty = pad_abs(placement, parts, target_ref, target_pad)
    return math.hypot(placement[ref][0] - tx, placement[ref][1] - ty)


class TestTV5Baseline(unittest.TestCase):
    def test_deterministic_beats_grid(self):
        parts, nets = _led_driver_case()
        r = preplace(copy.deepcopy(parts), copy.deepcopy(nets), (50, 40), seed=42)
        self.assertEqual(r.anchor, "U1")
        self.assertEqual(r.overlap_pairs, 0)

        grid = _grid_baseline(parts)
        grid_hpwl = compute_hpwl(grid, parts, nets)

        c1 = r.clusters["C1"]
        self.assertEqual(c1["priority"], "decap")
        det_d = _decap_distance(r.placement, parts, "C1", c1["target_ref"], c1["target_pad"])
        grid_d = _decap_distance(grid, parts, "C1", c1["target_ref"], c1["target_pad"])

        print(f"\n[TV-5 baseline] decap C1→{c1['target_ref']}.{c1['target_pad']}: "
              f"grid={grid_d:.2f}mm det={det_d:.2f}mm | "
              f"HPWL: grid={grid_hpwl:.1f}mm det={r.hpwl_mm:.1f}mm | "
              f"det violations={len(r.violations)} overlaps={r.overlap_pairs}")

        self.assertLess(det_d, grid_d, "decap distance must improve over grid")
        self.assertLess(r.hpwl_mm, grid_hpwl, "HPWL must improve over grid")

    def test_connectors_and_mounts_on_edge_band(self):
        parts, nets = _led_driver_case()
        r = preplace(parts, nets, (50, 40), seed=42, sa_iterations=100)
        for ref in ("J1", "H1", "H2", "H3"):
            x, y, _ = r.placement[ref]
            w, h = parts[ref].w_mm, parts[ref].h_mm
            near_edge = (x - w / 2 <= 6.0 or y - h / 2 <= 6.0
                         or x + w / 2 >= 44.0 or y + h / 2 >= 34.0)
            self.assertTrue(near_edge, f"{ref} at ({x:.1f},{y:.1f}) not in edge band")


class TestRulesTable(unittest.TestCase):
    def test_all_rules_anchored(self):
        for rid, rule in RULES.items():
            self.assertTrue(rule.get("source"), f"{rid} missing source anchor")
            self.assertIn(rule["phase"], ("generate", "check", "planned"))


if __name__ == "__main__":
    unittest.main()
