"""PC-001 relocated into the delivery path (plan c03_delivery_contract_and_engine_seams
WP2, DD-01/DD-08).

The detector existed and was correct at
skills/bodesign/engines/kicad/scripts/validation_detectors.py:1261 — and the MCP
delivery path never called it. A rule the delivery path cannot reach is, from the
deliverable's point of view, a rule that does not exist. These tests measure it
where C03 is actually adjudicated: through check_c03() itself.

The pair that carries the weight is 2.5a / 2.5b. They share ONE fixture builder
whose only axis is whether the decoupling cap exists, so a verdict change cannot
be attributed to anything else. 2.5b additionally asserts that the OTHER findings
are byte-identical — a "fix" that silences the finding by breaking the rest of the
gate would otherwise read as a pass.
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


def _codes(result) -> list[str]:
    return [f.code for f in result.blocking]


# ── the single mutation axis ────────────────────────────────────────────────

def _bom_rows(*, decoupling: bool) -> list[str]:
    rows = ["PRODUCT,U1,MCU,STM32N657X0,1,finalized,official"]
    if decoupling:
        rows.append("PRODUCT,C1,100n,CC0402-100N,1,finalized,official")
    return rows


def _netlist(*, decoupling: bool, pinfunction: bool = True,
             rail_name: str = "+3V3") -> str:
    """An active IC on a power rail, with and without a rail→GND capacitor.

    Everything except C1 is byte-identical between the two forms: same refdes,
    same nets, same pin functions. `pinfunction=False` strips the annotations to
    exercise the not-run path, which must NOT read as clean.
    """
    comps = ['(comp (ref "U1") (value "STM32N657X0"))']
    if decoupling:
        comps.append('(comp (ref "C1") (value "100n"))')

    def _pf(name: str) -> str:
        return f'(pinfunction "{name}") ' if pinfunction else ""

    rail_nodes = [f'(node (ref "U1") (pin "F1") {_pf("VDD")}(pintype "power_in"))']
    gnd_nodes = [f'(node (ref "U1") (pin "F2") {_pf("VSS")}(pintype "power_in"))']
    if decoupling:
        rail_nodes.append('(node (ref "C1") (pin "1") (pintype "passive"))')
        gnd_nodes.append('(node (ref "C1") (pin "2") (pintype "passive"))')
    return f"""(export (version "E")
  (design (source "/work/probe/pc001.kicad_sch"))
  (components
    {chr(10).join('    ' + c for c in comps)})
  (nets
    (net (code "1") (name "{rail_name}") (class "Default")
      {chr(10).join('      ' + n for n in rail_nodes)})
    (net (code "2") (name "GND") (class "Default")
      {chr(10).join('      ' + n for n in gnd_nodes)})))
"""


def _run(tmp: str, *, decoupling: bool, **kw):
    bom = _write(tmp, "bom.csv", _HDR + "".join(
        r + "\n" for r in _bom_rows(decoupling=decoupling)))
    net = _write(tmp, "board.net", _netlist(decoupling=decoupling, **kw))
    return check_c03.check_c03(bom, netlist_path=net)


# ── 2.5a / 2.5b: the discriminating pair ────────────────────────────────────

class PC001MutationProofTests(unittest.TestCase):
    """The rule must go red on the defect and green on its repair.

    Either half alone proves nothing: a rule that always fires passes 2.5a, and a
    rule that never fires passes 2.5b.
    """

    def test_2_5a_undecoupled_active_ic_is_blocking(self):
        """POSITIVE CONTROL: no decoupling anywhere ⇒ gate=FAIL carrying PC-001."""
        with tempfile.TemporaryDirectory() as tmp:
            res = _run(tmp, decoupling=False)
        self.assertEqual(res.gate, "FAIL")
        self.assertIn("PC-001", _codes(res))
        pc = [f for f in res.blocking if f.code == "PC-001"]
        self.assertEqual([f.ref for f in pc], ["U1"])
        self.assertIn("+3V3", pc[0].detail)
        self.assertIn("ZERO decoupling", pc[0].detail)
        self.assertEqual(res.passive_completeness["status"], "run")

    def test_2_5b_adding_decoupling_removes_the_finding_and_changes_nothing_else(self):
        """NEGATIVE CONTROL: same fixture + one cap ⇒ PC-001 gone.

        The second assertion is the load-bearing one: every OTHER finding must be
        literally unchanged. Without it, a rule that silenced PC-001 by breaking
        R1-R8 would pass this test.
        """
        with tempfile.TemporaryDirectory() as tmp:
            before = _run(tmp, decoupling=False)
        with tempfile.TemporaryDirectory() as tmp:
            after = _run(tmp, decoupling=True)

        self.assertIn("PC-001", _codes(before))
        self.assertNotIn("PC-001", _codes(after))

        others_before = sorted((f.code, f.ref, f.detail)
                               for f in before.blocking if f.code != "PC-001")
        others_after = sorted((f.code, f.ref, f.detail)
                              for f in after.blocking if f.code != "PC-001")
        self.assertEqual(others_before, others_after,
                         "the repair must silence PC-001 and nothing else")
        self.assertEqual(after.passive_completeness["status"], "run")
        self.assertEqual(
            [c for c in after.passive_completeness["ics_checked"]
             if c["ref"] == "U1"][0]["verdict"], "ok")


# ── not-run discipline: zero subjects is never clean ────────────────────────

class PC001NotRunTests(unittest.TestCase):

    def test_no_netlist_reports_not_run_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom = _write(tmp, "bom.csv", _HDR + "".join(
                r + "\n" for r in _bom_rows(decoupling=False)))
            res = check_c03.check_c03(bom)
        self.assertEqual(res.passive_completeness["status"], "not_run")
        self.assertIn("netlist_path not supplied",
                      res.passive_completeness["reason"])

    def test_netlist_without_pinfunctions_reports_not_run(self):
        """No pinfunction ⇒ a supply pin cannot be named ⇒ nothing was examined.

        This is the same board as 2.5a — genuinely undecoupled. Reporting it as
        `run` with zero findings would be the exact false-pass PC-001 exists for.
        """
        with tempfile.TemporaryDirectory() as tmp:
            res = _run(tmp, decoupling=False, pinfunction=False)
        self.assertEqual(res.passive_completeness["status"], "not_run")
        self.assertIn("no pinfunction annotations",
                      res.passive_completeness["reason"])
        self.assertNotIn("PC-001", _codes(res))

    def test_pinfunctions_present_but_no_supply_pin_on_a_power_net(self):
        """Annotations exist, none names a rail ⇒ zero rails examined ⇒ not_run.

        Mirrors R8's `checked == 0` rule: a loop that ran over nothing has not run.
        """
        with tempfile.TemporaryDirectory() as tmp:
            res = _run(tmp, decoupling=False, rail_name="GND2")
        self.assertEqual(res.passive_completeness["status"], "not_run")
        self.assertIn("zero rails were examined",
                      res.passive_completeness["reason"])
        self.assertIn("U1",
                      res.passive_completeness["ics_without_identifiable_rail"])


# ── the disclosure half (_build_not_checked third branch) ───────────────────

class PC001DisclosureTests(unittest.TestCase):

    def test_not_run_states_that_pc001_did_not_run(self):
        nc = check_c03._build_not_checked(
            {"status": "not_run", "reason": "no netlist supplied"},
            {"status": "not_run", "reason": "no netlist supplied"},
            {"status": "not_run", "reason": "no netlist supplied"})
        joined = " ".join(nc)
        self.assertIn("PC-001 did NOT run", joined)
        self.assertIn("zero decoupling caps passes this gate", joined)

    def test_run_states_the_residual_scope_rather_than_going_silent(self):
        """PC-001 green means presence only. Saying nothing would re-imply that
        the datasheet's decoupling requirement was verified — it was not."""
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [], "parts_not_covered": []},
            {"status": "run"},
            {"status": "run"})
        joined = " ".join(nc)
        self.assertNotIn("PC-001 did NOT run", joined)
        self.assertIn("NOT its value, count or placement", joined)

    def test_omitted_passive_argument_is_not_a_silent_pass(self):
        """A caller predating PC-001 must not read as 'decoupling was checked'.

        REVERSE CONTROL for the default: if the default were treated as `run`,
        this assertion is the one that fails.
        """
        nc = check_c03._build_not_checked(
            {"status": "run", "parts_unresolved": [], "parts_not_covered": []},
            {"status": "run"})
        self.assertIn("PC-001 did NOT run", " ".join(nc))

    def test_decoupling_adequacy_is_no_longer_unconditional_base_text(self):
        """It moved out of _NOT_CHECKED_BASE into a conditional branch; leaving a
        copy behind would print the not-run text beside a run verdict."""
        base = " ".join(check_c03._NOT_CHECKED_BASE)
        self.assertNotIn("decoupling_adequacy", base)


# ── waiver scope is declared, not silently absent ───────────────────────────

class PC001WaiverScopeTests(unittest.TestCase):

    def test_report_states_that_waivers_are_not_honoured_here(self):
        """DD-3's sidecar is not ported in this pass. A caller who assumes a
        waiver would be honoured must be told, not left to discover it."""
        with tempfile.TemporaryDirectory() as tmp:
            res = _run(tmp, decoupling=False)
        self.assertEqual(res.passive_completeness["waivers"]["status"], "not_run")
        self.assertIn("NOT ported",
                      res.passive_completeness["waivers"]["reason"])

    def test_leaf_waiver_sidecar_not_honoured_when_check_c03_called_on_root(self):
        """A waiver sidecar next to a leaf .kicad_sch is NOT honoured by check_c03.

        check_c03 delivery path reports waivers.status='not_run' (DD-3 waiver sidecar
        is not ported to delivery path). Thus a leaf-level passive_waivers.json
        has no effect on check_c03, and the undecoupled IC remains a blocking PC-001 error.
        """
        import json
        with tempfile.TemporaryDirectory() as tmp:
            leaf_dir = os.path.join(tmp, "leaf")
            os.makedirs(leaf_dir, exist_ok=True)
            _write(tmp, "root.kicad_sch", "(kicad_sch)\n")
            _write(leaf_dir, "leaf.kicad_sch", "(kicad_sch)\n")
            _write(leaf_dir, "passive_waivers.json", json.dumps([{
                "ref": "U1", "obligation": "decoupling",
                "source": "leaf_waiver", "reason": "leaf scope", "scope": "leaf"
            }]))
            bom = _write(tmp, "bom.csv", _HDR + "".join(
                r + "\n" for r in _bom_rows(decoupling=False)))
            net = _write(tmp, "root.net", _netlist(decoupling=False))
            res = check_c03.check_c03(bom, netlist_path=net)

        self.assertEqual(res.gate, "FAIL")
        self.assertIn("PC-001", _codes(res))
        self.assertEqual(res.passive_completeness["waivers"]["status"], "not_run")
        self.assertIn("NOT ported", res.passive_completeness["waivers"]["reason"])


if __name__ == "__main__":
    unittest.main()
