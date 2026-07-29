"""Autoroute search-budget attribution (BR_20260729 §J).

A consumer throttled freerouting to `-mp 10` (default 40), read the resulting
`unconnected` as a property of the BOARD, concluded "the geometry cannot be
routed", and wrote that into a deliverable — for four rounds. Re-running at the
default took routed nets 74 -> 81/111. The return value was accurate and still
produced a wrong conclusion, because `unconnected` is a property of
(board, budget) and only one of the two was visible.

These lock the parts a future refactor could quietly break:
  * the advisory fires ONLY when the budget was cut AND the outcome is adverse
    (reverse discrimination — an advisory that fires always is noise, and one
    that never fires is the bug we just fixed),
  * the default lives in exactly ONE place (V4-c: the MCP handler must not
    re-declare it),
  * the advisory never flips the routing verdict.

Pure-function by construction so it runs on the host: gating this on pcbnew
would skip everywhere and report 0-coverage-as-clean, which is the L10 failure
mode this same BR line exists to stop.
"""
import ast
import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MOD = _REPO / "packages/eda-bridge/bodesign_eda_bridge/routing.py"
_spec = importlib.util.spec_from_file_location("_routing_budget_under_test", _MOD)
_routing = importlib.util.module_from_spec(_spec)
sys.modules["_routing_budget_under_test"] = _routing
_spec.loader.exec_module(_routing)

_report = _routing.autoroute_budget_report
_DEFAULT = _routing.DEFAULT_AUTOROUTE_PASSES


class BudgetIsAlwaysEchoed(unittest.TestCase):
    """The budget is reported unconditionally — the advisory is the conditional part."""

    def test_echoes_limit_and_default_even_when_not_throttled(self):
        rep = _report(_DEFAULT, 43)
        self.assertEqual(rep["passes_limit"], _DEFAULT)
        self.assertEqual(rep["passes_limit_default"], _DEFAULT)
        self.assertFalse(rep["throttled"])

    def test_echoes_limit_when_throttled(self):
        rep = _report(10, 138)
        self.assertEqual(rep["passes_limit"], 10)
        self.assertEqual(rep["passes_limit_default"], _DEFAULT)
        self.assertTrue(rep["throttled"])

    def test_above_default_is_not_throttled(self):
        """A caller paying for MORE search than default is not being warned about effort."""
        rep = _report(_DEFAULT * 2, 5)
        self.assertFalse(rep["throttled"])
        self.assertNotIn("advisories", rep)


class AdvisoryDiscrimination(unittest.TestCase):
    """The reason this guard has value: it must be SILENT in three cases and loud in one."""

    def test_fires_on_throttled_and_unrouted(self):
        """The recorded failure: -mp 10 leaving 138 unconnected."""
        rep = _report(10, 138)
        self.assertIn("advisories", rep)
        self.assertEqual(len(rep["advisories"]), 1)
        msg = rep["advisories"][0]
        self.assertIn("passes_throttled", msg)
        self.assertIn("-mp 10", msg)
        self.assertIn(str(_DEFAULT), msg)

    def test_silent_at_full_budget_even_when_unrouted(self):
        """An unrouted board at FULL budget is a real stackup/geometry finding.

        Diluting it with a note about effort would teach the caller to discount
        the one case where the number really does describe the board.
        """
        self.assertNotIn("advisories", _report(_DEFAULT, 43))

    def test_silent_when_fully_routed_even_if_throttled(self):
        """unconnected == 0 needs no caveat: a cheap search that succeeded is just a win."""
        self.assertNotIn("advisories", _report(1, 0))

    def test_silent_when_count_unavailable(self):
        """`unconnected is None` means we could not measure the outcome.

        Claiming the budget explains an outcome we never measured would be a
        fabricated attribution — the same class of defect, pointed the other way.
        """
        self.assertNotIn("advisories", _report(10, None))

    def test_advisory_does_not_carry_a_verdict_field(self):
        """Advisory must not smuggle in a flag that flips the routing result.

        The routing numbers were never wrong; only their attribution was. A
        `blocking`/`complete` key appearing here would let a note about effort
        override a measured outcome.
        """
        rep = _report(10, 138)
        for forbidden in ("complete", "blocking", "routed", "unconnected"):
            self.assertNotIn(forbidden, rep, forbidden)

    def test_message_names_the_remedy_without_overreaching(self):
        """Says what to re-run, and explicitly disclaims the infeasibility reading."""
        msg = _report(10, 138)["advisories"][0]
        self.assertIn("NOT evidence", msg)
        self.assertIn(f"passes={_DEFAULT}", msg)


class DefaultHasExactlyOneOwner(unittest.TestCase):
    """V4-c: the same fact recorded twice drifts. §I was that; this prevents a repeat.

    `passes` has THREE readers (the router kwarg, the MCP handler's `.get`
    fallback, and the `passes_limit_default` echoed to the caller). If the
    handler hard-codes its own number, a future change to the router's default
    silently leaves callers routing at the old budget while the response claims
    the new one.
    """

    def test_signature_default_is_the_module_constant(self):
        src = _MOD.read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "autoroute")
        kw = {a.arg: d for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults)}
        self.assertIn("passes", kw)
        node = kw["passes"]
        self.assertIsInstance(node, ast.Name,
                              "autoroute(passes=...) must default to the module constant, "
                              "not a literal (a literal is a second copy of the fact)")
        self.assertEqual(node.id, "DEFAULT_AUTOROUTE_PASSES")

    def test_mcp_handler_does_not_hardcode_a_passes_default(self):
        server = _REPO / "services/mcp/server.py"
        tree = ast.parse(server.read_text())
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_h_autoroute"), None)
        self.assertIsNotNone(fn, "_h_autoroute not found — did the handler get renamed?")
        literals = []
        for node in ast.walk(fn):
            # a.get("passes", <literal>) — the shape that drifts
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and len(node.args) == 2
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "passes"
                    and isinstance(node.args[1], ast.Constant)):
                literals.append(node.args[1].value)
        self.assertEqual(literals, [],
                         f"_h_autoroute hard-codes a passes default {literals}; import "
                         "DEFAULT_AUTOROUTE_PASSES from bodesign_eda_bridge instead")

    def test_handler_reaches_the_constant(self):
        """Positive half: the handler must actually reference the shared constant.

        Without this, deleting the `.get` fallback entirely would also pass the
        negative test above while changing behaviour.
        """
        server = (_REPO / "services/mcp/server.py").read_text()
        tree = ast.parse(server)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_h_autoroute")
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        names |= {a.name for n in ast.walk(fn) if isinstance(n, ast.ImportFrom)
                  for a in n.names}
        self.assertIn("DEFAULT_AUTOROUTE_PASSES", names)


class ConstantMatchesFreeroutingSemantics(unittest.TestCase):
    """`-mp` is an UPPER LIMIT, per freerouting v1.9.0's own command_line_help:

        -mp <number_of_passes>
            Sets the upper limit of the number of auto-router passes
            that will be performed

    So the field is named `passes_limit`, not `passes`: freerouting gates its
    per-pass log line behind TestLevel, so at the default log level the passes
    ACTUALLY performed are unobservable. Reporting the limit as if it were the
    count would swap one misleading number for another.
    """

    def test_field_is_named_as_a_limit(self):
        rep = _report(10, 138)
        self.assertIn("passes_limit", rep)
        self.assertNotIn("passes", rep,
                         "a bare `passes` key would read as 'passes performed', which "
                         "freerouting does not expose at the default log level")

    def test_docstring_records_the_spec_evidence(self):
        doc = _routing.autoroute.__doc__ or ""
        self.assertIn("UPPER LIMIT", doc)


if __name__ == "__main__":
    unittest.main()
