"""Phase 2 tests: chunks + FTS5 full-text search (R3, TV-R3-*)."""

import json
import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import VaultRepository, VaultRepositoryError
from bodesign_component_kb.storage import open_vault
from bodesign_doc_core import DocumentSourceChunk

ACTOR = "test-agent"


class ChunkTestCase(unittest.TestCase):
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

    def _ingest_fixture_document(self, name="ds_ap2112k.pdf", mpns=("AP2112K-3.3",)):
        path = Path(self._temp.name) / name
        path.write_bytes(b"%PDF-1.4 " + name.encode())
        result = self.repo.ingest_document(path, "datasheet", "user-provided", list(mpns), actor=ACTOR)
        return result.document_id

    def _chunk(self, **overrides):
        chunk = {
            "chunk_kind": "table",
            "page_number": 5,
            "anchor": {"bbox": [40, 120, 520, 380]},
            "content": "Dropout Voltage 250 mV @ 300mA",
            "extractor": "docxmcp@1.4",
        }
        chunk.update(overrides)
        return chunk


class ChunkIngestTests(ChunkTestCase):
    def test_tv_r3_1_chunk_ingest_carries_anchor_and_extractor(self):
        document_id = self._ingest_fixture_document()

        result = self.repo.ingest_chunks(document_id, [self._chunk()], actor=ACTOR)

        self.assertEqual(1, result.chunks_added)
        self.assertEqual(0, result.stale_marked)
        row = self.storage.conn.execute("SELECT * FROM chunks").fetchone()
        self.assertEqual(document_id, row["document_id"])
        self.assertEqual("table", row["chunk_kind"])
        self.assertEqual(5, row["page_number"])
        self.assertEqual([40, 120, 520, 380], json.loads(row["anchor"])["bbox"])
        self.assertEqual("docxmcp@1.4", row["extractor"])
        self.assertEqual(0, row["stale"])
        fts_hits = self.storage.conn.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'dropout'"
        ).fetchall()
        self.assertEqual([row["id"]], [hit["rowid"] for hit in fts_hits])

    def test_unknown_document_id_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.ingest_chunks(999, [self._chunk()], actor=ACTOR)
        self.assertEqual("VAULT-E301", ctx.exception.code)

    def test_missing_required_fields_rejected_atomically(self):
        document_id = self._ingest_fixture_document()
        for missing_field, override in (
            ("chunk_kind", {"chunk_kind": None}),
            ("chunk_kind", {"chunk_kind": "bogus-kind"}),
            ("content", {"content": "   "}),
            ("extractor", {"extractor": None}),
        ):
            with self.assertRaises(VaultRepositoryError, msg=missing_field) as ctx:
                self.repo.ingest_chunks(document_id, [self._chunk(), self._chunk(**override)], actor=ACTOR)
            self.assertEqual("VAULT-E302", ctx.exception.code)
            self.assertIn(missing_field, str(ctx.exception))
        chunk_count = self.storage.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        self.assertEqual(0, chunk_count)

    def test_empty_batch_rejected(self):
        document_id = self._ingest_fixture_document()
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.ingest_chunks(document_id, [], actor=ACTOR)
        self.assertEqual("VAULT-E302", ctx.exception.code)

    def test_chunk_writes_are_audited_and_require_actor(self):
        document_id = self._ingest_fixture_document()
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.ingest_chunks(document_id, [self._chunk()])
        self.assertEqual("VAULT-E702", ctx.exception.code)

        self.repo.ingest_chunks(document_id, [self._chunk()], actor=ACTOR)
        audit_rows = self.storage.conn.execute(
            "SELECT actor, action FROM audit_log WHERE table_name = 'chunks'"
        ).fetchall()
        self.assertEqual(1, len(audit_rows))
        self.assertEqual(ACTOR, audit_rows[0]["actor"])
        self.assertEqual("insert", audit_rows[0]["action"])

    def test_doc_core_source_chunk_adapter(self):
        document_id = self._ingest_fixture_document()
        source_chunks = [
            DocumentSourceChunk(
                source_id="proj-doc-src-ds",
                source_path="/tmp/ds_ap2112k.pdf",
                chunk_id="proj-doc-src-ds-chunk-1",
                kind="pdf-text",
                text="Output voltage accuracy 1.5% maximum dropout 250mV",
                page_hint=3,
                char_start=0,
                char_end=50,
            )
        ]

        result = self.repo.ingest_source_chunks(document_id, source_chunks, extractor="doc-core@0.1", actor=ACTOR)

        self.assertEqual(1, result.chunks_added)
        row = self.storage.conn.execute("SELECT * FROM chunks").fetchone()
        self.assertEqual("text", row["chunk_kind"])
        self.assertEqual(3, row["page_number"])
        self.assertEqual("doc-core@0.1", row["extractor"])
        anchor = json.loads(row["anchor"])
        self.assertEqual("proj-doc-src-ds-chunk-1", anchor["chunk_id"])
        self.assertEqual(0, anchor["char_start"])
        self.assertEqual(50, anchor["char_end"])


class ChunkSearchTests(ChunkTestCase):
    def test_tv_r3_2_search_returns_bm25_hit_with_mpn_document_page(self):
        document_id = self._ingest_fixture_document(mpns=("AP2112K-3.3", "AP2112K-1.8"))
        other_document_id = self._ingest_fixture_document(name="ds_w25q128.pdf", mpns=("W25Q128JVSIQ",))
        self.repo.ingest_chunks(
            document_id,
            [
                self._chunk(),
                self._chunk(chunk_kind="text", page_number=1, content="General purpose 600mA CMOS LDO"),
            ],
            actor=ACTOR,
        )
        self.repo.ingest_chunks(
            other_document_id,
            [self._chunk(chunk_kind="text", page_number=8, content="Quad SPI flash erase timing")],
            actor=ACTOR,
        )

        hits = self.repo.search_chunks("dropout voltage")

        self.assertGreaterEqual(len(hits), 1)
        first = hits[0]
        self.assertEqual(["AP2112K-1.8", "AP2112K-3.3"], first.mpns)
        self.assertEqual("ds_ap2112k.pdf", first.filename)
        self.assertEqual(document_id, first.document_id)
        self.assertEqual(5, first.page_number)
        self.assertIn("bbox", first.anchor)
        flash_hits = self.repo.search_chunks("flash erase")
        self.assertEqual(["W25Q128JVSIQ"], flash_hits[0].mpns)

    def test_search_no_hit_returns_empty_list(self):
        document_id = self._ingest_fixture_document()
        self.repo.ingest_chunks(document_id, [self._chunk()], actor=ACTOR)
        self.assertEqual([], self.repo.search_chunks("nonexistentterm"))

    def test_empty_query_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.search_chunks("   ")
        self.assertEqual("VAULT-E302", ctx.exception.code)


class ExtractorStalenessTests(ChunkTestCase):
    def test_tv_r3_3_extractor_upgrade_marks_old_chunks_stale_keeps_them(self):
        document_id = self._ingest_fixture_document()
        old_chunks = [
            self._chunk(content=f"old extractor content {index}", extractor="docxmcp@1.4")
            for index in range(3)
        ]
        self.repo.ingest_chunks(document_id, old_chunks, actor=ACTOR)

        new_chunks = [
            self._chunk(content=f"new extractor content {index}", extractor="docxmcp@1.5")
            for index in range(3)
        ]
        result = self.repo.ingest_chunks(document_id, new_chunks, actor=ACTOR)

        self.assertEqual(3, result.chunks_added)
        self.assertEqual(3, result.stale_marked)
        stale = self.storage.conn.execute("SELECT COUNT(*) FROM chunks WHERE stale = 1").fetchone()[0]
        active = self.storage.conn.execute("SELECT COUNT(*) FROM chunks WHERE stale = 0").fetchone()[0]
        total = self.storage.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        self.assertEqual(3, stale)
        self.assertEqual(3, active)
        self.assertEqual(6, total)
        active_extractors = {
            row["extractor"]
            for row in self.storage.conn.execute("SELECT extractor FROM chunks WHERE stale = 0")
        }
        self.assertEqual({"docxmcp@1.5"}, active_extractors)

    def test_same_extractor_reingest_does_not_mark_stale(self):
        document_id = self._ingest_fixture_document()
        self.repo.ingest_chunks(document_id, [self._chunk()], actor=ACTOR)
        result = self.repo.ingest_chunks(document_id, [self._chunk(content="second pass")], actor=ACTOR)

        self.assertEqual(0, result.stale_marked)
        stale = self.storage.conn.execute("SELECT COUNT(*) FROM chunks WHERE stale = 1").fetchone()[0]
        self.assertEqual(0, stale)

    def test_staleness_is_scoped_to_document(self):
        document_a = self._ingest_fixture_document(name="ds_a.pdf", mpns=("AP2112K-3.3",))
        document_b = self._ingest_fixture_document(name="ds_b.pdf", mpns=("W25Q128JVSIQ",))
        self.repo.ingest_chunks(document_a, [self._chunk(extractor="docxmcp@1.4")], actor=ACTOR)
        self.repo.ingest_chunks(document_b, [self._chunk(extractor="docxmcp@1.4", content="flash spec")], actor=ACTOR)

        self.repo.ingest_chunks(document_a, [self._chunk(extractor="docxmcp@1.5", content="updated")], actor=ACTOR)

        stale_b = self.storage.conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_id = ? AND stale = 1", (document_b,)
        ).fetchone()[0]
        self.assertEqual(0, stale_b)

    def test_stale_chunks_excluded_from_search_by_default(self):
        document_id = self._ingest_fixture_document()
        self.repo.ingest_chunks(
            document_id, [self._chunk(content="dropout voltage legacy", extractor="docxmcp@1.4")], actor=ACTOR
        )
        self.repo.ingest_chunks(
            document_id, [self._chunk(content="dropout voltage current", extractor="docxmcp@1.5")], actor=ACTOR
        )

        default_hits = self.repo.search_chunks("dropout voltage")
        all_hits = self.repo.search_chunks("dropout voltage", include_stale=True)

        self.assertEqual(1, len(default_hits))
        self.assertEqual("docxmcp@1.5", default_hits[0].extractor)
        self.assertEqual(2, len(all_hits))

    def test_stale_marking_is_audited(self):
        document_id = self._ingest_fixture_document()
        self.repo.ingest_chunks(document_id, [self._chunk(extractor="docxmcp@1.4")], actor=ACTOR)
        self.repo.ingest_chunks(document_id, [self._chunk(extractor="docxmcp@1.5")], actor="upgrade-agent")

        rows = self.storage.conn.execute(
            "SELECT actor, action, field, old_value, new_value FROM audit_log"
            " WHERE table_name = 'chunks' AND field = 'stale'"
        ).fetchall()
        self.assertEqual(1, len(rows))
        self.assertEqual("upgrade-agent", rows[0]["actor"])
        self.assertEqual("update", rows[0]["action"])
        self.assertEqual("0", rows[0]["old_value"])
        self.assertEqual("1", rows[0]["new_value"])


class FtsSyncIntegrityTests(ChunkTestCase):
    def test_fts_stays_in_sync_on_insert_update_delete(self):
        document_id = self._ingest_fixture_document()
        self.repo.ingest_chunks(document_id, [self._chunk()], actor=ACTOR)
        chunk_id = self.storage.conn.execute("SELECT id FROM chunks").fetchone()["id"]

        self.storage.conn.execute(
            "UPDATE chunks SET content = 'quiescent current 55uA' WHERE id = ?", (chunk_id,)
        )
        self.assertEqual([], self.repo.search_chunks("dropout"))
        self.assertEqual(1, len(self.repo.search_chunks("quiescent")))

        self.storage.conn.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))
        self.assertEqual([], self.repo.search_chunks("quiescent"))
        fts_count = self.storage.conn.execute(
            "SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'quiescent'"
        ).fetchone()[0]
        self.assertEqual(0, fts_count)

    def test_fts_integrity_check_passes_after_batch_operations(self):
        document_id = self._ingest_fixture_document()
        self.repo.ingest_chunks(
            document_id,
            [self._chunk(content=f"spec line {index}") for index in range(10)],
            actor=ACTOR,
        )
        self.repo.ingest_chunks(
            document_id,
            [self._chunk(content=f"new spec line {index}", extractor="docxmcp@1.5") for index in range(5)],
            actor=ACTOR,
        )
        try:
            self.storage.conn.execute("INSERT INTO chunks_fts(chunks_fts, rank) VALUES ('integrity-check', 0)")
        except sqlite3.DatabaseError as error:
            self.fail(f"VAULT-E303: FTS index out of sync with chunks table ({error})")


class MigrationTests(unittest.TestCase):
    def test_existing_v1_db_migrates_cleanly_to_v2(self):
        with TemporaryDirectory() as temp:
            vault_dir = Path(temp) / "vault"
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                from bodesign_component_kb import storage as storage_module

                original_migrations = storage_module.MIGRATIONS
                original_version = storage_module.SCHEMA_VERSION
                storage_module.MIGRATIONS = original_migrations[:1]
                storage_module.SCHEMA_VERSION = 1
                try:
                    v1_storage = open_vault(vault_dir)
                    repo = VaultRepository(v1_storage)
                    repo.upsert_component("STM32F405RGT6", actor=ACTOR)
                    self.assertEqual(1, v1_storage.conn.execute("PRAGMA user_version").fetchone()[0])
                    v1_storage.close()
                finally:
                    storage_module.MIGRATIONS = original_migrations
                    storage_module.SCHEMA_VERSION = original_version

                v2_storage = open_vault(vault_dir)
                try:
                    self.assertEqual(
                        storage_module.SCHEMA_VERSION,
                        v2_storage.conn.execute("PRAGMA user_version").fetchone()[0],
                    )
                    repo = VaultRepository(v2_storage)
                    self.assertEqual("found", repo.resolve("STM32F405RGT6").status)
                    tables = {
                        row[0]
                        for row in v2_storage.conn.execute(
                            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                        )
                    }
                    self.assertIn("chunks", tables)
                    self.assertIn("chunks_fts", tables)
                finally:
                    v2_storage.close()
            finally:
                if saved_env is not None:
                    os.environ["BODESIGN_VAULT_DIR"] = saved_env

    def test_fresh_db_lands_on_latest_schema_version(self):
        from bodesign_component_kb.storage import SCHEMA_VERSION

        with TemporaryDirectory() as temp:
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                storage = open_vault(Path(temp) / "vault")
                try:
                    self.assertEqual(SCHEMA_VERSION, storage.conn.execute("PRAGMA user_version").fetchone()[0])
                finally:
                    storage.close()
            finally:
                if saved_env is not None:
                    os.environ["BODESIGN_VAULT_DIR"] = saved_env


if __name__ == "__main__":
    unittest.main()
