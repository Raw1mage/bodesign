import os
import unittest
from pathlib import Path

from bodesign_eda_bridge import PackageQuery, build_footprint_map, match_footprints, openmv_package_queries
from bodesign_shared import data_root

FOOTPRINT_DIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
HAS_BGA = (FOOTPRINT_DIR / "Package_BGA.pretty").exists()
OPENMV_PLAN = data_root() / "products" / "openmv"
HAS_OPENMV = OPENMV_PLAN.exists()


@unittest.skipUnless(HAS_BGA, "KiCad BGA footprint library not installed")
class FootprintMapTests(unittest.TestCase):
    def test_24_ball_5x5_package_matches_a_bga24_footprint(self):
        query = PackageQuery(component_ref="U7", mpn="MX25UM25645G", package="24-Ball BGA", ball_count=24, array="5x5")

        candidates = match_footprints(query, FOOTPRINT_DIR)

        matches = [c for c in candidates if c.is_match]
        self.assertTrue(matches)
        self.assertTrue(matches[0].lib_id.startswith("Package_BGA:BGA-24"))
        self.assertEqual("5x5", matches[0].layout)

    def test_223_ball_package_has_no_stdlib_match(self):
        query = PackageQuery(component_ref="U5", mpn="STM32N657L0", package="VFBGA223", ball_count=223, pitch_mm=0.5)

        candidates = match_footprints(query, FOOTPRINT_DIR)

        self.assertFalse(any(c.is_match for c in candidates))

    @unittest.skipUnless(HAS_OPENMV, "OpenMV plan artifacts not present")
    def test_openmv_footprint_map_flags_match_and_gap_honestly(self):
        queries = openmv_package_queries(OPENMV_PLAN)
        self.assertEqual({"U5", "U7"}, {q.component_ref for q in queries})

        result = build_footprint_map(queries, FOOTPRINT_DIR)
        entries = {entry["component_ref"]: entry for entry in result["entries"]}

        self.assertEqual("project-local-only", result["library_scope"])
        # MCU: flagship-new 223-ball package, no stdlib footprint -> gap.
        self.assertEqual("no-stdlib-footprint-gap", entries["U5"]["status"])
        self.assertIsNone(entries["U5"]["best_match"])
        self.assertTrue(entries["U5"]["gaps"])
        # Flash: real 24-ball 5x5 candidate, flagged as needing verification (not silently exact).
        self.assertEqual("candidate-match-needs-verification", entries["U7"]["status"])
        self.assertTrue(entries["U7"]["best_match"].startswith("Package_BGA:BGA-24"))
        self.assertTrue(entries["U7"]["gaps"])


if __name__ == "__main__":
    unittest.main()
