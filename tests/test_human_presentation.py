"""S2 human presentation ingestion -- contract cells (DD-13 / AC17).

Fixture: a SYNTHETIC native root + 2 leaves (tests/fixtures/human_presentation),
generated once by the bodesign emitter and loaded by real kicad-cli 9.0.9.  It proves
the ingestion contract only; it does NOT satisfy real-user-draft AC17.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import types
import unittest
import unittest.mock
from pathlib import Path

from bodesign_eda_bridge import human_presentation as hp
from bodesign_workflow_core import human_presentation as pol

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "human_presentation" / "synthetic_root_2leaves"
FILES = ("brd.kicad_sch", "power.kicad_sch", "mcu.kicad_sch")

DECLARED = {
    "revision": "rev-A",
    "nets": [{"name": "NET_X", "nodes": ["R1.1", "R2.1"]}, {"name": "NET_Y", "nodes": ["R2.2", "R3.1"]}],
    "nc": ["R3.2"],
    "isolated": ["R1.2", "R4.1", "R4.2"],
}
LIBS = [{"name": "Device", "version": "9.0"}]


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def scratch_root() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        raise RuntimeError("XDG_RUNTIME_DIR is unset; refusing to relocate scratch")
    root = Path(base) / "bodesign-human-presentation"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        root.chmod(0o700)
    return root


def setUpModule():
    # Real tool required: a missing kicad-cli must fail loudly, not skip.
    if hp.find_kicad_cli() is None:
        raise RuntimeError("kicad-cli is required for the S2 ingestion cells")


class Base(unittest.TestCase):
    def setUp(self):
        self.root = scratch_root() / self.id().rsplit(".", 1)[-1]
        if self.root.exists():
            shutil.rmtree(self.root)
        self.src = self.root / "src"
        self.out = self.root / "out"
        self.src.mkdir(parents=True, mode=0o700)
        for f in FILES:
            shutil.copyfile(_FIXTURE / f, self.src / f)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def baseline(self, files=FILES, libs=None, **over):
        b = {"schema_version": "1.0", "source": "human", "source_dir": str(self.src),
             "root": "brd.kicad_sch", "kicad_version": "9.0",
             "files": [{"path": f, "sha256": sha(self.src / f)} for f in files],
             "libraries": LIBS if libs is None else libs}
        b.update(over)
        return b

    def request(self, declared=None, baseline=None, **over):
        a = {"out_dir": str(self.out), "project_name": "brd", "spec": {},
             "presentation_baseline": baseline or self.baseline(),
             "declared_circuit": declared if declared is not None else DECLARED}
        a.update(over)
        return a

    def src_hashes(self):
        return {f: sha(self.src / f) for f in FILES if (self.src / f).exists()}

    def assertRefused(self, out, code, kind):
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["error"]["code"], code, out["error"])
        self.assertIn(kind, {g["kind"] for g in out["error"]["details"].get("gaps", [])}, out["error"])
        self.assertEqual(out["files"], [])
        self.assertFalse(self.out.exists(), "a refusal must not write anything")

    def edit_leaf(self, name, fn):
        p = self.src / name
        p.write_bytes(fn(p.read_bytes()))


class Cell1BytesRetained(Base):
    """(1) every byte of the native set survives inspect/derive, source AND retained copy."""

    def test_all_bytes_retained_and_every_object_pinned(self):
        before = self.src_hashes()
        out = pol.ingest_human_presentation(self.request())
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.src_hashes(), before)
        self.assertEqual(out["native_hashes_before"], before)
        self.assertEqual(out["native_hashes_after"], before)
        self.assertTrue(out["native_unchanged"])
        for f in FILES:
            copy = self.out / "baseline_copy" / f
            self.assertEqual(copy.read_bytes(), (self.src / f).read_bytes())
        expected = set()
        for f in FILES:
            text = (self.src / f).read_bytes().decode("latin-1")
            expected |= {f"{f}#{u}" for u in re.findall(r'\(uuid "([^"]+)"', text)}
        self.assertTrue(expected)
        # source=human pins ALL existing objects, not a caller-selected subset.
        self.assertEqual(set(out["proposal"]["locked_object_ids"]) if out["proposal"] else
                         set(pol_inventory_ids(self)), expected)

    def test_control_a_mutated_source_is_detected_by_the_same_assertion(self):
        ns = hp.load_native_set(self.baseline())
        hp.assert_unchanged(ns)
        (self.src / "power.kicad_sch").write_bytes((self.src / "power.kicad_sch").read_bytes() + b"\n")
        with self.assertRaises(hp.HumanPresentationError) as cm:
            hp.assert_unchanged(ns)
        self.assertEqual(cm.exception.code, "E_BASELINE_CHANGED")


def pol_inventory_ids(case):
    ns = hp.load_native_set(case.baseline())
    return hp.inventory(ns)["pinned_object_ids"]


class Cell2SameTopology(Base):
    """(2) same topology => derived same-revision outputs, separate sidecars with receipts."""

    def test_consistent_topology_yields_no_proposal(self):
        out = pol.ingest_human_presentation(self.request())
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["status"], "consistent")
        self.assertEqual(out["topology_mismatches"], [])
        self.assertIsNone(out["proposal"])
        self.assertEqual(out["declared_circuit_revision"], "rev-A")
        self.assertEqual(out["apply"]["status"], "NOT_IMPLEMENTED")
        self.assertIn("human_source_is_not_approval", out["does_not_authorize"])

    def test_each_sidecar_is_separate_with_a_complete_receipt(self):
        out = pol.ingest_human_presentation(self.request())
        src = self.src_hashes()
        self.assertEqual(set(out["receipts"]), {"netlist", "erc", "bom", "companion_svg"})
        dirs = set()
        for kind, r in out["receipts"].items():
            self.assertEqual(r["status"], "succeeded", r)
            self.assertTrue(r["kicad_cli_version"].startswith("9.0"), r)
            self.assertEqual(r["command"][0], r["kicad_cli"])
            self.assertEqual(r["input_hashes"], src)
            dirs.add(Path(r["output"]["path"]).parent if "sha256" in r["output"] else Path(r["output"]["path"]))
            outs = [r["output"]] if "sha256" in r["output"] else r["output"]["files"]
            self.assertTrue(outs)
            for o in outs:
                self.assertEqual(sha(Path(o["path"])), o["sha256"])
        self.assertEqual(len(dirs), 4, "sidecars must live in separate directories")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", out["baseline_manifest_sha256"]))

    def test_receipt_command_was_run_on_the_retained_copy_not_the_source(self):
        out = pol.ingest_human_presentation(self.request())
        for r in out["receipts"].values():
            self.assertIn(str(self.out / "baseline_copy" / "brd.kicad_sch"), r["command"])
            self.assertNotIn(str(self.src / "brd.kicad_sch"), r["command"])


def declared_with(**kw):
    d = {"revision": "rev-A", "nets": [dict(n) for n in DECLARED["nets"]],
         "nc": list(DECLARED["nc"]), "isolated": list(DECLARED["isolated"])}
    d.update(kw)
    return d


class Cell3TopologyMismatch(Base):
    """(3) missing / fused / NC / isolated disagreement => explicit proposal, nothing edited."""

    def _run(self, declared):
        before = self.src_hashes()
        out = pol.ingest_human_presentation(self.request(declared=declared))
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.src_hashes(), before, "neither side may be edited to force parity")
        self.assertEqual(out["status"], "proposal_pending")
        prop = out["proposal"]
        self.assertIsNotNone(prop)
        self.assertEqual(prop["baseline_manifest_sha256"], out["subject_manifest_sha256"])
        self.assertNotEqual(out["subject_manifest_sha256"], out["baseline_manifest_sha256"],
                            "the proposal subject also binds the declared-circuit digest")
        self.assertIsNone(prop["approval_ref"], "a proposal is NOT approval")
        for op in prop["operations"]:
            self.assertEqual(op["declared_circuit_revision"], "rev-A")
            self.assertTrue(op["affected_ids"])
            self.assertIn("before", op)
            self.assertIn("after", op)
        self.assertTrue(prop["locked_object_ids"], "human source pins every existing object")
        self.assertEqual(out["operation_outcome"]["outcome"], "indeterminate")
        self.assertEqual(out["operation_outcome"]["code"], "PROPOSAL_PENDING_APPROVAL")
        return out

    def kinds(self, out):
        return {m["kind"] for m in out["topology_mismatches"]}

    def test_missing_pin_becomes_a_proposal(self):
        out = self._run(declared_with(isolated=DECLARED["isolated"] + ["R9.1"]))
        miss = [m for m in out["topology_mismatches"] if m["kind"] == "missing"]
        self.assertEqual([m["affected_nodes"] for m in miss], [["R9.1"]])

    def test_fused_nets_become_a_proposal(self):
        decl = declared_with(nets=[{"name": "NET_A", "nodes": ["R1.1", "R4.1"]},
                                   {"name": "NET_B", "nodes": ["R2.1", "R4.2"]},
                                   {"name": "NET_Y", "nodes": ["R2.2", "R3.1"]}],
                             isolated=["R1.2"])
        out = self._run(decl)
        fused = [m for m in out["topology_mismatches"] if m["kind"] == "fused"]
        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]["affected_nodes"], ["R1.1", "R2.1"])
        self.assertEqual(fused[0]["after"]["declared_nets"], ["NET_A", "NET_B"])

    def test_declared_connected_but_native_nc_becomes_a_proposal(self):
        decl = declared_with(nets=DECLARED["nets"] + [{"name": "NET_Z", "nodes": ["R3.2", "R4.1"]}],
                             nc=[], isolated=["R1.2", "R4.2"])
        out = self._run(decl)
        nc = [m for m in out["topology_mismatches"] if m["kind"] == "nc"]
        self.assertEqual([m["affected_nodes"] for m in nc], [["R3.2"]])

    def test_declared_connected_but_native_isolated_becomes_a_proposal(self):
        decl = declared_with(nets=DECLARED["nets"] + [{"name": "NET_Z", "nodes": ["R1.2", "R4.1"]}],
                             isolated=["R4.2"])
        out = self._run(decl)
        iso = [m for m in out["topology_mismatches"] if m["kind"] == "isolated"]
        self.assertEqual(sorted(n for m in iso for n in m["affected_nodes"]), ["R1.2", "R4.1"])

    def test_declared_nc_but_native_connected_becomes_a_proposal(self):
        decl = declared_with(nc=["R3.2", "R2.1"], nets=[DECLARED["nets"][1]],
                             isolated=["R1.1", "R1.2", "R4.1", "R4.2"])
        out = self._run(decl)
        self.assertIn("nc", self.kinds(out))

    def test_every_operation_carries_an_explicit_adapter_capability_conflict(self):
        out = self._run(declared_with(isolated=DECLARED["isolated"] + ["R9.1"]))
        types = [c["type"] for c in out["proposal"]["conflicts"]]
        self.assertIn("ADAPTER_CAPABILITY_MISSING", types)
        self.assertFalse(out["precondition_gate"]["allowed"])
        self.assertEqual(out["apply"]["status"], "NOT_IMPLEMENTED")

    def test_control_matching_declaration_produces_no_mismatch(self):
        out = pol.ingest_human_presentation(self.request(declared=declared_with()))
        self.assertEqual(out["topology_mismatches"], [])


class Cell4ChangedBaseline(Base):
    """(4) a baseline that no longer matches its declared hashes is refused before any write."""

    def test_leaf_changed_after_manifest_was_declared(self):
        b = self.baseline()
        self.edit_leaf("power.kicad_sch", lambda d: d + b"\n")
        out = pol.ingest_human_presentation(self.request(baseline=b))
        self.assertRefused(out, "E_BASELINE_CHANGED", "baseline_changed")
        self.assertEqual(out["apply"]["status"], "NOT_IMPLEMENTED")

    def test_declared_manifest_digest_mismatch(self):
        b = self.baseline(baseline_manifest_sha256="0" * 64)
        out = pol.ingest_human_presentation(self.request(baseline=b))
        self.assertRefused(out, "E_BASELINE_CHANGED", "baseline_changed")

    def test_control_correct_manifest_digest_is_accepted(self):
        ns = hp.load_native_set(self.baseline())
        digest = ns.manifest("rev-A").manifest_sha256
        out = pol.ingest_human_presentation(self.request(baseline=self.baseline(baseline_manifest_sha256=digest)))
        self.assertTrue(out["ok"], out)


class Cell5RefuseWithNamedGap(Base):
    """(5) missing sheet / library / identity / unsupported syntax => refusal naming the gap, no write."""

    def test_missing_referenced_sheet(self):
        out = pol.ingest_human_presentation(self.request(baseline=self.baseline(files=("brd.kicad_sch", "mcu.kicad_sch"))))
        self.assertRefused(out, "E_MISSING_SHEET", "missing_sheet")
        gap = [g for g in out["error"]["details"]["gaps"] if g["kind"] == "missing_sheet"][0]
        self.assertEqual(gap["path"], "power.kicad_sch")
        self.assertEqual(gap["referenced_by"], "brd.kicad_sch")

    def test_declared_file_missing_on_disk(self):
        b = self.baseline()
        (self.src / "power.kicad_sch").unlink()
        out = pol.ingest_human_presentation(self.request(baseline=b))
        self.assertRefused(out, "E_MISSING_SHEET", "missing_sheet")

    def test_path_traversal_in_manifest(self):
        b = self.baseline()
        b["files"].append({"path": "../escape.kicad_sch", "sha256": "0" * 64})
        self.assertRefused(pol.ingest_human_presentation(self.request(baseline=b)), "E_PATH_TRAVERSAL", "path_traversal")

    def test_absolute_path_in_manifest(self):
        b = self.baseline()
        b["files"][1]["path"] = "/etc/passwd.kicad_sch"
        self.assertRefused(pol.ingest_human_presentation(self.request(baseline=b)), "E_PATH_TRAVERSAL", "path_traversal")

    def test_symlink_escaping_the_source_dir(self):
        outside = self.root / "outside.kicad_sch"
        shutil.copyfile(_FIXTURE / "power.kicad_sch", outside)
        (self.src / "power.kicad_sch").unlink()
        os.symlink(outside, self.src / "power.kicad_sch")
        out = pol.ingest_human_presentation(self.request(baseline=self.baseline()))
        self.assertRefused(out, "E_PATH_ESCAPE", "symlink_escape")

    def test_undeclared_library(self):
        out = pol.ingest_human_presentation(self.request(baseline=self.baseline(libs=[{"name": "Other", "version": "1"}])))
        self.assertRefused(out, "E_UNRESOLVED_LIBRARY", "undeclared_library")

    def test_symbol_definition_not_embedded(self):
        self.edit_leaf("mcu.kicad_sch", lambda d: d.replace(b'(lib_id "Device:R")', b'(lib_id "Device:C")', 1))
        out = pol.ingest_human_presentation(self.request())
        self.assertRefused(out, "E_UNRESOLVED_LIBRARY", "unresolved_symbol_definition")

    def test_duplicate_reference_identity(self):
        self.edit_leaf("mcu.kicad_sch", lambda d: d.replace(b'"Reference" "R3"', b'"Reference" "R2"', 1))
        out = pol.ingest_human_presentation(self.request())
        self.assertRefused(out, "E_UNRESOLVED_IDENTITY", "duplicate_identity")

    def test_unsupported_native_version(self):
        self.edit_leaf("power.kicad_sch", lambda d: d.replace(b"(version 20250114)", b"(version 20200101)", 1))
        self.assertRefused(pol.ingest_human_presentation(self.request()), "E_UNSUPPORTED_SYNTAX", "unsupported_version")

    def test_unparseable_syntax(self):
        self.edit_leaf("power.kicad_sch", lambda d: d + b"(")
        self.assertRefused(pol.ingest_human_presentation(self.request()), "E_UNSUPPORTED_SYNTAX", "unsupported_syntax")

    def test_unsupported_kicad_release_declared(self):
        out = pol.ingest_human_presentation(self.request(baseline=self.baseline(kicad_version="8.0")))
        self.assertRefused(out, "E_KICAD_VERSION", "unsupported_kicad_version")

    def test_declared_but_unreferenced_sheet_is_never_assigned_a_partition(self):
        shutil.copyfile(self.src / "mcu.kicad_sch", self.src / "extra.kicad_sch")
        b = self.baseline()
        b["files"].append({"path": "extra.kicad_sch", "sha256": sha(self.src / "extra.kicad_sch")})
        self.assertRefused(pol.ingest_human_presentation(self.request(baseline=b)), "E_SHEET_PARTITION_AMBIGUOUS", "unreferenced_file")

    def test_spec_alongside_a_baseline_is_refused(self):
        out = pol.ingest_human_presentation(self.request(spec={"components": [{"ref": "R1"}]}))
        self.assertRefused(out, "E_BASELINE_SPEC_CONFLICT", "malformed_field")

    def test_restyle_arguments_are_refused(self):
        out = pol.ingest_human_presentation(self.request(paper="A3"))
        self.assertRefused(out, "E_BASELINE_EMIT_ARGS", "malformed_field")

    def test_missing_declared_circuit(self):
        a = self.request()
        del a["declared_circuit"]
        self.assertRefused(pol.ingest_human_presentation(a), "E_DECLARED_CIRCUIT_MISSING", "missing_field")

    def test_out_dir_inside_source_dir(self):
        out = pol.ingest_human_presentation(self.request(out_dir=str(self.src / "derived")))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_OUTPUT_DIR")
        self.assertEqual(sorted(p.name for p in self.src.iterdir()), sorted(FILES))

    def test_control_the_unmodified_set_is_accepted(self):
        self.assertTrue(pol.ingest_human_presentation(self.request())["ok"])


class Cell6MetadataNeverChangesGeometry(Base):
    """(6) value / footprint / annotation / label requests become proposals, never edits."""

    def _symbol_uuid(self, ref):
        ns = hp.load_native_set(self.baseline())
        for path, sh in hp.inventory(ns)["sheets"].items():
            for s in sh["symbols"]:
                if s["ref"] == ref:
                    return f"{path}#{s['uuid']}"  # scoped identity, as pinned
        raise AssertionError(ref)

    def _ops(self):
        r2 = self._symbol_uuid("R2")
        return [
            {"edit_class": "set_value", "target_kind": "object", "target_id": r2, "before": "10k", "after": "22k"},
            {"edit_class": "set_footprint", "target_kind": "component", "target_id": "R2", "before": "", "after": "R_0603_1608Metric"},
            {"edit_class": "set_annotation", "target_kind": "object", "target_id": r2, "before": "R2", "after": "R20"},
            {"edit_class": "add_label", "target_kind": "pin", "target_id": "R4.1", "after": {"text": "SENSE"}},
        ]

    def test_requests_become_proposal_operations_and_bytes_are_unchanged(self):
        before = self.src_hashes()
        out = pol.ingest_human_presentation(self.request(requested_operations=self._ops()))
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.src_hashes(), before)
        self.assertEqual(out["native_hashes_after"], before)
        for f in FILES:
            self.assertEqual((self.out / "baseline_copy" / f).read_bytes(), (self.src / f).read_bytes())
        self.assertEqual(out["status"], "proposal_pending")
        ops = out["proposal"]["operations"]
        self.assertEqual([o["edit_class"] for o in ops],
                         ["set_value", "set_footprint", "set_annotation", "add_label"])
        self.assertTrue(all(o["origin"] == "caller_request" for o in ops))
        self.assertIsNone(out["proposal"]["approval_ref"])
        self.assertFalse(out["precondition_gate"]["allowed"])
        self.assertEqual(out["apply"]["status"], "NOT_IMPLEMENTED")
        # the value in the retained copy is still the human's value
        self.assertIn('(property "Value" "10k"', (self.out / "baseline_copy" / "mcu.kicad_sch").read_text())
        self.assertNotIn("22k", (self.out / "baseline_copy" / "mcu.kicad_sch").read_text())

    def test_requests_are_pinned_not_applicable(self):
        out = pol.ingest_human_presentation(self.request(requested_operations=self._ops()))
        types = {c["type"] for c in out["proposal"]["conflicts"]}
        self.assertIn("ADAPTER_CAPABILITY_MISSING", types)
        self.assertIn("LOCKED_OBJECT_MUTATION", types)

    def test_a_bare_uuid_target_is_not_silently_resolved(self):
        bare = self._symbol_uuid("R2").split("#", 1)[1]
        out = pol.ingest_human_presentation(self.request(requested_operations=[
            {"edit_class": "set_value", "target_kind": "object", "target_id": bare, "after": "1"}]))
        self.assertIn("TARGET_NOT_FOUND", {c["type"] for c in out["proposal"]["conflicts"]})

    def test_request_for_an_unknown_target_is_a_conflict(self):
        out = pol.ingest_human_presentation(self.request(requested_operations=[
            {"edit_class": "set_value", "target_kind": "object", "target_id": "no-such-uuid", "after": "1"}]))
        self.assertIn("TARGET_NOT_FOUND", {c["type"] for c in out["proposal"]["conflicts"]})

    def test_malformed_request_is_refused(self):
        out = pol.ingest_human_presentation(self.request(requested_operations=[{"edit_class": "set_value"}]))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_OPERATION_MALFORMED")
        self.assertFalse(self.out.exists())

    def test_default_requests_are_empty(self):
        out = pol.ingest_human_presentation(self.request())
        self.assertIsNone(out["proposal"])

    def test_no_apply_function_exists(self):
        for mod in (pol, hp):
            self.assertFalse([n for n in dir(mod) if n.startswith(("apply_", "write_native", "commit_"))])


# --------------------------------------------------------------------------
# Round 2 (Astra RETURN): five inspect/derive invariants
# --------------------------------------------------------------------------

class R2_1OutputAliases(Base):
    """Invariant 1: no output target may alias a source byte; workspace must be fresh."""

    def test_symlinked_report_target_is_refused_and_source_untouched(self):
        before = self.src_hashes()
        self.out.mkdir(mode=0o700)
        os.symlink(self.src / "mcu.kicad_sch", self.out / "ingestion_report.json")
        out = pol.ingest_human_presentation(self.request())
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["error"]["code"], "E_OUTPUT_EXISTS")
        self.assertIn("output_exists", {g["kind"] for g in out["error"]["details"]["gaps"]})
        self.assertEqual(self.src_hashes(), before)
        self.assertTrue((self.out / "ingestion_report.json").is_symlink(), "alias left exactly as found")

    def test_hardlinked_report_target_is_refused_and_source_untouched(self):
        before = self.src_hashes()
        self.out.mkdir(mode=0o700)
        os.link(self.src / "mcu.kicad_sch", self.out / "ingestion_report.json")
        out = pol.ingest_human_presentation(self.request())
        self.assertEqual(out["error"]["code"], "E_OUTPUT_EXISTS")
        self.assertEqual(self.src_hashes(), before)

    def test_existing_empty_out_dir_is_refused(self):
        self.out.mkdir(mode=0o700)
        out = pol.ingest_human_presentation(self.request())
        self.assertEqual(out["error"]["code"], "E_OUTPUT_EXISTS")
        self.assertEqual(list(self.out.iterdir()), [], "a refusal wrote nothing into it")

    def test_out_dir_that_is_a_symlink_into_the_source_is_refused(self):
        before = self.src_hashes()
        link = self.root / "link_out"
        os.symlink(self.src, link)
        out = pol.ingest_human_presentation(self.request(out_dir=str(link)))
        self.assertFalse(out["ok"])
        self.assertIn(out["error"]["code"], ("E_OUTPUT_DIR", "E_OUTPUT_EXISTS"))
        self.assertEqual(self.src_hashes(), before)

    def test_exclusive_write_never_writes_through_a_symlink(self):
        target = self.root / "victim"
        target.write_bytes(b"keep")
        link = self.root / "alias"
        os.symlink(target, link)
        with self.assertRaises(FileExistsError):
            hp.exclusive_write(link, b"overwrite")
        self.assertEqual(target.read_bytes(), b"keep")

    def test_derive_refuses_a_non_empty_or_symlinked_workspace(self):
        ns = hp.load_native_set(self.baseline())
        self.out.mkdir(mode=0o700)
        (self.out / "stray").write_text("x")
        with self.assertRaises(hp.HumanPresentationError) as cm:
            hp.derive_sidecars(ns, self.out)
        self.assertEqual(cm.exception.code, "E_OUTPUT_EXISTS")

    def test_files_list_is_only_this_invocations_artifacts(self):
        out = pol.ingest_human_presentation(self.request())
        self.assertTrue(out["ok"], out)
        on_disk = sorted(str(p) for p in self.out.rglob("*") if p.is_file())
        self.assertEqual(out["files"], on_disk)
        self.assertTrue(all(p.startswith(str(self.out)) for p in out["files"]))


class R2_2PartitionIdentity(Base):
    """Invariant 2: declared net identity is the partition cell, never the display name."""

    def test_duplicate_declared_net_names_are_refused(self):
        decl = declared_with(nets=[{"name": "X", "nodes": ["R1.1", "R2.1"]},
                                   {"name": "X", "nodes": ["R2.2", "R3.1"]}])
        out = pol.ingest_human_presentation(self.request(declared=decl))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_DECLARED_CIRCUIT_MALFORMED")
        self.assertIn("duplicate declared net name",
                      " ".join(g.get("detail", "") for g in out["error"]["details"]["gaps"]))
        self.assertFalse(self.out.exists())

    def test_same_label_cells_merged_natively_are_still_fused(self):
        # Bypass validation on purpose: two DISJOINT cells carrying the same display name,
        # merged in the native net.  Name-keyed logic reports nothing; cell-keyed reports fused.
        declared = {"revision": "r", "nc": [], "isolated": [],
                    "nets": [{"name": "X", "nodes": ["R1.1", "R2.1"]},
                             {"name": "X", "nodes": ["R3.1", "R4.1"]}]}
        native = {"all_nodes": ["R1.1", "R2.1", "R3.1", "R4.1"], "nc_nodes": [],
                  "nets": [{"name": "M", "nodes": ["R1.1", "R2.1", "R3.1", "R4.1"]}]}
        kinds = [m["kind"] for m in pol.compare_topology(declared, native)]
        self.assertIn("fused", kinds)

    def test_control_distinct_cells_native_distinct_report_nothing(self):
        declared = {"revision": "r", "nc": [], "isolated": [],
                    "nets": [{"name": "X", "nodes": ["R1.1", "R2.1"]},
                             {"name": "Y", "nodes": ["R3.1", "R4.1"]}]}
        native = {"all_nodes": ["R1.1", "R2.1", "R3.1", "R4.1"], "nc_nodes": [],
                  "nets": [{"name": "A", "nodes": ["R1.1", "R2.1"]}, {"name": "B", "nodes": ["R3.1", "R4.1"]}]}
        self.assertEqual(pol.compare_topology(declared, native), [])

    def test_all_nc_isolated_circuit_is_a_supported_bounded_case(self):
        d = pol.validate_declared_circuit({"revision": "r", "nets": [], "nc": ["R3.2"], "isolated": ["R1.2"]})
        self.assertEqual(d["nets"], [])

    def test_a_declaration_of_nothing_is_still_refused(self):
        with self.assertRaises(hp.HumanPresentationError):
            pol.validate_declared_circuit({"revision": "r", "nets": [], "nc": [], "isolated": []})


class R2_3DeclaredSubjectBinding(Base):
    """Invariant 3: the declared circuit digest is a bound subject dependency."""

    def test_report_and_proposal_carry_the_declared_digest(self):
        decl = declared_with(isolated=DECLARED["isolated"] + ["R9.1"])
        out = pol.ingest_human_presentation(self.request(declared=decl))
        d = pol.validate_declared_circuit(decl)
        self.assertEqual(out["declared_circuit_sha256"], d["sha256"])
        self.assertTrue(all(o["declared_circuit_sha256"] == d["sha256"] for o in out["proposal"]["operations"]))
        self.assertEqual(out["proposal"]["baseline_manifest_sha256"], out["subject_manifest_sha256"])
        deps = {(x["kind"], x["name"], x.get("digest")) for x in
                (self.out / "ingestion_report.json").read_text() and
                __import__("json").loads((self.out / "ingestion_report.json").read_text())["subject_manifest"]["dependencies"]}
        self.assertIn(("source", "declared_circuit", d["sha256"]), deps)
        rep = __import__("json").loads((self.out / "ingestion_report.json").read_text())
        self.assertIn("CALLER-DECLARED", rep["library_identity_note"])

    def test_same_native_different_declaration_gives_different_subject(self):
        a = pol.ingest_human_presentation(self.request())
        shutil.rmtree(self.out)
        b = pol.ingest_human_presentation(self.request(declared=declared_with(revision="rev-B")))
        self.assertEqual(a["baseline_manifest_sha256"] == b["baseline_manifest_sha256"], False,
                         "revision is part of the native manifest identity too")
        self.assertNotEqual(a["subject_manifest_sha256"], b["subject_manifest_sha256"])

    def test_same_revision_changed_nets_changes_the_subject_digest(self):
        a = pol.ingest_human_presentation(self.request())
        shutil.rmtree(self.out)
        b = pol.ingest_human_presentation(self.request(declared=declared_with(isolated=DECLARED["isolated"] + ["R9.1"])))
        self.assertEqual(a["baseline_manifest_sha256"], b["baseline_manifest_sha256"])
        self.assertNotEqual(a["declared_circuit_sha256"], b["declared_circuit_sha256"])
        self.assertNotEqual(a["subject_manifest_sha256"], b["subject_manifest_sha256"])


class R2_4DerivationHonesty(Base):
    """Invariant 4: execution failure is never reported as success; ERC findings are findings."""

    def _patched_run(self, fail_kind=None, mode="rc"):
        real = hp.subprocess.run

        def fake(argv, *a, **k):
            if fail_kind and fail_kind in argv:
                if mode == "timeout":
                    raise hp.subprocess.TimeoutExpired(argv, 1)
                if mode == "oserror":
                    raise OSError("boom")
                return hp.subprocess.CompletedProcess(argv, 3, "", "induced failure")
            return real(argv, *a, **k)
        return fake

    def _run_with(self, **kw):
        with unittest.mock.patch.object(hp.subprocess, "run", self._patched_run(**kw)):
            return pol.ingest_human_presentation(self.request())

    def test_rc0_with_zero_outputs_is_not_success(self):
        ns = types.SimpleNamespace(kicad_cli="/usr/bin/true", kicad_cli_version="x")
        d = self.root / "empty_out"
        d.mkdir(mode=0o700)
        r = hp._run_export(ns, "companion_svg", ["/usr/bin/true"], d, {}, expected_files=3)
        self.assertEqual(r["returncode"], 0)
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["coverage"], {"expected_files": 3, "actual_nonempty_files": 0})
        self.assertIn("expected 3", r["failure"])

    def test_control_real_svg_export_meets_its_coverage(self):
        out = pol.ingest_human_presentation(self.request())
        svg = out["receipts"]["companion_svg"]
        self.assertEqual(svg["coverage"], {"expected_files": 3, "actual_nonempty_files": 3})
        self.assertEqual(svg["status"], "succeeded")

    def test_bom_failure_makes_the_overall_derive_partial_not_ok(self):
        out = self._run_with(fail_kind="bom")
        self.assertFalse(out["ok"])
        self.assertEqual(out["derive_status"], "partial")
        self.assertEqual(out["status"], "derive_partial")
        self.assertEqual(out["error"]["code"], "E_DERIVE_PARTIAL")
        self.assertEqual(out["failed_sidecars"], ["bom"])
        self.assertEqual(out["topology_status"], "consistent", "topology stays a separate field")
        self.assertEqual(out["operation_outcome"]["outcome"], "indeterminate")
        self.assertTrue(out["files"], "written files are reported, not []")
        self.assertEqual(out["receipts"]["bom"]["status"], "failed")

    def test_erc_timeout_is_a_typed_receipt_not_an_escaped_exception(self):
        out = self._run_with(fail_kind="erc", mode="timeout")
        self.assertEqual(out["derive_status"], "partial")
        self.assertIn("TimeoutExpired", out["receipts"]["erc"]["failure"])
        self.assertIsNone(out["receipts"]["erc"]["returncode"])

    def test_oserror_on_an_export_is_a_typed_receipt(self):
        out = self._run_with(fail_kind="svg", mode="oserror")
        self.assertEqual(out["failed_sidecars"], ["companion_svg"])
        self.assertIn("OSError", out["receipts"]["companion_svg"]["failure"])

    def test_netlist_failure_is_a_refusal_that_keeps_files_and_receipts(self):
        out = self._run_with(fail_kind="netlist")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_DERIVE_FAILED")
        self.assertTrue(out["files"], "failure after retention must not report files=[]")
        self.assertTrue(any("baseline_copy" in f for f in out["files"]))
        self.assertEqual(out["receipts"]["netlist"]["status"], "failed")

    def test_erc_violations_are_findings_not_failure_or_approval(self):
        out = pol.ingest_human_presentation(self.request())
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["receipts"]["erc"]["status"], "succeeded")
        self.assertGreater(out["erc_findings"]["total"], 0)
        self.assertIn("not an approval", out["erc_findings"]["meaning"])
        self.assertIn("electrical_correctness", out["does_not_authorize"])

    def test_unreadable_netlist_parse_is_a_typed_refusal(self):
        with unittest.mock.patch.object(hp, "parse_native_connectivity", side_effect=ValueError("bad net")):
            out = pol.ingest_human_presentation(self.request())
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_DERIVE_FAILED")
        self.assertTrue(out["files"])
        self.assertIn("netlist", out["receipts"])

    def test_tool_version_probe_failure_is_typed(self):
        with unittest.mock.patch.object(hp.subprocess, "run", side_effect=OSError("no exec")):
            out = pol.ingest_human_presentation(self.request())
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "E_TOOL_UNAVAILABLE")
        self.assertFalse(self.out.exists())


class R2_5PinPopulation(Base):
    """Invariant 5: the pin denominator comes from native symbols, not from the export."""

    def test_pin_dropped_by_the_export_is_refused_not_assigned(self):
        real = hp.parse_native_connectivity

        def dropping(path):
            n = real(path)
            for k in ("all_nodes", "nc_nodes", "isolated_nodes"):
                n[k] = [x for x in n[k] if x != "R4.2"]
            for net in n["nets"]:
                net["nodes"] = [x for x in net["nodes"] if x != "R4.2"]
            n["nets"] = [x for x in n["nets"] if x["nodes"]]
            return n
        with unittest.mock.patch.object(hp, "parse_native_connectivity", dropping):
            # declare the dropped pin isolated: it must NOT be silently confirmed
            out = pol.ingest_human_presentation(self.request())
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["error"]["code"], "E_PIN_POPULATION_INCOMPLETE")
        gap = [g for g in out["error"]["details"]["gaps"] if g["kind"] == "pin_missing_from_export"][0]
        self.assertEqual(gap["pins"], ["R4.2"])
        self.assertTrue(out["files"] and out["receipts"])

    def test_control_unpatched_export_reconciles_every_pin(self):
        ns = hp.load_native_set(self.baseline())
        pop = hp.native_pin_population(ns)
        self.assertEqual(sorted(pop["expected"]), sorted(f"R{r}.{p}" for r in (1, 2, 3, 4) for p in (1, 2)))
        out = pol.ingest_human_presentation(self.request())
        self.assertTrue(out["ok"], out)

    def test_unresolvable_symbol_definition_refuses_the_population(self):
        ns = hp.load_native_set(self.baseline())
        pop = hp.native_pin_population(ns)
        pop["unresolved"].append({"path": "x", "ref": "U1", "lib_id": "A:B", "detail": "no readable embedded definition"})
        gaps = hp.reconcile_pin_population(pop, {"all_nodes": list(pop["expected"])})
        self.assertEqual([g["kind"] for g in gaps], ["unresolved_pin_population"])


class R2_6TypedTargets(Base):
    """Ruling (a): component / REF.PIN targets are explicit typed kinds, uniquely resolved."""

    def _call(self, op):
        return pol.ingest_human_presentation(self.request(requested_operations=[op]))

    def test_missing_target_kind_is_refused(self):
        out = self._call({"edit_class": "set_value", "target_id": "R2", "after": "1"})
        self.assertEqual(out["error"]["code"], "E_OPERATION_MALFORMED")

    def test_component_target_resolves_as_a_component(self):
        out = self._call({"edit_class": "set_value", "target_kind": "component", "target_id": "R2", "after": "1"})
        self.assertNotIn("TARGET_NOT_FOUND", {c["type"] for c in out["proposal"]["conflicts"]})

    def test_pin_is_not_a_valid_target_for_set_value(self):
        out = self._call({"edit_class": "set_value", "target_kind": "pin", "target_id": "R2.1", "after": "1"})
        self.assertIn("TARGET_KIND_UNSUPPORTED", {c["type"] for c in out["proposal"]["conflicts"]})

    def test_ref_pin_is_not_a_valid_object_target(self):
        out = self._call({"edit_class": "set_value", "target_kind": "object", "target_id": "R2.1", "after": "1"})
        self.assertIn("TARGET_NOT_FOUND", {c["type"] for c in out["proposal"]["conflicts"]})

    def test_ambiguous_component_reference_is_a_conflict(self):
        ops = [{"edit_class": "set_value", "target_kind": "component", "target_id": "R2", "origin": "caller_request"}]
        got = pol.target_conflicts(ops, set(), set(), {"R2": 2})
        self.assertEqual([c["type"] for c in got], ["TARGET_AMBIGUOUS"])

    def test_unknown_pin_is_not_found(self):
        out = self._call({"edit_class": "add_label", "target_kind": "pin", "target_id": "R9.9", "after": {"text": "X"}})
        self.assertIn("TARGET_NOT_FOUND", {c["type"] for c in out["proposal"]["conflicts"]})


class R3_OutputValidation(Base):
    """Round 3: malformed tool OUTPUT is fed through the real parsers (no mocked exceptions)."""

    NET_OK = ('(export (version "E")\n (components (comp (ref "R1")))\n'
              ' (nets (net (code "1") (name "N1") (node (ref "R1") (pin "1")))))\n')

    def _file(self, name, text):
        p = self.root / name
        p.write_text(text, encoding="utf-8")
        return p

    def _inject(self, tool, text):
        """Run the REAL kicad-cli, then overwrite one tool's output with ``text`` (rc stays 0)."""
        real = hp.subprocess.run

        def fake(argv, *a, **k):
            proc = real(argv, *a, **k)
            if tool in argv and "-o" in argv:
                Path(argv[argv.index("-o") + 1]).write_text(text, encoding="utf-8")
            return proc
        with unittest.mock.patch.object(hp.subprocess, "run", fake):
            return pol.ingest_human_presentation(self.request())

    # --- A. ERC output ---------------------------------------------------------------------
    def test_erc_parser_rejects_each_malformed_shape(self):
        cases = {"invalid_text": "not json {", "list": "[]", "null": "null", "number": "3",
                 "no_sheets": "{}", "sheets_not_list": '{"sheets": {}}',
                 "sheet_not_object": '{"sheets": [1]}',
                 "sheet_without_violations": '{"sheets": [{}]}',
                 "violation_not_object": '{"sheets": [{"violations": [1]}]}',
                 "violation_missing_severity": '{"sheets": [{"violations": [{"type": "x"}]}]}'}
        for label, text in cases.items():
            with self.subTest(label):
                with self.assertRaises(hp.HumanPresentationError) as cm:
                    hp.erc_findings(self._file(f"erc_{label}.json", text))
                self.assertEqual(cm.exception.code, "E_OUTPUT_INVALID")
                self.assertEqual(cm.exception.gaps[0]["tool"], "erc")

    def test_erc_parser_control_valid_shapes(self):
        ok = hp.erc_findings(self._file("ok.json", '{"sheets": [{"violations": [{"severity": "error"}, {"severity": "warning"}]}]}'))
        self.assertEqual(ok["by_severity"], {"error": 1, "warning": 1})
        empty = hp.erc_findings(self._file("empty.json", '{"sheets": [{"violations": []}]}'))
        self.assertEqual(empty["total"], 0)

    def test_malformed_erc_output_makes_derive_partial_and_keeps_the_rc0_receipt(self):
        for label, text in (("invalid_json", "not json {"), ("list", "[]"), ("null", "null"),
                            ("violation_no_severity", '{"sheets": [{"violations": [{}]}]}')):
            with self.subTest(label):
                if self.out.exists():
                    shutil.rmtree(self.out)
                out = self._inject("erc", text)
                self.assertFalse(out["ok"], out)
                self.assertEqual(out["derive_status"], "partial")
                self.assertEqual(out["error"]["code"], "E_DERIVE_PARTIAL")
                self.assertEqual(out["failed_sidecars"], ["erc"])
                self.assertIn("erc", out["output_validation_failures"])
                erc = out["receipts"]["erc"]
                self.assertEqual((erc["returncode"], erc["status"]), (0, "succeeded"),
                                 "execution receipt is preserved: the run succeeded, the evidence did not")
                self.assertTrue(any(f.endswith("erc/erc.json") for f in out["files"]))
                self.assertIn("unusable", out["erc_findings"])
                self.assertNotIn("total", out["erc_findings"], "never reported as zero findings")

    def test_control_real_erc_violations_stay_findings_and_ok(self):
        out = pol.ingest_human_presentation(self.request())
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output_validation_failures"], {})
        self.assertGreater(out["erc_findings"]["total"], 0)

    # --- B. netlist parser -----------------------------------------------------------------
    def test_netlist_parser_rejects_each_malformed_shape(self):
        cases = {
            "unbalanced": "(export (nets",
            "empty": "",
            "wrong_root": "(foo)",
            "no_sections": "(export (version \"E\"))",
            "no_components": '(export (nets (net (name "N"))))',
            "net_without_name": '(export (components) (nets (net (code "1"))))',
            "node_missing_ref": '(export (components) (nets (net (name "N") (node (pin "1")))))',
            "node_missing_pin": '(export (components) (nets (net (name "N") (node (ref "R1")))))',
            "node_empty_atoms": '(export (components) (nets (net (name "N") (node (ref) (pin)))))',
            "comp_missing_ref": '(export (components (comp (value "1k"))) (nets))',
            "comp_empty_ref": '(export (components (comp (ref))) (nets))',
        }
        for label, text in cases.items():
            with self.subTest(label):
                with self.assertRaises(hp.HumanPresentationError) as cm:
                    hp.parse_native_connectivity(self._file(f"net_{label}.net", text))
                self.assertEqual(cm.exception.code, "E_OUTPUT_INVALID")
                self.assertEqual(cm.exception.gaps[0]["tool"], "netlist")

    def test_netlist_parser_control_valid_shape(self):
        got = hp.parse_native_connectivity(self._file("ok.net", self.NET_OK))
        self.assertEqual(got["all_nodes"], ["R1.1"])
        self.assertEqual(got["components"], ["R1"])

    def test_malformed_netlist_is_a_typed_refusal_with_files_and_receipts(self):
        for label, text in (("missing_ref", '(export (components) (nets (net (name "N") (node (pin "1")))))'),
                            ("missing_pin", '(export (components) (nets (net (name "N") (node (ref "R1")))))'),
                            ("empty_atoms", '(export (components) (nets (net (name "N") (node (ref) (pin)))))')):
            with self.subTest(label):
                if self.out.exists():
                    shutil.rmtree(self.out)
                out = self._inject("netlist", text)
                self.assertFalse(out["ok"], out)
                self.assertEqual(out["error"]["code"], "E_OUTPUT_INVALID")
                self.assertEqual(out["error"]["details"]["gaps"][0]["tool"], "netlist")
                self.assertTrue(out["files"], "failure after retention must not report files=[]")
                self.assertEqual(out["receipts"]["netlist"]["returncode"], 0)
                self.assertEqual(self.src_hashes(), {f: sha(_FIXTURE / f) for f in FILES})


if __name__ == "__main__":
    unittest.main()
