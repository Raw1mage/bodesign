import json
import tempfile
import unittest
from pathlib import Path

from bodesign_component_kb import audit_claims, list_entries, lookup, register, spec_check


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


    def test_rca_audit_blocks_ungrounded_claims(self):
        register("W25Q128JVSIQ",
                 specs={"vcc_min_v": {"value": 2.7, "source": "Digi-Key spec table"}}, root=self.root)
        register("TLV75733PDRVR",
                 specs={"vout_v": 3.3}, root=self.root)  # unverified (no source)
        out = audit_claims([
            {"mpn": "W25Q128JVSIQ", "field": "vcc_min_v", "asserted_value": 2.7},   # verified+match -> ok
            {"mpn": "W25Q128JVSIQ", "field": "vcc_min_v", "asserted_value": 1.65},  # verified but contradicts -> block
            {"mpn": "TLV75733PDRVR", "field": "vout_v", "asserted_value": 3.3},      # unverified -> block
            {"mpn": "AMS1117", "field": "vout_v", "asserted_value": 3.3},            # absent -> block
        ], root=self.root)
        self.assertFalse(out["publishable"])
        self.assertEqual(out["blocking_count"], 3)
        reasons = {b["field"] + ":" + str(b.get("claimed_value")): b["block_reason"] for b in out["blocking"]}
        self.assertIn("contradicts", reasons["vcc_min_v:1.65"])

    def test_rca_audit_passes_when_all_grounded(self):
        register("W25Q128JVSIQ",
                 specs={"vcc_min_v": {"value": 2.7, "source": "ds"}, "vcc_max_v": {"value": 3.6, "source": "ds"}},
                 root=self.root)
        out = audit_claims([
            {"mpn": "W25Q128JVSIQ", "field": "vcc_min_v", "asserted_value": 2.7},
            {"mpn": "W25Q128JVSIQ", "field": "vcc_max_v"},  # no asserted value, just must be grounded
        ], root=self.root)
        self.assertTrue(out["publishable"])


if __name__ == "__main__":
    unittest.main()
