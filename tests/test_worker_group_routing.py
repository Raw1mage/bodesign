"""Group routing is DERIVED from the code, not remembered (BR_20260729 §A/§I).

`_EE_GROUP_TOOLS` is a hand-maintained set of tool names, and `_group_of()` sends
anything not listed there to `core` — the lean facade, which has no pcbnew and no
freerouting. So a tool omitted from that set does not degrade: it fails outright,
in an environment that could never have run it.

That omission has now happened twice:

  §A  `bodesign_autoroute_preflight` + `bodesign_placement_preflight` were missing,
      so the preflight gate probed the FACADE for a toolchain that lives in the ee
      worker — `ready:false` on every call, for a toolchain that was present all along.
  §I  `bodesign_clean_micro_stubs` was missing, so it raised
      "pcbnew not importable (run in the KiCad/EE worker)" while running in the
      facade, which is exactly right and exactly useless.

Twice is a pattern, and the pattern is not "someone forgot a name". The fact
"this tool needs pcbnew" is recorded in TWO places — the `_need_pcbnew()` call in
the function body (authoritative) and this hand-copied list (a transcription of it)
— and nothing forces them to agree. So the third omission is only a matter of time.

These tests DERIVE the membership from the authority instead of restating it:

    eda_bridge fn calls _need_pcbnew()   (AST over the package)
      -> which _h_* handler imports that fn   (AST over server.py)
        -> which TOOLS entry names that handler   (AST over server.py)
          -> that tool name MUST be in _EE_GROUP_TOOLS

No name is written down here, so this file cannot itself drift out of date: add a
pcbnew-backed tool and forget the list, and the derivation reports it.

Scope note (honest boundary): `_need_pcbnew()` is the only such sentinel in the
packages — `_ME_GROUP_TOOLS` guards OpenSCAD/pyrender/build123d tools that have no
equivalent marker, so this file does NOT cover them. Adding a sentinel there would
extend the same guard; until then, ME membership stays hand-maintained.
"""
import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "services/mcp/server.py"
BRIDGE = REPO / "packages/eda-bridge/bodesign_eda_bridge"

SENTINEL = "_need_pcbnew"


def _calls_sentinel(fn: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == SENTINEL
               for n in ast.walk(fn))


def _pcbnew_backed_functions() -> set[str]:
    """eda_bridge functions that cannot run outside the KiCad worker."""
    found = set()
    for src in sorted(BRIDGE.glob("*.py")):
        for fn in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and _calls_sentinel(fn):
                found.add(fn.name)
    return found


def _server_tree() -> ast.Module:
    return ast.parse(SERVER.read_text(encoding="utf-8"))


def _handler_imports(tree: ast.Module) -> dict[str, set[str]]:
    """_h_* handler -> the eda_bridge names it imports (handlers import lazily inside the body)."""
    out: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name.startswith("_h_"):
            names = {alias.name
                     for n in ast.walk(fn)
                     if isinstance(n, ast.ImportFrom) and n.module == "bodesign_eda_bridge"
                     for alias in n.names}
            if names:
                out[fn.name] = names
    return out


def _tool_handlers(tree: ast.Module) -> dict[str, str]:
    """TOOLS entry: exposed tool name -> handler function name."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
        if "name" not in keys or "handler" not in keys:
            continue
        pairs = dict(zip(keys, node.values))
        name, handler = pairs.get("name"), pairs.get("handler")
        if isinstance(name, ast.Constant) and isinstance(handler, ast.Name):
            out[name.value] = handler.id
    return out


def _group_set(tree: ast.Module, var: str) -> set[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if var in targets and isinstance(node.value, ast.Set):
                return {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    raise AssertionError(f"{var} not found as a set literal in server.py")


class DerivationInputs(unittest.TestCase):
    """If these degrade to empty the checks below would pass vacuously."""

    def test_the_sentinel_still_marks_worker_only_functions(self):
        fns = _pcbnew_backed_functions()
        self.assertGreaterEqual(len(fns), 10, "AST found almost no _need_pcbnew() callers")
        self.assertIn("autoroute", fns)
        self.assertIn("clean_micro_stubs", fns)

    def test_handlers_and_tools_are_still_parseable(self):
        tree = _server_tree()
        self.assertGreaterEqual(len(_handler_imports(tree)), 20)
        self.assertGreaterEqual(len(_tool_handlers(tree)), 40)
        self.assertGreaterEqual(len(_group_set(tree, "_EE_GROUP_TOOLS")), 20)


class EeMembershipIsDerived(unittest.TestCase):

    def setUp(self):
        tree = _server_tree()
        self.needs = _pcbnew_backed_functions()
        self.h2imp = _handler_imports(tree)
        self.tool2h = _tool_handlers(tree)
        self.ee = _group_set(tree, "_EE_GROUP_TOOLS")

    def _misrouted(self) -> list[tuple[str, list[str]]]:
        bad = []
        for tool, handler in sorted(self.tool2h.items()):
            backing = self.h2imp.get(handler, set()) & self.needs
            if backing and tool not in self.ee:
                bad.append((tool, sorted(backing)))
        return bad

    def test_every_pcbnew_backed_tool_is_routed_to_the_ee_worker(self):
        bad = self._misrouted()
        self.assertEqual(
            bad, [],
            "these tools call pcbnew but _group_of() sends them to the lean facade, "
            "where the import fails: "
            + "; ".join(f"{t} (via {', '.join(f)})" for t, f in bad)
            + " — add them to _EE_GROUP_TOOLS in services/mcp/server.py")

    def test_the_two_tools_that_actually_broke_are_covered(self):
        # §A: probed the facade for a toolchain that lives in the worker.
        # §I: raised "pcbnew not importable" from the facade.
        for tool in ("bodesign_autoroute_preflight", "bodesign_placement_preflight",
                     "bodesign_clean_micro_stubs"):
            self.assertIn(tool, self.tool2h, f"{tool} is no longer an exposed tool")
            self.assertIn(tool, self.ee, tool)

    def test_a_gate_runs_in_the_same_worker_as_the_action_it_gates(self):
        # §A's real lesson: a preflight that evaluates somewhere else than the
        # gated action answers a question nobody asked.
        for gate, gated in (("bodesign_autoroute_preflight", "bodesign_autoroute"),
                            ("bodesign_placement_preflight", "bodesign_route_net2pcb"),
                            ("bodesign_bga_escape_capacity", "bodesign_autoroute")):
            self.assertEqual(gate in self.ee, gated in self.ee,
                             f"{gate} and {gated} would evaluate in different workers")

    def test_multisheet_native_geometry_is_routed_to_ee(self):
        from services.mcp import server
        self.assertEqual(server._group_of("bodesign_emit_multisheet"), "ee")

    def test_a_new_pcbnew_tool_left_off_the_list_is_reported(self):
        # Proves the derivation actually discriminates: drop a real member and it
        # must be named. Without this, an over-broad membership set (or a broken
        # AST walk) would let the check above pass on anything.
        self.ee = self.ee - {"bodesign_autoroute"}
        bad = dict(self._misrouted())
        self.assertIn("bodesign_autoroute", bad)
        self.assertIn("autoroute", bad["bodesign_autoroute"])


class MeMembershipBoundary(unittest.TestCase):
    """Documents what this file does NOT guard, so the gap is visible rather than assumed."""

    def test_me_group_has_no_sentinel_to_derive_from(self):
        sentinels = set()
        for src in sorted(BRIDGE.glob("*.py")):
            for fn in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
                if isinstance(fn, ast.FunctionDef) and fn.name.startswith("_need_"):
                    sentinels.add(fn.name)
        self.assertEqual(
            sentinels, {SENTINEL},
            "a new _need_* sentinel appeared — extend the derivation to cover its group "
            "instead of leaving that membership hand-maintained")


if __name__ == "__main__":
    unittest.main(verbosity=2)
