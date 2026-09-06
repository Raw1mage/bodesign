"""WP4 — `bodesign_verify_netlist_fidelity`, the electrical-axis gate.

plan c03_delivery_contract_and_engine_seams DD-06, errors.md §WP4.

The hole this closes (RCA §10.3(c)): a spec of single-pin nets compared against
an empty export returned `ok=True`. Nothing had been read, nothing had been
compared, and the verdict was a pass — because "no differences found" and
"no comparison happened" shared one output.

The status codomain is therefore what these tests are about. Four values, and
each one needs a case that reaches it AND a control proving the resolver can
return something else on neighbouring input:

    ok             parsed >0, all readable, five difference axes empty
    failed         parsed >0, all readable, >=1 axis non-empty
    not-run        precondition unmet BEFORE any read
    indeterminate  nets_parsed == 0, or a path unparseable — pre-comparison

A named `.net` that does not exist is deliberately NOT on this axis: it raises
`FidelityInputError(NETLIST_MISSING)`, because "fix the path you typed" and
"the comparison was inconclusive" send a reader to different places.
"""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path

fid = importlib.import_module("bodesign_eda_bridge.fidelity")

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR")
                    or (Path.home() / ".cache")) / "claude-work"


def _net(nets: dict[str, list[tuple[str, str]]]) -> str:
    """A minimal KiCad `.net` export carrying exactly the given nets."""
    blocks = []
    for i, (name, nodes) in enumerate(nets.items(), start=1):
        node_lines = "\n".join(
            f'      (node (ref "{r}") (pin "{p}") (pintype "passive"))'
            for r, p in nodes)
        blocks.append(f'    (net (code "{i}") (name "{name}") (class "Default")\n'
                      f'{node_lines})')
    return ('(export (version "E")\n  (nets\n'
            + "\n".join(blocks) + "))\n")


class _Case(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-wp4-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write(self, name: str, body: str) -> str:
        p = self.work / name
        p.write_text(body, encoding="utf-8")
        return str(p)


# ── the ok / failed pair ────────────────────────────────────────────────────

#: One spec, used by both halves below. The ONLY thing that varies is the
#: export, so a verdict change cannot be attributed to anything else.
_SPEC = {"N1": [["U1", "1"], ["R1", "1"]],
         "N2": [["U1", "2"], ["R2", "1"]]}


class OkAndFailedTests(_Case):

    def test_matching_export_is_ok(self):
        path = self._write("m.net", _net({"N1": [("U1", "1"), ("R1", "1")],
                                          "N2": [("U1", "2"), ("R2", "1")]}))
        out = fid.verify_netlist_fidelity(_SPEC, [path])
        self.assertEqual(out["status"], "ok", out)
        self.assertEqual(out["fused"], [])
        self.assertEqual(out["split"], [])
        self.assertEqual(out["node_diff"], {"spec_only": [], "emitted_only": []})
        self.assertEqual(out["nc_wired"], [])
        self.assertEqual(out["nets_parsed"], 2)

    def test_fused_export_is_failed_and_names_the_fused_nodes(self):
        """NEGATIVE CONTROL for `ok`: weld N1 and N2 into one net.

        This is the defect ERC cannot see — one net instead of two, no dangling
        pin, so the export looks *cleaner* than the correct one.
        """
        path = self._write("f.net", _net({"BOTH": [("U1", "1"), ("R1", "1"),
                                                   ("U1", "2"), ("R2", "1")]}))
        out = fid.verify_netlist_fidelity(_SPEC, [path])
        self.assertEqual(out["status"], "failed", out)
        self.assertEqual(out["fused"], ["R1.1", "R2.1", "U1.1", "U1.2"])
        self.assertEqual(out["split"], [])
        self.assertEqual(out["nets_parsed"], 1)

    def test_cut_net_is_split_not_fused(self):
        """The two mechanisms must not share a field: an open circuit and a
        short are opposite defects and `moved` alone cannot tell them apart."""
        path = self._write("s.net", _net({"N1": [("U1", "1"), ("R9", "1")],
                                          "N1b": [("R1", "1"), ("R8", "1")],
                                          "N2": [("U1", "2"), ("R2", "1")]}))
        out = fid.verify_netlist_fidelity(_SPEC, [path])
        self.assertEqual(out["status"], "failed", out)
        self.assertIn("U1.1", out["split"])
        self.assertIn("R1.1", out["split"])
        self.assertEqual(out["fused"], [])

    def test_node_diff_separates_spec_only_from_emitted_only(self):
        spec = dict(_SPEC, N3=[["U1", "3"], ["R3", "1"]])
        path = self._write("d.net", _net({"N1": [("U1", "1"), ("R1", "1")],
                                          "N2": [("U1", "2"), ("R2", "1")],
                                          "N4": [("U1", "4"), ("R4", "1")]}))
        out = fid.verify_netlist_fidelity(spec, [path])
        self.assertEqual(out["status"], "failed", out)
        self.assertEqual(out["node_diff"]["spec_only"], ["R3.1", "U1.3"])
        self.assertEqual(out["node_diff"]["emitted_only"], ["R4.1", "U1.4"])


# ── nc_wired: an independent axis ───────────────────────────────────────────

class NcWiredTests(_Case):
    """A declared-NC pin wired to a real net is its own defect.

    Folding it into `fused` would mean a board that violates an explicit NC
    declaration can be reported as merely "fused", and a board whose partition
    is otherwise perfect would report nothing at all.
    """

    _NC_SPEC = {"N1": [["U1", "1"], ["R1", "1"]]}

    def test_declared_nc_pin_wired_to_a_net_lands_in_nc_wired_only(self):
        """POSITIVE CONTROL. U1.9 is declared NC and the export ties it to GND."""
        path = self._write("nc.net", _net({"N1": [("U1", "1"), ("R1", "1")],
                                           "GND": [("U1", "9"), ("C1", "2")]}))
        out = fid.verify_netlist_fidelity(self._NC_SPEC, [path],
                                          nc_declared=[["U1", "9"]])
        self.assertEqual(out["status"], "failed", out)
        self.assertEqual(out["nc_wired"], ["U1.9"])
        # The two axes are independent: U1.9 is not a spec node at all, so it
        # must NOT be reported as a fusion of something.
        self.assertNotIn("U1.9", out["fused"])
        self.assertEqual(out["fused"], [])

    def test_same_fixture_with_the_pin_genuinely_left_open(self):
        """NEGATIVE CONTROL: same spec, same declaration, pin actually unconnected.

        kicad-cli emits an isolated pin as its own single-node net; a pin that
        shares a net with nobody cannot violate an NC declaration.
        """
        path = self._write("open.net", _net({"N1": [("U1", "1"), ("R1", "1")],
                                             "unconnected-(U1-Pad9)": [("U1", "9")]}))
        out = fid.verify_netlist_fidelity(self._NC_SPEC, [path],
                                          nc_declared=[["U1", "9"]])
        self.assertEqual(out["nc_wired"], [])
        self.assertEqual(out["status"], "ok", out)

    def test_omitting_nc_declared_is_absent_not_verified_clean(self):
        """An empty `nc_wired` with no declaration means NOBODY LOOKED.

        Same wired-NC export as the positive case; without the declaration the
        verb cannot know U1.9 was supposed to be open, and the field is empty
        for that reason rather than because the board is clean.
        """
        path = self._write("nc2.net", _net({"N1": [("U1", "1"), ("R1", "1")],
                                            "GND": [("U1", "9"), ("C1", "2")]}))
        out = fid.verify_netlist_fidelity(self._NC_SPEC, [path])
        self.assertEqual(out["nc_wired"], [])
        with_decl = fid.verify_netlist_fidelity(self._NC_SPEC, [path],
                                                nc_declared=[["U1", "9"]])
        self.assertEqual(with_decl["nc_wired"], ["U1.9"],
                         "the SAME export yields a finding once declared — so the "
                         "empty field above is absence of input, not a clean board")


# ── parsed-zero and the not-run / indeterminate split ───────────────────────

class ParsedZeroAndPreconditionTests(_Case):
    """The RCA §10.3(c) hole, and the distinction that closes it."""

    _SINGLE = {"N1": [["U1", "1"]]}          # single-pin nets only

    def test_empty_net_file_is_indeterminate_never_ok(self):
        """THE REGRESSION TEST. This exact input returned ok=True before."""
        path = self._write("empty.net", '(export (version "E")\n  (nets))\n')
        out = fid.verify_netlist_fidelity(self._SINGLE, [path])
        self.assertEqual(out["status"], "indeterminate", out)
        self.assertEqual(out["nets_parsed"], 0)
        self.assertIn("zero", out["reason"])
        self.assertNotEqual(out["status"], "ok")

    def test_control_non_empty_export_same_spec_is_not_indeterminate(self):
        """CONTROL for the above: the verdict tracks the EXPORT, not the spec.

        Without this, `indeterminate` might simply be what a single-pin spec
        always produces, and the test above would measure nothing.
        """
        path = self._write("one.net", _net({"N1": [("U1", "1"), ("R1", "1")]}))
        out = fid.verify_netlist_fidelity(self._SINGLE, [path])
        self.assertNotEqual(out["status"], "indeterminate", out)
        self.assertGreater(out["nets_parsed"], 0)

    def test_empty_emitted_list_is_not_run_not_indeterminate(self):
        """Nothing was READ at all — a different fact from an unreadable read.

        Collapsing them loses the only actionable bit: one says the caller
        supplied nothing, the other says the file could not be made sense of.
        """
        out = fid.verify_netlist_fidelity(_SPEC, [])
        self.assertEqual(out["status"], "not-run", out)
        self.assertEqual(out["nets_parsed"], 0)
        self.assertIn("empty list", out["reason"])

    def test_empty_spec_is_not_run(self):
        path = self._write("m.net", _net({"N1": [("U1", "1"), ("R1", "1")]}))
        out = fid.verify_netlist_fidelity({}, [path])
        self.assertEqual(out["status"], "not-run", out)
        self.assertIn("spec is empty", out["reason"])

    def test_missing_file_is_a_typed_input_error_not_a_status(self):
        """Absence of the FILE and inconclusiveness of the DATA are different
        channels, with different remedies."""
        with self.assertRaises(fid.FidelityInputError) as ctx:
            fid.verify_netlist_fidelity(_SPEC, [str(self.work / "nope.net")])
        self.assertEqual(ctx.exception.code, "NETLIST_MISSING")
        self.assertIn("nope.net", ctx.exception.message)

    def test_the_four_statuses_are_all_reachable(self):
        """A codomain with one reachable value measures nothing. All four, in
        one test, from inputs that differ only as described."""
        good = self._write("g.net", _net({"N1": [("U1", "1"), ("R1", "1")],
                                          "N2": [("U1", "2"), ("R2", "1")]}))
        bad = self._write("b.net", _net({"X": [("U1", "1"), ("R1", "1"),
                                               ("U1", "2"), ("R2", "1")]}))
        empty = self._write("e.net", '(export (version "E")\n  (nets))\n')
        seen = {
            fid.verify_netlist_fidelity(_SPEC, [good])["status"],
            fid.verify_netlist_fidelity(_SPEC, [bad])["status"],
            fid.verify_netlist_fidelity(_SPEC, [])["status"],
            fid.verify_netlist_fidelity(_SPEC, [empty])["status"],
        }
        self.assertEqual(seen, {"ok", "failed", "not-run", "indeterminate"})


# ── multi-sheet merge ───────────────────────────────────────────────────────

class MultiSheetTests(_Case):

    def test_a_net_split_across_sheets_merges_by_shared_node(self):
        a = self._write("a.net", _net({"N1": [("U1", "1"), ("J1", "1")]}))
        b = self._write("b.net", _net({"N1": [("J1", "1"), ("R1", "1")]}))
        spec = {"N1": [["U1", "1"], ["J1", "1"], ["R1", "1"]]}
        out = fid.verify_netlist_fidelity(spec, [a, b])
        self.assertEqual(out["status"], "ok", out)
        self.assertEqual(out["nets_parsed"], 2, "both blocks were parsed")
        self.assertEqual(out["emitted_nets"], 1, "and merged into one class")


# ── the unreadable-path arm (replaces the swallowed `continue`) ─────────────

class UnreadableInputTests(_Case):

    def test_an_unparseable_export_is_indeterminate_and_names_the_path(self):
        """`sch_union_classes:220` swallows this class of failure with a bare
        `continue`, which reaches the comparison as "that sheet had no nets"."""
        good = self._write("g.net", _net({"N1": [("U1", "1"), ("R1", "1")]}))
        bad = self.work / "bad.net"
        bad.write_bytes(b"\xff\xfe\x00 not a netlist")
        original = fid.parse_net_file

        def _boom(path):
            if Path(path).name == "bad.net":
                raise OSError("simulated read failure")
            return original(path)

        fid.parse_net_file = _boom
        try:
            out = fid.verify_netlist_fidelity(_SPEC, [good, str(bad)])
        finally:
            fid.parse_net_file = original
        self.assertEqual(out["status"], "indeterminate", out)
        self.assertTrue(out["emitted_unreadable"])
        self.assertIn("bad.net", out["emitted_unreadable"][0]["path"])


if __name__ == "__main__":
    unittest.main()
