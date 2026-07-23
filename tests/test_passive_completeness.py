"""Tests for PC-001 passive-completeness gate (BR_20260723).

Seam: validate_passive_completeness in validation_detectors.py — a machine
projection of the pinout-to-circuit obligation table onto a composed schematic.

Policy (plan c03-ee_passive-completeness-gate, USER-adjudicated):
  DD-2 mandatory scope = DECOUPLING-ONLY hard fail.
  DD-3 waiver = passive_waivers.json sidecar + per-(ref, obligation) match;
       matched gap recorded as `waived` (info, visible), never suppressed.

Coverage (mirrors BR validation plan):
  1. pinout-only fixture (active IC, power pin, zero passives) -> PC-001 error
  2. decoupled fixture -> PASS (no PC-001 error)
  3. waiver fixture (honest subset + sidecar) -> PASS, gap recorded waived
  + malformed waiver -> fail-fast; no-power-pin IC -> skipped (no false positive)
"""
import json
import os
import sys
import tempfile
import unittest

_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "bodesign", "engines", "kicad", "scripts",
)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from kicad_types import AnalysisContext  # noqa: E402
from validation_detectors import (  # noqa: E402
    validate_passive_completeness,
    PassiveWaiverError,
    WAIVER_SIDECAR_FILENAME,
)


def _mcu_pins():
    """An active IC symbol: pin 1 = VDD (power_in), pin 2 = GND, pin 3 = GPIO."""
    return [
        {"number": "1", "name": "VDD", "type": "power_in"},
        {"number": "2", "name": "GND", "type": "power_in"},
        {"number": "3", "name": "PA0", "type": "bidirectional"},
    ]


def _ctx(components, pin_net, *, sch_path=None):
    """Build an AnalysisContext. known_power_rails seeded so is_power_net()
    recognises the rail without needing a #PWR symbol in the fixture."""
    nets: dict[str, dict] = {}
    for (ref, pin), (net, _info) in pin_net.items():
        if not net:
            continue
        nets.setdefault(net, {"pins": []})["pins"].append(
            {"component": ref, "pin": pin})
    return AnalysisContext(
        components=components,
        nets=nets,
        lib_symbols={},
        pin_net=pin_net,
        known_power_rails={"+3V3", "VDD_MCU"},
        sch_path=sch_path,
    )


# A bare MCU: VDD -> +3V3 rail, GND -> GND, no caps anywhere.
def _pinout_only_ctx(sch_path=None):
    comps = [
        {"reference": "U1", "value": "STM32N657", "lib_id": "MCU:STM32N657",
         "type": "ic", "pins": _mcu_pins()},
    ]
    pin_net = {
        ("U1", "1"): ("+3V3", None),
        ("U1", "2"): ("GND", None),
        ("U1", "3"): ("PA0", None),
    }
    return _ctx(comps, pin_net, sch_path=sch_path)


# The same MCU plus a decoupling cap C1: pin1 -> +3V3, pin2 -> GND.
def _decoupled_ctx():
    comps = [
        {"reference": "U1", "value": "STM32N657", "lib_id": "MCU:STM32N657",
         "type": "ic", "pins": _mcu_pins()},
        {"reference": "C1", "value": "100n", "lib_id": "Device:C",
         "type": "capacitor",
         "pins": [{"number": "1", "name": "1", "type": "passive"},
                  {"number": "2", "name": "2", "type": "passive"}]},
    ]
    pin_net = {
        ("U1", "1"): ("+3V3", None),
        ("U1", "2"): ("GND", None),
        ("U1", "3"): ("PA0", None),
        ("C1", "1"): ("+3V3", None),
        ("C1", "2"): ("GND", None),
    }
    return _ctx(comps, pin_net)


class PassiveCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.sch = os.path.join(self.dir, "board.kicad_sch")
        with open(self.sch, "w") as fp:
            fp.write("(kicad_sch)\n")

    def _write_waivers(self, waivers):
        with open(os.path.join(self.dir, WAIVER_SIDECAR_FILENAME), "w") as fp:
            json.dump(waivers, fp)

    # ── 1. pinout-only → PC-001 error ───────────────────────────────────────
    def test_pinout_only_active_ic_fails(self):
        findings = validate_passive_completeness(_pinout_only_ctx())
        pc = [f for f in findings if f["rule_id"] == "PC-001"]
        self.assertEqual(len(pc), 1)
        f = pc[0]
        self.assertEqual(f["severity"], "error")
        self.assertEqual(f["confidence"], "deterministic")
        self.assertIn("U1", f["components"])
        self.assertIn("+3V3", f["nets"])
        self.assertFalse(f.get("waived"))

    # ── 2. decoupled → PASS ──────────────────────────────────────────────────
    def test_decoupled_active_ic_passes(self):
        findings = validate_passive_completeness(_decoupled_ctx())
        pc = [f for f in findings if f["rule_id"] == "PC-001"]
        self.assertEqual(pc, [])

    # ── 3. honest subset + waiver → PASS with waiver recorded ────────────────
    def test_waived_gap_recorded_not_silent(self):
        self._write_waivers([{
            "ref": "U1", "obligation": "decoupling",
            "source": "Netlist_Status.md",
            "reason": "reverse-engineered interface subset; decoupling out of scope",
            "scope": "baseline extraction",
        }])
        findings = validate_passive_completeness(_pinout_only_ctx(sch_path=self.sch))
        pc = [f for f in findings if f["rule_id"] == "PC-001"]
        self.assertEqual(len(pc), 1)
        f = pc[0]
        # No silent pass: still a finding, but downgraded + provenance carried.
        self.assertTrue(f.get("waived"))
        self.assertEqual(f["severity"], "info")
        self.assertEqual(f["waiver"]["source"], "Netlist_Status.md")
        self.assertIn("reverse-engineered", f["waiver"]["reason"])
        # No blocking error remains.
        self.assertFalse(any(x["severity"] == "error" for x in pc))

    # ── waiver provenance mandatory (no silent waiver) ───────────────────────
    def test_waiver_without_provenance_fails_fast(self):
        self._write_waivers([{"ref": "U1", "obligation": "decoupling"}])  # no source/reason
        with self.assertRaises(PassiveWaiverError) as ctx:
            validate_passive_completeness(_pinout_only_ctx(sch_path=self.sch))
        self.assertIn("provenance", str(ctx.exception))

    def test_malformed_waiver_json_fails_fast(self):
        with open(os.path.join(self.dir, WAIVER_SIDECAR_FILENAME), "w") as fp:
            fp.write("{not valid json")
        with self.assertRaises(PassiveWaiverError):
            validate_passive_completeness(_pinout_only_ctx(sch_path=self.sch))

    # ── waiver only matches the named (ref, obligation) ──────────────────────
    def test_waiver_for_other_ref_does_not_cover(self):
        self._write_waivers([{
            "ref": "U9", "obligation": "decoupling",
            "source": "x", "reason": "y",
        }])
        findings = validate_passive_completeness(_pinout_only_ctx(sch_path=self.sch))
        pc = [f for f in findings if f["rule_id"] == "PC-001"]
        self.assertEqual(len(pc), 1)
        self.assertEqual(pc[0]["severity"], "error")  # U1 gap not waived by U9 waiver

    # ── no false positive on an IC with no detectable power pin ──────────────
    def test_ic_without_power_pin_skipped(self):
        comps = [
            {"reference": "U2", "value": "74LVC1G", "lib_id": "Logic:74LVC1G",
             "type": "ic",
             "pins": [{"number": "1", "name": "A", "type": "input"},
                      {"number": "2", "name": "Y", "type": "output"}]},
        ]
        pin_net = {("U2", "1"): ("SIG_A", None), ("U2", "2"): ("SIG_Y", None)}
        findings = validate_passive_completeness(_ctx(comps, pin_net))
        self.assertEqual([f for f in findings if f["rule_id"] == "PC-001"], [])

    # ── missing sidecar → no waivers (all gaps block), not a crash ───────────
    def test_missing_sidecar_is_not_a_waiver(self):
        findings = validate_passive_completeness(_pinout_only_ctx(sch_path=self.sch))
        pc = [f for f in findings if f["rule_id"] == "PC-001"]
        self.assertEqual(len(pc), 1)
        self.assertEqual(pc[0]["severity"], "error")

    # ── determinism ──────────────────────────────────────────────────────────
    def test_determinism(self):
        a = validate_passive_completeness(_pinout_only_ctx())
        b = validate_passive_completeness(_pinout_only_ctx())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
