"""L6 anchor-avoidance: the gate must be LIVE, and the product default must be OFF.

BR_20260802 (c4). Two separate things are pinned here, because they failed
independently and either one alone leaves the defect reachable.

1. THE GATE MUST BE LIVE.  `emit_kicad_schematic` declared an `l6_avoidance`
   parameter and then never read it -- the call site hardcoded `True`.  A caller
   could compute the flag, thread it in, and have it silently discarded.  That is
   the shape this repo calls a silent-degradation defect: the parameter's present
   state and its dead state produced the same output (a working schematic), so
   nothing ever surfaced it.  Measured with AST at the time of the fix: 0 reads
   of `l6_avoidance` in the function body, against 10 reads of `page_scale` as a
   control proving the probe had discriminating power.

2. THE PRODUCT DEFAULT MUST BE OFF (user ruling 2026-08-02, electrical-first).
   L6 displaces a label anchor away from its pin endpoint -- bounded by
   `_L6_AVOID_MAX_STEPS` x 1.0mm = 64mm, and the measured real-world range was
   1.57-53.38mm on the aiguard product page.  An anchor that far from its pin is
   an OPEN CIRCUIT, which is what the fidelity gate was already reporting.  The
   cost of OFF is real and is accepted knowingly: the co-point label blob returns
   (measured 15 label-label overlaps on a 6-flag same-anchor run, vs 0 with L6
   on).  Illegibility is a cosmetic defect; a label 31mm off its pin is an
   electrical one.  If that tradeoff is ever revisited, change it HERE, in the
   open, rather than by reintroducing a hardcoded True at the call site.

Note on what is NOT asserted: this file does not claim L6 is wrong.  It claims
the choice must be explicit and reachable from a spec.  A page that wants L6 can
set `l6_avoidance: true` in its spec and get exactly the old behaviour.
"""

import ast
import inspect
import re
import unittest

from bodesign_eda_bridge import kicad_emit
from bodesign_eda_bridge.kicad_emit import (
    _avoid_label_overlap,
    _staggered_label_blocks,
    emit_kicad_schematic,
)


def _param_reads(func_name: str, param: str) -> int:
    """Count Load-context reads of `param` inside `func_name`'s body.

    Deliberately AST, not grep: a mention inside a docstring or a comment is not
    a read, and grep cannot tell those apart from one.  That distinction is the
    entire point -- the dead parameter was mentioned in prose all along.
    """
    tree = ast.parse(inspect.getsource(kicad_emit))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return sum(
                1
                for n in ast.walk(node)
                if isinstance(n, ast.Name) and n.id == param and isinstance(n.ctx, ast.Load)
            )
    raise AssertionError(f"{func_name} not found -- this probe has no discriminating power")


def _anchors(blocks: list[str]) -> list[tuple[float, float]]:
    out = []
    for b in blocks:
        m = re.search(r"\(at ([-\d.]+) ([-\d.]+)", b)
        if m:
            out.append((float(m.group(1)), float(m.group(2))))
    return out


class TestL6GateIsLive(unittest.TestCase):
    def test_emit_actually_reads_the_l6_parameter(self):
        """Re-hardcoding the call site turns this RED."""
        reads = _param_reads("emit_kicad_schematic", "l6_avoidance")
        self.assertGreaterEqual(
            reads,
            1,
            "emit_kicad_schematic declares l6_avoidance but never reads it: the "
            "call site is hardcoding the value again and callers are being "
            "silently ignored (BR_20260802 c4)",
        )

    def test_the_ast_probe_can_tell_read_from_unread(self):
        """Control for the assertion above.

        Without this, a probe that returns 0 for EVERY parameter would make the
        test above fail loudly (fine) -- but a probe that returned a positive
        number for every name would make it pass vacuously, which is the failure
        mode that matters.  page_scale is read many times; a name that appears
        nowhere must read 0.
        """
        self.assertGreater(_param_reads("emit_kicad_schematic", "page_scale"), 0)
        self.assertEqual(_param_reads("emit_kicad_schematic", "zz_not_a_parameter"), 0)

    def test_signature_default_is_off(self):
        sig = inspect.signature(emit_kicad_schematic)
        self.assertIs(
            sig.parameters["l6_avoidance"].default,
            False,
            "the emitter's own default must be OFF; a page that wants anchor "
            "displacement opts in explicitly",
        )


class TestL6ActuallyMovesAnchors(unittest.TestCase):
    """Positive control for the whole file.

    Every assertion about "OFF keeps anchors on the pin" is worthless if L6 does
    not move anchors in the first place -- 'the feature is off' and 'the feature
    does nothing' would produce the same measurement.  So prove it moves them.
    """

    def test_l6_displaces_an_anchor_when_something_is_in_the_way(self):
        clear = _avoid_label_overlap("SIGNAL_A", 100.0, 50.0, (1.0, 0.0), [], 1.0, graphics=None)
        obstructed = _avoid_label_overlap(
            "SIGNAL_A", 100.0, 50.0, (1.0, 0.0), [(99.0, 104.0, 49.0, 51.0)], 1.0, graphics=None
        )
        self.assertEqual(clear, (100.0, 50.0), "with nothing in the way the anchor must not move")
        moved = ((obstructed[0] - clear[0]) ** 2 + (obstructed[1] - clear[1]) ** 2) ** 0.5
        self.assertGreater(
            moved,
            1.0,
            "L6 did not displace an obstructed anchor -- the rest of this file "
            "cannot distinguish 'gate off' from 'gate does nothing'",
        )


class TestGateOffKeepsAnchorsOnTheirPins(unittest.TestCase):
    # Six flags on ONE anchor point: the v17 co-point blob L6 was built for.
    BLOB = [(f"SIG{i}", 100.0, 50.0) for i in range(6)]

    def test_off_leaves_every_anchor_exactly_on_its_pin(self):
        off = _anchors(_staggered_label_blocks(self.BLOB, page_scale=1.0, l6_avoidance=False))
        self.assertEqual(len(off), len(self.BLOB), "no labels emitted -- nothing was measured")
        for x, y in off:
            self.assertAlmostEqual(x, 100.0, places=6)
            self.assertAlmostEqual(y, 50.0, places=6)

    def test_on_displaces_them_and_that_is_why_the_default_is_off(self):
        """Documents the cost being accepted, in executable form.

        This asserts the OLD behaviour still exists behind the flag.  If it ever
        stops displacing, L6 has become a no-op and the flag should be deleted
        rather than left as decoration.
        """
        on = _anchors(_staggered_label_blocks(self.BLOB, page_scale=1.0, l6_avoidance=True))
        self.assertEqual(len(on), len(self.BLOB))
        spread = max(x for x, _ in on) - min(x for x, _ in on)
        self.assertGreater(
            spread,
            1.0,
            "l6_avoidance=True no longer separates a co-point blob; the flag is "
            "now decorative and should be removed, not silently kept",
        )


if __name__ == "__main__":
    unittest.main()
