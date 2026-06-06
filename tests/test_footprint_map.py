import os
import unittest
from pathlib import Path

from bodesign_eda_bridge import PackageQuery, match_footprints

FOOTPRINT_DIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
HAS_BGA = (FOOTPRINT_DIR / "Package_BGA.pretty").exists()


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


if __name__ == "__main__":
    unittest.main()
