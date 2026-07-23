"""Tests for the I2C pull-up evidence-backed suggestion engine.

Plan knowledge_c03-ee-design-kb track C (scheme C) slice 1: verify that
suggest_i2c_pullups SUGGESTS (never decides), computes values from the KB rule
(not fabricated), and honours the honesty contract — deterministic, no mutation,
no file writes.
"""
import copy
import io
import os
import unittest
from unittest.mock import patch

from bodesign_eda_bridge.design_suggest import (
    suggest_i2c_pullups,
    suggest_series_termination,
    suggest_crystal_load_caps,
)

_SHARED_I2C_INTENT = {
    "bus": "SHARED_I2C",
    "scl_net": "SHARED_I2C_SCL",
    "sda_net": "SHARED_I2C_SDA",
    "pull_rail": "+1V8",
    "speed_hz": 400000,
    "bus_capacitance_pf": 150,
    "device_count": 4,
}


class SuggestI2CPullupsTests(unittest.TestCase):
    # ── 1. Happy path: real SHARED_I2C intent → two evidence-backed suggestions
    def test_shared_i2c_two_pullups_within_bounds(self):
        out = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        self.assertEqual(out["status"], "suggested")
        self.assertTrue(out["review_required"])
        self.assertEqual(out["bus"], "SHARED_I2C")
        self.assertEqual(len(out["suggestions"]), 2)

        nets = {s["component"]["net_from"] for s in out["suggestions"]}
        self.assertEqual(nets, {"SHARED_I2C_SCL", "SHARED_I2C_SDA"})

        for s in out["suggestions"]:
            comp = s["component"]
            self.assertEqual(comp["type"], "resistor")
            self.assertEqual(comp["net_to"], "+1V8")
            self.assertIsNotNone(comp["value"])  # a typical fit for 400kHz/1.8V/150pF
            c = s["computed"]
            # chosen ohm must sit inside the computed [Rp_min, Rp_max] window
            chosen_ohm = {"2.2k": 2200.0, "4.7k": 4700.0, "10k": 10000.0}[comp["value"]]
            self.assertGreaterEqual(chosen_ohm, c["rp_min_ohm"])
            self.assertLessEqual(chosen_ohm, c["rp_max_ohm"])
            self.assertNotIn("warning", c)  # a value fit; no warning

    def test_evidence_anchors_to_kb_object(self):
        out = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        for s in out["suggestions"]:
            ev = s["evidence"]
            self.assertEqual(ev["kb_object"], "control.sch.pullup-termination-sizing")
            self.assertIn("Rp_min", ev["formula"])
            self.assertIn("Rp_max", ev["formula"])
            self.assertIn("UM10204", ev["provenance"])
            self.assertEqual(ev["confidence"], "partial")

    def test_rp_bounds_match_kb_formula(self):
        # Rp_min = (1.8 - 0.4) / 3e-3 = 466.67 ; Rp_max = 300ns/(0.8473*150pF)
        out = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        c = out["suggestions"][0]["computed"]
        self.assertAlmostEqual(c["rp_min_ohm"], 466.7, delta=0.5)
        expected_rp_max = (300e-9) / (0.8473 * 150e-12)
        self.assertAlmostEqual(c["rp_max_ohm"], round(expected_rp_max, 1), delta=1.0)

    # ── 2. Boundary: huge Cb collapses the window → warning, no forced value
    def test_oversize_cb_warns_no_forced_value(self):
        intent = dict(_SHARED_I2C_INTENT, bus_capacitance_pf=800, speed_hz=400000)
        out = suggest_i2c_pullups(intent)
        # 300ns/(0.8473*800pF) ~= 442 ohm < Rp_min 466 ohm → no typical fits
        self.assertIn("warning", out)
        for s in out["suggestions"]:
            self.assertIsNone(s["component"]["value"])
            self.assertIn("warning", s["computed"])
            self.assertIsNone(s["computed"]["chosen"])

    # ── 3. Honesty contract: never committed, no mutation, no file writes
    def test_status_never_committed(self):
        out = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        self.assertNotEqual(out["status"], "committed")
        self.assertEqual(out["status"], "suggested")
        # no nested "committed" flag anywhere
        self.assertNotIn("committed", str(out).lower())

    def test_input_not_mutated(self):
        intent = copy.deepcopy(_SHARED_I2C_INTENT)
        before = copy.deepcopy(intent)
        suggest_i2c_pullups(intent)
        self.assertEqual(intent, before)

    def test_writes_no_files(self):
        # Patch builtins.open to fail the test if the function writes anything.
        real_open = open
        opened_for_write = []

        def _guarded_open(path, mode="r", *a, **k):
            if any(m in mode for m in ("w", "a", "x", "+")):
                opened_for_write.append((path, mode))
            return real_open(path, mode, *a, **k)

        with patch("builtins.open", _guarded_open):
            suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        self.assertEqual(opened_for_write, [])

    # ── Fail-loud guards (no silent fabrication) ─────────────────────────────
    def test_missing_required_key_raises(self):
        intent = dict(_SHARED_I2C_INTENT)
        del intent["scl_net"]
        with self.assertRaises(ValueError):
            suggest_i2c_pullups(intent)

    def test_unknown_rail_without_vcc_raises(self):
        intent = dict(_SHARED_I2C_INTENT, pull_rail="VBUS_WEIRD")
        intent.pop("vcc_v", None)
        with self.assertRaises(ValueError):
            suggest_i2c_pullups(intent)

    def test_explicit_vcc_overrides_rail_name(self):
        intent = dict(_SHARED_I2C_INTENT, pull_rail="VBUS_WEIRD", vcc_v=3.3)
        out = suggest_i2c_pullups(intent)
        self.assertAlmostEqual(out["intent_echo"]["vcc_v"], 3.3)

    def test_zero_bus_capacitance_raises(self):
        intent = dict(_SHARED_I2C_INTENT, bus_capacitance_pf=0)
        with self.assertRaises(ValueError):
            suggest_i2c_pullups(intent)

    def test_determinism(self):
        a = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        b = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        self.assertEqual(a, b)

    # ── spec_fragment: review-then-paste contract (consumer round=7) ────────
    def test_spec_fragment_pasteable_and_honest(self):
        out = suggest_i2c_pullups(copy.deepcopy(_SHARED_I2C_INTENT))
        frag = out["spec_fragment"]
        # honesty markers ride the fragment too (draft, not a decision)
        self.assertEqual(frag["status"], "suggested")
        self.assertTrue(frag["review_required"])
        # two draft pull-up components, each Device:R at the chosen value
        comps = frag["components"]
        self.assertEqual(len(comps), 2)
        value = out["suggestions"][0]["component"]["value"]
        for c in comps:
            self.assertEqual(c["symbol"], "Device:R")
            self.assertEqual(c["value"], value)
            self.assertTrue(c["draft_ref"])  # ref is a hint, reviewer renames
            self.assertEqual(set(c["pins"].keys()), {"1", "2"})
        refs = {c["ref"] for c in comps}
        self.assertEqual(refs, {"R_SCL_PU", "R_SDA_PU"})
        # each pull-up's pin2 lands on the pull rail; pin1 on its bus line
        pin2_nets = {c["pins"]["2"] for c in comps}
        self.assertEqual(pin2_nets, {"+1V8"})
        pin1_nets = {c["pins"]["1"] for c in comps}
        self.assertEqual(pin1_nets, {"SHARED_I2C_SCL", "SHARED_I2C_SDA"})
        # net_additions wire both new resistor pins into the right nets
        adds = {(a["net"], a["add_node"]) for a in frag["net_additions"]}
        self.assertIn(("SHARED_I2C_SCL", "R_SCL_PU.1"), adds)
        self.assertIn(("+1V8", "R_SCL_PU.2"), adds)
        self.assertIn(("SHARED_I2C_SDA", "R_SDA_PU.1"), adds)
        self.assertIn(("+1V8", "R_SDA_PU.2"), adds)


_XSPI_INTENT = {
    "net": "XSPI_CLK",
    "driver_ref": "U1",
    "net_class": "XSPI",
    "target_z0_ohm": 50,
    "trace_len_mm": 40,
    "edge_rate_ns": 1.0,
}


class SuggestSeriesTerminationTests(unittest.TestCase):
    # ── 1. target_z0 path: XSPI_CLK → series R ≈ Z0 at source, evidence-backed
    def test_target_z0_series_r_at_source(self):
        out = suggest_series_termination(copy.deepcopy(_XSPI_INTENT))
        self.assertEqual(out["status"], "suggested")
        self.assertTrue(out["review_required"])
        self.assertEqual(out["net"], "XSPI_CLK")
        self.assertEqual(out["driver_ref"], "U1")
        c = out["suggestion"]["computed"]
        self.assertEqual(c["z0_ohm"], 50.0)
        self.assertEqual(c["z0_source"], "caller-specified")
        self.assertEqual(c["series_r_ohm"], 50.0)
        # nearest E24 to 50 is 51R
        self.assertEqual(c["series_r_standard"], "51R")
        # 40mm trace @ 1ns edge: knee=350MHz, lambda/10 ~ 49.5mm; 40 < 49.5 => not needed
        self.assertIn("termination_needed", out)
        comp = out["suggestion"]["component"]
        self.assertEqual(comp["placement"], "series at source (U1)")

    def test_target_z0_longer_trace_needs_termination(self):
        # 80mm trace @ 1ns edge exceeds lambda/10 ~ 49.5mm => termination needed
        intent = dict(_XSPI_INTENT, trace_len_mm=80)
        out = suggest_series_termination(intent)
        self.assertIs(out["termination_needed"], True)
        comp = out["suggestion"]["component"]
        self.assertEqual(comp["value"], "51R")
        self.assertEqual(comp["net_to"], "XSPI_CLK")
        self.assertIsNotNone(out["spec_fragment"])
        frag = out["spec_fragment"]
        self.assertEqual(frag["status"], "suggested")
        self.assertEqual(len(frag["components"]), 1)
        self.assertTrue(frag["components"][0]["draft_ref"])

    def test_evidence_anchors_to_si_kb(self):
        out = suggest_series_termination(dict(_XSPI_INTENT, trace_len_mm=80))
        ev = out["suggestion"]["evidence"]
        self.assertEqual(ev["kb_object"], "control.si.interface-requirements")
        self.assertIn("Z0", ev["formula"])
        self.assertIn("lambda", ev["formula"])
        self.assertEqual(ev["confidence"], "partial")

    # ── 2. stackup path: Z0 computed from microstrip formula, c04 handoff flagged
    def test_stackup_derives_z0(self):
        intent = {
            "net": "QSPI_CLK", "driver_ref": "U2",
            "stackup": {"er": 4.2, "h_mm": 0.1, "w_mm": 0.15, "t_mm": 0.035},
            "trace_len_mm": 80, "edge_rate_ns": 1.0,
        }
        out = suggest_series_termination(intent)
        c = out["suggestion"]["computed"]
        self.assertEqual(c["z0_source"], "derived-from-assumed-stackup")
        # microstrip Z0 for this geometry lands in a plausible 40-70 ohm band
        self.assertGreater(c["z0_ohm"], 40.0)
        self.assertLess(c["z0_ohm"], 75.0)
        self.assertIn("C04", out["suggestion"]["c04_handoff"])

    # ── 3. short trace: sub-lambda/10 => not needed, value NOT forced
    def test_short_trace_no_termination(self):
        intent = dict(_XSPI_INTENT, trace_len_mm=2, edge_rate_ns=1.0)
        out = suggest_series_termination(intent)
        self.assertIs(out["termination_needed"], False)
        self.assertIsNone(out["suggestion"]["component"]["value"])
        self.assertIsNone(out["spec_fragment"])

    # ── 4. no impedance source => fail-loud (never guess Z0)
    def test_no_impedance_source_raises(self):
        intent = {"net": "X", "driver_ref": "U1", "trace_len_mm": 80,
                  "edge_rate_ns": 1.0}
        with self.assertRaises(ValueError):
            suggest_series_termination(intent)

    def test_missing_required_key_raises(self):
        with self.assertRaises(ValueError):
            suggest_series_termination({"driver_ref": "U1", "target_z0_ohm": 50})

    def test_unknown_length_is_null_not_skipped(self):
        # no trace_len/edge and no high_speed flag => termination_needed is None
        intent = {"net": "X", "driver_ref": "U1", "target_z0_ohm": 50}
        out = suggest_series_termination(intent)
        self.assertIsNone(out["termination_needed"])
        self.assertIn("length_note", out)

    # ── 5. honesty contract: never committed, no mutation, no file writes
    def test_status_never_committed(self):
        out = suggest_series_termination(dict(_XSPI_INTENT, trace_len_mm=80))
        self.assertEqual(out["status"], "suggested")
        self.assertNotIn("committed", str(out).lower())

    def test_input_not_mutated(self):
        intent = copy.deepcopy(_XSPI_INTENT)
        before = copy.deepcopy(intent)
        suggest_series_termination(intent)
        self.assertEqual(intent, before)

    def test_writes_no_files(self):
        real_open = open
        opened_for_write = []

        def _guarded_open(path, mode="r", *a, **k):
            if any(m in mode for m in ("w", "a", "x", "+")):
                opened_for_write.append((path, mode))
            return real_open(path, mode, *a, **k)

        with patch("builtins.open", _guarded_open):
            suggest_series_termination(dict(_XSPI_INTENT, trace_len_mm=80))
        self.assertEqual(opened_for_write, [])

    def test_determinism(self):
        a = suggest_series_termination(dict(_XSPI_INTENT, trace_len_mm=80))
        b = suggest_series_termination(dict(_XSPI_INTENT, trace_len_mm=80))
        self.assertEqual(a, b)


_X1_VERIFY_INTENT = {
    "crystal": "X1",
    "osc_pins": ["HSE_IN", "HSE_OUT"],
    "load_cap_refs": ["CX1", "CX2"],
    "crystal_cl_pf": 13,
    "cl_source": "back-derived-assumption",
    "stray_pf": 4,
    "existing_cap_pf": 18,
}


class SuggestCrystalLoadCapsTests(unittest.TestCase):
    # ── 1. verify mode: consumer X1 carrier, existing 18pF matches computed
    def test_verify_mode_x1_consistent(self):
        out = suggest_crystal_load_caps(copy.deepcopy(_X1_VERIFY_INTENT))
        self.assertEqual(out["status"], "suggested")
        self.assertEqual(out["mode"], "verify")
        self.assertEqual(out["crystal"], "X1")
        c = out["computed"]
        # C_load_each = 2*(13 - 4) = 18
        self.assertEqual(c["c_load_each_pf"], 18)
        self.assertEqual(c["cl_source"], "back-derived-assumption")
        self.assertEqual(out["verdict"], "CONSISTENT")
        self.assertEqual(out["delta_pf"], 0)
        self.assertEqual(out["existing_cap_pf"], 18)
        # honest CL-source note
        self.assertIn("BACK-DERIVED", out["note"])
        ev = out["suggestion"]["evidence"]
        self.assertEqual(ev["kb_object"], "control.si.crystal-oscillator-layout")
        self.assertEqual(ev["confidence"], "verified")

    # ── 2. suggest mode: no existing caps → from-zero suggestion
    def test_suggest_mode_from_zero(self):
        intent = {"crystal": "Y1", "osc_pins": ["OSC_IN", "OSC_OUT"],
                  "crystal_cl_pf": 20, "stray_pf": 5, "cl_source": "datasheet"}
        out = suggest_crystal_load_caps(intent)
        self.assertEqual(out["mode"], "suggest")
        # C_load_each = 2*(20 - 5) = 30
        self.assertEqual(out["computed"]["c_load_each_pf"], 30)
        self.assertNotIn("verdict", out)
        frag = out["spec_fragment"]
        self.assertEqual(len(frag["components"]), 2)
        for comp in frag["components"]:
            self.assertEqual(comp["symbol"], "Device:C")
            self.assertEqual(comp["value"], "30pF")

    # ── 3. MISMATCH: existing does not match computed → reported, spec untouched
    def test_verify_mode_mismatch(self):
        intent = dict(_X1_VERIFY_INTENT, existing_cap_pf=22)
        out = suggest_crystal_load_caps(intent)
        self.assertEqual(out["verdict"], "MISMATCH")
        self.assertEqual(out["computed"]["c_load_each_pf"], 18)
        self.assertEqual(out["delta_pf"], 4)  # 22 - 18
        self.assertIn("does NOT match", out["note"])

    # ── 4. honesty contract: never committed, no mutation, no file writes
    def test_status_never_committed(self):
        out = suggest_crystal_load_caps(copy.deepcopy(_X1_VERIFY_INTENT))
        self.assertEqual(out["status"], "suggested")
        self.assertNotIn("committed", str(out).lower())

    def test_input_not_mutated(self):
        intent = copy.deepcopy(_X1_VERIFY_INTENT)
        before = copy.deepcopy(intent)
        suggest_crystal_load_caps(intent)
        self.assertEqual(intent, before)

    def test_writes_no_files(self):
        real_open = open
        opened_for_write = []

        def _guarded_open(path, mode="r", *a, **k):
            if any(m in mode for m in ("w", "a", "x", "+")):
                opened_for_write.append((path, mode))
            return real_open(path, mode, *a, **k)

        with patch("builtins.open", _guarded_open):
            suggest_crystal_load_caps(copy.deepcopy(_X1_VERIFY_INTENT))
        self.assertEqual(opened_for_write, [])

    # ── 5. CL missing → fail-loud (no guessing CL)
    def test_missing_cl_raises(self):
        intent = dict(_X1_VERIFY_INTENT)
        del intent["crystal_cl_pf"]
        with self.assertRaises(ValueError):
            suggest_crystal_load_caps(intent)

    def test_missing_crystal_raises(self):
        intent = dict(_X1_VERIFY_INTENT)
        del intent["crystal"]
        with self.assertRaises(ValueError):
            suggest_crystal_load_caps(intent)

    # ── 6. evidence form_note: concept KB-verified, explicit form standard EE
    def test_evidence_form_note_honest(self):
        out = suggest_crystal_load_caps(copy.deepcopy(_X1_VERIFY_INTENT))
        ev = out["suggestion"]["evidence"]
        self.assertIn("form_note", ev)
        note = ev["form_note"].lower()
        self.assertIn("kb-verified", note)
        self.assertIn("not verbatim-anchored", note)

    def test_determinism(self):
        a = suggest_crystal_load_caps(copy.deepcopy(_X1_VERIFY_INTENT))
        b = suggest_crystal_load_caps(copy.deepcopy(_X1_VERIFY_INTENT))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
