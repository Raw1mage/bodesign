"""DD-13 clause 4c: replica input contract and display fidelity (tasks 4c.2/4c.5/4c.6).

WHAT EACH GROUP ANSWERS
-----------------------
ReplicaInputContractTests  the seven input-side codes, each with a paired positive
                           cell so a code that fired for the wrong reason is visible.
ReplicaInvariantTests      I-1 and I-2 must fail INDEPENDENTLY, in both directions.
DisplayFidelityTests       AC-12/AC-13. The load-bearing pair is TV-20 (a replica
                           miswired, which MUST fail while the canonical netlist and
                           BOM stay unchanged) and TV-21 (the same fixture wired
                           correctly, which MUST pass). Without TV-21 a check that
                           raised unconditionally would also pass TV-20.

Scratch is bound to $XDG_RUNTIME_DIR (repo AGENTS.md §3); TMPDIR is never consulted.
"""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import replica_fidelity as rfid
from bodesign_eda_bridge.hierarchical import (
    _REPLICA_FLAGS,
    HierarchicalEmitError,
    emit_multisheet,
    replica_nodes_for_view,
)
from bodesign_eda_bridge.kicad_emit import EmitNet
from bodesign_eda_bridge.partition import (
    PartitionError,
    ReplicaView,
    SheetMap,
    assert_partition_identity,
    assert_replica_wellformed,
    partition_components,
)

_SCRATCH_SLUG = "bodesign-replica-fidelity"
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


def _base_spec(replicas=None, nets=None):
    """U1 home on `power`, R1 home on `mcu`, joined by NET_X and NET_Y."""
    u1 = {"ref": "U1", "symbol": "Device:R", "sheet": "power"}
    if replicas is not None:
        u1["replicas"] = replicas
    return {
        "components": [u1, {"ref": "R1", "symbol": "Device:R", "sheet": "mcu"}],
        "nets": nets if nets is not None else [
            {"name": "NET_X", "nodes": ["U1.1", "R1.1"]},
            {"name": "NET_Y", "nodes": ["U1.2", "R1.2"]},
        ],
    }


class ReplicaInputContractTests(unittest.TestCase):
    """The seven input-side codes. Each negative cell names the condition it hit."""

    def test_absent_replicas_key_is_todays_behaviour_exactly(self):
        """POSITIVE CONTROL for the whole group: no `replicas` must stay clean.

        Without this, every negative cell below would also pass if the parser
        rejected all specs unconditionally.
        """
        result = partition_components(_base_spec(), project_name="board")
        self.assertEqual(result.replica_map, {})
        self.assertEqual(result.component_count, 2)
        self.assertEqual(result.drawn_instance_count, 2)

    def test_valid_replica_view_is_accepted(self):
        result = partition_components(
            _base_spec([{"sheet": "mcu", "nets": ["NET_X"]}]), project_name="board")
        self.assertEqual(list(result.replica_map), ["U1"])
        self.assertEqual(result.replica_map["U1"][0].nets, ("NET_X",))
        self.assertEqual(result.drawn_instance_count, 3)
        self.assertEqual(result.component_count, 2)

    def test_bare_string_entry_is_refused_not_read_as_all_nets(self):
        with self.assertRaises(PartitionError) as caught:
            partition_components(_base_spec(["mcu"]), project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_VIEW_MALFORMED")

    def test_empty_net_list_is_its_own_code(self):
        with self.assertRaises(PartitionError) as caught:
            partition_components(
                _base_spec([{"sheet": "mcu", "nets": []}]), project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_VIEW_EMPTY")

    def test_net_not_assigned_to_this_ref_is_refused(self):
        """NET_Z exists on no pin of U1, so drawing it would invent connectivity."""
        with self.assertRaises(PartitionError) as caught:
            partition_components(
                _base_spec([{"sheet": "mcu", "nets": ["NET_Z"]}]),
                project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_NET_NOT_CANONICAL")

    def test_net_belonging_to_another_ref_only_is_refused(self):
        """Sharper than the previous cell: NET_R exists, but not on U1."""
        spec = _base_spec(
            [{"sheet": "mcu", "nets": ["NET_R"]}],
            nets=[{"name": "NET_X", "nodes": ["U1.1", "R1.1"]},
                  {"name": "NET_R", "nodes": ["R1.2"]}])
        with self.assertRaises(PartitionError) as caught:
            partition_components(spec, project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_NET_NOT_CANONICAL")
        self.assertEqual(caught.exception.details["stray_nets"], ["NET_R"])

    def test_unknown_sheet_is_refused(self):
        with self.assertRaises(PartitionError) as caught:
            partition_components(
                _base_spec([{"sheet": "nosuch", "nets": ["NET_X"]}]),
                project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_UNKNOWN_SHEET")

    def test_replica_on_own_home_sheet_is_refused(self):
        with self.assertRaises(PartitionError) as caught:
            partition_components(
                _base_spec([{"sheet": "power", "nets": ["NET_X"]}]),
                project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_ON_HOME_SHEET")

    def test_same_sheet_twice_is_refused(self):
        with self.assertRaises(PartitionError) as caught:
            partition_components(
                _base_spec([{"sheet": "mcu", "nets": ["NET_X"]},
                            {"sheet": "mcu", "nets": ["NET_Y"]}]),
                project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_DUPLICATE")

    def test_replicas_on_legacy_route_is_refused(self):
        """No component declares `sheet`, so there is no home to be neutral against."""
        spec = {
            "components": [
                {"ref": "U1", "symbol": "Device:R",
                 "replicas": [{"sheet": "mcu", "nets": ["NET_X"]}]},
                {"ref": "R1", "symbol": "Device:R"},
            ],
            "nets": [{"name": "NET_X", "nodes": ["U1.1", "R1.1"]}],
        }
        with self.assertRaises(PartitionError) as caught:
            partition_components(spec, project_name="board")
        self.assertEqual(caught.exception.code, "E_REPLICA_WITHOUT_HOME")

    def test_legacy_route_without_replicas_still_works(self):
        """CONTROL for the previous cell: the legacy route itself is not broken."""
        spec = {"components": [{"ref": "U1", "symbol": "Device:R"},
                               {"ref": "R1", "symbol": "Device:R"}]}
        result = partition_components(spec, project_name="board")
        self.assertFalse(result.is_multi_sheet)
        self.assertEqual(result.replica_map, {})

    def test_canonical_net_check_records_when_it_did_not_run(self):
        """A spec with no `nets`: absence of a violation must not read as a pass."""
        spec = {"components": [
            {"ref": "U1", "symbol": "Device:R", "sheet": "power",
             "replicas": [{"sheet": "mcu", "nets": ["ANYTHING"]}]},
            {"ref": "R1", "symbol": "Device:R", "sheet": "mcu"},
        ]}
        result = partition_components(spec, project_name="board")
        self.assertFalse(result.replica_nets_checked)
        checked = partition_components(
            _base_spec([{"sheet": "mcu", "nets": ["NET_X"]}]), project_name="board")
        self.assertTrue(checked.replica_nets_checked)


class ReplicaInvariantTests(unittest.TestCase):
    """AC-10 / TV-24: I-1 and I-2 fail independently, in both directions."""

    def test_i1_fails_while_i2_passes(self):
        """A corrupt HOME partition with a well-formed replica list."""
        broken = SheetMap(
            sheets={"power": ["U1", "U1"], "mcu": ["R1"]},
            partition_source="declared",
            replica_map={"U1": [ReplicaView(sheet="mcu", nets=("NET_X",))]},
        )
        with self.assertRaises(PartitionError) as caught:
            assert_partition_identity(broken, 2)
        self.assertEqual(caught.exception.code, "E_PARTITION_IDENTITY_BROKEN")
        assert_replica_wellformed(broken)  # I-2 is unaffected

    def test_i2_fails_while_i1_passes(self):
        """A clean HOME partition with a malformed replica list."""
        broken = SheetMap(
            sheets={"power": ["U1"], "mcu": ["R1"]},
            partition_source="declared",
            replica_map={"U9": [ReplicaView(sheet="mcu", nets=("NET_X",))]},
        )
        assert_partition_identity(broken, 2)  # I-1 is unaffected
        with self.assertRaises(PartitionError) as caught:
            assert_replica_wellformed(broken)
        self.assertEqual(caught.exception.code, "E_REPLICA_UNKNOWN_REF")

    def test_i2_is_vacuous_on_an_empty_replica_map(self):
        """Named so nobody cites this cell as evidence I-2 works.

        It passes for a spec with NO replicas, which is every spec that exists
        today; only the two cells above carry evidence.
        """
        clean = SheetMap(sheets={"power": ["U1"]}, partition_source="declared")
        assert_replica_wellformed(clean)
        self.assertEqual(clean.replica_map, {})


class ReplicaNetFragmentTests(unittest.TestCase):
    """`replica_nodes_for_view` refuses to produce an empty fragment."""

    def test_fragment_carries_only_this_refs_pins(self):
        nets = [EmitNet(name="NET_X", nodes=[("U1", "1"), ("R1", "1")])]
        view = ReplicaView(sheet="mcu", nets=("NET_X",))
        fragments = replica_nodes_for_view("U1", view, nets)
        self.assertEqual(len(fragments), 1)
        self.assertEqual(fragments[0].nodes, [("U1", "1")])

    def test_net_with_no_pin_of_this_ref_raises_rather_than_drawing_nothing(self):
        nets = [EmitNet(name="NET_R", nodes=[("R1", "1")])]
        view = ReplicaView(sheet="mcu", nets=("NET_R",))
        with self.assertRaises(HierarchicalEmitError) as caught:
            replica_nodes_for_view("U1", view, nets)
        self.assertEqual(caught.exception.code, "E_REPLICA_NET_NOT_CANONICAL")
        self.assertTrue(caught.exception.details["net_exists"])


_KICAD_CLI = shutil.which("kicad-cli")


def _electrical_content(netlist_text: str) -> tuple:
    """The part of a netlist that carries meaning: comps and per-net node sets.

    Deliberately NOT the raw bytes. MEASURED 2026-09-08: miswiring a replica label
    shifts KiCad's arbitrary `(code "N")` integers and the embedded source path, so
    a byte comparison reports a difference that says nothing about connectivity. A
    cell asserting byte equality would fail for a reason unrelated to its claim.
    """
    comps = tuple(sorted(re.findall(r'\(comp \(ref "([^"]+)"\)', netlist_text)))
    nets = []
    for block in re.finditer(
            r'\(net \(code "[^"]*"\) \(name "([^"]*)"\)(.*?)(?=\n    \(net |\Z)',
            netlist_text, re.S):
        nodes = tuple(sorted(re.findall(
            r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', block.group(2))))
        nets.append((block.group(1), nodes))
    return comps, tuple(sorted(nets))


@unittest.skipIf(_KICAD_CLI is None, "kicad-cli absent: the canonical map cannot be "
                                     "exported, so this is indeterminate, not a pass")
class DisplayFidelityTests(unittest.TestCase):
    """AC-12 / AC-13. TV-20 must FAIL, TV-21 must PASS, TV-22 isolates F-3.

    Every cell reads the DRAWN map from the landed leaf bytes. None of them consults
    an emitter's intended-connection list, because that list is exactly what a
    defective emitter would be wrong about.
    """

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(
            prefix="fid_", dir=str(_scratch_root()))
        os.chmod(self.scratch.name, 0o700)
        self.root = Path(self.scratch.name)
        self.addCleanup(self.scratch.cleanup)

    def _emit(self, name, replicas):
        out = self.root / name
        spec = _base_spec(replicas)
        result = emit_multisheet(
            out, "board", spec, power_ports=False, symbol_dir=_SYMBOL_DIR)
        sheet_map = partition_components(spec, project_name="board")
        return out, result, sheet_map

    def _canonical(self, out_dir):
        netlist = out_dir / "canonical.net"
        rc, output = rfid.export_netlist(out_dir / "board.kicad_sch", netlist)
        self.assertEqual(rc, 0, f"kicad-cli export failed: {output}")
        return rfid.canonical_pin_net_map(netlist), netlist.read_text()

    def _miswire(self, leaf: Path, replica_x: str):
        """Rewrite ONLY the replica's own label; the canonical symbol is untouched."""
        text = leaf.read_text()
        mutated = text.replace(
            f'(global_label "NET_X" (shape bidirectional) (at {replica_x}',
            f'(global_label "NET_WRONG" (shape bidirectional) (at {replica_x}')
        self.assertNotEqual(
            mutated, text,
            "the miswire mutation matched nothing; this cell would then be testing "
            "a correct fixture while claiming to test a wrong one")
        leaf.write_text(mutated)

    def _replica_anchor(self, leaf: Path, ref: str) -> tuple[float, float]:
        for symbol in rfid.parse_placed_symbols(leaf.read_text()):
            if symbol.ref == ref and symbol.is_replica:
                return symbol.x, symbol.y
        self.fail(f"no replica symbol for {ref} in {leaf}")

    def _replica_anchor_x(self, leaf: Path, ref: str) -> str:
        for symbol in rfid.parse_placed_symbols(leaf.read_text()):
            if symbol.ref == ref and symbol.is_replica:
                return f"{symbol.x}"
        self.fail(f"no replica symbol for {ref} in {leaf}")

    def test_tv21_correct_replica_passes(self):
        """POSITIVE CONTROL for TV-20: without it, an always-raising check passes."""
        out, _result, sheet_map = self._emit(
            "tv21", [{"sheet": "mcu", "nets": ["NET_X"]}])
        canonical, _text = self._canonical(out)
        report = rfid.check_replica_display_fidelity(
            out / "mcu.kicad_sch", "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(report.status, rfid.STATUS_OK, report.to_dict())
        self.assertEqual(report.violations, [])
        self.assertEqual(report.replica_symbols_found, 1)
        self.assertEqual(report.drawn[("U1", "1")], "NET_X")

    def test_tv20_miswired_replica_fails_while_netlist_and_bom_are_unchanged(self):
        """The whole justification for clause 4c, in one cell.

        The netlist assertion is not decoration: it is what proves the defect is
        invisible to every netlist-based check, which is why the fidelity check has
        to read the leaf file.
        """
        out, _result, sheet_map = self._emit(
            "tv20", [{"sheet": "mcu", "nets": ["NET_X"]}])
        canonical, before_text = self._canonical(out)
        leaf = out / "mcu.kicad_sch"

        clean = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(clean.status, rfid.STATUS_OK, clean.to_dict())

        self._miswire(leaf, self._replica_anchor_x(leaf, "U1"))

        after_netlist = out / "after.net"
        rc, output = rfid.export_netlist(out / "board.kicad_sch", after_netlist)
        self.assertEqual(rc, 0, output)
        after_text = after_netlist.read_text()

        # THE INVISIBILITY CLAIM, measured rather than asserted from memory.
        self.assertEqual(_electrical_content(before_text),
                         _electrical_content(after_text),
                         "the miswire changed the exported connectivity; if it did, "
                         "the netlist WOULD be an instrument here and clause 4c's "
                         "premise would be false")
        self.assertEqual(
            rfid.canonical_pin_net_map(after_netlist), canonical)

        # BOM identity: the replica must not have produced a second row either.
        refs_before = sorted(re.findall(r'\(comp \(ref "([^"]+)"\)', before_text))
        refs_after = sorted(re.findall(r'\(comp \(ref "([^"]+)"\)', after_text))
        self.assertEqual(refs_before, refs_after)
        self.assertEqual(refs_after, ["R1", "U1"],
                         "a replica must contribute no extra comp entry")

        # AND YET the display check must see it.
        report = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(report.status, rfid.STATUS_FAILED, report.to_dict())
        codes = {v["code"] for v in report.violations}
        self.assertIn("E_REPLICA_WIRE_NOT_CANONICAL", codes)

    def test_tv22_requested_net_not_drawn_fails_f3(self):
        """F-3 alone: two nets requested, one label deleted from the landed file."""
        out, _result, sheet_map = self._emit(
            "tv22", [{"sheet": "mcu", "nets": ["NET_X", "NET_Y"]}])
        canonical, _text = self._canonical(out)
        leaf = out / "mcu.kicad_sch"

        before = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(before.status, rfid.STATUS_OK, before.to_dict())

        anchor = self._replica_anchor_x(leaf, "U1")
        text = leaf.read_text()
        mutated = re.sub(
            r'  \(global_label "NET_Y" \(shape bidirectional\) \(at '
            + re.escape(anchor) + r'[^\n]*\n[^\n]*\n', "", text)
        self.assertNotEqual(mutated, text, "the F-3 mutation matched nothing")
        leaf.write_text(mutated)

        report = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(report.status, rfid.STATUS_FAILED, report.to_dict())
        f3 = [v for v in report.violations
              if v["code"] == "E_REPLICA_NET_NOT_EXPANDED"]
        self.assertEqual(len(f3), 1, report.violations)
        self.assertEqual(f3[0]["net"], "NET_Y")

    def test_empty_request_is_empty_not_ok(self):
        """Absence of an obligation must not read as a satisfied obligation."""
        out, _result, _sheet_map = self._emit("noreq", None)
        canonical, _text = self._canonical(out)
        report = rfid.check_replica_display_fidelity(
            out / "mcu.kicad_sch", "mcu", [], canonical)
        self.assertEqual(report.status, rfid.STATUS_EMPTY)
        self.assertEqual(report.replica_views_requested, 0)

    def test_missing_leaf_is_failed_not_empty(self):
        report = rfid.check_replica_display_fidelity(
            self.root / "nosuch.kicad_sch", "mcu",
            [("U1", ReplicaView(sheet="mcu", nets=("NET_X",)))], {})
        self.assertEqual(report.status, rfid.STATUS_FAILED)
        self.assertEqual(report.violations[0]["code"], "E_REPLICA_LEAF_MISSING")

    def test_replica_symbol_deleted_is_caught(self):
        """Drawing NOTHING is the failure most likely to pass every other check."""
        out, _result, sheet_map = self._emit(
            "gone", [{"sheet": "mcu", "nets": ["NET_X"]}])
        canonical, _text = self._canonical(out)
        leaf = out / "mcu.kicad_sch"
        text = leaf.read_text()
        # The module constant, NOT a copied literal: a duplicated flag string here
        # would silently stop matching the moment the emitter's flags change, and
        # this cell would then delete nothing while still reporting a pass.
        marker = _REPLICA_FLAGS
        self.assertIn(marker, text)
        start = text.rindex("  (symbol", 0, text.index(marker))
        end = text.index("\n  )", text.index(marker)) + len("\n  )")
        leaf.write_text(text[:start] + text[end:])

        report = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(report.status, rfid.STATUS_FAILED, report.to_dict())
        codes = {v["code"] for v in report.violations}
        self.assertIn("E_REPLICA_SYMBOL_NOT_DRAWN", codes)

    def test_unread_attachment_is_indeterminate_with_no_violation(self):
        """The cell that actually exercises the `indeterminate` branch.

        MEASURED: the rotated-symbol cell below reaches `failed` via F-3 (the pin
        moves, so its label no longer matches), which means it never touches the
        indeterminate arm and a mutant collapsing indeterminate into `ok` survived
        it. A wire endpoint on a replica pin produces the shape that matters --
        NOTHING is found wrong, and part of the drawing is unread. That must not be
        a pass.
        """
        out, _result, sheet_map = self._emit(
            "unread", [{"sheet": "mcu", "nets": ["NET_X"]}])
        canonical, _text = self._canonical(out)
        leaf = out / "mcu.kicad_sch"
        text = leaf.read_text()

        symbol = next(s for s in rfid.parse_placed_symbols(text) if s.is_replica)
        pins, why = rfid.pin_endpoints_absolute(
            symbol, rfid._lib_symbols_source(text))
        self.assertEqual(why, [], "the fixture's own geometry must be readable")
        pin_x, pin_y = pins["1"]
        wire = (f'  (wire (pts (xy {pin_x} {pin_y}) (xy {pin_x + 10} {pin_y}))\n'
                f'    (stroke (width 0) (type default)) '
                f'(uuid "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))\n')
        mutated = text.replace("  (sheet_instances", wire + "  (sheet_instances")
        self.assertNotEqual(mutated, text, "the wire insertion matched nothing")
        leaf.write_text(mutated)

        report = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(report.violations, [],
                         "this cell is only meaningful when nothing is WRONG")
        self.assertEqual(report.status, rfid.STATUS_INDETERMINATE,
                         report.to_dict())
        self.assertTrue(report.indeterminate_reasons)

    def test_half_flagged_symbol_is_not_counted_as_a_replica(self):
        """Both flags are required; either alone leaves a real defect behind.

        MEASURED (DD-13 clause 2): `on_board no` alone still leaves a BOM row, and
        `in_bom no` alone still puts the pins in the netlist. A predicate accepting
        either would call such a symbol a valid replica -- so this cell forces the
        conjunction rather than trusting the docstring.
        """
        out, _result, sheet_map = self._emit(
            "half", [{"sheet": "mcu", "nets": ["NET_X"]}])
        canonical, _text = self._canonical(out)
        leaf = out / "mcu.kicad_sch"
        text = leaf.read_text()
        mutated = text.replace(_REPLICA_FLAGS, "(in_bom no) (on_board yes) (dnp yes)")
        self.assertNotEqual(mutated, text, "the half-flag mutation matched nothing")
        leaf.write_text(mutated)

        report = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertEqual(report.replica_symbols_found, 0)
        self.assertEqual(report.status, rfid.STATUS_FAILED, report.to_dict())
        codes = {v["code"] for v in report.violations}
        self.assertIn("E_REPLICA_SYMBOL_NOT_DRAWN", codes)

    def test_rotated_symbol_is_not_reported_as_a_clean_pass(self):
        """A rotated symbol must not be reported as a clean pass.

        Reaches `failed` (F-3) rather than `indeterminate`, because rotating moves
        the pin away from its label. Kept for the refusal REASON it records; the
        indeterminate arm itself is covered by the wire cell above.
        """
        out, _result, sheet_map = self._emit(
            "rot", [{"sheet": "mcu", "nets": ["NET_X"]}])
        canonical, _text = self._canonical(out)
        leaf = out / "mcu.kicad_sch"
        ax, ay = self._replica_anchor(leaf, "U1")
        text = leaf.read_text()
        mutated = text.replace(f"    (at {ax} {ay} 0)",
                               f"    (at {ax} {ay} 90)")
        self.assertNotEqual(mutated, text, "the rotation mutation matched nothing")
        leaf.write_text(mutated)

        report = rfid.check_replica_display_fidelity(
            leaf, "mcu", sheet_map.replicas_on("mcu"), canonical)
        self.assertIn(report.status,
                      (rfid.STATUS_INDETERMINATE, rfid.STATUS_FAILED),
                      report.to_dict())
        self.assertNotEqual(report.status, rfid.STATUS_OK)
        self.assertTrue(report.indeterminate_reasons)
