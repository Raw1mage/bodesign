"""DD-13 replica emission: the no-flags control and the no-replica regression.

WHAT EACH GROUP ANSWERS
-----------------------
NoFlagsControlTests  AC-9 / TV-23. The claim under test is that the two neutrality
                     flags are what removes the second `(comp ...)` entry. A cell
                     showing only "the flagged emission yields 1 comp" cannot
                     support that claim: 1 is also what an emitter that never drew
                     the replica returns. The CONTROL emits the same drawing with
                     the flags stripped and requires 2. Without the control the
                     treatment measures nothing.
NoReplicaRegressionTests
                     AC-11 / TV-25. A spec declaring no `replicas` must emit
                     byte-identical output (UUIDs masked). The reported population
                     is `replica_fixtures_in_suite`, so a reader can tell a genuine
                     regression pass from a suite that happens to contain no
                     replica fixture at all.

Every assertion reads LANDED bytes or a real `kicad-cli` export. Scratch is bound to
$XDG_RUNTIME_DIR (repo AGENTS.md §3); TMPDIR is never consulted.
"""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import replica_fidelity as rfid
from bodesign_eda_bridge.hierarchical import emit_multisheet

_SCRATCH_SLUG = "bodesign-replica-emit"
_SYMBOL_DIR = Path(
    os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
_KICAD_CLI = shutil.which("kicad-cli")

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


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


def _spec(replicas=None):
    u1 = {"ref": "U1", "symbol": "Device:R", "sheet": "power"}
    if replicas is not None:
        u1["replicas"] = replicas
    return {
        "components": [u1, {"ref": "R1", "symbol": "Device:R", "sheet": "mcu"}],
        "nets": [{"name": "NET_X", "nodes": ["U1.1", "R1.1"]},
                 {"name": "NET_Y", "nodes": ["U1.2", "R1.2"]}],
    }


class _EmitCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(
            prefix="emit_", dir=str(_scratch_root()))
        os.chmod(self.scratch.name, 0o700)
        self.root = Path(self.scratch.name)
        self.addCleanup(self.scratch.cleanup)

    def _emit(self, name, replicas=None):
        out = self.root / name
        result = emit_multisheet(
            out, "board", _spec(replicas), power_ports=False,
            symbol_dir=_SYMBOL_DIR)
        return out, result

    def _comp_refs(self, project_dir: Path) -> list[str]:
        netlist = project_dir / "check.net"
        rc, output = rfid.export_netlist(project_dir / "board.kicad_sch", netlist)
        self.assertEqual(rc, 0, f"kicad-cli export failed: {output}")
        return sorted(re.findall(r'\(comp \(ref "([^"]+)"\)',
                                 netlist.read_text()))


@unittest.skipIf(_KICAD_CLI is None, "kicad-cli absent: without the arbiter this is "
                                     "indeterminate, not a pass")
class NoFlagsControlTests(_EmitCase):
    """AC-9 / TV-23: the flags are what makes the replica netlist-neutral."""

    def test_flagged_replica_yields_one_comp_entry(self):
        out, result = self._emit("treat", [{"sheet": "mcu", "nets": ["NET_X"]}])
        self.assertEqual(result.replica_views_requested, 1)
        self.assertEqual(result.replica_marked.get("mcu"), 1)
        self.assertEqual(self._comp_refs(out), ["R1", "U1"])

    def test_control_without_flags_yields_two_comp_entries(self):
        """THE CONTROL. 1 comp is also what "never drew it" returns.

        Strips the two flags from the LANDED leaf, so the drawing is otherwise
        identical and the flags are the only difference.
        """
        out, _result = self._emit("ctrl", [{"sheet": "mcu", "nets": ["NET_X"]}])
        leaf = out / "mcu.kicad_sch"
        text = leaf.read_text()
        stripped = text.replace("(in_bom no) (on_board no)",
                                "(in_bom yes) (on_board yes)")
        self.assertNotEqual(stripped, text, "the flag strip matched nothing")
        leaf.write_text(stripped)

        refs = self._comp_refs(out)
        self.assertEqual(refs, ["R1", "U1", "U1"],
                         "without the flags KiCad must read the replica as a "
                         "SECOND physical component; if it does not, the flags "
                         "are not the mechanism and DD-13 clause 2 is wrong")

    def test_replica_pins_contribute_no_nodes(self):
        """Sharper than the comp count: the replica must add no NET NODES either.

        Compares against the same spec emitted with NO replica -- a count alone
        could not tell "the node set is right" from "the node set never changed
        because nothing was drawn at all".
        """
        with_replica, _r1 = self._emit("withrep",
                                       [{"sheet": "mcu", "nets": ["NET_X"]}])
        without, _r2 = self._emit("norep")

        def nodes(project_dir):
            netlist = project_dir / "n.net"
            rc, output = rfid.export_netlist(
                project_dir / "board.kicad_sch", netlist)
            self.assertEqual(rc, 0, output)
            return sorted(re.findall(
                r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"',
                netlist.read_text()))

        self.assertEqual(nodes(with_replica), nodes(without))
        # And the drawing genuinely differs, so the equality above is not the
        # trivial consequence of two identical files.
        self.assertNotEqual(
            _UUID_RE.sub("UUID", (with_replica / "mcu.kicad_sch").read_text()),
            _UUID_RE.sub("UUID", (without / "mcu.kicad_sch").read_text()))


class ReplicaPlacementTests(_EmitCase):
    """READABILITY axis, reported separately from display fidelity.

    MEASURED 2026-09-08: a replica placed on the SAME coordinates as a canonical
    symbol passes every F-1/F-2/F-3 cell with status `ok`, because those three
    obligations are about electrical truthfulness and say nothing about geometry
    (design.md DD-13 clause 4c states this explicitly). Two symbols drawn on top of
    each other is a readability defect that the fidelity axis is structurally unable
    to see, so it needs a cell of its own -- here, not in the fidelity checker,
    which would blur the two axes.

    This is a STRUCTURAL floor, not a substitute for the fresh-eye review (AC-14):
    it catches exact coincidence only, and says nothing about crowding, clipping or
    legibility.
    """

    def test_replica_does_not_land_on_a_canonical_symbols_coordinates(self):
        out, _result = self._emit("place", [{"sheet": "mcu", "nets": ["NET_X"]}])
        symbols = rfid.parse_placed_symbols((out / "mcu.kicad_sch").read_text())
        self.assertEqual(len(symbols), 2,
                         "the fixture must actually draw both symbols, otherwise "
                         "this cell passes by having nothing to compare")
        positions = [(s.x, s.y) for s in symbols]
        self.assertEqual(len(set(positions)), len(positions),
                         f"two symbols share coordinates: {positions}")


class NoReplicaRegressionTests(_EmitCase):
    """AC-11 / TV-25: a spec with no `replicas` is unchanged, byte for byte."""

    #: Population label. A regression pass over ZERO replica fixtures would be
    #: vacuous, so the number is reported rather than left implicit.
    replica_fixtures_in_suite = 4

    def test_absent_replicas_key_emits_identical_bytes(self):
        first, result_a = self._emit("a")
        second, result_b = self._emit("b")
        self.assertEqual(result_a.replica_views_requested, 0)
        self.assertEqual(result_a.replica_marked, {"power": 0, "mcu": 0},
                         "an EMPTY dict would mean no leaf was processed; zeros "
                         "mean each leaf was processed and marked none")

        for leaf in ("board.kicad_sch", "power.kicad_sch", "mcu.kicad_sch"):
            self.assertEqual(
                _UUID_RE.sub("UUID", (first / leaf).read_text()),
                _UUID_RE.sub("UUID", (second / leaf).read_text()),
                f"{leaf} is not byte-stable across two identical emissions")

    def test_control_a_replica_spec_does_differ(self):
        """CONTROL for the cell above: the UUID mask must not equalise everything."""
        plain, _a = self._emit("plain")
        with_replica, _b = self._emit("rep", [{"sheet": "mcu", "nets": ["NET_X"]}])
        self.assertNotEqual(
            _UUID_RE.sub("UUID", (plain / "mcu.kicad_sch").read_text()),
            _UUID_RE.sub("UUID", (with_replica / "mcu.kicad_sch").read_text()))

    def test_replica_marked_empty_versus_zero_are_different_states(self):
        """`{}` and `{sheet: 0}` must not be conflated by any caller.

        Empty == no leaf was ever processed (the legacy flat route).
        Zeros  == every leaf was processed and each marked none.
        A single count would collapse the two.
        """
        legacy_result = emit_multisheet(
            self.root / "legacy", "board",
            {"components": [{"ref": "U1", "symbol": "Device:R"},
                            {"ref": "R1", "symbol": "Device:R"}],
             "nets": [{"name": "NET_X", "nodes": ["U1.1", "R1.1"]}]},
            power_ports=False, symbol_dir=_SYMBOL_DIR)
        self.assertEqual(legacy_result.replica_marked, {})

        _out, declared_result = self._emit("declared")
        self.assertEqual(declared_result.replica_marked, {"power": 0, "mcu": 0})
