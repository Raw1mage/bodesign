"""BR1 regression: post-emit fidelity gate must catch collinear-wire net fusion.

Replays the aiguard C03 v03 class of bug in miniature: a connector-dense single
sheet where the draftsman 2-node drawn-wire route runs collinear on a tight x
column and KiCad fuses distinct nets. The fidelity gate (partition equivalence,
not net-name) must FAIL-LOUD; the all_label escape must make it PASS.

No project-private data — a synthetic Conn_01x08 + discretes fixture.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import (
    compose_schematic,
    verify_partition_fidelity,
    FidelityError,
)
from bodesign_eda_bridge.fidelity import (
    compare_partitions,
    expected_partition_from_nets,
)

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

# A connector-dense sheet: one 8-pin header whose pins fan out to many discretes,
# the shape that triggered collinear fusion. Distinct 2-node nets on a tight column.
DENSE_SPEC = {
    "components": (
        [{"ref": "J1", "symbol": "Connector:Conn_01x08_Pin", "value": "EDGE"}]
        + [{"ref": f"R{i}", "symbol": "Device:R", "value": "10k"} for i in range(1, 9)]
    ),
    "nets": [
        {"name": f"N{i}", "nodes": [f"J1.{i}", f"R{i}.1"]} for i in range(1, 9)
    ] + [
        {"name": "GND", "nodes": [f"R{i}.2" for i in range(1, 9)]}
    ],
}


class FidelityPartitionUnitTests(unittest.TestCase):
    """Pure-logic tests — no KiCad needed."""

    def test_expected_partition_from_dict_nets(self):
        part = expected_partition_from_nets(DENSE_SPEC["nets"])
        self.assertEqual(set(part["N1"]), {"J1.1", "R1.1"})
        self.assertEqual(len(part["GND"]), 8)

    def test_fused_candidate_is_flagged(self):
        # candidate where N1..N8 got fused into ONE class (the short) — must FAIL.
        expected = expected_partition_from_nets(DENSE_SPEC["nets"])
        fused = [frozenset(
            [f"J1.{i}" for i in range(1, 9)] + [f"R{i}.1" for i in range(1, 9)]
        )] + [frozenset(f"R{i}.2" for i in range(1, 9))]
        rep = compare_partitions(expected, fused)
        self.assertFalse(rep.ok)
        self.assertTrue(rep.moved, "fused pins must show as moved partition class")

    def test_faithful_candidate_passes(self):
        expected = expected_partition_from_nets(DENSE_SPEC["nets"])
        faithful = [frozenset({f"J1.{i}", f"R{i}.1"}) for i in range(1, 9)]
        faithful.append(frozenset(f"R{i}.2" for i in range(1, 9)))
        rep = compare_partitions(expected, faithful)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual(rep.moved, [])
        self.assertEqual(rep.only_baseline, [])
        self.assertEqual(rep.only_candidate, [])


@unittest.skipUnless(HAS_SYMBOLS and HAS_KICAD_CLI, "KiCad symbols + cli required")
class FidelityGateIntegrationTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-fidelity-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_all_label_path_is_faithful(self):
        # all_label forces every net (2-node included) onto global labels: zero
        # drawn wire, collinearity-free by construction -> fidelity PASSES.
        spec = dict(DENSE_SPEC, all_label=True)
        result = compose_schematic(
            self.work, "dense_demo", spec, symbol_dirs=SYMBOL_DIR,
            style="draftsman", fidelity=True,
        )
        self.assertTrue(result.fidelity.ok, result.fidelity.summary())

    def test_verify_partition_fidelity_standalone(self):
        # Standalone gate over a faithful (all_label) sheet: verify the public
        # verify_partition_fidelity() reconstructs the same partition the spec
        # declares. Uses the collinearity-free all_label path so the check
        # exercises the gate, not draftsman wire-route quirks.
        spec = dict(DENSE_SPEC, all_label=True)
        r = compose_schematic(self.work, "dense_demo2", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman")
        rep = verify_partition_fidelity(DENSE_SPEC["nets"], r.emit.schematic_path)
        self.assertTrue(rep.ok, rep.summary())


if __name__ == "__main__":
    unittest.main()
