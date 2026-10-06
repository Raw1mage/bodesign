"""MCP wiring surface for hierarchical emission (plan multi-sheet, Phase 4).

Two axes, deliberately separate:

  * REGISTRATION -- the tool exists in TOOLS, is reachable by name, and its schema
    declares what the handler actually reads. A handler that works but is not
    registered is unreachable; a schema that omits a required key makes a valid
    call look like a caller error.
  * ERROR SURFACE -- a contract violation comes back as ok:false with a machine
    `error.code` AND files:[], never as a partial success and never as a raised
    exception the transport would render as an opaque failure.

Every negative cell is paired with the positive that proves the same code path can
succeed, so "the check returned nothing" cannot be read as "the check passed".
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SERVER_PATH = _REPO_ROOT / "services" / "mcp" / "server.py"

_spec = importlib.util.spec_from_file_location("bodesign_mcp_server", _SERVER_PATH)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

TOOL_NAME = "bodesign_emit_multisheet"


def _scratch_root() -> Path:
    """A 0700 scratch dir under XDG_RUNTIME_DIR, refusing rather than relocating.

    Bound explicitly instead of relying on TemporaryDirectory's default, which
    follows the caller's TMPDIR and may land in /tmp under a direct unittest run.
    """
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        raise unittest.SkipTest("XDG_RUNTIME_DIR is unset; refusing to relocate")
    root = Path(base) / "bodesign-multisheet-mcp"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        root.chmod(0o700)
    return root


def _two_sheet_spec() -> dict:
    return {
        "components": [
            {"ref": "R1", "symbol": "Device:R", "value": "10k", "sheet": "power"},
            {"ref": "R2", "symbol": "Device:R", "value": "10k", "sheet": "mcu"},
        ],
        "nets": [{"name": "NET_X", "nodes": ["R1.1", "R2.1"]}],
    }


class ToolRegistration(unittest.TestCase):
    """The tool is reachable and its schema matches what the handler reads."""

    def test_the_tool_is_registered_under_its_name(self):
        self.assertIn(TOOL_NAME, server.TOOLS_BY_NAME)

    def test_a_name_that_was_never_registered_is_absent(self):
        # Control for the cell above: TOOLS_BY_NAME does not accept everything.
        self.assertNotIn("bodesign_emit_multisheet_zz", server.TOOLS_BY_NAME)

    def test_the_registered_handler_is_the_multisheet_handler(self):
        entry = server.TOOLS_BY_NAME[TOOL_NAME]
        self.assertIs(entry["handler"], server._h_emit_multisheet)

    def test_the_schema_requires_exactly_what_the_handler_indexes(self):
        # The handler uses a["out_dir"] / a["project_name"] / a["spec"] with []
        # rather than .get(), so any of them missing is a KeyError, not a default.
        schema = server.TOOLS_BY_NAME[TOOL_NAME]["schema"]
        self.assertEqual(
            sorted(schema["required"]), ["out_dir", "project_name", "spec"])

    def test_symbol_dirs_is_declared_as_a_single_type_array(self):
        # BR_20260730b: an anyOf/untyped argument gets stringified in transit, so
        # the array must be declared as exactly one type.
        prop = server.TOOLS_BY_NAME[TOOL_NAME]["schema"]["properties"]["symbol_dirs"]
        self.assertEqual(prop["type"], "array")
        self.assertNotIn("anyOf", prop)

    def test_registering_this_tool_introduced_no_duplicate_name(self):
        names = [tool["name"] for tool in server.TOOLS]
        self.assertEqual(len(names), len(set(names)))

    def test_schema_declares_subsystem_views_and_view_local_max_nodes(self):
        props = server.TOOLS_BY_NAME[TOOL_NAME]["schema"]["properties"]
        self.assertIn("subsystem_views", props)
        self.assertEqual(props["subsystem_views"]["type"], "object")
        self.assertIn("view_local_max_nodes", props)
        self.assertEqual(props["view_local_max_nodes"]["type"], "integer")


class ErrorSurface(unittest.TestCase):
    """A contract violation is DATA with a machine code, never a silent partial."""

    def setUp(self):
        self.root = _scratch_root() / self.id().rsplit(".", 1)[-1]
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, mode=0o700)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _call(self, spec, project_name="brd"):
        return server._h_emit_multisheet(
            {"out_dir": str(self.root), "project_name": project_name, "spec": spec})

    def test_a_partially_declared_spec_reports_E_UNASSIGNED_REFS(self):
        spec = _two_sheet_spec()
        del spec["components"][1]["sheet"]
        out = self._call(spec)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_UNASSIGNED_REFS")

    def test_a_rejected_call_writes_no_files_at_all(self):
        spec = _two_sheet_spec()
        del spec["components"][1]["sheet"]
        out = self._call(spec)
        self.assertEqual(out["files"], [])
        # files:[] is the CLAIM; the disk is the measurement. A manifest can be
        # empty while a partial write sits on disk, so both are asserted.
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [])

    def test_an_invalid_sheet_name_reports_E_SHEET_NAME_INVALID(self):
        spec = _two_sheet_spec()
        spec["components"][0]["sheet"] = "power/../etc"
        out = self._call(spec)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_SHEET_NAME_INVALID")

    def test_a_leaf_stem_equal_to_the_project_name_reports_a_collision(self):
        spec = _two_sheet_spec()
        out = self._call(spec, project_name="power")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_SHEET_NAME_COLLISION")

    def test_a_malformed_net_node_reports_E_NET_NODE_MALFORMED(self):
        spec = _two_sheet_spec()
        spec["nets"][0]["nodes"] = ["R1.1", "R2"]
        out = self._call(spec)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_NET_NODE_MALFORMED")

    def test_a_spec_with_no_components_reports_E_SPEC_NO_COMPONENTS(self):
        out = self._call({"components": [], "nets": []})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_SPEC_NO_COMPONENTS")

    def test_every_rejection_carries_a_code_that_is_not_None(self):
        # The point of returning DATA is that the caller can branch on identity.
        # A None code would defeat that while still reading as a handled error.
        spec = _two_sheet_spec()
        spec["components"][0]["sheet"] = ""
        out = self._call(spec)
        self.assertIsNotNone(out["error"]["code"])
        self.assertEqual(out["emit_mode"], None)


class SuccessSurface(unittest.TestCase):
    """The positive control for every cell above: this path really can succeed."""

    def setUp(self):
        self.root = _scratch_root() / self.id().rsplit(".", 1)[-1]
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, mode=0o700)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.result = server._h_emit_multisheet({
            "out_dir": str(self.root),
            "project_name": "brd",
            "spec": _two_sheet_spec(),
        })

    def test_a_well_formed_spec_succeeds(self):
        self.assertTrue(self.result["ok"], self.result)

    def test_it_reports_the_hierarchical_route(self):
        self.assertEqual(self.result["emit_mode"], "hierarchical")
        self.assertEqual(self.result["sheet_count"], 2)

    def test_every_path_in_files_exists_on_disk(self):
        for path in self.result["files"]:
            self.assertTrue(Path(path).exists(), path)

    def test_the_root_and_both_leaves_were_written(self):
        written = sorted(p.name for p in self.root.glob("*.kicad_sch"))
        self.assertEqual(written, ["brd.kicad_sch", "mcu.kicad_sch",
                                   "power.kicad_sch"])

    def test_the_cross_sheet_net_is_reported_as_cross_sheet(self):
        self.assertEqual(self.result["cross_sheet_nets"], ["NET_X"])

    def test_schematic_path_points_at_the_root_not_a_leaf(self):
        self.assertEqual(Path(self.result["schematic_path"]).name, "brd.kicad_sch")

    def test_each_leaf_reports_its_own_component_count(self):
        self.assertEqual(self.result["leaf_component_counts"],
                         {"power": 1, "mcu": 1})

    def test_forwarding_subsystem_views_and_view_local_max_nodes(self):
        root = self.root / "views_test"
        res = server._h_emit_multisheet({
            "out_dir": str(root),
            "project_name": "brd_views",
            "spec": _two_sheet_spec(),
            "subsystem_views": {"power": ["NET_X"]},
            "view_local_max_nodes": 5,
        })
        self.assertTrue(res["ok"], res)


if __name__ == "__main__":
    unittest.main()
