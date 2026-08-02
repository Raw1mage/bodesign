"""BR_20260802 — the gate's green meant "the wiring agrees with the paperwork"
but was read as "the circuit is correct".

Two real defects on the same board passed every rule AND ERC: a switching node
merged into a power rail (a legal net) and an absent feedforward capacitor (not
a wire at all). Neither is expressible in connectivity terms, so nothing in the
pipeline reported them — a human happened to read a datasheet.

F1 (not_checked) is the load-bearing half and is tested first: rules can never
be exhaustive, but the boundary can be stated in full. R7/R8 close the two
specific holes and each carries a MUTATION PROOF — remove the part / unshort the
node and the verdict must flip. A rule that cannot go red is not a rule.
"""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

check_c03 = importlib.import_module("bodesign_workflow_core.check_c03")

_HDR = "board,ref,value,mpn,qty,status,deck_status\n"


def _write(tmp: str, name: str, body: str) -> str:
    p = os.path.join(tmp, name)
    Path(p).write_text(body, encoding="utf-8")
    return p


def _bom(tmp: str, rows: list[str], name: str = "bom.csv") -> str:
    return _write(tmp, name, _HDR + "".join(
        r if r.endswith("\n") else r + "\n" for r in rows))


def _codes(result) -> list[str]:
    return [f.code for f in result.blocking]


# ── netlist fixtures ────────────────────────────────────────────────────────

def _buck_netlist(*, feedforward: bool, divider: bool = True) -> str:
    """An adjustable TPS62824 with FB divider, with/without the feedforward cap.

    This is the mutation axis for R7: the ONLY difference between the two forms
    is whether C_FF exists. Everything else — refdeses, nets, pin functions —
    is byte-identical, so a verdict change can only be attributed to the cap.
    """
    comps = ['(comp (ref "U6") (value "TPS62824DMQ"))',
             '(comp (ref "L1") (value "1uH"))']
    if divider:
        comps += ['(comp (ref "R_U6_1") (value "100k"))',
                  '(comp (ref "R_U6_2") (value "100k"))']
    if feedforward:
        comps.append('(comp (ref "C_FF_U6") (value "120p"))')
    fb_nodes = ['(node (ref "U6") (pin "5") (pinfunction "FB"))']
    if divider:
        fb_nodes += ['(node (ref "R_U6_1") (pin "2") (pintype "passive"))',
                     '(node (ref "R_U6_2") (pin "1") (pintype "passive"))']
    if feedforward:
        fb_nodes.append('(node (ref "C_FF_U6") (pin "2") (pintype "passive"))')
    return f"""(export (version "E")
  (design (source "/work/probe/buck.kicad_sch"))
  (components
    {chr(10).join('    ' + c for c in comps)})
  (nets
    (net (code "1") (name "VOUT_1V8") (class "Default")
      (node (ref "U6") (pin "1") (pinfunction "VOS"))
      (node (ref "L1") (pin "2") (pintype "passive")))
    (net (code "2") (name "SW_U6") (class "Default")
      (node (ref "U6") (pin "2") (pinfunction "SW"))
      (node (ref "L1") (pin "1") (pintype "passive")))
    (net (code "3") (name "FB_U6") (class "Default")
      {chr(10).join('      ' + n for n in fb_nodes)})
    (net (code "4") (name "GND") (class "Default")
      (node (ref "U6") (pin "6") (pinfunction "GND")))))
"""


def _smps_netlist(*, shorted: bool) -> str:
    """STM32-style SMPS whose switching output is (or is not) tied to +1V8.

    Mutation axis for R8. When `shorted`, VLXSMPS/VFBSMPS sit on the +1V8 rail —
    exactly the aiguard CCM defect: one ordinary-looking 3-pad net that ERC has
    no reason to complain about.
    """
    sw_net = "+1V8" if shorted else "VLX_SMPS"
    fb_net = "+1V8" if shorted else "VFB_SMPS"
    return f"""(export (version "E")
  (design (source "/work/probe/smps.kicad_sch"))
  (components
    (comp (ref "U1") (value "STM32N657"))
    (comp (ref "L2") (value "2u2")))
  (nets
    (net (code "1") (name "{sw_net}") (class "Default")
      (node (ref "U1") (pin "K1") (pinfunction "VLXSMPS"))
      (node (ref "L2") (pin "1") (pintype "passive")))
    (net (code "2") (name "{fb_net}") (class "Default")
      (node (ref "U1") (pin "G2") (pinfunction "VFBSMPS")))
    (net (code "3") (name "GND") (class "Default")
      (node (ref "U1") (pin "B1") (pinfunction "VSS")))))
"""


_NO_PINFUNCTION = """(export (version "E")
  (design (source "/work/probe/plain.kicad_sch"))
  (components
    (comp (ref "U6") (value "TPS62824DMQ")))
  (nets
    (net (code "1") (name "+1V8") (class "Default")
      (node (ref "U6") (pin "2") (pintype "passive")))))
"""

# pinfunction IS present throughout -- but not one of them names a switching or
# feedback node. R8's loop therefore completes having examined zero subjects.
# This is the shape of the real aiguard power-frontend netlist, not a contrivance.
_NO_SWITCH_PINS = """(export (version "E")
  (design (source "/work/probe/nosw.kicad_sch"))
  (components
    (comp (ref "U1") (value "MCU"))
    (comp (ref "R1") (value "10k")))
  (nets
    (net (code "1") (name "+3V3") (class "Default")
      (node (ref "U1") (pin "1") (pinfunction "VDD"))
      (node (ref "R1") (pin "1") (pinfunction "~")))
    (net (code "2") (name "GND") (class "Default")
      (node (ref "U1") (pin "2") (pinfunction "VSS"))
      (node (ref "R1") (pin "2") (pinfunction "~")))))
"""


# ── F1: the scope disclosure ────────────────────────────────────────────────

class NotCheckedDisclosureTests(unittest.TestCase):
    """F1 — the half of the verdict that says what was never examined.

    The BR's core claim is that "checked and clean" and "outside my domain"
    returned the same green. This field is what separates them, so it must be
    present in EVERY outcome, not only the interesting ones.
    """

    def test_not_checked_is_non_empty_on_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, ["CORE,R1,10k,RC0402J103,1,finalized,official"])
            res = check_c03.check_c03(bom)
            self.assertEqual(res.gate, "PASS")
            self.assertTrue(res.not_checked,
                            "a PASS is exactly when the reader most needs to be "
                            "told what was not examined")

    def test_not_checked_is_non_empty_on_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, ["CORE,R1,10k,TBD,1,draft,official"])
            res = check_c03.check_c03(bom)
            self.assertEqual(res.gate, "FAIL")
            self.assertTrue(res.not_checked,
                            "a FAIL lists what IS wrong; it must still say which "
                            "classes it never looked at")

    def test_not_checked_names_the_two_defect_classes_from_this_br(self):
        """Both defects that motivated this BR must be findable by name."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, ["CORE,R1,10k,RC0402J103,1,finalized,official"])
            joined = " ".join(check_c03.check_c03(bom).not_checked)
            self.assertIn("topology_plausibility", joined)
            self.assertIn("datasheet_mandated_passives", joined)

    def test_not_checked_says_a_rule_did_not_run_rather_than_omitting_it(self):
        """not_run must be stated, never silently dropped from the list.

        Omitting the entry would make an unrun rule indistinguishable from a
        covered one — the exact conflation this BR is about, reproduced one
        level down.
        """
        nc = check_c03._build_not_checked(
            {"status": "not_run", "reason": "no netlist supplied"},
            {"status": "not_run", "reason": "no netlist supplied"})
        joined = " ".join(nc)
        self.assertIn("R7 did NOT run", joined)
        self.assertIn("R8 did NOT run", joined)

    def test_not_checked_still_states_residual_scope_when_rules_did_run(self):
        """Even with R7/R8 green, what they do NOT cover must stay visible.

        R8 catches one topology error out of an unbounded space; saying nothing
        once it runs would re-imply full topology coverage.
        """
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_not_covered": ["U9: SOME-LDO"]},
            {"status": "run"})
        joined = " ".join(nc)
        self.assertIn("ONLY that one topology error", joined)
        self.assertIn("outside the requirement table", joined)

    def test_base_list_is_never_empty(self):
        """Reverse discrimination: empty the base list and the guarantee dies."""
        self.assertGreaterEqual(len(check_c03._NOT_CHECKED_BASE), 5)


# ── R7: datasheet-mandated passives ─────────────────────────────────────────

class MandatedPassiveTests(unittest.TestCase):

    _BOM = ["CORE,U6,buck 1V8,TPS62824DMQ,1,finalized,official"]

    def test_missing_feedforward_capacitor_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "b.net", _buck_netlist(feedforward=False))
            res = check_c03.check_c03(bom, netlist_path=net)
            self.assertIn("R7_MANDATED_PASSIVE", _codes(res))
            self.assertEqual(res.gate, "FAIL")

    def test_mutation_proof_adding_the_capacitor_turns_it_green(self):
        """The BR's acceptance condition: remove C_FF -> red, restore -> green.

        Without this pairing a rule can be permanently red or permanently green
        and look identical in CI.
        """
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            without = _write(tmp, "no.net", _buck_netlist(feedforward=False))
            with_cap = _write(tmp, "yes.net", _buck_netlist(feedforward=True))
            red = check_c03.check_c03(bom, netlist_path=without)
            green = check_c03.check_c03(bom, netlist_path=with_cap)
            self.assertIn("R7_MANDATED_PASSIVE", _codes(red))
            self.assertNotIn("R7_MANDATED_PASSIVE", _codes(green),
                             "restoring the mandated part must clear the finding, "
                             "else the rule is stuck red and will be ignored")

    def test_missing_divider_is_reported_distinctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "b.net", _buck_netlist(feedforward=True, divider=False))
            res = check_c03.check_c03(bom, netlist_path=net)
            detail = " ".join(f.detail for f in res.blocking
                              if f.code == "R7_MANDATED_PASSIVE")
            self.assertIn("feedback divider", detail)

    def test_finding_cites_the_datasheet_section(self):
        """An uncited electrical claim is exactly what this repo forbids."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "b.net", _buck_netlist(feedforward=False))
            res = check_c03.check_c03(bom, netlist_path=net)
            detail = " ".join(f.detail for f in res.blocking
                              if f.code == "R7_MANDATED_PASSIVE")
            self.assertIn("8.2.2.2", detail)

    def test_part_outside_the_table_is_named_not_swallowed(self):
        """BR acceptance #3 — an uncovered part must be listed, never folded
        into the green. This is the R4_SSOT zero-discrimination lesson."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, ["CORE,U9,ldo 3V3,TLV75533PDBVR,1,finalized,official"])
            net = _write(tmp, "b.net", _buck_netlist(feedforward=True))
            res = check_c03.check_c03(bom, netlist_path=net)
            self.assertNotIn("R7_MANDATED_PASSIVE", _codes(res))
            listed = " ".join(res.mandated_passives.get("parts_not_covered") or [])
            self.assertIn("U9", listed)
            self.assertIn("TLV75533PDBVR", listed)

    def test_part_in_table_but_absent_from_netlist_is_unresolved_not_clean(self):
        """A part the netlist never mentions cannot be verified — and must not
        read as verified."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, ["CORE,U7,buck,TPS62088YFPR,1,finalized,official"])
            net = _write(tmp, "b.net", _buck_netlist(feedforward=True))
            res = check_c03.check_c03(bom, netlist_path=net)
            refs = [u["ref"] for u in res.mandated_passives.get("parts_unresolved") or []]
            self.assertIn("U7", refs)

    def test_not_run_without_netlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            res = check_c03.check_c03(bom)
            self.assertEqual(res.mandated_passives.get("status"), "not_run")
            self.assertIn("reason", res.mandated_passives)


# ── R8: switch node on a power rail ─────────────────────────────────────────

class SwitchNodeShortTests(unittest.TestCase):

    _BOM = ["CORE,U1,soc,STM32N657X0H3Q,1,finalized,official"]

    def test_switching_node_on_power_rail_is_blocking(self):
        """The aiguard CCM defect: VLXSMPS/VFBSMPS merged into +1V8."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "s.net", _smps_netlist(shorted=True))
            res = check_c03.check_c03(bom, netlist_path=net)
            self.assertIn("R8_SWITCH_NODE", _codes(res))
            self.assertEqual(res.gate, "FAIL")

    def test_mutation_proof_separating_the_nets_turns_it_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            bad = _write(tmp, "bad.net", _smps_netlist(shorted=True))
            good = _write(tmp, "good.net", _smps_netlist(shorted=False))
            self.assertIn("R8_SWITCH_NODE",
                          _codes(check_c03.check_c03(bom, netlist_path=bad)))
            self.assertNotIn("R8_SWITCH_NODE",
                             _codes(check_c03.check_c03(bom, netlist_path=good)),
                             "a correctly-wired switch node must clear the rule")

    def test_finding_names_the_rail_and_the_pin_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "s.net", _smps_netlist(shorted=True))
            res = check_c03.check_c03(bom, netlist_path=net)
            detail = " ".join(f.detail for f in res.blocking
                              if f.code == "R8_SWITCH_NODE")
            self.assertIn("+1V8", detail)
            self.assertIn("VLXSMPS", detail)

    def test_no_pinfunction_reports_not_run_rather_than_clean(self):
        """Without pinfunction the rule CANNOT identify a switch node. Saying
        'run, clean' there would be the BR's own defect in miniature."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "p.net", _NO_PINFUNCTION)
            res = check_c03.check_c03(bom, netlist_path=net)
            self.assertEqual(res.switch_node_shorts.get("status"), "not_run")
            self.assertNotIn("R8_SWITCH_NODE", _codes(res))

    def test_exact_token_match_does_not_flag_an_unrelated_pin(self):
        """'VSW_SENSE' contains 'sw'. A substring rule would fire on it, and a
        rule that flags correct work trains the reader to ignore it."""
        self.assertFalse(check_c03._fn_matches("VSW_SENSE", check_c03._SWITCH_PIN_FUNCS))
        self.assertTrue(check_c03._fn_matches("SW", check_c03._SWITCH_PIN_FUNCS))
        self.assertTrue(check_c03._fn_matches("VLXSMPS", check_c03._SWITCH_PIN_FUNCS))

    def test_not_run_without_netlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            res = check_c03.check_c03(bom)
            self.assertEqual(res.switch_node_shorts.get("status"), "not_run")

    def test_zero_examined_pins_is_not_run_even_though_the_loop_completed(self):
        """pinfunction present, but no pin NAMES a switch/feedback node.

        The loop runs to completion and finds nothing, so the natural report is
        `run / shorted_to_rail: 0` -- indistinguishable from a board that was
        examined and is clean. Measured on the real aiguard power-frontend
        netlist, which is exactly this case.
        """
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            net = _write(tmp, "nofb.net", _NO_SWITCH_PINS)
            res = check_c03.check_c03(bom, netlist_path=net)
            rep = res.switch_node_shorts
            self.assertEqual(rep.get("status"), "not_run",
                             "a rule that inspected zero subjects has not run")
            self.assertEqual(rep.get("switch_feedback_pins_checked"), 0)
            self.assertIn("nothing was looked at", rep.get("reason", ""))

    def test_mutation_proof_adding_one_switch_pin_flips_it_to_run(self):
        """Reverse discrimination for the rule above: without this, `not_run`
        could be hard-coded and nothing would notice."""
        with tempfile.TemporaryDirectory() as tmp:
            bom = _bom(tmp, self._BOM)
            none = _write(tmp, "none.net", _NO_SWITCH_PINS)
            some = _write(tmp, "some.net", _smps_netlist(shorted=False))
            self.assertEqual(
                check_c03.check_c03(bom, netlist_path=none)
                .switch_node_shorts.get("status"), "not_run")
            self.assertEqual(
                check_c03.check_c03(bom, netlist_path=some)
                .switch_node_shorts.get("status"), "run",
                "one identifiable switch pin must be enough to make it a real run")


# ── F1 follow-up: what the disclosure itself was hiding ───────────────────

class UnresolvedInTablePartsTests(unittest.TestCase):
    """A part that IS in the requirement table but could not be resolved.

    Measured on the real aiguard inputs: U5/U6 are both in the table, both
    unresolvable (no pinfunction on their nodes), and `not_checked` said
    nothing about them -- the disclosure reproduced, one level down, the very
    conflation it was built to remove.
    """

    def test_unresolved_in_table_parts_are_named_in_not_checked(self):
        nc = check_c03._build_not_checked(
            {"status": "run",
             "parts_unresolved": [{"ref": "U6", "family": "TPS6282x",
                                  "reason": "no feedback pin identifiable"}],
             "parts_not_covered": []},
            {"status": "run"})
        joined = " ".join(nc)
        self.assertIn("U6", joined)
        self.assertIn("TPS6282x", joined)
        self.assertIn("hole inside the covered set", joined)

    def test_unresolved_entry_comes_before_the_out_of_table_count(self):
        """Ordering is the whole point: the known-requirement miss must not sit
        below a line reporting dozens of parts nobody expected coverage for."""
        nc = check_c03._build_not_checked(
            {"status": "run",
             "parts_unresolved": [{"ref": "U5", "family": "TPS6208x"}],
             "parts_not_covered": [f"R{i}: RC0402" for i in range(30)]},
            {"status": "run"})
        idx_unres = next(i for i, x in enumerate(nc) if "U5" in x)
        idx_outside = next(i for i, x in enumerate(nc)
                           if "outside the requirement table" in x)
        self.assertLess(idx_unres, idx_outside)

    def test_reverse_no_unresolved_parts_adds_no_line(self):
        """A gate that always says 'something went unverified' says nothing."""
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [], "parts_not_covered": []},
            {"status": "run"})
        self.assertNotIn("hole inside the covered set", " ".join(nc))


class NotCoveredSignalToNoiseTests(unittest.TestCase):
    """Passives are counted; actives are named.

    On the real aiguard BOM the out-of-table list is 32 parts. Listing all of
    them makes the line unreadable, and an unread disclosure is the unread
    green it replaced. But suppressing it entirely would hide an unrecognised
    IC, which is the one thing a reader must see.
    """

    def test_active_parts_are_named(self):
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [],
             "parts_not_covered": ["U9: TLV75533PDBVR", "R1: RC0402J103"]},
            {"status": "run"})
        joined = " ".join(nc)
        self.assertIn("U9: TLV75533PDBVR", joined)

    def test_passive_parts_are_counted_not_listed(self):
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [],
             "parts_not_covered": [f"R{i}: RC0402J103" for i in range(40)]},
            {"status": "run"})
        line = next(x for x in nc if "outside the requirement table" in x)
        self.assertIn("40 part(s)", line)
        self.assertIn("0 active", line)
        self.assertIn("40 passive", line)
        self.assertNotIn("RC0402J103", line,
                         "listing 40 resistors is how a disclosure stops being read")

    def test_the_count_still_states_the_total_so_nothing_is_hidden(self):
        """Summarising must never become omitting: the total stays exact."""
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [],
             "parts_not_covered": ["U9: LDO"] + [f"C{i}: CC0402" for i in range(31)]},
            {"status": "run"})
        line = next(x for x in nc if "outside the requirement table" in x)
        self.assertIn("32 part(s)", line)
        self.assertIn("1 active", line)
        self.assertIn("31 passive", line)

    def test_many_actives_are_truncated_with_an_explicit_remainder(self):
        """Truncation must announce itself -- a silently cut list is a lie."""
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [],
             "parts_not_covered": [f"U{i}: PART{i}" for i in range(20)]},
            {"status": "run"})
        line = next(x for x in nc if "outside the requirement table" in x)
        self.assertIn("20 active", line)
        self.assertIn("more", line)


if __name__ == "__main__":
    unittest.main()
