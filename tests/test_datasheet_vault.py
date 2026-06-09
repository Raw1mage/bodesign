import json
import tempfile
import unittest
from pathlib import Path

from bodesign_component_kb import audit_claims, list_entries, lookup, spec_check


def _write_cache(root: Path, entries: dict):
    """Write a minimal `datasheets`-skill cache: extracted/<MPN>.json + manifest.json."""
    ed = root / "extracted"
    ed.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 2, "extractions": {}}
    for mpn, extraction in entries.items():
        fn = f"{mpn}.json"
        (ed / fn).write_text(json.dumps(extraction), encoding="utf-8")
        manifest["extractions"][mpn] = {
            "file": fn, "mpn": mpn, "category": extraction.get("category", ""),
            "source_pdf": extraction.get("extraction_metadata", {}).get("source_pdf", ""),
            "extraction_score": extraction.get("extraction_metadata", {}).get("extraction_score", 0),
        }
    (ed / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _flash(source_pdf=None, source_note="Digi-Key spec table"):
    return {"mpn": "W25Q128JVSIQ", "category": "memory",
            "recommended_operating_conditions": {"vin_min_v": 2.7, "vin_max_v": 3.6},
            "extraction_metadata": {"source_pdf": source_pdf, "source_note": source_note,
                                    "extraction_score": 2.5}}


def _ldo():
    return {"mpn": "TLV75733PDRVR", "category": "linear_regulator",
            "electrical_characteristics": {"vref_v": 3.3, "dropout_mv": 425, "output_current_max_ma": 1000},
            "extraction_metadata": {"source_pdf": "TLV75733PDRVR.pdf", "extraction_score": 4.0}}


class DatasheetGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_absent_is_honest(self):
        chk = spec_check("W25Q128JVSIQ", "vcc_min_v", root=self.root)
        self.assertEqual(chk["status"], "absent")
        self.assertIn("do not state the value from memory", chk["advice"].lower())

    def test_reads_skill_cache_via_aliases(self):
        _write_cache(self.root, {"W25Q128JVSIQ": _flash(), "TLV75733PDRVR": _ldo()})
        # alias -> nested schema path
        self.assertEqual(spec_check("W25Q128JVSIQ", "vcc_min_v", root=self.root)["value"], 2.7)
        self.assertEqual(spec_check("TLV75733PDRVR", "vout_v", root=self.root)["value"], 3.3)
        self.assertEqual(spec_check("TLV75733PDRVR", "dropout_mv", root=self.root)["value"], 425)
        # raw dotted path also works
        self.assertEqual(
            spec_check("TLV75733PDRVR", "electrical_characteristics.output_current_max_ma", root=self.root)["value"],
            1000)

    def test_verified_requires_a_source(self):
        _write_cache(self.root, {
            "TLV75733PDRVR": _ldo(),                                  # has source_pdf -> verified
            "W25Q128JVSIQ": _flash(source_pdf=None, source_note=""),  # no source -> unverified
        })
        self.assertEqual(spec_check("TLV75733PDRVR", "vout_v", root=self.root)["status"], "verified")
        self.assertEqual(spec_check("W25Q128JVSIQ", "vcc_min_v", root=self.root)["status"], "unverified")

    def test_audit_blocks_and_passes(self):
        _write_cache(self.root, {"W25Q128JVSIQ": _flash(), "TLV75733PDRVR": _ldo()})
        out = audit_claims([
            {"mpn": "W25Q128JVSIQ", "field": "vcc_min_v", "asserted_value": 2.7},     # ok
            {"mpn": "W25Q128JVSIQ", "field": "vcc_min_v", "asserted_value": 1.65},    # contradicts -> block
            {"mpn": "TLV75733PDRVR", "field": "vout_v", "asserted_value": 3.3},        # ok
            {"mpn": "AMS1117", "field": "vout_v", "asserted_value": 3.3},              # absent -> block
        ], root=self.root)
        self.assertFalse(out["publishable"])
        self.assertEqual(out["blocking_count"], 2)
        good = audit_claims([{"mpn": "TLV75733PDRVR", "field": "dropout_mv", "asserted_value": 425}], root=self.root)
        self.assertTrue(good["publishable"])

    def test_list_entries(self):
        _write_cache(self.root, {"W25Q128JVSIQ": _flash(), "TLV75733PDRVR": _ldo()})
        names = [e["mpn"] for e in list_entries(root=self.root)]
        self.assertEqual(names, ["TLV75733PDRVR", "W25Q128JVSIQ"])


if __name__ == "__main__":
    unittest.main()
