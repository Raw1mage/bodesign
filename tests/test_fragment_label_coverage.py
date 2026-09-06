"""round 13: a split daisy-chain must name EVERY fragment, not just the first.

The multi-node drawn path routes a bus hop by hop. A hop the guard rejects does
not discard the net any more -- it SPLITS the chain, and the split is safe only
because of the contract stated where the split happens:

    "every fragment gets its own net-name label, which is precisely how the
     wholesale fallback connected those same pins"

The emitter labelled `segments[0]` -- the first fragment's trunk -- and stopped.
Fragments 2..n carried drawn copper with NO net name: electrically floating
islands that LOOK wired. Geometry clean, circuit wrong.

Why it survived: the single-fragment case is byte-identical either way, and a
fragment only appears when a hop is actually blocked. Measured on a 13-component
synthetic board with power rails routed, VCC produced 2 fragments / 1 label and
`verify_partition_fidelity` reported all 5 of its nodes as `disconnected`; GND
produced 1 fragment and was unaffected.

The control below is the load-bearing half: a net that produced ONE fragment
must still get exactly ONE label. Without it, "labels every fragment" and
"emits labels unconditionally" share the same green.
"""

import os
import unittest
from pathlib import Path

from bodesign_eda_bridge.composer import compose_schematic

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))


def _label_names(sch_text):
    """Every local `(label "NAME"` in the sheet, in order of appearance."""
    out = []
    for line in sch_text.splitlines():
        s = line.strip()
        if s.startswith('(label "'):
            out.append(s.split('"')[1])
    return out


class FragmentLabelSourceTests(unittest.TestCase):
    """Source-level assertions: they hold with no KiCad libraries installed.

    The emitter needs symbol libraries to produce a sheet, and the core
    container has none. Rather than let this file be silently skipped there --
    a skip and a pass are the same green -- the contract is asserted against the
    emitter's own source, which is always present.
    """

    def setUp(self):
        import bodesign_eda_bridge.kicad_emit as ke
        self.src = Path(ke.__file__).read_text()

    def test_label_loop_iterates_fragments(self):
        """The label call must sit inside a per-fragment loop."""
        self.assertIn("for _frag in _sig_frags:", self.src,
                      "the per-fragment label loop is gone; a split chain would "
                      "again name only its first fragment")
        self.assertIn('_ftrunk = _frag["segs"][0]', self.src,
                      "the loop no longer takes each fragment's own trunk")

    def test_single_fragment_label_is_not_reintroduced(self):
        """CONTROL: the old per-net form must be absent.

        This is what makes the assertion above discriminating -- both forms can
        coexist syntactically, and if they did the emitter would double-label
        fragment 1 while the first test still passed.
        """
        self.assertNotIn("trunk = segments[0]", self.src,
                         "the pre-round-13 per-net label call is back alongside "
                         "the per-fragment loop; fragment 1 gets two labels")

    def test_probe_can_fail(self):
        """ACCEPTING CONTROL: the source really is being read.

        A string that must be present anchors the two absence-style assertions
        above -- without it, an empty or wrong-file read would pass them both.
        """
        self.assertIn("_place_local_label", self.src,
                      "read the wrong file, or read nothing: the emitter has no "
                      "_place_local_label, so the assertions above proved nothing")


@unittest.skipUnless(SYMBOL_DIR.is_dir(), f"no KiCad symbol libraries at {SYMBOL_DIR}")
class FragmentLabelEmissionTests(unittest.TestCase):
    """Behavioural assertion: an UNSPLIT net gets exactly one label.

    Provoking a split through natural input needs a board crowded enough for the
    guard to reject a hop, which makes the fixture fragile and its failure hard
    to attribute. What IS cheap and stable here is the control: a clean 3-pin
    net produces one fragment, and must therefore still produce exactly one
    label. That is the regression the per-fragment loop could plausibly cause.
    """

    def setUp(self):
        import tempfile
        self.work = Path(tempfile.mkdtemp(
            prefix="fraglabel-",
            dir=os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())))

    def test_unsplit_multinode_net_gets_exactly_one_label(self):
        spec = {
            "components": [
                {"ref": "R1", "symbol": "Device:R"},
                {"ref": "R2", "symbol": "Device:R"},
                {"ref": "R3", "symbol": "Device:R"},
            ],
            "nets": [{"name": "SIGNAL_X",
                      "nodes": ["R1.1", "R2.1", "R3.1"],
                      "kind": "signal"}],
        }
        res = compose_schematic(self.work, "fraglabel", spec,
                                symbol_dirs=SYMBOL_DIR, style="draftsman")
        text = Path(res.emit.schematic_path).read_text()
        names = _label_names(text)
        self.assertEqual(
            1, names.count("SIGNAL_X"),
            f"an unsplit 3-pin net produced {names.count('SIGNAL_X')} labels "
            f"(expected exactly 1); all labels seen: {names}")

    def test_label_probe_has_discriminating_power(self):
        """CONTROL for the probe itself: a name never declared must not appear.

        `_label_names` returning [] for the wrong reason would make the count
        assertion above pass vacuously in the other direction, so pin both ends.
        """
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R"},
                           {"ref": "R2", "symbol": "Device:R"}],
            "nets": [{"name": "NET_PRESENT", "nodes": ["R1.1", "R2.1"],
                      "kind": "signal"}],
        }
        res = compose_schematic(self.work, "fragctl", spec,
                                symbol_dirs=SYMBOL_DIR, style="draftsman")
        names = _label_names(Path(res.emit.schematic_path).read_text())
        self.assertIn("NET_PRESENT", names,
                      "the probe found no label for a net that IS drawn -- it "
                      "cannot be trusted to report absence either")
        self.assertNotIn("NET_ABSENT", names,
                         "the probe reports a label that was never declared")


if __name__ == "__main__":
    unittest.main()
