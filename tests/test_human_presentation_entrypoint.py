"""S2 human presentation ingestion -- the REAL formal entrypoint (bodesign_emit_multisheet).

Every cell goes through the registered tool handler, not through the policy function.
Synthetic fixture: proves the ingestion contract only, NOT real-user-draft AC17.
"""
from __future__ import annotations

import importlib.util
import shutil
import unittest
from pathlib import Path

from tests.test_human_presentation import (DECLARED, FILES, LIBS, Base,
                                           declared_with, setUpModule as _need_kicad)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bodesign_mcp_server_hp", _REPO_ROOT / "services" / "mcp" / "server.py")
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

TOOL = "bodesign_emit_multisheet"


def setUpModule():
    _need_kicad()


def call(args: dict):
    return server.TOOLS_BY_NAME[TOOL]["handler"](args)


class Registration(unittest.TestCase):
    def test_schema_declares_the_baseline_arguments(self):
        props = server.TOOLS_BY_NAME[TOOL]["schema"]["properties"]
        self.assertEqual(props["presentation_baseline"]["type"], "object")
        self.assertEqual(props["declared_circuit"]["type"], "object")
        self.assertEqual(props["requested_operations"]["type"], "array")

    def test_required_list_is_unchanged(self):
        self.assertEqual(sorted(server.TOOLS_BY_NAME[TOOL]["schema"]["required"]),
                         ["out_dir", "project_name", "spec"])

    def test_handler_is_still_the_multisheet_handler(self):
        self.assertIs(server.TOOLS_BY_NAME[TOOL]["handler"], server._h_emit_multisheet)


class FormalPath(Base):
    def test_cell1_bytes_retained_through_the_formal_path(self):
        before = self.src_hashes()
        out = call(self.request())
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["emit_mode"], "human_inspect_derive")
        self.assertEqual(self.src_hashes(), before)
        self.assertEqual(out["native_hashes_after"], before)
        for f in FILES:
            self.assertEqual((self.out / "baseline_copy" / f).read_bytes(), (self.src / f).read_bytes())
        # every file in `files` exists on disk (no phantom entries)
        self.assertTrue(out["files"])
        for p in out["files"]:
            self.assertTrue(Path(p).is_file(), p)

    def test_cell2_same_topology_derives_same_revision_outputs(self):
        out = call(self.request())
        self.assertEqual(out["status"], "consistent")
        self.assertEqual(out["declared_circuit_revision"], "rev-A")
        self.assertEqual(set(out["receipts"]), {"netlist", "erc", "bom", "companion_svg"})
        self.assertTrue(all(r["status"] == "succeeded" for r in out["receipts"].values()))
        self.assertTrue(all(r["kicad_cli_version"].startswith("9.0") for r in out["receipts"].values()))

    def test_cell3_mismatch_returns_a_proposal_not_an_edit(self):
        before = self.src_hashes()
        out = call(self.request(declared=declared_with(isolated=DECLARED["isolated"] + ["R9.1"])))
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["status"], "proposal_pending")
        self.assertIsNone(out["proposal"]["approval_ref"])
        self.assertEqual(out["apply"]["status"], "NOT_IMPLEMENTED")
        self.assertEqual(self.src_hashes(), before)
        self.assertTrue((self.out / "change_proposal.json").is_file())

    def test_cell4_changed_baseline_is_refused_as_data(self):
        b = self.baseline()
        self.edit_leaf("mcu.kicad_sch", lambda d: d + b"\n")
        out = call(self.request(baseline=b))
        self.assertRefused(out, "E_BASELINE_CHANGED", "baseline_changed")

    def test_cell5_missing_sheet_refused_with_named_gap(self):
        out = call(self.request(baseline=self.baseline(files=("brd.kicad_sch", "power.kicad_sch"))))
        self.assertRefused(out, "E_MISSING_SHEET", "missing_sheet")

    def test_cell5_missing_library_refused_with_named_gap(self):
        out = call(self.request(baseline=self.baseline(libs=[{"name": "Other", "version": "1"}])))
        self.assertRefused(out, "E_UNRESOLVED_LIBRARY", "undeclared_library")

    def test_cell5_unsupported_syntax_refused_with_named_gap(self):
        self.edit_leaf("power.kicad_sch", lambda d: d.replace(b"(version 20250114)", b"(version 20211014)", 1))
        out = call(self.request())  # manifest hashes are computed from the edited bytes
        self.assertRefused(out, "E_UNSUPPORTED_SYNTAX", "unsupported_version")

    def test_cell6_metadata_request_never_changes_geometry(self):
        before = self.src_hashes()
        out = call(self.request(requested_operations=[
            {"edit_class": "set_value", "target_kind": "component", "target_id": "R2", "before": "10k", "after": "22k"}]))
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["status"], "proposal_pending")
        self.assertEqual(self.src_hashes(), before)
        self.assertEqual(out["native_hashes_after"], before)
        self.assertEqual(out["proposal"]["operations"][0]["edit_class"], "set_value")

    def test_a_supplied_baseline_is_never_bypassed_after_a_refusal(self):
        # Fall-through control: spec={} on the legacy path would answer E_SPEC_NO_COMPONENTS.
        out = call(self.request(baseline=self.baseline(files=("brd.kicad_sch",))))
        self.assertFalse(out["ok"])
        self.assertNotEqual(out["error"]["code"], "E_SPEC_NO_COMPONENTS")
        self.assertEqual(out["emit_mode"], None)

    def test_a_non_empty_spec_with_a_baseline_is_a_conflict(self):
        out = call(self.request(spec={"components": [{"ref": "R1", "symbol": "Device:R", "sheet": "a"}]}))
        self.assertRefused(out, "E_BASELINE_SPEC_CONFLICT", "malformed_field")

    def test_control_without_a_baseline_the_legacy_path_is_untouched(self):
        # Same handler, no presentation_baseline: still the emitter, still the old contract.
        out = call({"out_dir": str(self.out), "project_name": "brd", "spec": {}})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_SPEC_NO_COMPONENTS")


class Round2FormalPath(Base):
    """Astra round-2 invariants, exercised through the registered tool handler."""

    def test_r1_symlinked_report_target_is_refused_and_source_untouched(self):
        before = self.src_hashes()
        self.out.mkdir(mode=0o700)
        (self.out / "ingestion_report.json").symlink_to(self.src / "mcu.kicad_sch")
        out = call(self.request())
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_OUTPUT_EXISTS")
        self.assertEqual(self.src_hashes(), before)

    def test_r2_duplicate_declared_net_names_are_refused(self):
        decl = declared_with(nets=[{"name": "X", "nodes": ["R1.1", "R2.1"]},
                                   {"name": "X", "nodes": ["R2.2", "R3.1"]}])
        out = call(self.request(declared=decl))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_DECLARED_CIRCUIT_MALFORMED")
        self.assertFalse(self.out.exists())

    def test_r3_proposal_and_report_bind_the_declared_circuit_digest(self):
        out = call(self.request(declared=declared_with(isolated=DECLARED["isolated"] + ["R9.1"])))
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["proposal"]["baseline_manifest_sha256"], out["subject_manifest_sha256"])
        self.assertTrue(all(o["declared_circuit_sha256"] == out["declared_circuit_sha256"]
                            for o in out["proposal"]["operations"]))

    def test_r4_a_failed_export_is_reported_with_real_files_not_empty(self):
        import unittest.mock as um
        from bodesign_eda_bridge import human_presentation as hp
        real = hp._run_export

        def broken(ns, kind, argv, out_path, inputs, expected):
            if kind == "bom":
                argv = [argv[0], "version"]      # rc=0, but produces no bom.csv
            return real(ns, kind, argv, out_path, inputs, expected)
        with um.patch.object(hp, "_run_export", broken):
            out = call(self.request())
        self.assertFalse(out["ok"])
        self.assertEqual(out["derive_status"], "partial")
        self.assertEqual(out["failed_sidecars"], ["bom"])
        self.assertTrue(out["files"], "files after retention must be the real disk listing")
        self.assertEqual(out["topology_status"], "consistent")

    def test_r5_typed_target_without_kind_is_refused(self):
        out = call(self.request(requested_operations=[
            {"edit_class": "set_value", "target_id": "R2", "after": "1"}]))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_OPERATION_MALFORMED")


if __name__ == "__main__":
    unittest.main()
