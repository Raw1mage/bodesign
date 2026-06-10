"""Phase 5 tests: usage writeback + sourcing snapshots + client cache import
(R8, R9 import scenario, TV-R8-*, TV-R9-1) and migration v3->v4."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import VaultRepository, VaultRepositoryError
from bodesign_component_kb.storage import SCHEMA_VERSION, open_vault

ACTOR = "test-agent"


class UsageTestCase(unittest.TestCase):
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


class UsageRecordingTests(UsageTestCase):
    def test_tv_r8_1_usage_aggregates_across_projects(self):
        self.repo.record_usage(
            "GRM1555C1H180JA01", "proj-a", refdes=["C1", "C2"], workflow="forward", actor=ACTOR
        )
        self.repo.record_usage(
            "GRM1555C1H180JA01", "proj-b", refdes=["C7"], workflow="reverse", actor=ACTOR
        )

        out = self.repo.occurrences("GRM1555C1H180JA01")

        self.assertEqual("found", out["status"])
        self.assertEqual(3, out["total_occurrences"])
        self.assertEqual(2, out["project_count"])
        by_project = {p["project_id"]: p for p in out["projects"]}
        self.assertEqual(["C1", "C2"], by_project["proj-a"]["refdes"])
        self.assertEqual("forward", by_project["proj-a"]["workflow"])
        self.assertEqual(["C7"], by_project["proj-b"]["refdes"])

    def test_same_project_rerecord_replaces_not_duplicates(self):
        self.repo.record_usage("GRM1555C1H180JA01", "proj-a", refdes=["C1"], actor=ACTOR)
        self.repo.record_usage("GRM1555C1H180JA01", "proj-a", refdes=["C1", "C2", "C3"], actor=ACTOR)
        out = self.repo.occurrences("GRM1555C1H180JA01")
        self.assertEqual(1, out["project_count"])
        self.assertEqual(3, out["total_occurrences"])
        rows = self.storage.conn.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        self.assertEqual(1, rows)

    def test_missing_project_id_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.record_usage("GRM1555C1H180JA01", "  ", refdes=["C1"], actor=ACTOR)
        self.assertEqual("VAULT-E801", ctx.exception.code)

    def test_occurrences_absent_for_unknown_component(self):
        self.assertEqual("absent", self.repo.occurrences("UNKNOWN-1")["status"])

    def test_usage_writes_are_audited(self):
        self.repo.record_usage("GRM1555C1H180JA01", "proj-a", refdes=["C1"], actor=ACTOR)
        rows = self.storage.conn.execute(
            "SELECT actor FROM audit_log WHERE table_name = 'usage'"
        ).fetchall()
        self.assertEqual(1, len(rows))
        self.assertEqual(ACTOR, rows[0]["actor"])

    def test_tv_r8_2_queue_ranks_by_real_occurrences(self):
        # AP2112K: 4 refdes across projects (>=3 -> normal); RT9080: 1 (low);
        # W25Q: prefix -> high regardless of usage.
        for mpn in ("AP2112K-3.3", "RT9080-33GJ5", "W25Q128JVSIQ"):
            self.repo.upsert_component(mpn, actor=ACTOR)
            self.repo.record_gap(mpn, "pinout", "Pinout pending.", actor=ACTOR)
        self.repo.record_usage("AP2112K-3.3", "proj-a", refdes=["U1", "U2"], actor=ACTOR)
        self.repo.record_usage("AP2112K-3.3", "proj-b", refdes=["U3", "U4"], actor=ACTOR)
        self.repo.record_usage("RT9080-33GJ5", "proj-a", refdes=["U9"], actor=ACTOR)

        queue = self.repo.knowledge_queue()

        self.assertEqual(3, len(queue))
        by_mpn = {item["mpn"]: item for item in queue}
        self.assertEqual("high", by_mpn["W25Q128JVSIQ"]["priority"])
        self.assertEqual("normal", by_mpn["AP2112K-3.3"]["priority"])
        self.assertEqual(4, by_mpn["AP2112K-3.3"]["occurrence_count"])
        self.assertEqual("low", by_mpn["RT9080-33GJ5"]["priority"])
        self.assertEqual(
            ["W25Q128JVSIQ", "AP2112K-3.3", "RT9080-33GJ5"], [item["mpn"] for item in queue]
        )


class SourcingSnapshotTests(UsageTestCase):
    def test_snapshot_round_trip_marked_point_in_time(self):
        self.repo.record_sourcing_snapshot(
            "W25Q128JVSIQ", "lcsc", distributor_pn="C97521", stock=12000, moq=1,
            price_breaks=[{"qty": 1, "unit_price": 1.2, "currency": "USD"}],
            actor=ACTOR,
        )
        out = self.repo.sourcing_snapshots("W25Q128JVSIQ")
        self.assertEqual("found", out["status"])
        self.assertTrue(out["point_in_time"])
        self.assertEqual(1, len(out["snapshots"]))
        snapshot = out["snapshots"][0]
        self.assertEqual("C97521", snapshot["distributor_pn"])
        self.assertEqual([{"qty": 1, "unit_price": 1.2, "currency": "USD"}], snapshot["price_breaks"])
        self.assertTrue(snapshot["snapshot_at"])

    def test_snapshots_newest_first_and_filterable(self):
        self.repo.record_sourcing_snapshot("W25Q128JVSIQ", "lcsc", stock=100, actor=ACTOR)
        self.repo.record_sourcing_snapshot("W25Q128JVSIQ", "digikey", stock=50, actor=ACTOR)
        all_snapshots = self.repo.sourcing_snapshots("W25Q128JVSIQ")["snapshots"]
        self.assertEqual(2, len(all_snapshots))
        only_lcsc = self.repo.sourcing_snapshots("W25Q128JVSIQ", distributor="lcsc")["snapshots"]
        self.assertEqual(1, len(only_lcsc))
        self.assertEqual("lcsc", only_lcsc[0]["distributor"])

    def test_missing_distributor_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.record_sourcing_snapshot("W25Q128JVSIQ", "", actor=ACTOR)
        self.assertEqual("VAULT-E802", ctx.exception.code)

    def test_substitution_round_trip_and_unverified_without_evidence(self):
        verified = self.repo.record_substitution(
            "AP2112K-3.3", "RT9080-33GJ5", "functional",
            differences="Lower Iq, different pinout", evidence_ref="chunk:9",
            confidence="verified", actor=ACTOR,
        )
        self.assertEqual("verified", verified["confidence"])
        unverified = self.repo.record_substitution(
            "AP2112K-3.3", "ME6211C33", "drop-in", confidence="verified", actor=ACTOR,
        )
        self.assertEqual("unverified", unverified["confidence"])  # no evidence -> forced
        subs = self.repo.substitutions("AP2112K-3.3")
        self.assertEqual(2, len(subs))
        self.assertEqual({"RT9080-33GJ5", "ME6211C33"}, {s["substitute_mpn"] for s in subs})

    def test_substitution_pair_unique(self):
        self.repo.record_substitution("AP2112K-3.3", "RT9080-33GJ5", "functional", actor=ACTOR)
        again = self.repo.record_substitution("AP2112K-3.3", "RT9080-33GJ5", "partial", actor=ACTOR)
        self.assertEqual("functional", again["compatibility"])  # existing row returned
        rows = self.storage.conn.execute("SELECT COUNT(*) FROM substitutions").fetchone()[0]
        self.assertEqual(1, rows)


def _write_cache(root: Path, entries: dict):
    """Minimal `datasheets`-skill cache (same shape as test_datasheet_vault)."""
    extract_dir = root / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 2, "extractions": {}}
    for mpn, extraction in entries.items():
        filename = f"{mpn}.json"
        (extract_dir / filename).write_text(json.dumps(extraction), encoding="utf-8")
        manifest["extractions"][mpn] = {"file": filename, "mpn": mpn}
    (extract_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class ClientCacheImportTests(UsageTestCase):
    def _cache_root(self) -> Path:
        return Path(self._temp.name) / "datasheets"

    def test_tv_r9_1_no_source_import_is_unverified_and_conflict_kept(self):
        # Pre-existing verified vault row (evidence-backed via source_note).
        self.repo.write_spec(
            "W25Q128JVSIQ", "recommended_operating_conditions.vin_min_v",
            value_num=2.7, source_note="datasheet rev5 p.12", confidence="verified",
            actor=ACTOR,
        )
        _write_cache(self._cache_root(), {
            "W25Q128JVSIQ": {
                "mpn": "W25Q128JVSIQ", "category": "memory",
                "recommended_operating_conditions": {"vin_min_v": 2.5},
                "extraction_metadata": {"source_pdf": None, "source_note": ""},
            },
        })

        report = self.repo.import_client_cache(self._cache_root(), actor=ACTOR)

        self.assertEqual(1, report["specs_written"])
        self.assertEqual(1, len(report["conflicts"]))
        self.assertEqual("VAULT-E903", report["error_code"])
        conflict = report["conflicts"][0]
        self.assertEqual(2.7, conflict["existing_value"])
        self.assertEqual(2.5, conflict["imported_value"])
        self.assertEqual("unverified", conflict["imported_confidence"])
        rows = self.storage.conn.execute(
            "SELECT value_num, confidence, source_note FROM spec_values ORDER BY id"
        ).fetchall()
        self.assertEqual(2, len(rows))  # both kept, no overwrite
        self.assertEqual(2.7, rows[0]["value_num"])
        self.assertEqual("verified", rows[0]["confidence"])
        self.assertEqual(2.5, rows[1]["value_num"])
        self.assertEqual("unverified", rows[1]["confidence"])
        self.assertTrue(rows[1]["source_note"].startswith("client-cache-import"))

    def test_import_with_real_source_can_be_verified(self):
        _write_cache(self._cache_root(), {
            "TLV75733PDRVR": {
                "mpn": "TLV75733PDRVR", "category": "linear_regulator",
                "electrical_characteristics": {"dropout_mv": 425},
                "extraction_metadata": {"source_pdf": "TLV75733PDRVR.pdf"},
            },
        })
        report = self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        self.assertEqual(1, report["specs_written"])
        self.assertEqual([], report["conflicts"])
        row = self.storage.conn.execute("SELECT * FROM spec_values").fetchone()
        self.assertEqual("verified", row["confidence"])
        self.assertIn("TLV75733PDRVR.pdf", row["source_note"])

    def test_reimport_same_manifest_is_idempotent(self):
        _write_cache(self._cache_root(), {
            "TLV75733PDRVR": {
                "mpn": "TLV75733PDRVR",
                "electrical_characteristics": {"dropout_mv": 425, "vref_v": 3.3},
                "extraction_metadata": {"source_pdf": "TLV75733PDRVR.pdf"},
            },
        })
        first = self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        self.assertEqual(2, first["specs_written"])
        second = self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        self.assertEqual(0, second["specs_written"])
        self.assertEqual(2, second["skipped_duplicates"])
        self.assertEqual([], second["conflicts"])
        rows = self.storage.conn.execute("SELECT COUNT(*) FROM spec_values").fetchone()[0]
        self.assertEqual(2, rows)

    def test_import_provenance_recorded(self):
        _write_cache(self._cache_root(), {
            "TLV75733PDRVR": {
                "mpn": "TLV75733PDRVR",
                "electrical_characteristics": {"dropout_mv": 425},
                "extraction_metadata": {},
            },
        })
        self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        row = self.storage.conn.execute("SELECT * FROM spec_values").fetchone()
        self.assertEqual("unverified", row["confidence"])
        self.assertEqual("client-cache-import", row["source_note"])

    def test_missing_manifest_is_explicit_error(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        self.assertEqual("VAULT-E902", ctx.exception.code)

    def test_malformed_manifest_is_explicit_error(self):
        extract_dir = self._cache_root() / "extracted"
        extract_dir.mkdir(parents=True)
        (extract_dir / "manifest.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        self.assertEqual("VAULT-E902", ctx.exception.code)

    def test_legacy_index_json_accepted(self):
        extract_dir = self._cache_root() / "extracted"
        extract_dir.mkdir(parents=True)
        extraction = {
            "mpn": "TLV75733PDRVR",
            "electrical_characteristics": {"dropout_mv": 425},
            "extraction_metadata": {"source_pdf": "TLV75733PDRVR.pdf"},
        }
        (extract_dir / "TLV75733PDRVR.json").write_text(json.dumps(extraction), encoding="utf-8")
        (extract_dir / "index.json").write_text(json.dumps({
            "version": 1,
            "extractions": {"TLV75733PDRVR": {"file": "TLV75733PDRVR.json", "mpn": "TLV75733PDRVR"}},
        }), encoding="utf-8")
        report = self.repo.import_client_cache(self._cache_root(), actor=ACTOR)
        self.assertEqual(1, report["specs_written"])


class MigrationTests(unittest.TestCase):
    def test_existing_v3_db_migrates_cleanly_to_v4(self):
        with TemporaryDirectory() as temp:
            vault_dir = Path(temp) / "vault"
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                from bodesign_component_kb import storage as storage_module

                original_migrations = storage_module.MIGRATIONS
                original_version = storage_module.SCHEMA_VERSION
                storage_module.MIGRATIONS = original_migrations[:3]
                storage_module.SCHEMA_VERSION = 3
                try:
                    v3_storage = open_vault(vault_dir)
                    repo = VaultRepository(v3_storage)
                    repo.upsert_component("STM32F405RGT6", actor=ACTOR)
                    repo.record_gap("STM32F405RGT6", "pinout", "Pinout pending.", actor=ACTOR)
                    self.assertEqual(3, v3_storage.conn.execute("PRAGMA user_version").fetchone()[0])
                    v3_storage.close()
                finally:
                    storage_module.MIGRATIONS = original_migrations
                    storage_module.SCHEMA_VERSION = original_version

                v4_storage = open_vault(vault_dir)
                try:
                    self.assertEqual(
                        SCHEMA_VERSION, v4_storage.conn.execute("PRAGMA user_version").fetchone()[0]
                    )
                    repo = VaultRepository(v4_storage)
                    self.assertEqual("found", repo.resolve("STM32F405RGT6").status)
                    names = {
                        row[0]
                        for row in v4_storage.conn.execute(
                            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                        )
                    }
                    for required in ("usage", "sourcing_snapshots", "substitutions", "knowledge_queue"):
                        self.assertIn(required, names)
                    # rebuilt view reads real usage totals
                    repo.record_usage("STM32F405RGT6", "proj-a", refdes=["U1", "U2"], actor=ACTOR)
                    queue = repo.knowledge_queue()
                    self.assertEqual(2, queue[0]["occurrence_count"])
                finally:
                    v4_storage.close()
            finally:
                if saved_env is not None:
                    os.environ["BODESIGN_VAULT_DIR"] = saved_env

    def test_fresh_db_lands_on_schema_version(self):
        with TemporaryDirectory() as temp:
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                storage = open_vault(Path(temp) / "vault")
                try:
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
