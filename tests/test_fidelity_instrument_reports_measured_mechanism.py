"""BR_20260802 instrument repair: the fidelity gate must report the mechanism it
MEASURED, and must be structurally capable of seeing an open circuit.

Two defects this pins down (both found while doing the RCA on the gate's own red
light, and both of which made two independent readers diagnose a FUSION that was
never there):

1. `sch_union_classes` only unioned `nodes[1:]`, so a SINGLE-node net
   (`unconnected-(R1-Pad1)` — exactly what an open circuit produces) never entered
   the union-find `parent` dict and vanished from the candidate universe. That made
   `only_candidate` structurally unable to be non-zero for a broken net.
2. `FidelityError` hardcoded "(collinear-wire fusion / label collision)" for EVERY
   divergence — naming a cause it had not measured.

Every test here carries a control: an assertion that the same instrument reports
something DIFFERENT for the opposite input, so a vacuous "always passes" check
cannot masquerade as a real one.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.fidelity import (
    FidelityError,
    compare_partitions,
    expected_partition_from_nets,
    parse_net_file,
    sch_union_classes,
)

# One 2-pin net (N1) and one 3-pin net (GND). The spec's electrical truth.
SPEC_NETS = [
    {"name": "N1", "nodes": ["J1.1", "R1.1"]},
    {"name": "GND", "nodes": ["R1.2", "R2.2", "J1.2"]},
]

# A KiCad netlist in which N1 has been CUT: each of its pins is alone on its own
# auto-named net, which is literally what kicad-cli emits for an unconnected pin.
NETLIST_OPEN_CIRCUIT = """
(export (version "E")
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "2") (pintype "passive")))
    (net (code "2") (name "unconnected-(J1-Pad1)")
      (node (ref "J1") (pin "1") (pintype "passive")))
    (net (code "3") (name "unconnected-(R1-Pad1)")
      (node (ref "R1") (pin "1") (pintype "passive")))))
"""

# The same board with N1 intact — the control.
NETLIST_FAITHFUL = """
(export (version "E")
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "2") (pintype "passive")))
    (net (code "2") (name "N1")
      (node (ref "J1") (pin "1") (pintype "passive"))
      (node (ref "R1") (pin "1") (pintype "passive")))))
"""

# Faithful, PLUS one isolated pin the spec never mentions — exactly what
# kicad-cli emits for the unused ways of a multi-way connector. It shares a net
# with nobody, so it cannot short anything: an exemption, not a violation.
NETLIST_FAITHFUL_PLUS_ISOLATED_EXTRA = """
(export (version "E")
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "2") (pintype "passive")))
    (net (code "2") (name "N1")
      (node (ref "J1") (pin "1") (pintype "passive"))
      (node (ref "R1") (pin "1") (pintype "passive")))
    (net (code "3") (name "unconnected-(J1-Pad3)")
      (node (ref "J1") (pin "3") (pintype "passive")))))
"""

# Faithful, PLUS a CONNECTED pair the spec never mentions. Same "extra in
# candidate" shape as above, but these two DO share a net, so the exemption must
# NOT apply — this is the control that proves the exemption discriminates.
NETLIST_FAITHFUL_PLUS_CONNECTED_EXTRA = """
(export (version "E")
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "2") (pintype "passive")))
    (net (code "2") (name "N1")
      (node (ref "J1") (pin "1") (pintype "passive"))
      (node (ref "R1") (pin "1") (pintype "passive")))
    (net (code "3") (name "STRAY")
      (node (ref "X1") (pin "1") (pintype "passive"))
      (node (ref "X1") (pin "2") (pintype "passive")))))
"""


def _parse(text: str):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.net"
        p.write_text(text, encoding="utf-8")
        return parse_net_file(p)


class SingleNodeNetSurvivesUnionFind(unittest.TestCase):
    """Defect 1: an open-circuit pin must stay in the candidate universe."""

    def _classes(self, netlist_text: str):
        """Run the REAL sch_union_classes over a stubbed kicad-cli export.

        Returns the PARTITION (list of node-sets), not a flattened universe:
        the union step is only observable in the class STRUCTURE. Flattening
        first destroys exactly the evidence `test_multi_node_net_still_merges`
        needs -- see its docstring.
        """
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            sch = work / "board.kicad_sch"
            sch.write_text("(kicad_sch)", encoding="utf-8")
            # Stub the export: write the fixture where sch_union_classes will read it.
            real_run = subprocess.run

            def fake_run(cmd, *a, **kw):
                Path(cmd[cmd.index("-o") + 1]).write_text(netlist_text, encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, "", "")

            subprocess.run = fake_run
            try:
                return sch_union_classes([sch], work)
            finally:
                subprocess.run = real_run

    def _universe(self, netlist_text: str):
        out = self._classes(netlist_text)
        return set().union(*out) if out else set()

    def test_open_circuit_pin_is_not_dropped_from_the_universe(self):
        universe = self._universe(NETLIST_OPEN_CIRCUIT)
        for pin in ("J1.1", "R1.1"):
            self.assertIn(pin, universe,
                          f"{pin} is an open-circuit pin; dropping it from the "
                          f"candidate universe is what made only_candidate "
                          f"structurally unable to be non-zero")

    def test_universe_matches_the_raw_netlist_exactly(self):
        # Control: the union-find universe must equal what the parser saw. If the
        # two ever diverge again, this fails regardless of which node was lost.
        raw = set().union(*_parse(NETLIST_OPEN_CIRCUIT))
        self.assertEqual(self._universe(NETLIST_OPEN_CIRCUIT), raw)

    def test_multi_node_net_still_merges(self):
        """Control in the OTHER direction: seeding must not stop nets from merging.

        Measured 2026-08-31: this test used to call `_parse()` -- i.e.
        `parse_net_file`, the PARSER -- while claiming to control the union step.
        Removing the union entirely (`for n in nodes[1:]: pass`) left it green,
        because the parser's per-net grouping is unaffected by union-find. It was
        naming a thing it did not measure, which is the very defect this file
        exists to pin down.

        It must therefore read `sch_union_classes`' own output, and it must read
        the CLASSES: the flattened universe is invariant under a missing union
        (seeding alone already puts every node in `parent`), so a flat-set
        assertion has zero discriminating power here.
        """
        classes = self._classes(NETLIST_FAITHFUL)
        gnd = [c for c in classes if "R1.2" in c][0]
        self.assertEqual(gnd, frozenset({"R1.2", "R2.2", "J1.2"}),
                         "the 3-pin GND net must survive union-find as ONE class")

    def test_merging_is_what_makes_the_two_fixtures_differ(self):
        # Control for the control: if union-find returned singletons for
        # everything, the assertion above would be the only thing standing --
        # so pin the class COUNT too. Faithful board = 2 real nets; the cut board
        # = 3 (GND intact, N1 split in two).
        self.assertEqual(len(self._classes(NETLIST_FAITHFUL)), 2)
        self.assertEqual(len(self._classes(NETLIST_OPEN_CIRCUIT)), 3)


class DiagnosisIsDerivedNotAsserted(unittest.TestCase):
    """Defect 2: the named mechanism must be the one actually measured."""

    def _report(self, netlist_text: str):
        return compare_partitions(expected_partition_from_nets(SPEC_NETS),
                                  _parse(netlist_text))

    def test_open_circuit_is_named_open_circuit(self):
        rep = self._report(NETLIST_OPEN_CIRCUIT)
        self.assertFalse(rep.ok)
        self.assertEqual(sorted(rep.disconnected), ["J1.1", "R1.1"])
        self.assertEqual(rep.fused, [], "nothing gained peers; nothing was fused")
        joined = " ".join(rep.diagnosis()).lower()
        self.assertIn("open circuit", joined)
        self.assertNotIn("fusion", joined,
                         "the gate must not name a mechanism it did not measure")

    def test_fusion_is_named_fusion(self):
        # The opposite input: N1 and GND welded into one net. Same instrument,
        # different verdict -> proves the classifier discriminates.
        fused_candidate = [frozenset({"J1.1", "R1.1", "R1.2", "R2.2", "J1.2"})]
        rep = compare_partitions(expected_partition_from_nets(SPEC_NETS),
                                 fused_candidate)
        self.assertFalse(rep.ok)
        self.assertEqual(rep.disconnected, [], "nothing lost peers; nothing was cut")
        self.assertTrue(rep.fused)
        joined = " ".join(rep.diagnosis()).lower()
        self.assertIn("fusion", joined)
        self.assertNotIn("open circuit", joined)

    def test_faithful_board_passes_and_names_nothing(self):
        rep = self._report(NETLIST_FAITHFUL)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual(rep.diagnosis(), [])

    def test_error_message_carries_the_measured_mechanism(self):
        rep = self._report(NETLIST_OPEN_CIRCUIT)
        msg = str(FidelityError(rep))
        self.assertIn("open circuit", msg.lower())
        self.assertNotIn("collinear-wire fusion / label collision", msg,
                         "the hardcoded cause must be gone from the raised message")

    @staticmethod
    def _cause(err: FidelityError) -> str:
        """Just the `(...)` cause clause -- the part `FidelityError` DERIVES.

        Everything after the first `:\n` is `report.summary()`, which differs
        between any two unlike reports for reasons that have nothing to do with
        the cause. Comparing whole messages therefore cannot see the cause at
        all; see `test_error_message_differs_between_the_two_mechanisms`.
        """
        return str(err).split(":\n", 1)[0]

    def test_error_message_differs_between_the_two_mechanisms(self):
        """The DERIVED cause clause must differ between the two mechanisms.

        Measured 2026-08-31: this test used to compare the two messages WHOLE,
        and a `cause` replaced by a constant naming both mechanisms left it
        green -- because each message carries its own `summary()`, and those
        differ regardless of the cause. It claimed to catch exactly the
        hardcoding it could not see. The comparison is now scoped to the cause
        clause, which is the only part the fix under test produces.
        """
        open_err = FidelityError(self._report(NETLIST_OPEN_CIRCUIT))
        fused_err = FidelityError(compare_partitions(
            expected_partition_from_nets(SPEC_NETS),
            [frozenset({"J1.1", "R1.1", "R1.2", "R2.2", "J1.2"})]))
        open_cause = self._cause(open_err)
        fused_cause = self._cause(fused_err)
        # Precondition: the split must have actually found a cause clause. A
        # silently-empty slice on both sides would make assertNotEqual vacuous.
        self.assertIn("(", open_cause)
        self.assertIn("(", fused_cause)
        # Precondition, the other direction (measured 2026-08-31): if the
        # separator `_cause` splits on ever changes, `split` finds nothing, the
        # "slice" silently becomes the WHOLE message, and the inequality below is
        # once again satisfied by the summary bodies -- the exact round-1 defect,
        # restored without a word of warning. An over-long slice and a correct
        # one must not share an output, so name a string only `summary()` emits.
        for cause in (open_cause, fused_cause):
            self.assertNotIn("baseline nets=", cause,
                             "the cause slice swallowed summary(): the separator "
                             "contract in _cause() no longer holds, so this test "
                             "is measuring the summary, not the cause")
        self.assertNotEqual(open_cause, fused_cause,
                            "a cause that does not change with the mechanism is "
                            "a hardcoded cause, whatever words it contains")
        # And each names ONLY its own mechanism -- a constant carrying both
        # words would satisfy a bare inequality on longer inputs.
        self.assertIn("open circuit", open_cause.lower())
        self.assertNotIn("fusion", open_cause.lower())
        self.assertIn("fusion", fused_cause.lower())
        self.assertNotIn("open circuit", fused_cause.lower())

    def test_whole_message_comparison_is_not_what_pins_the_cause(self):
        """Two UNLIKE boards, same mechanism -> same cause, different messages.

        This is the control that justifies scoping `_cause()`, and it is asserted
        against the real instrument rather than against constructed strings.

        Measured 2026-08-31 (round 3): the first version of this control compared
        two string LITERALS and then asserted `_cause(e) == str(e).split(":\\n")[0]`
        -- which is `f(x) == f(x)`, true by construction. It went red for 0 of 12
        mutants. It was the same empty-control defect it was written to explain,
        wearing the costume of the fix.

        The property it now pins is real and is the whole reason the scoping was
        needed: the cause clause is derived from the mechanism and a COUNT, not
        from node identities, so two boards that share neither a net nor a
        reference produce a byte-identical cause -- while their summaries, and
        therefore their whole messages, differ. A test comparing whole messages
        is thus satisfied by the summaries alone and can never see the cause.
        """
        # Same shape (one 2-pin net cut, one 3-pin net intact), disjoint refs.
        spec_b = [{"name": "A1", "nodes": ["U1.1", "U2.1"]},
                  {"name": "GND", "nodes": ["R1.2", "R2.2", "J1.2"]}]
        cand_b = [frozenset({"U1.1"}), frozenset({"U2.1"}),
                  frozenset({"R1.2", "R2.2", "J1.2"})]
        err_a = FidelityError(self._report(NETLIST_OPEN_CIRCUIT))
        err_b = FidelityError(compare_partitions(
            expected_partition_from_nets(spec_b), cand_b))

        # Precondition: both really are open circuits, on disjoint node sets --
        # otherwise "same cause" would be trivial rather than informative.
        self.assertEqual(sorted(err_a.report.disconnected), ["J1.1", "R1.1"])
        self.assertEqual(sorted(err_b.report.disconnected), ["U1.1", "U2.1"])

        self.assertEqual(self._cause(err_a), self._cause(err_b),
                         "the cause names the mechanism and a count; two boards "
                         "with the same mechanism must produce the same cause")
        self.assertNotEqual(err_a.report.summary(), err_b.report.summary())
        self.assertNotEqual(str(err_a), str(err_b),
                            "whole messages differ on the summary alone -- which "
                            "is precisely why comparing them cannot pin the cause")


class SummaryCarriesTheMechanismBlock(unittest.TestCase):
    """`summary()` must SHOW the measured mechanism, not only `diagnosis()`.

    Mutation gap this closes (measured 2026-08-31): deleting the
    `if not self.ok: ... MEASURED MECHANISM ...` block from `summary()`
    left the whole suite green. `summary()` is what a human reads in CI logs and
    what `FidelityError` appends to its message body, so a report whose mechanism
    is derivable but never printed puts the reader back where BR_20260802 found
    them: a divergence with no named mechanism.
    """

    def _report(self, netlist_text: str):
        return compare_partitions(expected_partition_from_nets(SPEC_NETS),
                                  _parse(netlist_text))

    def test_failing_summary_prints_the_mechanism_it_measured(self):
        text = self._report(NETLIST_OPEN_CIRCUIT).summary()
        self.assertIn("MEASURED MECHANISM", text,
                      "summary() is the reader-facing surface; a mechanism that "
                      "only diagnosis() knows about is invisible in practice")
        self.assertIn("open circuit", text.lower(),
                      "the block must carry the mechanism, not just its heading")

    def test_passing_summary_names_no_mechanism(self):
        # Negative control for the assertion above: if summary() printed the
        # block unconditionally, the test above would pass vacuously.
        text = self._report(NETLIST_FAITHFUL).summary()
        self.assertNotIn("MEASURED MECHANISM", text)
        self.assertIn("FIDELITY PASS", text)

    def test_every_diagnosis_line_reaches_the_summary(self):
        # Stronger than a substring probe on one phrase: whatever diagnosis()
        # derived must be present verbatim. Deleting any single branch of the
        # block fails here even if another branch still prints.
        rep = self._report(NETLIST_OPEN_CIRCUIT)
        text = rep.summary()
        dx = rep.diagnosis()
        self.assertTrue(dx, "precondition: this input must derive a mechanism")
        for line in dx:
            self.assertIn(line, text)

    def test_raised_message_body_contains_the_summary_block(self):
        # The error body is summary(); this pins the two together so the block
        # cannot be dropped from the message by editing either side alone.
        msg = str(FidelityError(self._report(NETLIST_OPEN_CIRCUIT)))
        self.assertIn("MEASURED MECHANISM", msg)


class ExtraCandidateNodesAreJudgedByWhetherTheyConnect(unittest.TestCase):
    """The candidate-side singleton exemption (`singleton_only_candidate`).

    Mutation gap this closes (measured 2026-08-31): reverting
    `only_c = sorted(... if len(c_idx[nd]) > 1)` back to `only_c = sorted(raw_only_c)`
    left the whole suite green. Without the exemption, the 34 unused ways of a
    40-pin connector each become a fidelity violation — an isolated pin shares a
    net with nobody and cannot short anything.

    Both directions are asserted here, because an exemption that fires for
    EVERYTHING is the same defect wearing the opposite sign.
    """

    def _report(self, netlist_text: str):
        return compare_partitions(expected_partition_from_nets(SPEC_NETS),
                                  _parse(netlist_text))

    def test_isolated_extra_pin_is_exempt_and_stays_visible(self):
        rep = self._report(NETLIST_FAITHFUL_PLUS_ISOLATED_EXTRA)
        self.assertEqual(rep.only_candidate, [],
                         "an isolated extra pin connects to nothing and cannot "
                         "short anything; flagging it is a false positive")
        self.assertEqual(rep.singleton_only_candidate, ["J1.3"],
                         "the exemption must remain VISIBLE — an exemption the "
                         "reader cannot see is indistinguishable from a check "
                         "that was never made")
        self.assertTrue(rep.ok, rep.summary())

    def test_connected_extra_pins_are_not_exempt(self):
        # Reverse control: same "extra in candidate" shape, but these two share a
        # net. If the exemption swallowed them too, the gate would be blind to a
        # whole stray net.
        rep = self._report(NETLIST_FAITHFUL_PLUS_CONNECTED_EXTRA)
        self.assertEqual(rep.only_candidate, ["X1.1", "X1.2"])
        self.assertEqual(rep.singleton_only_candidate, [])
        self.assertFalse(rep.ok)

    def test_the_two_inputs_do_not_produce_the_same_verdict(self):
        # Guards against both assertions above passing on a constant: the
        # instrument must actually discriminate between the two shapes.
        exempt = self._report(NETLIST_FAITHFUL_PLUS_ISOLATED_EXTRA)
        flagged = self._report(NETLIST_FAITHFUL_PLUS_CONNECTED_EXTRA)
        self.assertNotEqual(exempt.ok, flagged.ok)

    def test_extra_connected_nodes_are_named_absent_from_spec(self):
        # Mutation gap: `diagnosis()` could drop its only_candidate branch and
        # nothing noticed — the gate would fail with a divergence it declined to
        # name, which is the exact BR_20260802 failure mode.
        rep = self._report(NETLIST_FAITHFUL_PLUS_CONNECTED_EXTRA)
        joined = " ".join(rep.diagnosis()).lower()
        self.assertIn("absent from spec", joined,
                      "only_candidate is non-empty; the mechanism must be named")
        self.assertNotIn("open circuit", joined,
                         "nothing lost peers here")

    def test_a_report_with_no_extra_nodes_names_nothing(self):
        # Negative control for the assertion above.
        rep = self._report(NETLIST_FAITHFUL)
        self.assertEqual(rep.only_candidate, [])
        self.assertNotIn("absent from spec", " ".join(rep.diagnosis()).lower())


if __name__ == "__main__":
    unittest.main()
