"""Phase 3 tests: spec EAV + trust gate (R4, R7, TV-R4-*, TV-R7-*)."""

import json
import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import VaultRepository, VaultRepositoryError, resolve_field_path
from bodesign_component_kb.storage import open_vault
from bodesign_component_kb.vault import spec_check

ACTOR = "test-agent"


class SpecTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.vault_dir = Path(self._temp.name) / "vault"
        self._saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
        self.addCleanup(self._restore_env)
        self.storage = open_vault(self.vault_dir)
        self.addCleanup(self.storage.close)
        self.repo = VaultRepository(self.storage)

    def _restore_env(self):
        if self._saved_env is not None:
            os.environ["BODESIGN_VAULT_DIR"] = self._saved_env

    def _ingest_chunk(self, mpn="AP2112K-3.3", content="Dropout Voltage 250 mV @ 300mA"):
        path = Path(self._temp.name) / f"ds_{mpn.lower().replace('.', '_')}.pdf"
        path.write_bytes(b"%PDF-1.4 " + mpn.encode())
        document = self.repo.ingest_document(path, "datasheet", "user-provided", [mpn], actor=ACTOR)
        self.repo.ingest_chunks(
            document.document_id,
            [{"chunk_kind": "table", "page_number": 5, "content": content, "extractor": "docxmcp@1.4"}],
            actor=ACTOR,
        )
        return self.storage.conn.execute("SELECT id FROM chunks ORDER BY id DESC").fetchone()["id"]


class FieldPathRegistryTests(SpecTestCase):
    def test_tv_r4_5_friendly_alias_resolves_to_canonical_path(self):
        self.assertEqual("electrical_characteristics.dropout_mv", resolve_field_path("dropout_mv"))
        self.assertEqual("recommended_operating_conditions.vin_min_v", resolve_field_path("vcc_min_v"))

    def test_canonical_dotted_path_passes_through(self):
        self.assertEqual(
            "thermal_characteristics.theta_ja_c_per_w",
            resolve_field_path("thermal_characteristics.theta_ja_c_per_w"),
        )

    def test_tv_r4_3_unknown_field_path_rejected_explicitly(self):
        for bogus in ("made_up.nonsense_v", "nonsense", "electrical_characteristics"):
            with self.assertRaises(VaultRepositoryError, msg=bogus) as ctx:
                resolve_field_path(bogus)
            self.assertEqual("VAULT-E401", ctx.exception.code)
            self.assertIn("candidates", str(ctx.exception))

    def test_write_with_unknown_path_does_not_touch_db(self):
        with self.assertRaises(VaultRepositoryError):
            self.repo.write_spec("AP2112K-3.3", "made_up.nonsense_v", value_num=1, actor=ACTOR)
        rows = self.storage.conn.execute("SELECT COUNT(*) FROM spec_values").fetchone()[0]
        self.assertEqual(0, rows)


class SpecWriteTests(SpecTestCase):
    def test_tv_r4_1_write_without_evidence_is_forced_unverified(self):
        row = self.repo.write_spec(
            "AP2112K-3.3", "electrical_characteristics.dropout_mv",
            value_num=250, unit="mV", confidence="verified",  # asked verified, no evidence
            actor=ACTOR,
        )
        self.assertEqual("unverified", row["confidence"])

    def test_write_with_evidence_chunk_can_be_verified(self):
        chunk_id = self._ingest_chunk()
        row = self.repo.write_spec(
            "AP2112K-3.3", "dropout_mv", value_num=250, unit="mV",
            evidence_chunk_id=chunk_id, confidence="verified", actor=ACTOR,
        )
        self.assertEqual("verified", row["confidence"])
        self.assertEqual("electrical_characteristics.dropout_mv", row["field_path"])

    def test_tv_r4_2_raw_verified_insert_without_evidence_aborts(self):
        component = self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            self.storage.conn.execute(
                "INSERT INTO spec_values (component_id, field_path, value_num, confidence)"
                " VALUES (?,?,?, 'verified')",
                (component["id"], "electrical_characteristics.dropout_mv", 250),
            )
        self.assertIn("verified spec requires evidence", str(ctx.exception))

    def test_raw_update_to_verified_without_evidence_aborts(self):
        row = self.repo.write_spec("AP2112K-3.3", "dropout_mv", value_num=250, actor=ACTOR)
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            self.storage.conn.execute(
                "UPDATE spec_values SET confidence='verified' WHERE id = ?", (row["id"],)
            )
        self.assertIn("verified spec requires evidence", str(ctx.exception))

    def test_all_value_slots_null_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.write_spec("AP2112K-3.3", "dropout_mv", actor=ACTOR)
        self.assertEqual("VAULT-E403", ctx.exception.code)

    def test_tv_r4_4_same_field_multiple_conditions_coexist(self):
        chunk_id = self._ingest_chunk()
        self.repo.write_spec(
            "AP2112K-3.3", "dropout_mv", value_num=250, condition="Iout=300mA, Tj=25C",
            evidence_chunk_id=chunk_id, confidence="verified", actor=ACTOR,
        )
        self.repo.write_spec(
            "AP2112K-3.3", "dropout_mv", value_num=400, condition="Iout=600mA, Tj=85C",
            evidence_chunk_id=chunk_id, confidence="verified", actor=ACTOR,
        )

        everything = self.repo.read_spec("AP2112K-3.3", "dropout_mv")
        self.assertEqual("found", everything["status"])
        self.assertEqual(2, len(everything["values"]))
        by_condition = self.repo.read_spec("AP2112K-3.3", "dropout_mv", condition="Iout=600mA, Tj=85C")
        self.assertEqual(1, len(by_condition["values"]))
        self.assertEqual(400, by_condition["values"][0]["value_num"])

    def test_read_spec_absent_and_no_field(self):
        absent = self.repo.read_spec("UNKNOWN-1", "dropout_mv")
        self.assertEqual("absent", absent["status"])
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        no_field = self.repo.read_spec("AP2112K-3.3", "dropout_mv")
        self.assertEqual("no-field", no_field["status"])

    def test_spec_writes_are_audited(self):
        self.repo.write_spec("AP2112K-3.3", "dropout_mv", value_num=250, actor=ACTOR)
        rows = self.storage.conn.execute(
            "SELECT actor, field FROM audit_log WHERE table_name = 'spec_values'"
        ).fetchall()
        self.assertEqual(1, len(rows))
        self.assertEqual(ACTOR, rows[0]["actor"])
        self.assertEqual("electrical_characteristics.dropout_mv", rows[0]["field"])


class PackagePinTests(SpecTestCase):
    def test_pinout_unique_per_component_package(self):
        self.repo.register_package("AP2112K-3.3", "SOT-23-5", actor=ACTOR)
        self.repo.write_pins(
            "AP2112K-3.3",
            [{"pin_number": "1", "pin_name": "VIN", "role": "power"}],
            package_name="SOT-23-5",
            actor=ACTOR,
        )
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.write_pins(
                "AP2112K-3.3",
                [{"pin_number": "1", "pin_name": "VIN-DUP"}],
                package_name="SOT-23-5",
                actor=ACTOR,
            )
        self.assertEqual("VAULT-E404", ctx.exception.code)

    def test_multiple_packages_pinouts_coexist(self):
        self.repo.register_package("STM32F405RGT6", "LQFP-64", actor=ACTOR)
        self.repo.register_package("STM32F405RGT6", "UFBGA-64", actor=ACTOR)
        self.repo.write_pins(
            "STM32F405RGT6", [{"pin_number": "1", "pin_name": "VBAT"}], package_name="LQFP-64", actor=ACTOR
        )
        self.repo.write_pins(
            "STM32F405RGT6", [{"pin_number": "1", "pin_name": "PA0"}], package_name="UFBGA-64", actor=ACTOR
        )
        pins = self.storage.conn.execute("SELECT COUNT(*) FROM pins").fetchone()[0]
        self.assertEqual(2, pins)
        packages = self.storage.conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
        self.assertEqual(2, packages)

    def test_pins_for_unregistered_package_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.write_pins(
                "AP2112K-3.3", [{"pin_number": "1", "pin_name": "VIN"}], package_name="QFN-16", actor=ACTOR
            )
        self.assertEqual("VAULT-E404", ctx.exception.code)


class GapsCompletenessQueueTests(SpecTestCase):
    def test_completeness_reports_explicit_gaps_not_empty_fakes(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        self.repo.record_gap("AP2112K-3.3", "pinout", "Pinout extraction is pending.", actor=ACTOR)

        report = self.repo.component_completeness("AP2112K-3.3")

        self.assertEqual("found", report["status"])
        self.assertEqual(0, report["has_pinout"])
        self.assertEqual(0, report["has_package"])
        self.assertEqual(0, report["has_electrical"])
        self.assertEqual(1, report["unresolved_gaps"])
        self.assertEqual(1, len(report["gaps"]))
        self.assertEqual("pinout", report["gaps"][0]["gap_kind"])

    def test_completeness_absent_for_unknown_component(self):
        self.assertEqual("absent", self.repo.component_completeness("UNKNOWN-1")["status"])

    def test_resolve_gap_audited_and_score_updates(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        gap = self.repo.record_gap("AP2112K-3.3", "electrical", "Specs pending.", actor=ACTOR)
        resolved = self.repo.resolve_gap(gap["id"], actor="gap-resolver")
        self.assertEqual(1, resolved["resolved"])
        audit = self.storage.conn.execute(
            "SELECT action FROM audit_log WHERE table_name='knowledge_gaps' AND action='resolve-gap'"
        ).fetchall()
        self.assertEqual(1, len(audit))
        self.assertEqual(0, self.repo.component_completeness("AP2112K-3.3")["unresolved_gaps"])

    def test_tv_r8_2_queue_priority_prefix_then_rank(self):
        for mpn in ("AP2112K-3.3", "W25Q128JVSIQ", "STM32F405RGT6"):
            self.repo.upsert_component(mpn, actor=ACTOR)
            self.repo.record_gap(mpn, "pinout", "Pinout pending.", actor=ACTOR)

        queue = self.repo.knowledge_queue()

        self.assertEqual(3, len(queue))
        priorities = {item["mpn"]: item["priority"] for item in queue}
        self.assertEqual("high", priorities["W25Q128JVSIQ"])
        self.assertEqual("high", priorities["STM32F405RGT6"])
        self.assertEqual("low", priorities["AP2112K-3.3"])
        self.assertEqual({"STM32F405RGT6", "W25Q128JVSIQ"}, {item["mpn"] for item in queue[:2]})
        self.assertEqual("AP2112K-3.3", queue[2]["mpn"])

    def test_queue_only_lists_components_with_open_gaps(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        self.assertEqual([], self.repo.knowledge_queue())


class SpecCheckIntegrationTests(SpecTestCase):
    """TV-R7-1: spec_check four states + origin labeling (task 3.6)."""

    def test_verified_hit_carries_server_vault_origin(self):
        chunk_id = self._ingest_chunk()
        self.repo.write_spec(
            "AP2112K-3.3", "dropout_mv", value_num=250, unit="mV",
            evidence_chunk_id=chunk_id, confidence="verified", actor=ACTOR,
        )

        out = spec_check("AP2112K-3.3", "dropout_mv", repository=self.repo)

        self.assertEqual("verified", out["status"])
        self.assertEqual("server-vault", out["origin"])
        self.assertEqual(250, out["value"])
        self.assertEqual("chunk:%d" % chunk_id, out["source"])

    def test_unverified_server_value_reported_with_origin(self):
        self.repo.write_spec("AP2112K-3.3", "dropout_mv", value_num=250, actor=ACTOR)
        out = spec_check("AP2112K-3.3", "dropout_mv", repository=self.repo)
        self.assertEqual("unverified", out["status"])
        self.assertEqual("server-vault", out["origin"])

    def test_no_field_when_component_known_but_field_unrecorded(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        out = spec_check("AP2112K-3.3", "iout_max_ma", repository=self.repo)
        self.assertEqual("no-field", out["status"])
        self.assertEqual("server-vault", out["origin"])

    def test_absent_when_neither_source_knows_component(self):
        out = spec_check("UNKNOWN-1", "vin_max_v", repository=self.repo)
        self.assertEqual("absent", out["status"])

    def test_claimed_value_match_and_mismatch(self):
        chunk_id = self._ingest_chunk()
        self.repo.write_spec(
            "AP2112K-3.3", "dropout_mv", value_num=250,
            evidence_chunk_id=chunk_id, confidence="verified", actor=ACTOR,
        )
        self.assertTrue(spec_check("AP2112K-3.3", "dropout_mv", claimed_value=250, repository=self.repo)["matches"])
        self.assertFalse(spec_check("AP2112K-3.3", "dropout_mv", claimed_value=999, repository=self.repo)["matches"])

    def test_client_cache_path_unchanged_and_labeled(self):
        cache_root = Path(self._temp.name) / "datasheets"
        extract_dir = cache_root / "extracted"
        extract_dir.mkdir(parents=True)
        extraction = {
            "mpn": "TLV75733PDRVR", "category": "linear_regulator",
            "electrical_characteristics": {"dropout_mv": 425},
            "extraction_metadata": {"source_pdf": "TLV75733PDRVR.pdf"},
        }
        (extract_dir / "TLV75733PDRVR.json").write_text(json.dumps(extraction), encoding="utf-8")
        (extract_dir / "manifest.json").write_text(
            json.dumps({"version": 2, "extractions": {
                "TLV75733PDRVR": {"file": "TLV75733PDRVR.json", "mpn": "TLV75733PDRVR"}
            }}), encoding="utf-8",
        )

        # without repository: pure client-cache behavior (regression guard)
        no_repo = spec_check("TLV75733PDRVR", "dropout_mv", root=cache_root)
        self.assertEqual("verified", no_repo["status"])
        self.assertEqual("client-cache", no_repo["origin"])
        # with repository that does NOT know the part: falls through to client cache
        with_repo = spec_check("TLV75733PDRVR", "dropout_mv", root=cache_root, repository=self.repo)
        self.assertEqual("verified", with_repo["status"])
        self.assertEqual("client-cache", with_repo["origin"])


class MigrationTests(unittest.TestCase):
    def test_existing_v2_db_migrates_cleanly_to_v3(self):
        with TemporaryDirectory() as temp:
            vault_dir = Path(temp) / "vault"
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                from bodesign_component_kb import storage as storage_module

                original_migrations = storage_module.MIGRATIONS
                original_version = storage_module.SCHEMA_VERSION
                storage_module.MIGRATIONS = original_migrations[:2]
                storage_module.SCHEMA_VERSION = 2
                try:
                    v2_storage = open_vault(vault_dir)
                    repo = VaultRepository(v2_storage)
                    repo.upsert_component("STM32F405RGT6", actor=ACTOR)
                    self.assertEqual(2, v2_storage.conn.execute("PRAGMA user_version").fetchone()[0])
                    v2_storage.close()
                finally:
                    storage_module.MIGRATIONS = original_migrations
                    storage_module.SCHEMA_VERSION = original_version

                v3_storage = open_vault(vault_dir)
                try:
                    from bodesign_component_kb.storage import SCHEMA_VERSION
                    self.assertEqual(
                        SCHEMA_VERSION, v3_storage.conn.execute("PRAGMA user_version").fetchone()[0]
                    )
                    repo = VaultRepository(v3_storage)
                    self.assertEqual("found", repo.resolve("STM32F405RGT6").status)
                    names = {
                        row[0]
                        for row in v3_storage.conn.execute(
                            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                        )
                    }
                    for required in ("spec_values", "packages", "pins", "knowledge_gaps",
                                     "component_completeness", "knowledge_queue"):
                        self.assertIn(required, names)
                finally:
                    v3_storage.close()
            finally:
                if saved_env is not None:
                    os.environ["BODESIGN_VAULT_DIR"] = saved_env

    def test_fresh_db_lands_on_v3(self):
        with TemporaryDirectory() as temp:
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                storage = open_vault(Path(temp) / "vault")
                try:
                    from bodesign_component_kb.storage import SCHEMA_VERSION
                    self.assertEqual(
                        SCHEMA_VERSION, storage.conn.execute("PRAGMA user_version").fetchone()[0]
                    )
                finally:
                    storage.close()
            finally:
                if saved_env is not None:
                    os.environ["BODESIGN_VAULT_DIR"] = saved_env


if __name__ == "__main__":
    unittest.main()
