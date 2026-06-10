import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import VaultRepository, VaultRepositoryError
from bodesign_component_kb.storage import (
    VaultStorageError,
    consistency_scan,
    open_vault,
    resolve_vault_dir,
    write_blob,
)

ACTOR = "test-agent"


class VaultTestCase(unittest.TestCase):
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

    def _fixture_file(self, name, content):
        path = Path(self._temp.name) / name
        path.write_bytes(content)
        return path


class IdentityTests(VaultTestCase):
    def test_tv_r1_1_upsert_is_idempotent(self):
        first = self.repo.upsert_component("STM32F405RGT6", actor=ACTOR)
        second = self.repo.upsert_component("STM32F405RGT6", actor=ACTOR)

        self.assertEqual("component:stm32f405rgt6", first["canonical_key"])
        self.assertEqual(first["id"], second["id"])
        row_count = self.storage.conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        self.assertEqual(1, row_count)

    def test_tv_r1_2_alias_resolves_to_canonical_record(self):
        self.repo.upsert_component("W25Q128JVSIQ", actor=ACTOR)
        self.repo.add_alias("W25Q128JVSIQ", "C97521", "distributor", distributor="lcsc", actor=ACTOR)

        result = self.repo.resolve("C97521")

        self.assertEqual("found", result.status)
        self.assertEqual("component:w25q128jvsiq", result.canonical_key)
        self.assertEqual("distributor", result.hit_alias_type)

    def test_tv_r1_3_unknown_mpn_returns_explicit_absent(self):
        result = self.repo.resolve("NOTAPART-9999")

        self.assertEqual("absent", result.status)
        self.assertIsNone(result.component)
        row_count = self.storage.conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        self.assertEqual(0, row_count)

    def test_empty_mpn_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.upsert_component("   ", actor=ACTOR)
        self.assertEqual("VAULT-E101", ctx.exception.code)

    def test_alias_conflict_is_not_remapped(self):
        self.repo.upsert_component("W25Q128JVSIQ", actor=ACTOR)
        self.repo.upsert_component("W25Q64JVSIQ", actor=ACTOR)
        self.repo.add_alias("W25Q128JVSIQ", "C97521", "distributor", distributor="lcsc", actor=ACTOR)

        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.add_alias("W25Q64JVSIQ", "C97521", "distributor", distributor="lcsc", actor=ACTOR)
        self.assertEqual("VAULT-E102", ctx.exception.code)
        self.assertIn("component:w25q128jvsiq", str(ctx.exception))


class DocumentTests(VaultTestCase):
    def test_tv_r2_1_sha256_dedup_links_both_mpns(self):
        pdf = self._fixture_file("ds_ap2112k.pdf", b"%PDF-1.4 ap2112k fixture")
        first = self.repo.ingest_document(pdf, "datasheet", "user-provided", ["AP2112K-3.3"], actor=ACTOR)
        second = self.repo.ingest_document(pdf, "datasheet", "user-provided", ["AP2112K-1.8"], actor=ACTOR)

        self.assertFalse(first.dedup_hit)
        self.assertTrue(second.dedup_hit)
        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(1, second.links_added)
        blob_files = [path for path in (self.vault_dir / "blobs").rglob("*") if path.is_file()]
        self.assertEqual(1, len(blob_files))
        document_rows = self.storage.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        self.assertEqual(1, document_rows)
        link_rows = self.storage.conn.execute("SELECT COUNT(*) FROM component_documents").fetchone()[0]
        self.assertEqual(2, link_rows)

    def test_tv_r2_2_revision_chain_latest_first_history_listable(self):
        rev4 = self._fixture_file("ds_w25q128_rev4.pdf", b"%PDF-1.4 w25q128 rev4")
        rev5 = self._fixture_file("ds_w25q128_rev5.pdf", b"%PDF-1.4 w25q128 rev5")
        self.repo.ingest_document(rev4, "datasheet", "user-provided", ["W25Q128JVSIQ"], revision="Rev. 4", actor=ACTOR)
        self.repo.ingest_document(rev5, "datasheet", "user-provided", ["W25Q128JVSIQ"], revision="Rev. 5", actor=ACTOR)

        history = self.repo.list_documents("W25Q128JVSIQ")
        latest = self.repo.latest_document("W25Q128JVSIQ")

        self.assertEqual(2, len(history))
        self.assertEqual("Rev. 5", history[0]["revision"])
        self.assertEqual("Rev. 4", history[1]["revision"])
        self.assertEqual("Rev. 5", latest["revision"])

    def test_tv_r2_3_provenance_is_mandatory(self):
        pdf = self._fixture_file("ds_ap2112k.pdf", b"%PDF-1.4 ap2112k fixture")
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.ingest_document(pdf, "datasheet", None, ["AP2112K-3.3"], actor=ACTOR)
        self.assertEqual("VAULT-E201", ctx.exception.code)
        document_rows = self.storage.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        self.assertEqual(0, document_rows)

    def test_blob_written_before_commit_failure_leaves_no_db_row(self):
        pdf = self._fixture_file("ds_orphan.pdf", b"%PDF-1.4 orphan fixture")
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.ingest_document(pdf, "datasheet", "user-provided", ["   "], actor=ACTOR)
        self.assertEqual("VAULT-E101", ctx.exception.code)

        document_rows = self.storage.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        self.assertEqual(0, document_rows)
        blob_files = [path for path in (self.vault_dir / "blobs").rglob("*") if path.is_file()]
        self.assertEqual(1, len(blob_files))
        report = consistency_scan(self.storage)
        self.assertEqual(1, len(report.blobs_without_records))
        self.assertEqual(0, len(report.records_without_blobs))
        self.assertFalse(report.clean)

    def test_blob_dedup_does_not_rewrite(self):
        pdf = self._fixture_file("dup.pdf", b"%PDF-1.4 dedup fixture")
        sha_a, rel_a = write_blob(self.vault_dir, pdf)
        target = self.vault_dir / rel_a
        first_mtime = target.stat().st_mtime_ns
        sha_b, rel_b = write_blob(self.vault_dir, pdf)
        self.assertEqual(sha_a, sha_b)
        self.assertEqual(rel_a, rel_b)
        self.assertEqual(first_mtime, target.stat().st_mtime_ns)


class AuditTests(VaultTestCase):
    def test_tv_r7_2_audit_log_update_and_delete_abort(self):
        self.repo.upsert_component("STM32F405RGT6", actor=ACTOR)
        with self.assertRaises(sqlite3.IntegrityError) as update_ctx:
            self.storage.conn.execute("UPDATE audit_log SET actor='x' WHERE id=1")
        self.assertIn("append-only", str(update_ctx.exception))
        with self.assertRaises(sqlite3.IntegrityError) as delete_ctx:
            self.storage.conn.execute("DELETE FROM audit_log WHERE id=1")
        self.assertIn("append-only", str(delete_ctx.exception))

    def test_audit_row_appended_for_every_write_with_actor(self):
        self.repo.upsert_component("W25Q128JVSIQ", actor="agent-a")
        self.repo.add_alias("W25Q128JVSIQ", "C97521", "distributor", distributor="lcsc", actor="agent-b")
        pdf = self._fixture_file("ds.pdf", b"%PDF-1.4 audit fixture")
        self.repo.ingest_document(pdf, "datasheet", "user-provided", ["W25Q128JVSIQ"], actor="agent-c")

        rows = self.storage.conn.execute("SELECT actor, table_name FROM audit_log ORDER BY id").fetchall()
        actors = {row["actor"] for row in rows}
        tables = {row["table_name"] for row in rows}
        self.assertEqual({"agent-a", "agent-b", "agent-c"}, actors)
        self.assertIn("components", tables)
        self.assertIn("component_aliases", tables)
        self.assertIn("documents", tables)
        self.assertIn("component_documents", tables)

    def test_write_without_actor_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.upsert_component("STM32F405RGT6")
        self.assertEqual("VAULT-E702", ctx.exception.code)
        pdf = self._fixture_file("ds.pdf", b"%PDF-1.4")
        with self.assertRaises(VaultRepositoryError) as ingest_ctx:
            self.repo.ingest_document(pdf, "datasheet", "user-provided", ["AP2112K-3.3"])
        self.assertEqual("VAULT-E702", ingest_ctx.exception.code)


class StorageLifecycleTests(VaultTestCase):
    def test_tv_r10_1_reopen_keeps_data(self):
        self.repo.upsert_component("STM32F405RGT6", actor=ACTOR)
        pdf = self._fixture_file("ds.pdf", b"%PDF-1.4 restart fixture")
        self.repo.ingest_document(pdf, "datasheet", "user-provided", ["STM32F405RGT6"], actor=ACTOR)
        self.storage.close()

        reopened = open_vault(self.vault_dir)
        self.addCleanup(reopened.close)
        repo = VaultRepository(reopened)
        result = repo.resolve("STM32F405RGT6")
        self.assertEqual("found", result.status)
        report = consistency_scan(reopened)
        self.assertTrue(report.clean)

    def test_tv_r10_1_corrupt_db_fails_fast_without_recreate(self):
        self.storage.close()
        db_path = self.vault_dir / "vault.db"
        garbage = b"this is definitely not a sqlite database " * 16
        db_path.write_bytes(garbage)

        with self.assertRaises(VaultStorageError) as ctx:
            open_vault(self.vault_dir)
        self.assertEqual("VAULT-E001", ctx.exception.code)
        self.assertEqual(garbage, db_path.read_bytes())

    def test_vault_dir_resolution_requires_env_or_argument(self):
        with self.assertRaises(VaultStorageError) as ctx:
            resolve_vault_dir(None)
        self.assertEqual("VAULT-E002", ctx.exception.code)

    def test_vault_dir_env_takes_precedence(self):
        env_dir = Path(self._temp.name) / "env-vault"
        os.environ["BODESIGN_VAULT_DIR"] = str(env_dir)
        try:
            resolved = resolve_vault_dir(self.vault_dir)
        finally:
            del os.environ["BODESIGN_VAULT_DIR"]
        self.assertEqual(env_dir, resolved)

    def test_schema_version_beyond_known_is_rejected(self):
        self.storage.close()
        raw = sqlite3.connect(self.vault_dir / "vault.db")
        raw.execute("PRAGMA user_version = 99")
        raw.close()

        with self.assertRaises(VaultStorageError) as ctx:
            open_vault(self.vault_dir)
        self.assertEqual("VAULT-E003", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
