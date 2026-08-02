"""BR_20260731 — a gate must not report a pass for an input it never checked.

Each site gets BOTH halves of the control pair, because a check that only asserts
"empty input is rejected" cannot distinguish a working gate from one that rejects
everything:

  * vacuous  — zero / unparsable input yields a third state, and the success wording
               is absent from the envelope.
  * control  — a real, non-empty input still produces the ordinary pass.

`bodesign_eda_bridge.__init__` is broken at HEAD (composer imports a nonexistent
`_vendor_sym_scale` from kicad_emit), which also breaks `tests/test_pin_allocation.py`.
That is unrelated to this BR, so the pin_allocation module is loaded from its file
directly — an import-erroring test module reports zero failures, which is the exact
shape this BR exists to eliminate.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb import audit_claims
from bodesign_workflow_core import crosscheck_nets

_PA_PATH = Path(__file__).resolve().parents[1] / "packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py"
_spec = importlib.util.spec_from_file_location("_br20260731_pin_allocation", _PA_PATH)
pin_allocation = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = pin_allocation
_spec.loader.exec_module(pin_allocation)
build_pin_allocation = pin_allocation.build_pin_allocation


def _write_vault(root: Path, entries: dict) -> None:
    """Same minimal `datasheets`-skill cache shape tests/test_datasheet_vault.py uses."""
    ed = root / "extracted"
    ed.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 2, "extractions": {}}
    for mpn, extraction in entries.items():
        fn = f"{mpn}.json"
        (ed / fn).write_text(json.dumps(extraction), encoding="utf-8")
        meta = extraction.get("extraction_metadata", {})
        manifest["extractions"][mpn] = {
            "file": fn, "mpn": mpn, "category": extraction.get("category", ""),
            "source_pdf": meta.get("source_pdf", ""),
            "extraction_score": meta.get("extraction_score", 0),
        }
    (ed / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


_LDO = {"mpn": "TLV75733PDRVR", "category": "linear_regulator",
        "electrical_characteristics": {"vref_v": 3.3, "dropout_mv": 425},
        "extraction_metadata": {"source_pdf": "TLV75733PDRVR.pdf", "extraction_score": 4.0}}


class AuditClaimsVacuousTests(unittest.TestCase):
    def test_zero_claims_is_not_publishable_and_says_so(self):
        out = audit_claims([], root="/nonexistent-vault-br20260731")
        self.assertIsNone(out["publishable"], "zero claims must not be True")
        self.assertNotEqual(out["publishable"], True)
        self.assertEqual("vacuous", out["verdict"])
        self.assertEqual(0, out["claim_count"])
        self.assertNotIn("All asserted specs are datasheet-grounded", out["advice"])
        self.assertIn("NOT a pass", out["advice"])

    def test_control_real_clean_audit_still_publishable(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_vault(root, {"TLV75733PDRVR": _LDO})
            out = audit_claims(
                [{"mpn": "TLV75733PDRVR", "field": "vout_v", "asserted_value": 3.3}],
                root=root)
            self.assertIs(True, out["publishable"])
            self.assertEqual(1, out["claim_count"])
            self.assertIn("All asserted specs are datasheet-grounded", out["advice"])

    def test_control_real_blocking_audit_still_blocks(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_vault(root, {"TLV75733PDRVR": _LDO})
            out = audit_claims(
                [{"mpn": "NOSUCHPART", "field": "vout_v", "asserted_value": 3.3}],
                root=root)
            self.assertIs(False, out["publishable"])
            self.assertEqual(1, out["blocking_count"])


class CrosscheckNetsVacuousTests(unittest.TestCase):
    def test_empty_reference_is_not_a_match(self):
        chk = crosscheck_nets(set(), set(), "vacuous")
        self.assertTrue(chk.vacuous)
        self.assertNotIn("matches the reference", chk.verdict)
        self.assertNotIn("covers all", chk.verdict)
        self.assertIn("no reference nets", chk.verdict)
        self.assertEqual(0, chk.coverage_pct)
        self.assertTrue(chk.to_dict()["vacuous"])

    def test_empty_reference_with_generated_nets_is_not_a_match(self):
        chk = crosscheck_nets({"A", "B"}, set(), "vacuous")
        self.assertTrue(chk.vacuous)
        self.assertNotIn("matches the reference", chk.verdict)
        self.assertEqual(["A", "B"], chk.extra)

    def test_control_exact_match_still_reports_the_match(self):
        chk = crosscheck_nets({"A", "B"}, {"A", "B"}, "iface")
        self.assertFalse(chk.vacuous)
        self.assertIn("matches the reference exactly (2 nets)", chk.verdict)
        self.assertEqual(100, chk.coverage_pct)

    def test_control_incomplete_still_reports_missing(self):
        chk = crosscheck_nets({"A"}, {"A", "B"}, "iface")
        self.assertFalse(chk.vacuous)
        self.assertIn("incomplete", chk.verdict)
        self.assertEqual(["B"], chk.missing)


NETS = [{"name": "VIN", "nodes": ["U1.1", "R1.1"]},
        {"name": "GND", "nodes": ["U1.10", "C1.2"]}]


class PinAllocationVacuousTests(unittest.TestCase):
    def test_no_nets_is_vacuous_not_an_empty_design(self):
        alloc = build_pin_allocation([])
        self.assertTrue(alloc.vacuous)
        self.assertEqual([], alloc.unparsed_nets)
        self.assertIn("NOT an empty design", alloc.advice)
        self.assertTrue(alloc.to_dict()["vacuous"])

    def test_unparsable_net_shape_is_counted_and_loud(self):
        alloc = build_pin_allocation([{"name": "VIN", "pin": "1"}, {"name": "GND", "pin": "2"}])
        self.assertTrue(alloc.vacuous)
        self.assertEqual(["VIN", "GND"], alloc.unparsed_nets)
        self.assertEqual(2, alloc.to_dict()["unparsed_net_count"])
        self.assertIn("none yielded a REF.PIN node", alloc.advice)

    def test_partially_unparsable_input_is_not_vacuous_but_still_reports_the_loss(self):
        alloc = build_pin_allocation(NETS + [{"name": "BAD", "pin": "9"}])
        self.assertFalse(alloc.vacuous)
        self.assertEqual(["BAD"], alloc.unparsed_nets)
        self.assertIn("BAD", alloc.advice)
        self.assertEqual(["C1", "R1", "U1"], alloc.refs)

    def test_control_real_nets_still_produce_a_clean_table(self):
        alloc = build_pin_allocation(NETS, mcu_refs=("U1",))
        self.assertFalse(alloc.vacuous)
        self.assertEqual([], alloc.unparsed_nets)
        self.assertEqual("", alloc.advice)
        self.assertEqual(["C1", "R1", "U1"], alloc.refs)
        self.assertEqual(2, alloc.net_count)
        csv_text = pin_allocation.render_pin_allocation_csv(alloc)
        self.assertIn("U1,1,VIN,yes", csv_text)


if __name__ == "__main__":
    unittest.main()
