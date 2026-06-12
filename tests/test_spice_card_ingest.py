"""P1 (knowledge/datasheet-spice-models) — L4 spice_model.* namespace + ingest.

Covers tasks 1.1–1.3 (R1, R2):
- registry: spice_model.* roots resolve; unknown leaf fail-fast (TV-R1-*)
- ingest: legal batch writes trust=unverified; per-row rejection for missing
  evidence / unknown field / invalid value; not_found never written to DB
  (TV-R2-*)
"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import (
    SPICE_MODEL_FIELDS,
    VaultRepository,
    VaultRepositoryError,
    resolve_field_path,
)
from bodesign_component_kb.spice_card import (
    IngestReport,
    SpiceCardError,
    ingest_spice_extraction,
)
from bodesign_component_kb.storage import open_vault

ACTOR = "test-agent"
SHA = "a" * 64
MPN = "1N4148W"


def _row(field_path, value_num=1.0, *, status="found", with_evidence=True,
         value_kind="typ", unit=None, condition=None):
    row = {"field_path": field_path, "status": status}
    if status == "found":
        row["value_num"] = value_num
        row["value_kind"] = value_kind
        if with_evidence:
            row["evidence"] = {"document_sha256": SHA, "page": 3}
    if unit is not None:
        row["unit"] = unit
    if condition is not None:
        row["condition"] = condition
    return row


class SpiceCardTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self._saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
        self.addCleanup(self._restore_env)
        self.storage = open_vault(Path(self._temp.name) / "vault")
        self.addCleanup(self.storage.close)
        self.repo = VaultRepository(self.storage)

    def _restore_env(self):
        if self._saved_env is not None:
            os.environ["BODESIGN_VAULT_DIR"] = self._saved_env

    def _count_specs(self):
        return self.storage.conn.execute("SELECT COUNT(*) FROM spec_values").fetchone()[0]


class RegistryTests(SpiceCardTestCase):
    def test_tv_r1_1_spice_model_roots_resolve(self):
        for fp in (
            "spice_model.diode.is_a",
            "spice_model.ldo.vout_v",
            "spice_model.passive.c_f",
        ):
            self.assertEqual(fp, resolve_field_path(fp))

    def test_tv_r1_2_known_root_unknown_leaf_resolves_at_db_layer(self):
        # resolve_field_path only gates the root (longest-prefix); leaf
        # validation (closed v1 field list) is enforced at the ingest layer
        # (SPX_FIELD_UNKNOWN), not here. A known root + arbitrary leaf passes.
        self.assertEqual(
            "spice_model.diode.bogus", resolve_field_path("spice_model.diode.bogus")
        )

    def test_root_without_leaf_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            resolve_field_path("spice_model.diode")
        self.assertEqual("VAULT-E401", ctx.exception.code)

    def test_unknown_root_still_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            resolve_field_path("spice_model.transistor.beta")
        self.assertEqual("VAULT-E401", ctx.exception.code)

    def test_registry_closed_list_shape(self):
        self.assertEqual({"diode", "ldo", "passive"}, set(SPICE_MODEL_FIELDS))
        self.assertTrue(SPICE_MODEL_FIELDS["diode"]["is_a"]["required"])
        self.assertFalse(SPICE_MODEL_FIELDS["diode"]["rs_ohm"]["required"])


class IngestTests(SpiceCardTestCase):
    def test_tv_r2_1_legal_batch_writes_unverified(self):
        report = ingest_spice_extraction(
            self.repo, MPN,
            [
                _row("spice_model.diode.is_a", 2.5e-9, unit="A"),
                _row("spice_model.diode.n", 1.8, unit="1"),
            ],
            actor=ACTOR,
        )
        self.assertIsInstance(report, IngestReport)
        self.assertEqual(2, len(report.written))
        self.assertEqual([], report.rejected)
        self.assertEqual(2, self._count_specs())
        # all rows landed trust=unverified
        confidences = {
            r["confidence"]
            for r in self.storage.conn.execute("SELECT confidence FROM spec_values")
        }
        self.assertEqual({"unverified"}, confidences)

    def test_tv_r2_2_missing_evidence_row_rejected(self):
        report = ingest_spice_extraction(
            self.repo, MPN,
            [
                _row("spice_model.diode.is_a", 2.5e-9),  # has evidence
                _row("spice_model.diode.n", 1.8, with_evidence=False),  # rejected
            ],
            actor=ACTOR,
        )
        self.assertEqual(1, len(report.written))
        self.assertEqual(1, len(report.rejected))
        self.assertEqual("SPX_EVIDENCE_MISSING", report.rejected[0].error_code)
        self.assertEqual("spice_model.diode.n", report.rejected[0].field_path)
        self.assertEqual(1, self._count_specs())  # only the valid row landed

    def test_tv_r2_3_unknown_field_rejected(self):
        report = ingest_spice_extraction(
            self.repo, MPN,
            [_row("spice_model.diode.made_up_param", 1.0)],
            actor=ACTOR,
        )
        self.assertEqual(0, len(report.written))
        self.assertEqual("SPX_FIELD_UNKNOWN", report.rejected[0].error_code)
        self.assertEqual(0, self._count_specs())

    def test_unknown_root_field_rejected_too(self):
        report = ingest_spice_extraction(
            self.repo, MPN,
            [_row("spice_model.transistor.beta", 100.0)],
            actor=ACTOR,
        )
        self.assertEqual("SPX_FIELD_UNKNOWN", report.rejected[0].error_code)
        self.assertEqual(0, self._count_specs())

    def test_invalid_value_rejected(self):
        bad = _row("spice_model.diode.is_a")
        bad["value_num"] = "not-a-number"
        report = ingest_spice_extraction(self.repo, MPN, [bad], actor=ACTOR)
        self.assertEqual("SPX_VALUE_INVALID", report.rejected[0].error_code)
        self.assertEqual(0, self._count_specs())

    def test_bool_value_rejected_as_non_numeric(self):
        bad = _row("spice_model.diode.is_a")
        bad["value_num"] = True
        report = ingest_spice_extraction(self.repo, MPN, [bad], actor=ACTOR)
        self.assertEqual("SPX_VALUE_INVALID", report.rejected[0].error_code)

    def test_tv_r2_4_not_found_never_written(self):
        report = ingest_spice_extraction(
            self.repo, MPN,
            [
                _row("spice_model.diode.is_a", 2.5e-9),
                _row("spice_model.diode.cj0_f", status="not_found"),
            ],
            actor=ACTOR,
        )
        self.assertEqual(1, len(report.written))
        self.assertEqual(["spice_model.diode.cj0_f"], report.not_found)
        self.assertEqual(1, self._count_specs())

    def test_value_kind_routed_to_correct_slot(self):
        ingest_spice_extraction(
            self.repo, MPN,
            [_row("spice_model.diode.is_a", 2.5e-9, value_kind="max")],
            actor=ACTOR,
        )
        row = self.storage.conn.execute(
            "SELECT min_val, typ_val, max_val FROM spec_values"
        ).fetchone()
        self.assertIsNone(row["typ_val"])
        self.assertIsNone(row["min_val"])
        self.assertEqual(2.5e-9, row["max_val"])

    def test_malformed_evidence_sha_rejected(self):
        bad = _row("spice_model.diode.is_a")
        bad["evidence"] = {"document_sha256": "short", "page": 3}
        report = ingest_spice_extraction(self.repo, MPN, [bad], actor=ACTOR)
        self.assertEqual("SPX_EVIDENCE_MISSING", report.rejected[0].error_code)

    def test_invalid_page_rejected(self):
        bad = _row("spice_model.diode.is_a")
        bad["evidence"] = {"document_sha256": SHA, "page": 0}
        report = ingest_spice_extraction(self.repo, MPN, [bad], actor=ACTOR)
        self.assertEqual("SPX_EVIDENCE_MISSING", report.rejected[0].error_code)

    def test_empty_batch_raises(self):
        with self.assertRaises(SpiceCardError) as ctx:
            ingest_spice_extraction(self.repo, MPN, [], actor=ACTOR)
        self.assertEqual("SPX_VALUE_INVALID", ctx.exception.code)

    def test_report_to_dict_shape(self):
        report = ingest_spice_extraction(
            self.repo, MPN,
            [_row("spice_model.diode.is_a", 2.5e-9)],
            actor=ACTOR,
        )
        d = report.to_dict()
        self.assertEqual(MPN, d["mpn"])
        self.assertEqual(1, len(d["written"]))
        self.assertEqual("unverified", d["written"][0]["trust"])
        self.assertIn("spec_value_id", d["written"][0])


if __name__ == "__main__":
    unittest.main()
