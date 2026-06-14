"""Phase 4 integration tests: vault API surface (R9, R10 wiring).

Tests at the level the repo tests services/mcp (test_mcp_server.py
pattern): import services.mcp.server and drive run_tool, plus the
shared vault_api thin layer the HTTP endpoints delegate to. The
Starlette routes are 1:1 wrappers over vault_api + http_status, so
contract coverage here covers both surfaces.
"""

import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.storage import VaultStorageError

ACTOR = "test-agent"


class VaultApiTestCase(unittest.TestCase):
    def setUp(self):
        self.server = importlib.import_module("services.mcp.server")
        self.vault_api = importlib.import_module("services.mcp.vault_api")
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.vault_dir = str(Path(self._temp.name) / "vault")
        self._saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
        self.addCleanup(self._restore_env)
        os.environ["BODESIGN_VAULT_DIR"] = self.vault_dir

    def _restore_env(self):
        os.environ.pop("BODESIGN_VAULT_DIR", None)
        if self._saved_env is not None:
            os.environ["BODESIGN_VAULT_DIR"] = self._saved_env

    def _datasheet(self, name="ap2112k.pdf"):
        path = Path(self._temp.name) / name
        path.write_bytes(b"%PDF-1.4 " + name.encode())
        return str(path)


class ToolRegistryTests(VaultApiTestCase):
    def test_vault_tools_registered_in_core_group(self):
        for name in ("bodesign_vault_ingest", "bodesign_vault_query",
                     "bodesign_vault_spec_check", "bodesign_vault_queue",
                     "bodesign_vault_diagnostics"):
            spec = self.server.TOOLS_BY_NAME.get(name)
            self.assertIsNotNone(spec, name)
            self.assertEqual("core", spec["group"], name)
            self.assertTrue(spec["description"])
            self.assertIn("type", spec["schema"])


class IngestQueryRoundtripTests(VaultApiTestCase):
    def test_r9_happy_path_ingest_then_query_roundtrip(self):
        ingest = self.server.run_tool("bodesign_vault_ingest", {
            "actor": ACTOR,
            "component": {"mpn": "AP2112K-3.3", "manufacturer": "Diodes", "category": "ldo"},
            "document": {"path": self._datasheet(), "doc_type": "datasheet", "provenance": "user-provided"},
            "chunks": [{"chunk_kind": "table", "page_number": 5,
                        "content": "Dropout Voltage 250 mV @ 300mA",
                        "extractor": "docxmcp@1.4"}],
            "specs": [{"mpn": "AP2112K-3.3", "field_path": "dropout_mv", "value_num": 250.0,
                       "unit": "mV", "evidence_chunk_id": 1, "confidence": "verified"}],
        })
        self.assertTrue(ingest["ok"], ingest)
        summary = ingest["result"]["summary"]
        self.assertEqual("AP2112K-3.3", summary["component"]["mpn"])
        self.assertFalse(summary["document"]["dedup_hit"])
        self.assertEqual(1, summary["chunks"]["chunks_added"])
        self.assertEqual(1, summary["specs_written"])
        self.assertIn("AP2112K-3.3", ingest["result"]["gaps"])

        query = self.server.run_tool("bodesign_vault_query", {"mpn": "ap2112k-3.3"})
        self.assertTrue(query["ok"], query)
        self.assertEqual("found", query["result"]["status"])
        self.assertEqual(1, len(query["result"]["documents"]))
        self.assertIn("completeness", query["result"])

        search = self.server.run_tool("bodesign_vault_query", {"query": "dropout"})
        self.assertTrue(search["ok"], search)
        hits = search["result"]["hits"]
        self.assertEqual(1, len(hits))
        self.assertIn("AP2112K-3.3", hits[0]["mpns"])
        self.assertEqual(5, hits[0]["page_number"])

    def test_r9_absent_path_unknown_mpn_is_explicit(self):
        result = self.server.run_tool("bodesign_vault_query", {"mpn": "NOPE-9999"})
        self.assertTrue(result["ok"], result)
        self.assertEqual("absent", result["result"]["status"])
        self.assertIn("advice", result["result"])

    def test_r9_search_no_hit_is_explicit_empty(self):
        result = self.server.run_tool("bodesign_vault_query", {"query": "unobtainium"})
        self.assertTrue(result["ok"], result)
        self.assertEqual([], result["result"]["hits"])

    def test_r9_error_path_bad_payload_carries_vault_code(self):
        missing_provenance = self.server.run_tool("bodesign_vault_ingest", {
            "actor": ACTOR,
            "mpns": ["AP2112K-3.3"],
            "document": {"path": self._datasheet(), "doc_type": "datasheet", "provenance": None},
        })
        self.assertTrue(missing_provenance["ok"])
        self.assertEqual("error", missing_provenance["result"]["status"])
        self.assertEqual("VAULT-E201", missing_provenance["result"]["error_code"])
        self.assertEqual(400, missing_provenance["result"]["http_status"])

        empty = self.server.run_tool("bodesign_vault_ingest", {"actor": ACTOR})
        self.assertTrue(empty["ok"])
        self.assertEqual("VAULT-E101", empty["result"]["error_code"])

        no_actor = self.server.run_tool("bodesign_vault_ingest", {
            "component": {"mpn": "AP2112K-3.3"}})
        self.assertTrue(no_actor["ok"])
        self.assertEqual("VAULT-E702", no_actor["result"]["error_code"])

        bad_query = self.server.run_tool("bodesign_vault_query", {})
        self.assertTrue(bad_query["ok"])
        self.assertEqual("VAULT-E101", bad_query["result"]["error_code"])


class SpecCheckAndQueueTests(VaultApiTestCase):
    def test_spec_check_hits_server_vault_with_origin(self):
        self.server.run_tool("bodesign_vault_ingest", {
            "actor": ACTOR,
            "component": {"mpn": "AP2112K-3.3"},
            "document": {"path": self._datasheet(), "doc_type": "datasheet", "provenance": "user-provided"},
            "chunks": [{"chunk_kind": "table", "content": "Dropout 250 mV", "extractor": "docxmcp@1.4"}],
            "specs": [{"mpn": "AP2112K-3.3", "field_path": "dropout_mv", "value_num": 250.0,
                       "evidence_chunk_id": 1, "confidence": "verified"}],
        })
        check = self.server.run_tool("bodesign_vault_spec_check",
                                     {"mpn": "AP2112K-3.3", "field": "dropout_mv"})
        self.assertTrue(check["ok"], check)
        self.assertEqual("verified", check["result"]["status"])
        self.assertEqual("server-vault", check["result"]["origin"])

    def test_spec_check_absent_part_falls_back_to_client_cache_origin(self):
        check = self.server.run_tool("bodesign_vault_spec_check",
                                     {"mpn": "NOPE-9999", "field": "dropout_mv"})
        self.assertTrue(check["ok"], check)
        self.assertEqual("absent", check["result"]["status"])
        self.assertEqual("client-cache", check["result"]["origin"])

    def test_queue_lists_open_gap_components(self):
        with self.vault_api.open_repository() as repo:
            repo.upsert_component("AP2112K-3.3", actor=ACTOR)
            repo.record_gap("AP2112K-3.3", "pinout", "no pins recorded", actor=ACTOR)
        queue = self.server.run_tool("bodesign_vault_queue", {})
        self.assertTrue(queue["ok"], queue)
        mpns = [row["mpn"] for row in queue["result"]["queue"]]
        self.assertIn("AP2112K-3.3", mpns)

    def test_diagnostics_reports_live_vault_without_temp_fallback(self):
        with self.vault_api.open_repository() as repo:
            repo.upsert_component("AP2112K-3.3", actor=ACTOR)
            repo.record_gap("AP2112K-3.3", "datasheet", "datasheet missing", actor=ACTOR)
        result = self.server.run_tool("bodesign_vault_diagnostics", {"limit": 5})
        self.assertTrue(result["ok"], result)
        diagnostics = result["result"]
        self.assertEqual("ok", diagnostics["status"])
        self.assertEqual(self.vault_dir, diagnostics["vault_dir"])
        self.assertTrue(diagnostics["db_exists"])
        self.assertEqual(1, diagnostics["queue_count"])
        self.assertEqual("AP2112K-3.3", diagnostics["queue"][0]["mpn"])
        self.assertIn("docker compose run", diagnostics["safe_diagnostic_command"])
        self.assertEqual("policy-gated-until-configured",
                         diagnostics["external_fetch_policy"]["implementation_state"])


class HttpContractTests(VaultApiTestCase):
    def test_http_status_mapping(self):
        self.assertEqual(503, self.vault_api.http_status("VAULT-E001"))
        self.assertEqual(503, self.vault_api.http_status("VAULT-E002"))
        self.assertEqual(503, self.vault_api.http_status("VAULT-E003"))
        self.assertEqual(404, self.vault_api.http_status("VAULT-E901"))
        self.assertEqual(400, self.vault_api.http_status("VAULT-E201"))
        self.assertEqual(400, self.vault_api.http_status("VAULT-E702"))

    def test_r10_unconfigured_vault_dir_fails_fast(self):
        os.environ.pop("BODESIGN_VAULT_DIR", None)
        with self.assertRaises(VaultStorageError) as ctx:
            with self.vault_api.open_repository():
                pass
        self.assertEqual("VAULT-E002", ctx.exception.code)

    def test_r10_corrupt_db_fails_fast_never_recreated(self):
        with self.vault_api.open_repository() as repo:
            repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        db_path = Path(self.vault_dir) / "vault.db"
        db_path.write_bytes(b"this is not a sqlite database " * 64)
        with self.assertRaises(VaultStorageError) as ctx:
            with self.vault_api.open_repository():
                pass
        self.assertEqual("VAULT-E001", ctx.exception.code)
        self.assertEqual(b"this is not a sqlite database ",
                         db_path.read_bytes()[:30])

    def test_r10_data_survives_reopen(self):
        with self.vault_api.open_repository() as repo:
            repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        with self.vault_api.open_repository() as repo:
            self.assertEqual("found", repo.resolve("AP2112K-3.3").status)


if __name__ == "__main__":
    unittest.main()
