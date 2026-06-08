import json
import tempfile
import unittest
from pathlib import Path

from bodesign_component_kb import list_entries, lookup, register, spec_check


class DatasheetVaultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_absent_lookup_is_honest(self):
        self.assertIsNone(lookup("W25Q128JVSIQ", root=self.root))
        chk = spec_check("W25Q128JVSIQ", "vcc_min_v", root=self.root)
        self.assertEqual(chk["status"], "absent")
        self.assertIn("acquire", chk["advice"].lower())

    def test_verified_vs_unverified_provenance(self):
        register("W25Q128JVSIQ", vendor="Winbond",
                 source_url="https://www.digikey.com/en/products/detail/winbond-electronics/W25Q128JVSIQ/5803943",
                 aliases=["W25Q128JV"],
                 specs={
                     "vcc_min_v": {"value": 2.7, "unit": "V", "source": "Digi-Key spec table (W25Q128JVSIQ)"},
                     "vcc_max_v": {"value": 3.6, "unit": "V", "source": "Digi-Key spec table (W25Q128JVSIQ)"},
                     "package_guess": 8,  # bare scalar -> unverified
                 }, root=self.root)

        v = spec_check("W25Q128JVSIQ", "vcc_min_v", root=self.root)
        self.assertEqual(v["status"], "verified")
        self.assertEqual(v["value"], 2.7)
        self.assertTrue(v["source"])

        u = spec_check("W25Q128JVSIQ", "package_guess", root=self.root)
        self.assertEqual(u["status"], "unverified")

    def test_claim_match_and_alias(self):
        register("W25Q128JVSIQ", aliases=["W25Q128JV"],
                 specs={"vcc_min_v": {"value": 2.7, "source": "datasheet"}}, root=self.root)
        # the alias resolves to the same entry
        self.assertIsNotNone(lookup("W25Q128JV", root=self.root))
        # 2.3V measured vs 2.7V min -> mismatch flagged
        chk = spec_check("W25Q128JVSIQ", "vcc_min_v", claimed_value=2.3, root=self.root)
        self.assertFalse(chk["matches"])

    def test_meta_written_and_listed(self):
        register("TLV75733PDRVR", vendor="Texas Instruments",
                 specs={"vout_v": {"value": 3.3, "source": "TI datasheet fixed-output"}}, root=self.root)
        meta = json.loads((self.root / "tlv75733pdrvr" / "meta.json").read_text())
        self.assertEqual(meta["vendor"], "Texas Instruments")
        names = [e["mpn"] for e in list_entries(root=self.root)]
        self.assertIn("TLV75733PDRVR", names)


if __name__ == "__main__":
    unittest.main()
