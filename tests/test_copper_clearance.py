"""Cross-spec extend — copper-clearance checker (control.dfm.ipc-clearance-voltage).

Proves the stub→landed flip is a GENUINE working gate (no false-green): it consumes
the two now-graduated capabilities (gerber-core copper geometry + design-ir NET_ROLES)
and fails fast on every missing/invalid input rather than passing silently.
"""

import unittest

from bodesign_gerber_core import build_copper_geometry
from bodesign_workflow_core.checkers.copper_clearance import check_copper_clearance
from bodesign_workflow_core.checkers.errors import CheckerError


def _two_island_geom():
    # island0 at x=0, island1 at x=3  ->  edge-to-edge 3.0mm
    return build_copper_geometry(
        tracks=[
            {"x1": 0, "y1": 0, "x2": 0, "y2": 10},
            {"x1": 3, "y1": 0, "x2": 3, "y2": 10},
        ]
    )


_THRESHOLD = {"metric": "min_clearance_mm", "value": 2.0, "unit": "mm",
              "source_anchor": "IPC-2221B Table 6-1"}


class CopperClearancePassFailTests(unittest.TestCase):
    def test_pass_when_spacing_above_limit(self):
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "island1": "ground"}}
        ev = check_copper_clearance(ir, threshold_block=_THRESHOLD)
        self.assertEqual(ev.severity, "info")
        self.assertEqual(ev.findings, [])
        self.assertEqual(ev.raw_result["island_pair_count"], 1)
        self.assertEqual(ev.raw_result["under_limit"], 0)

    def test_fail_when_spacing_below_limit(self):
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "island1": "ground"}}
        tight = dict(_THRESHOLD, value=5.0)  # demand 5mm, actual 3mm -> violation
        ev = check_copper_clearance(ir, threshold_block=tight)
        self.assertEqual(ev.severity, "major")
        self.assertEqual(len(ev.findings), 1)
        self.assertEqual(ev.findings[0].severity, "major")
        self.assertIn("power", ev.findings[0].message)
        self.assertIn("ground", ev.findings[0].message)

    def test_deterministic_repeat(self):
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "island1": "ground"}}
        a = check_copper_clearance(ir, threshold_block=_THRESHOLD).to_dict()
        b = check_copper_clearance(ir, threshold_block=_THRESHOLD).to_dict()
        self.assertEqual(a, b)


class CopperClearanceNoFabricationTests(unittest.TestCase):
    def test_unbound_threshold_fails_fast(self):
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "island1": "ground"}}
        with self.assertRaises(CheckerError) as ctx:
            check_copper_clearance(ir, threshold_block=None)
        self.assertEqual(ctx.exception.code, "CHK_THRESHOLD_UNBOUND")

    def test_missing_source_anchor_fails_fast(self):
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "island1": "ground"}}
        no_anchor = {"metric": "min_clearance_mm", "value": 2.0, "unit": "mm"}
        with self.assertRaises(CheckerError) as ctx:
            check_copper_clearance(ir, threshold_block=no_anchor)
        self.assertEqual(ctx.exception.code, "CHK_SOURCE_ANCHOR_MISSING")

    def test_missing_copper_geometry_fails_fast(self):
        ir = {"island_roles": {"island0": "power", "island1": "ground"}}
        with self.assertRaises(CheckerError) as ctx:
            check_copper_clearance(ir, threshold_block=_THRESHOLD)
        self.assertEqual(ctx.exception.code, "CHK_IR_FIELD_MISSING")

    def test_missing_island_roles_fails_fast(self):
        ir = {"copper_geometry": _two_island_geom()}
        with self.assertRaises(CheckerError) as ctx:
            check_copper_clearance(ir, threshold_block=_THRESHOLD)
        self.assertEqual(ctx.exception.code, "CHK_IR_FIELD_MISSING")

    def test_role_outside_closed_enum_rejected(self):
        # no-fabrication: a bad role token is rejected, never coerced to a default.
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "island1": "NOT_A_ROLE"}}
        with self.assertRaises(CheckerError) as ctx:
            check_copper_clearance(ir, threshold_block=_THRESHOLD)
        self.assertEqual(ctx.exception.code, "CHK_IR_FIELD_INVALID")

    def test_uncomputable_pair_fails_not_passes(self):
        # A gated pair with no computable geometry must fail fast, never be
        # treated as a passing (infinite) clearance.
        ir = {"copper_geometry": _two_island_geom(),
              "island_roles": {"island0": "power", "ghost": "ground"}}
        with self.assertRaises(CheckerError) as ctx:
            check_copper_clearance(ir, threshold_block=_THRESHOLD)
        self.assertEqual(ctx.exception.code, "CHK_IR_FIELD_MISSING")


if __name__ == "__main__":
    unittest.main()
