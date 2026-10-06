"""Phase 3: root + N leaf emission, arbitrated by the real kicad-cli.

WHAT EACH GROUP ANSWERS
-----------------------
RouteSelectionTests   DD-10: declaration decides the route, not the sheet count.
                      The load-bearing cell is the explicit N=1 one -- it must produce
                      root+1 leaf, NOT the flat legacy file.
KiCadArbitrationTests root+1 and root+2 through `kicad-cli sch export netlist`, with
                      the same-name / different-name control pair. Skips (never passes)
                      when kicad-cli is absent: an unavailable arbiter is
                      `indeterminate` per errors.md, and recording that as a pass is
                      the absence/failure collapse this package forbids.
CleanupTests          DD-12c: a failed emit removes ONLY what it created. The
                      pre-existing file is the cell that matters.
NetSplitTests         no endpoint is silently discarded when nets are split per leaf.

Scratch is bound to $XDG_RUNTIME_DIR (repo AGENTS.md §3); TMPDIR is never consulted.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.hierarchical import (
    EMIT_MODE_HIERARCHICAL,
    EMIT_MODE_LEGACY,
    HierarchicalEmitError,
    assert_no_endpoint_lost,
    emit_from_spec,
    nets_by_sheet,
)
from bodesign_eda_bridge.kicad_emit import EmitComponent, EmitNet
from bodesign_eda_bridge.partition import partition_components

_SCRATCH_SLUG = "bodesign-multisheet-phase3"

#: The stock KiCad library, which is where `Device:R` lives. `vendor_symbols/` holds
#: only `ST_vendor.kicad_sym`, so pointing there yields zero embedded symbols and an
#: empty `(components)` block in the netlist -- with the emitter behaving correctly.
_SYMBOL_DIR = Path(
    os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))


def _scratch_root() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        raise RuntimeError(
            "XDG_RUNTIME_DIR is unset; this test refuses to fall back to TMPDIR or "
            "/tmp (repo AGENTS.md §3 scratch placement rule)")
    root = Path(runtime_dir)
    if not root.is_dir():
        raise RuntimeError(f"XDG_RUNTIME_DIR={runtime_dir!r} is not a directory")
    scratch = root / _SCRATCH_SLUG
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(scratch, 0o700)
    return scratch


def _spec_comp(ref, sheet=None, group=None):
    out = {"ref": ref, "symbol": "Device:R"}
    if sheet is not None:
        out["sheet"] = sheet
    if group is not None:
        out["group"] = group
    return out


def _placed(ref, pos_x, pos_y):
    return EmitComponent(ref=ref, lib_id="Device:R", value="10k",
                         footprint="", x=pos_x, y=pos_y)


class RouteSelectionTests(unittest.TestCase):
    """DD-10: the trigger is DECLARATION, not count."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(
            prefix="route_", dir=str(_scratch_root()))
        os.chmod(self.scratch.name, 0o700)
        self.out_dir = Path(self.scratch.name)
        self.addCleanup(self.scratch.cleanup)

    def _emit(self, spec_components, placed, nets):
        return emit_from_spec(
            self.out_dir, "proj", spec_components, placed, nets,
            symbol_dir=_SYMBOL_DIR)

    def test_legacy_route_is_byte_identical_to_calling_the_flat_emitter(self):
        """DD-6: routing through the partition must not perturb legacy output.

        UUIDs are regenerated per call, so they are masked before comparison. The
        control below is what stops that mask from making everything look equal:
        the DECLARED route's root must still differ.
        """
        from bodesign_eda_bridge.kicad_emit import emit_kicad_schematic

        comps = [_placed("R1", 50, 50), _placed("R2", 80, 50)]
        nets = [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])]
        uuid_re = re.compile(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

        flat = emit_kicad_schematic(
            self.out_dir / "flat", "proj", comps, nets, symbol_dir=_SYMBOL_DIR)
        through_partition = emit_from_spec(
            self.out_dir / "viaspec", "proj",
            [_spec_comp("R1"), _spec_comp("R2")], comps, nets,
            symbol_dir=_SYMBOL_DIR)

        flat_text = uuid_re.sub("UUID", Path(flat.schematic_path).read_text())
        legacy_text = uuid_re.sub(
            "UUID", Path(through_partition.schematic_path).read_text())
        self.assertEqual(flat_text, legacy_text)

        declared = emit_from_spec(
            self.out_dir / "decl", "proj",
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="power")],
            comps, nets, symbol_dir=_SYMBOL_DIR)
        declared_text = uuid_re.sub(
            "UUID", Path(declared.schematic_path).read_text())
        self.assertNotEqual(flat_text, declared_text,
                            "the uuid mask erased the difference it should keep")

    def test_no_sheet_anywhere_takes_the_flat_legacy_route(self):
        result = self._emit(
            [_spec_comp("R1"), _spec_comp("R2")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        self.assertEqual(result.emit_mode, EMIT_MODE_LEGACY)
        self.assertEqual(result.leaf_paths, {})
        self.assertTrue(result.schematic_path.endswith("proj.kicad_sch"))

    def test_one_explicitly_declared_sheet_produces_root_plus_one_leaf(self):
        """THE DD-10 cell. Round 2 left this open; the coordinator ruled that an
        explicit single sheet is NOT the legacy path. If the engine collapsed it,
        the caller's explicit request would be indistinguishable from silence.
        """
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="power")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        self.assertEqual(result.emit_mode, EMIT_MODE_HIERARCHICAL)
        self.assertEqual(list(result.leaf_paths), ["power"])
        self.assertTrue(result.schematic_path.endswith("proj.kicad_sch"))
        self.assertTrue(Path(self.out_dir / "power.kicad_sch").exists())

    def test_two_declared_sheets_produce_root_plus_two_leaves(self):
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        self.assertEqual(sorted(result.leaf_paths), ["io", "power"])
        self.assertEqual(len(result.files), 4)  # root + 2 leaves + project

    def test_schematic_path_is_the_root_on_the_declared_route(self):
        """The 29 existing single-path call sites (K10 class C) read this field; it
        must keep meaning 'the schematic you open', which the root satisfies."""
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        self.assertEqual(result.schematic_path, str(self.out_dir / "proj.kicad_sch"))
        self.assertNotIn(result.schematic_path, result.leaf_paths.values())

    def test_files_lists_only_paths_that_exist_on_disk(self):
        """repo commandment §2.2: no phantom entries."""
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        for path in result.files:
            self.assertTrue(Path(path).exists(), f"phantom entry: {path}")

    def test_only_the_root_owns_a_project_file(self):
        """A leaf emitted through the flat emitter also writes <name>.kicad_pro; in
        a hierarchy that stray file must not survive."""
        self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        self.assertTrue((self.out_dir / "proj.kicad_pro").exists())
        self.assertFalse((self.out_dir / "power.kicad_pro").exists())
        self.assertFalse((self.out_dir / "io.kicad_pro").exists())

    def test_emitting_from_a_map_with_no_collision_check_is_refused(self):
        """A SheetMap built without project_name never ran the leaf-vs-root check,
        so emitting from it could write a leaf over the root."""
        from bodesign_eda_bridge.hierarchical import emit_hierarchical_schematic
        unchecked = partition_components(
            {"components": [_spec_comp("R1", sheet="power")]})
        self.assertFalse(unchecked.collision_checked)
        with self.assertRaises(HierarchicalEmitError) as ctx:
            emit_hierarchical_schematic(
                self.out_dir, "proj", [_placed("R1", 50, 50)], [], unchecked,
                symbol_dir=_SYMBOL_DIR)
        self.assertEqual(ctx.exception.code, "E_COLLISION_CHECK_NOT_RUN")


class CleanupTests(unittest.TestCase):
    """DD-12c: cleanup removes ONLY what this call created."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(
            prefix="cleanup_", dir=str(_scratch_root()))
        os.chmod(self.scratch.name, 0o700)
        self.out_dir = Path(self.scratch.name)
        self.addCleanup(self.scratch.cleanup)

    def test_a_preexisting_output_path_is_refused_not_overwritten(self):
        preexisting = self.out_dir / "power.kicad_sch"
        preexisting.write_text("USER DATA -- must survive\n")
        with self.assertRaises(HierarchicalEmitError) as ctx:
            emit_from_spec(
                self.out_dir, "proj",
                [_spec_comp("R1", sheet="power")], [_placed("R1", 50, 50)], [],
                symbol_dir=_SYMBOL_DIR)
        self.assertEqual(ctx.exception.code, "E_OUTPUT_PATH_OCCUPIED")
        self.assertEqual(preexisting.read_text(), "USER DATA -- must survive\n")

    def test_partial_write_failure_removes_only_created_paths(self):
        """A pre-existing UNRELATED file in the same directory must survive a
        failed emit, and the leaf already written must be rolled back.

        Pattern-based cleanup (`*.kicad_sch` in out_dir) would delete the bystander
        too, which is why the ledger tracks individual paths.

        THE FAILURE MUST STRIKE THE SECOND LEAF, and that is the whole design of
        this fixture. `nc=["R1.2"]` resolves on the `power` leaf (R1 lives there) and
        does NOT resolve on the `mcu` leaf, so leaf 1 is already on disk when leaf 2
        raises -- which is the only state in which a rollback has anything to undo.
        An `nc` that fails on the FIRST leaf leaves the ledger empty, and then a
        no-op rollback and a correct rollback are indistinguishable (measured: two
        mutants, one disabling the rollback and one making it delete by pattern,
        both stayed green against such a fixture).

        `nc` was chosen as the failure channel by measurement, not by guess: a
        missing SYMBOL for a 2-pin passive legitimately degrades to a placeholder
        box and raises nothing, so it could not induce a mid-emit failure at all.
        """
        bystander = self.out_dir / "notes.kicad_sch"
        bystander.write_text("unrelated user file\n")
        with self.assertRaises(HierarchicalEmitError) as ctx:
            emit_from_spec(
                self.out_dir, "proj",
                [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="mcu")],
                [_placed("R1", 50, 50), _placed("R2", 80, 50)],
                [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])],
                symbol_dir=_SYMBOL_DIR, nc=["R1.2"])
        self.assertEqual(ctx.exception.code, "E_LEAF_WRITE_FAILED")
        self.assertTrue(bystander.exists(), "an unrelated file was destroyed")
        self.assertEqual(bystander.read_text(), "unrelated user file\n")

    def test_rollback_removed_the_leaf_that_had_already_been_written(self):
        """Control for the cell above: the bystander survives whether the rollback
        works or does nothing at all, so that cell alone cannot show the rollback
        is real. This one asserts the already-written leaf is gone AND that the
        rollback reported removing it.
        """
        with self.assertRaises(HierarchicalEmitError) as ctx:
            emit_from_spec(
                self.out_dir, "proj",
                [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="mcu")],
                [_placed("R1", 50, 50), _placed("R2", 80, 50)],
                [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])],
                symbol_dir=_SYMBOL_DIR, nc=["R1.2"])
        removed = ctx.exception.details["removed"]
        self.assertEqual(len(removed), 1,
                         f"expected the written leaf to be rolled back; removed={removed}")
        self.assertTrue(removed[0].endswith("power.kicad_sch"), removed)
        leftovers = sorted(p.name for p in self.out_dir.iterdir())
        self.assertEqual(leftovers, [], f"partial file set left behind: {leftovers}")

    def test_rollback_leaves_an_unrelated_schematic_in_the_same_directory_alone(self):
        """The pattern-deletion cell. A rollback implemented as `out_dir.glob(
        '*.kicad_sch')` would remove BOTH the leaf it wrote and this bystander;
        the ledger removes only the former.
        """
        bystander = self.out_dir / "someone_elses.kicad_sch"
        bystander.write_text("peer work\n")
        with self.assertRaises(HierarchicalEmitError) as ctx:
            emit_from_spec(
                self.out_dir, "proj",
                [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="mcu")],
                [_placed("R1", 50, 50), _placed("R2", 80, 50)],
                [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])],
                symbol_dir=_SYMBOL_DIR, nc=["R1.2"])
        removed = ctx.exception.details["removed"]
        self.assertNotIn(str(bystander), removed,
                         "cleanup reported removing a file it did not create")
        self.assertTrue(bystander.exists(), "a peer's file was destroyed")
        self.assertEqual(bystander.read_text(), "peer work\n")

    def test_successful_emit_records_every_created_path(self):
        """Positive control for the ledger: if `created_paths` were empty on
        success, the cleanup cells above would prove nothing -- an empty ledger
        also removes nothing."""
        result = emit_from_spec(
            self.out_dir, "proj",
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)], [],
            symbol_dir=_SYMBOL_DIR)
        self.assertEqual(len(result.created_paths), 4)
        for path in result.created_paths:
            self.assertTrue(Path(path).exists())


class NetSplitTests(unittest.TestCase):
    """Endpoints are partitioned, never discarded."""

    def test_a_net_spanning_two_sheets_is_reported_as_cross_sheet(self):
        nets = [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])]
        per_sheet, cross, orphans = nets_by_sheet(
            nets, {"R1": "power", "R2": "io"})
        self.assertEqual(cross, ["NET_X"])
        self.assertEqual(sorted(per_sheet), ["io", "power"])
        self.assertEqual(orphans, [])

    def test_a_net_within_one_sheet_is_not_cross_sheet(self):
        """Control: without it, a function that called everything cross-sheet would
        pass the cell above."""
        nets = [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])]
        per_sheet, cross, orphans = nets_by_sheet(
            nets, {"R1": "power", "R2": "power"})
        self.assertEqual(cross, [])
        self.assertEqual(list(per_sheet), ["power"])

    def test_an_unplaceable_node_is_reported_as_an_orphan_not_dropped(self):
        nets = [EmitNet(name="NET_X", nodes=[("R1", "1"), ("GHOST", "1")])]
        per_sheet, _cross, orphans = nets_by_sheet(nets, {"R1": "power"})
        self.assertEqual(orphans, ["NET_X:GHOST.1"])
        assert_no_endpoint_lost(nets, per_sheet, orphans)

    def test_endpoint_accounting_goes_red_when_a_node_vanishes(self):
        """Positive control for the accounting assertion: it must be able to fire,
        otherwise the cells above only prove it never runs."""
        nets = [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])]
        truncated = {"power": [EmitNet(name="NET_X", nodes=[("R1", "1")])]}
        with self.assertRaises(HierarchicalEmitError) as ctx:
            assert_no_endpoint_lost(nets, truncated, [])
        self.assertEqual(ctx.exception.code, "E_ENDPOINT_LOST")


@unittest.skipUnless(shutil.which("kicad-cli"),
                     "kicad-cli not on host (arbitration indeterminate)")
class KiCadArbitrationTests(unittest.TestCase):
    """The real arbiter opens the emitted root and reaches every leaf."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(
            prefix="arb_", dir=str(_scratch_root()))
        os.chmod(self.scratch.name, 0o700)
        self.out_dir = Path(self.scratch.name)
        self.addCleanup(self.scratch.cleanup)

    def _export(self, root_path: Path) -> str:
        out_path = self.out_dir / "net.net"
        proc = subprocess.run(
            ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
             "-o", str(out_path), str(root_path)],
            capture_output=True, text=True, timeout=180)
        self.assertEqual(proc.returncode, 0,
                         f"kicad-cli rc={proc.returncode} stderr={proc.stderr!r}")
        self.assertTrue(out_path.exists(),
                        f"rc=0 but no netlist written; stderr={proc.stderr!r}")
        return out_path.read_text()

    @staticmethod
    def _ref_to_nets(netlist_text: str) -> dict[str, set[str]]:
        net_re = re.compile(
            r'\(net\s+\(code\s+"?\d+"?\)\s*\(name\s+"([^"]*)"\)(.*?)'
            r'(?=\n\s*\(net\s|\Z)', re.S)
        node_re = re.compile(r'\(node\s+\(ref\s+"([^"]+)"\)')
        out: dict[str, set[str]] = {}
        for name, body in net_re.findall(netlist_text):
            for ref in node_re.findall(body):
                out.setdefault(ref, set()).add(name)
        return out

    def _emit(self, spec_components, placed, nets):
        return emit_from_spec(
            self.out_dir, "proj", spec_components, placed, nets,
            symbol_dir=_SYMBOL_DIR)

    def _emit_wire(self, spec_components, placed, nets):
        """Drawn-wire style. Required by the cross-sheet cells: under the default
        label style every net is already a global label, so forcing is unobservable.
        """
        return emit_from_spec(
            self.out_dir, "proj", spec_components, placed, nets,
            symbol_dir=_SYMBOL_DIR, connection_style="wire")

    def test_root_plus_one_leaf_opens_and_covers_its_components(self):
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="power")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        text = self._export(Path(result.schematic_path))
        refs = self._ref_to_nets(text)
        self.assertIn("R1", refs)
        self.assertIn("R2", refs)
        self.assertIn('(sheetpath (names "/power/")', text)

    def test_root_plus_two_leaves_same_net_name_merges_across_files(self):
        """TREATMENT. Both leaves carry NET_X; the two ends must land on one net."""
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        text = self._export(Path(result.schematic_path))
        refs = self._ref_to_nets(text)
        self.assertIn("R1", refs, f"refs={sorted(refs)}")
        self.assertIn("R2", refs, f"refs={sorted(refs)}")
        shared = refs["R1"] & refs["R2"]
        self.assertIn("NET_X", shared,
                      f"R1={sorted(refs['R1'])} R2={sorted(refs['R2'])}")

    def test_root_plus_two_leaves_different_net_names_stay_separate(self):
        """CONTROL. Without it, the treatment cannot be told apart from an exporter
        that merges everything it reads."""
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_A", nodes=[("R1", "1")]),
             EmitNet(name="NET_B", nodes=[("R2", "1")])])
        text = self._export(Path(result.schematic_path))
        refs = self._ref_to_nets(text)
        self.assertIn("R1", refs)
        self.assertIn("R2", refs)
        self.assertEqual(refs["R1"] & refs["R2"], set(),
                         f"R1={sorted(refs['R1'])} R2={sorted(refs['R2'])}")

    def test_leaf_symbol_instances_resolve_under_the_root(self):
        """The re-anchor cell, and its criterion was chosen by MEASUREMENT.

        `emit_kicad_schematic` writes each leaf believing it is a standalone root,
        so its symbol instance paths read `/self_uuid`. In a hierarchy they must
        read `/root_uuid/sheet_uuid`, or KiCad cannot bind the placed symbol to the
        sheet instance.

        A first attempt asserted only that R1/R2 appear -- and they appear EITHER
        WAY, so that assertion had no discriminating power (a mutant disabling the
        re-anchor stayed green). Measured difference: without the re-anchor the
        netlist loses the `unconnected-(Rn-Pad2)` nets entirely, because the
        unbound pins never enter connectivity analysis. That is what is asserted.
        """
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        for name, path in result.leaf_paths.items():
            text = Path(path).read_text()
            self.assertIn('(path "/', text)
            self.assertNotIn('(path "/" (reference', text, f"{name} unanchored")

        netlist = self._export(Path(result.schematic_path))
        net_names = set(re.findall(
            r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)', netlist))
        self.assertIn("unconnected-(R1-Pad2)", net_names,
                      f"pin 2 never entered connectivity analysis; nets={sorted(net_names)}")
        self.assertIn("unconnected-(R2-Pad2)", net_names,
                      f"pin 2 never entered connectivity analysis; nets={sorted(net_names)}")

    #: The cross-sheet fixture, and its SHAPE is load-bearing.
    #:
    #: `CROSS` must leave TWO nodes on the `power` leaf. A slice with only ONE node
    #: already falls back to a global label on its own (single-pin nets always do),
    #: so forcing would be unobservable there and a mutant deleting it stays green.
    #: Measured on the 2-node slice: forcing ON -> global_label present, 0 wires;
    #: forcing OFF -> no global label, 3 drawn wires, 1 local label.
    _CROSS_SPEC = [
        _spec_comp("R1", sheet="power"),
        _spec_comp("R3", sheet="power"),
        _spec_comp("R2", sheet="io"),
    ]
    _CROSS_PLACED = [_placed("R1", 50, 50), _placed("R3", 50, 90),
                     _placed("R2", 80, 50)]
    _CROSS_NETS = [
        EmitNet(name="CROSS", nodes=[("R1", "1"), ("R3", "1"), ("R2", "1")]),
        EmitNet(name="LOCAL", nodes=[("R1", "2"), ("R3", "2")]),
    ]

    def test_a_cross_sheet_net_is_emitted_as_a_global_label_on_every_leaf(self):
        """A net spanning two files cannot be a drawn wire, so it must be forced
        onto label connectivity on each leaf it touches.

        `connection_style="wire"` is required to reach this: under the default
        `"label"` style every net is already a global label, so the forcing is a
        no-op and a mutant removing it stays green (measured).
        """
        result = self._emit_wire(self._CROSS_SPEC, self._CROSS_PLACED,
                                 self._CROSS_NETS)
        self.assertEqual(result.cross_sheet_nets, ["CROSS"])
        for name in ("power", "io"):
            text = Path(result.leaf_paths[name]).read_text()
            self.assertIn('(global_label "CROSS"', text,
                          f"{name} carries no global label for the cross-sheet net")
        power = Path(result.leaf_paths["power"]).read_text()
        self.assertNotIn('(label "CROSS"', power,
                         "a cross-sheet net was drawn as a LOCAL label, which does "
                         "not cross a file boundary")

        netlist = self._export(Path(result.schematic_path))
        refs = self._ref_to_nets(netlist)
        self.assertIn("CROSS", refs.get("R1", set()) & refs.get("R2", set()),
                      f"R1={sorted(refs.get('R1', ()))} R2={sorted(refs.get('R2', ()))}")

    def test_a_within_sheet_net_is_not_forced_onto_a_global_label(self):
        """Control for the cell above: without it, an implementation that forced
        EVERY net onto a global label would pass, and drawn wires would silently
        disappear from every leaf. `LOCAL` lives entirely on `power`, so it must
        stay a drawn wire.
        """
        result = self._emit_wire(self._CROSS_SPEC, self._CROSS_PLACED,
                                 self._CROSS_NETS)
        self.assertNotIn("LOCAL", result.cross_sheet_nets)
        power = Path(result.leaf_paths["power"]).read_text()
        self.assertNotIn('(global_label "LOCAL"', power,
                         "a single-sheet net was needlessly forced onto a label")
        self.assertIn("(wire ", power,
                      "the wire style drew nothing at all on this leaf")

    def test_both_leaf_files_were_traversed(self):
        result = self._emit(
            [_spec_comp("R1", sheet="power"), _spec_comp("R2", sheet="io")],
            [_placed("R1", 50, 50), _placed("R2", 80, 50)],
            [EmitNet(name="NET_X", nodes=[("R1", "1"), ("R2", "1")])])
        text = self._export(Path(result.schematic_path))
        self.assertIn('(sheetpath (names "/power/")', text)
        self.assertIn('(sheetpath (names "/io/")', text)


if __name__ == "__main__":
    unittest.main()
