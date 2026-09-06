"""Unit tests for declare_circuit — TV-1..TV-8 of the plan's test-vectors.json.

Reading guide, because the point of several of these is NOT that they pass:

  TV-2, TV-4, TV-5 are CONTROLS. They must FAIL the thing TV-1/TV-3 pass, and
  they must fail FOR THE STATED REASON. A negative control is the one kind of
  check that can be satisfied by an accident — a rejection for the wrong cause
  looks exactly like a rejection for the right one — so each of them asserts the
  error CODE and the offending VALUE, not merely `status != ok`.

  test_codomain_all_five_statuses_are_reachable is the codomain coverage
  required by errors.md: each of the five status values is produced by some
  input in this file. A declared outcome nobody can trigger is a comment.
"""

import unittest

from bodesign_eda_bridge.declare import (
    GATE_FAIL,
    GATE_PASS,
    GATE_UNKNOWN,
    GATE_VACUOUS,
    STATUS_EMPTY,
    STATUS_INDETERMINATE,
    STATUS_NOT_RUN,
    STATUS_OK,
    STATUS_REJECTED,
    declare_circuit,
)

R = "Device:R"


def _codes(result):
    return [e["code"] for e in result["errors"]]


def _net(result, name):
    for n in result["spec"]["nets"]:
        if n["name"] == name:
            return n["nodes"]
    return None


class TestDividerExpansion(unittest.TestCase):
    """TV-1 — the acceptance shape named in the BR: a battery-sense divider."""

    def test_tv1_divider_expands_with_three_node_tap(self):
        r = declare_circuit(
            components=[
                {"ref": "R13", "symbol": R, "value": "100k"},
                {"ref": "R14", "symbol": R, "value": "100k"},
                {"ref": "U2", "symbol": "MCU_RaspberryPi:Pico2W"},
            ],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "VBAT_SENSE",
                    "r_top": "R13",
                    "r_bottom": "R14",
                    "load": "U2.31",
                }
            ],
            _pin_lists={"R13": ["1", "2"], "R14": ["1", "2"], "U2": ["31"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertEqual(_net(r, "BATT"), ["R13.1"])
        self.assertEqual(sorted(_net(r, "VBAT_SENSE")), ["R13.2", "R14.1", "U2.31"])
        self.assertEqual(_net(r, "GND"), ["R14.2"])
        self.assertEqual(r["completeness"]["verdict"], GATE_PASS)
        # The tap carries three endpoints; that is what forces a junction
        # downstream rather than a label farm.
        self.assertEqual(len(_net(r, "VBAT_SENSE")), 3)

    def test_tv1_provenance_names_the_declaration_for_every_node(self):
        r = declare_circuit(
            components=[
                {"ref": "R13", "symbol": R},
                {"ref": "R14", "symbol": R},
            ],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "VBAT_SENSE",
                    "r_top": "R13",
                    "r_bottom": "R14",
                }
            ],
            _pin_lists={"R13": ["1", "2"], "R14": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertTrue(r["provenance"])
        self.assertEqual(set(r["provenance"].values()), {"d1"})


class TestDividerTapControl(unittest.TestCase):
    """TV-2 — THE control for TV-1.

    Without this, TV-1's `ok` proves only that the function returns something.
    """

    def test_tv2_tap_equal_to_top_is_rejected_naming_the_tap(self):
        r = declare_circuit(
            components=[{"ref": "R13", "symbol": R}, {"ref": "R14", "symbol": R}],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "BATT",
                    "r_top": "R13",
                    "r_bottom": "R14",
                }
            ],
            _pin_lists={"R13": ["1", "2"], "R14": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_REJECTED)
        self.assertIn("E_DIVIDER_TAP_DEGENERATE", _codes(r))
        # It must be rejected BECAUSE of the tap, and say which tap. An error
        # object that does not echo the offending value cannot distinguish
        # "rejected for this reason" from "rejected for some other reason".
        err = next(e for e in r["errors"] if e["code"] == "E_DIVIDER_TAP_DEGENERATE")
        self.assertIn("BATT", err["refs"])
        self.assertIn("BATT", err["detail"])
        self.assertIn("top", err["detail"])

    def test_tv2b_tap_equal_to_bottom_is_also_rejected(self):
        r = declare_circuit(
            components=[{"ref": "R13", "symbol": R}, {"ref": "R14", "symbol": R}],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "GND",
                    "r_top": "R13",
                    "r_bottom": "R14",
                }
            ],
            _pin_lists={"R13": ["1", "2"], "R14": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_REJECTED)
        err = next(e for e in r["errors"] if e["code"] == "E_DIVIDER_TAP_DEGENERATE")
        self.assertIn("bottom", err["detail"])

    def test_tv2c_a_nondegenerate_tap_is_NOT_rejected(self):
        """Accepting control: proves the tap check is not rejecting everything."""
        r = declare_circuit(
            components=[{"ref": "R13", "symbol": R}, {"ref": "R14", "symbol": R}],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "MID",
                    "r_top": "R13",
                    "r_bottom": "R14",
                }
            ],
            _pin_lists={"R13": ["1", "2"], "R14": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertNotIn("E_DIVIDER_TAP_DEGENERATE", _codes(r))


class TestBridgeExpansion(unittest.TestCase):
    """TV-3 — decoupling / pull-up / current-limit all share this one shape."""

    def test_tv3_bridge_puts_one_pin_on_each_net(self):
        r = declare_circuit(
            components=[{"ref": "C8", "symbol": "Device:C", "value": "100nF"}],
            declarations=[
                {"id": "d2", "kind": "bridge", "part": "C8", "between": ["+3V3", "GND"]}
            ],
            _pin_lists={"C8": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertEqual(_net(r, "+3V3"), ["C8.1"])
        self.assertEqual(_net(r, "GND"), ["C8.2"])
        self.assertEqual(r["completeness"]["verdict"], GATE_PASS)

    def test_tv3b_explicit_pins_override_the_default_order(self):
        """Polarised parts must be able to say which pin goes where."""
        r = declare_circuit(
            components=[{"ref": "C8", "symbol": "Device:C_Polarized"}],
            declarations=[
                {
                    "id": "d2",
                    "kind": "bridge",
                    "part": "C8",
                    "between": ["+3V3", "GND"],
                    "pins": ["2", "1"],
                }
            ],
            _pin_lists={"C8": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertEqual(_net(r, "+3V3"), ["C8.2"])
        self.assertEqual(_net(r, "GND"), ["C8.1"])


class TestCompletenessGate(unittest.TestCase):
    """TV-4 / TV-5 — the two findings that make this entry point worth having."""

    def test_tv4_unassigned_pins_are_ALL_listed_not_just_the_first(self):
        r = declare_circuit(
            components=[{"ref": "U1", "symbol": "Regulator:TP4056"}],
            declarations=[
                {"id": "d3", "kind": "rail", "name": "GND", "nodes": ["U1.1"]}
            ],
            _pin_lists={"U1": ["1", "2", "3", "4", "5", "6", "7", "8"]},
        )
        self.assertEqual(r["status"], STATUS_REJECTED)
        self.assertIn("E_PIN_UNASSIGNED", _codes(r))
        err = next(e for e in r["errors"] if e["code"] == "E_PIN_UNASSIGNED")
        # All seven, not one. A first-error-only report makes the caller
        # iterate once per defect, and each iteration looks like progress.
        self.assertEqual(len(err["refs"]), 7)
        self.assertEqual(
            sorted(err["refs"]),
            ["U1.2", "U1.3", "U1.4", "U1.5", "U1.6", "U1.7", "U1.8"],
        )
        self.assertNotIn("U1.1", err["refs"])

    def test_tv5_a_pin_on_two_nets_is_an_electrical_contradiction(self):
        """Directly the shape of BR_20260802 (six pins declared in >1 net).

        Deviation from test-vectors.json TV-5, stated rather than hidden: the
        vector's R2/R3 are absent from components[], which this build rejects
        earlier as E_REF_UNKNOWN (status=not_run) and so never reaches the gate.
        Declaring them is what lets the vector test the thing it names.
        """
        r = declare_circuit(
            components=[
                {"ref": "R1", "symbol": R},
                {"ref": "R2", "symbol": R},
                {"ref": "R3", "symbol": R},
            ],
            declarations=[
                {"id": "d4", "kind": "connect", "endpoints": ["R1.1", "R2.1"], "net": "CC1"},
                {"id": "d5", "kind": "connect", "endpoints": ["R1.1", "R3.1"], "net": "VBUS_CON"},
            ],
            _pin_lists={"R1": ["1", "2"], "R2": ["1", "2"], "R3": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_REJECTED)
        self.assertIn("E_PIN_MULTI_NET", _codes(r))
        err = next(e for e in r["errors"] if e["code"] == "E_PIN_MULTI_NET")
        joined = " ".join(err["refs"])
        # Naming BOTH nets is what makes this actionable; "R1.1 is on 2 nets"
        # would not tell the caller which declaration to change.
        self.assertIn("R1.1", joined)
        self.assertIn("CC1", joined)
        self.assertIn("VBUS_CON", joined)

    def test_tv5b_the_same_two_declarations_on_DIFFERENT_pins_pass(self):
        """Accepting control for TV-5: the gate is not rejecting all pairs."""
        r = declare_circuit(
            components=[
                {"ref": "R1", "symbol": R},
                {"ref": "R2", "symbol": R},
                {"ref": "R3", "symbol": R},
            ],
            declarations=[
                {"id": "d4", "kind": "connect", "endpoints": ["R1.1", "R2.1"], "net": "CC1"},
                {"id": "d5", "kind": "connect", "endpoints": ["R1.2", "R3.1"], "net": "VBUS_CON"},
                {"id": "d6", "kind": "no_connect", "pins": ["R2.2", "R3.2"]},
            ],
            _pin_lists={"R1": ["1", "2"], "R2": ["1", "2"], "R3": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertNotIn("E_PIN_MULTI_NET", _codes(r))

    def test_tv13_no_connect_counts_as_assigned(self):
        r = declare_circuit(
            components=[{"ref": "U2", "symbol": "MCU_RaspberryPi:Pico2W"}],
            declarations=[{"id": "d11", "kind": "no_connect", "pins": ["U2.35"]}],
            _pin_lists={"U2": ["35"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        self.assertIn("U2.35", r["spec"]["nc"])
        self.assertEqual(r["completeness"]["unassigned"], [])


class TestEmptyIsNotOk(unittest.TestCase):
    """TV-6 — BR_20260730b: four gates went green on an empty spec.

    If this returned `ok`, this module would have reproduced the exact defect
    the package was opened to remove.
    """

    def test_tv6_no_declarations_yields_empty_not_ok(self):
        r = declare_circuit(components=[], declarations=[])
        self.assertEqual(r["status"], STATUS_EMPTY)
        self.assertNotEqual(r["status"], STATUS_OK)

    def test_tv6b_gate_on_zero_components_is_vacuous_not_pass(self):
        """The gate's own empty state. `vacuous` and `pass` must not share a value:
        'checked 8 pins, all fine' and 'had nothing to check' are different facts.
        """
        r = declare_circuit(components=[], declarations=[])
        self.assertEqual(r["completeness"]["verdict"], GATE_VACUOUS)
        self.assertNotEqual(r["completeness"]["verdict"], GATE_PASS)


class TestIndeterminate(unittest.TestCase):
    """TV-7 — an unreadable symbol is neither a pass nor the caller's fault."""

    def test_tv7_unreadable_symbol_yields_indeterminate(self):
        r = declare_circuit(
            components=[{"ref": "U9", "symbol": "NoSuchLib:NoSuchPart"}],
            declarations=[
                {"id": "d6", "kind": "rail", "name": "GND", "nodes": ["U9.1"]}
            ],
            symbol_dirs=["/nonexistent"],
            _pin_lists={},  # nothing resolved, as if every load_symbol raised
        )
        self.assertEqual(r["status"], STATUS_INDETERMINATE)
        self.assertEqual(r["completeness"]["verdict"], GATE_UNKNOWN)
        self.assertTrue(any("U9" in u for u in r["unknown"]))
        # Claiming ok would be a lie; claiming rejected would blame the caller
        # for the engine's inability to read a library.
        self.assertNotEqual(r["status"], STATUS_OK)
        self.assertNotEqual(r["status"], STATUS_REJECTED)

    def test_tv7b_same_input_with_a_readable_symbol_is_ok(self):
        """Accepting control for TV-7: proves `unknown` tracks readability,
        not merely the presence of a rail declaration."""
        r = declare_circuit(
            components=[{"ref": "U9", "symbol": "Device:R"}],
            declarations=[
                {"id": "d6", "kind": "rail", "name": "GND", "nodes": ["U9.1"]}
            ],
            _pin_lists={"U9": ["1"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])


class TestProvenance(unittest.TestCase):
    """TV-8 — DD-6: the machine-checkable form of the No-fabrication rule."""

    def test_tv8_every_node_has_an_originating_declaration(self):
        r = declare_circuit(
            components=[{"ref": "R13", "symbol": R}, {"ref": "R14", "symbol": R}],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "VBAT_SENSE",
                    "r_top": "R13",
                    "r_bottom": "R14",
                }
            ],
            _pin_lists={"R13": ["1", "2"], "R14": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_OK, r["errors"])
        all_nodes = {
            f"{n['name']}.{ep}" for n in r["spec"]["nets"] for ep in n["nodes"]
        }
        self.assertEqual(all_nodes, set(r["provenance"]))
        self.assertEqual(len(all_nodes - set(r["provenance"])), 0)

    def test_tv8b_the_orphan_assertion_can_actually_fail(self):
        """Control for TV-8. Without this, the equality above proves only that
        two views of the same loop agree — it would hold even if the assertion
        were incapable of detecting an invented node.
        """
        from bodesign_eda_bridge.declare import _Expansion, _check_provenance

        ex = _Expansion()
        ex.add_node("BATT", "R13.1", "d1")
        # An invented node: present in nets, absent from provenance.
        ex.nets["GHOST"] = ["R99.1"]
        errs = _check_provenance(ex)
        self.assertEqual([e.code for e in errs], ["E_PROVENANCE_ORPHAN"])
        self.assertIn("GHOST.R99.1", errs[0].refs)


class TestNotRun(unittest.TestCase):
    """status=not_run — emitted BEFORE the expander, and distinct from rejected."""

    def test_unknown_ref_is_not_run_not_rejected(self):
        r = declare_circuit(
            components=[{"ref": "R13", "symbol": R}],
            declarations=[
                {
                    "id": "d1",
                    "kind": "divider",
                    "top": "BATT",
                    "bottom": "GND",
                    "tap": "MID",
                    "r_top": "R13",
                    "r_bottom": "R_MISSING",
                }
            ],
            _pin_lists={"R13": ["1", "2"]},
        )
        self.assertEqual(r["status"], STATUS_NOT_RUN)
        self.assertIn("E_REF_UNKNOWN", _codes(r))
        self.assertIn("R_MISSING", r["offending_refs"])
        # not_run means the expander never ran, so there is no gate verdict.
        self.assertEqual(r["completeness"]["verdict"], "not_run")
        self.assertIsNone(r["spec"])


class TestOutcomeCodomainCoverage(unittest.TestCase):
    """errors.md #Outcome Codomain: every declared status is reachable.

    A codomain row nobody can trigger is a comment. This test is what makes the
    table in errors.md a claim about this build rather than about an intention.
    """

    def test_all_five_declare_circuit_statuses_are_reachable(self):
        seen = set()

        seen.add(
            declare_circuit(
                components=[{"ref": "C8", "symbol": "Device:C"}],
                declarations=[
                    {"id": "a", "kind": "bridge", "part": "C8", "between": ["+3V3", "GND"]}
                ],
                _pin_lists={"C8": ["1", "2"]},
            )["status"]
        )
        seen.add(declare_circuit(components=[], declarations=[])["status"])
        seen.add(
            declare_circuit(
                components=[{"ref": "R1", "symbol": R}],
                declarations=[{"id": "b", "kind": "connect", "endpoints": ["NOPE.1"]}],
                _pin_lists={"R1": ["1", "2"]},
            )["status"]
        )
        seen.add(
            declare_circuit(
                components=[{"ref": "R1", "symbol": R}],
                declarations=[
                    {
                        "id": "c",
                        "kind": "divider",
                        "top": "A",
                        "bottom": "B",
                        "tap": "A",
                        "r_top": "R1",
                        "r_bottom": "R1",
                    }
                ],
                _pin_lists={"R1": ["1", "2"]},
            )["status"]
        )
        seen.add(
            declare_circuit(
                components=[{"ref": "U9", "symbol": "NoSuchLib:X"}],
                declarations=[
                    {"id": "d", "kind": "rail", "name": "GND", "nodes": ["U9.1"]}
                ],
                _pin_lists={},
            )["status"]
        )

        self.assertEqual(
            seen,
            {
                STATUS_OK,
                STATUS_REJECTED,
                STATUS_NOT_RUN,
                STATUS_EMPTY,
                STATUS_INDETERMINATE,
            },
        )

    def test_all_five_gate_verdicts_are_reachable(self):
        from bodesign_eda_bridge.declare import _Expansion, check_completeness

        seen = set()
        # vacuous: ran, nothing to check
        seen.add(check_completeness([], _Expansion(), {}).verdict)
        # unknown: symbol unreadable
        seen.add(
            check_completeness(
                [{"ref": "U9", "symbol": "NoSuchLib:X"}], _Expansion(), {}
            ).verdict
        )
        # fail: a pin left unassigned
        seen.add(
            check_completeness(
                [{"ref": "R1", "symbol": R}], _Expansion(), {"R1": ["1", "2"]}
            ).verdict
        )
        # pass: everything accounted for
        ex = _Expansion()
        ex.add_node("N1", "R1.1", "d")
        ex.add_node("N2", "R1.2", "d")
        seen.add(
            check_completeness(
                [{"ref": "R1", "symbol": R}], ex, {"R1": ["1", "2"]}
            ).verdict
        )
        # not_run is emitted by the CALLER, not by the gate: the gate cannot
        # report that it was never called. Its reachability is asserted where it
        # is actually produced (TestNotRun above).
        self.assertEqual(seen, {GATE_PASS, GATE_FAIL, GATE_VACUOUS, GATE_UNKNOWN})


if __name__ == "__main__":
    unittest.main()
