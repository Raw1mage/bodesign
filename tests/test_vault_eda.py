"""Phase 6 tests: EDA assets (R5, TV-R5-*) + application knowledge (R6, TV-R6-1)
and migration v4->v5 (completeness view reads real eda_assets)."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import VaultRepository, VaultRepositoryError
from bodesign_component_kb.storage import SCHEMA_VERSION, open_vault
from bodesign_eda_bridge.footprint_map import vault_footprint
from bodesign_eda_bridge.kicad_emit import vault_symbol

ACTOR = "test-agent"


class EdaTestCase(unittest.TestCase):
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


class EdaAssetTests(EdaTestCase):
    def test_tv_r5_1_register_with_verification_provenance(self):
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3",
            "kicad-symbol",
            "Regulator_Linear:AP2112K-3.3",
            verification_status="pin-checked",
            verified_in={"project_id": "rockbox-fixture", "date": "2026-06-11"},
            actor=ACTOR,
        )
        self.assertEqual("pin-checked", asset["verification_status"])
        self.assertEqual(
            {"project_id": "rockbox-fixture", "date": "2026-06-11"},
            json.loads(asset["verified_in"]),
        )

    def test_initial_status_above_unverified_requires_provenance(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.register_eda_asset(
                "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3",
                verification_status="pin-checked", actor=ACTOR,
            )
        self.assertEqual("VAULT-E502", ctx.exception.code)

    def test_register_idempotent_same_mapping(self):
        first = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        second = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        self.assertEqual(first["id"], second["id"])
        rows = self.storage.conn.execute("SELECT COUNT(*) FROM eda_assets").fetchone()[0]
        self.assertEqual(1, rows)

    def test_ladder_upgrades_one_rung_with_provenance(self):
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-footprint", "Package_TO_SOT_SMD:SOT-23-5", actor=ACTOR
        )
        upgraded = self.repo.upgrade_eda_asset(
            asset["id"], "pin-checked", {"project_id": "proj-a", "run_id": "run-1"}, actor=ACTOR
        )
        self.assertEqual("pin-checked", upgraded["verification_status"])
        final = self.repo.upgrade_eda_asset(
            asset["id"], "drc-passed", {"project_id": "proj-a", "run_id": "run-2"}, actor=ACTOR
        )
        self.assertEqual("drc-passed", final["verification_status"])
        self.assertEqual({"project_id": "proj-a", "run_id": "run-2"}, json.loads(final["verified_in"]))

    def test_ladder_skip_rejected(self):
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-footprint", "Package_TO_SOT_SMD:SOT-23-5", actor=ACTOR
        )
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.upgrade_eda_asset(
                asset["id"], "drc-passed", {"project_id": "proj-a"}, actor=ACTOR
            )
        self.assertEqual("VAULT-E502", ctx.exception.code)

    def test_ladder_downgrade_rejected(self):
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-footprint", "Package_TO_SOT_SMD:SOT-23-5", actor=ACTOR
        )
        self.repo.upgrade_eda_asset(asset["id"], "pin-checked", {"project_id": "p"}, actor=ACTOR)
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.upgrade_eda_asset(asset["id"], "unverified", {"project_id": "p"}, actor=ACTOR)
        self.assertEqual("VAULT-E502", ctx.exception.code)

    def test_upgrade_without_provenance_rejected(self):
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.upgrade_eda_asset(asset["id"], "pin-checked", {}, actor=ACTOR)
        self.assertEqual("VAULT-E502", ctx.exception.code)

    def test_upgrade_is_audited_with_evidence(self):
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        self.repo.upgrade_eda_asset(
            asset["id"], "pin-checked", {"project_id": "proj-a"}, actor=ACTOR
        )
        row = self.storage.conn.execute(
            "SELECT * FROM audit_log WHERE table_name='eda_assets' AND action='update'"
        ).fetchone()
        self.assertEqual("verification_status", row["field"])
        self.assertEqual("unverified", row["old_value"])
        self.assertEqual("pin-checked", row["new_value"])
        self.assertIn("proj-a", row["evidence_ref"])

    def test_tv_r5_2_missing_mapping_absent_never_guessed(self):
        out = self.repo.query_eda_asset("NOTMAPPED-1", "kicad-footprint")
        self.assertEqual("absent", out["status"])
        self.assertEqual([], out["assets"])

    def test_known_component_without_assets_is_absent(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        out = self.repo.query_eda_asset("AP2112K-3.3", "kicad-symbol")
        self.assertEqual("absent", out["status"])

    def test_query_returns_mapping_with_status(self):
        self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        out = self.repo.query_eda_asset("AP2112K-3.3", "kicad-symbol")
        self.assertEqual("found", out["status"])
        self.assertEqual(1, len(out["assets"]))
        self.assertEqual("Regulator_Linear:AP2112K-3.3", out["assets"][0]["library_ref"])
        self.assertEqual("unverified", out["assets"][0]["verification_status"])

    def test_package_scoped_asset(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        self.repo.register_package("AP2112K-3.3", "SOT-23-5", actor=ACTOR)
        asset = self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-footprint", "Package_TO_SOT_SMD:SOT-23-5",
            package_name="SOT-23-5", actor=ACTOR,
        )
        self.assertIsNotNone(asset["package_id"])

    def test_unregistered_package_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.register_eda_asset(
                "AP2112K-3.3", "kicad-footprint", "Package_TO_SOT_SMD:SOT-23-5",
                package_name="QFN-16", actor=ACTOR,
            )
        self.assertEqual("VAULT-E404", ctx.exception.code)


class ConsumerTests(EdaTestCase):
    def test_kicad_emit_consumer_reads_vault(self):
        self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        out = vault_symbol(self.repo, "AP2112K-3.3")
        self.assertEqual("found", out["status"])
        self.assertEqual("Regulator_Linear:AP2112K-3.3", out["assets"][0]["library_ref"])

    def test_kicad_emit_consumer_absent_not_guessed(self):
        out = vault_symbol(self.repo, "NOTMAPPED-1")
        self.assertEqual("absent", out["status"])
        self.assertEqual([], out["assets"])

    def test_footprint_map_consumer_reads_vault(self):
        self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-footprint", "Package_TO_SOT_SMD:SOT-23-5", actor=ACTOR
        )
        out = vault_footprint(self.repo, "AP2112K-3.3")
        self.assertEqual("found", out["status"])
        self.assertEqual("Package_TO_SOT_SMD:SOT-23-5", out["assets"][0]["library_ref"])

    def test_footprint_map_consumer_absent_not_guessed(self):
        out = vault_footprint(self.repo, "NOTMAPPED-1")
        self.assertEqual("absent", out["status"])


class AppKnowledgeTests(EdaTestCase):
    def test_tv_r6_1_companion_part_round_trip(self):
        entry = self.repo.write_app_knowledge(
            "ABM8-25.000MHZ",
            "companion-part",
            "Load capacitors",
            {"companion_mpn": "GRM1555C1H180JA01", "qty": 2, "rule": "CL=(C1*C2)/(C1+C2)+Cstray"},
            companion_mpn="GRM1555C1H180JA01",
            evidence_chunk_id=None,
            source_note="datasheet table 4",
            confidence="verified",
            actor=ACTOR,
        )
        self.assertEqual("verified", entry["confidence"])
        out = self.repo.app_knowledge("ABM8-25.000MHZ", knowledge_type="companion-part")
        self.assertEqual("found", out["status"])
        self.assertEqual(1, len(out["entries"]))
        got = out["entries"][0]
        self.assertEqual("GRM1555C1H180JA01", got["companion_mpn"])
        self.assertEqual(2, got["payload"]["qty"])
        self.assertEqual("datasheet table 4", got["source_note"])

    def test_companion_part_requires_companion(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.write_app_knowledge(
                "ABM8-25.000MHZ", "companion-part", "Load capacitors",
                {"qty": 2}, actor=ACTOR,
            )
        self.assertEqual("VAULT-E601", ctx.exception.code)

    def test_invalid_payload_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.write_app_knowledge(
                "AP2112K-3.3", "layout-rule", "Input cap placement", "{not json", actor=ACTOR
            )
        self.assertEqual("VAULT-E602", ctx.exception.code)

    def test_no_evidence_forced_unverified(self):
        entry = self.repo.write_app_knowledge(
            "AP2112K-3.3", "layout-rule", "Input cap placement",
            {"rule": "place 1uF within 2mm of VIN"}, confidence="verified", actor=ACTOR,
        )
        self.assertEqual("unverified", entry["confidence"])

    def test_all_four_types_writable_and_filterable(self):
        payloads = {
            "layout-rule": {"rule": "keep SW node short"},
            "reference-circuit": {"ir": "buck-3v3-fragment"},
            "design-rule": {"rule": "Cff 10nF when Vout>=1.8V"},
        }
        for knowledge_type, payload in payloads.items():
            self.repo.write_app_knowledge(
                "TPS62840", knowledge_type, f"{knowledge_type} entry", payload, actor=ACTOR
            )
        self.repo.write_app_knowledge(
            "TPS62840", "companion-part", "Inductor", {"companion_mpn": "XFL4020-222"},
            companion_mpn="XFL4020-222", actor=ACTOR,
        )
        out = self.repo.app_knowledge("TPS62840")
        self.assertEqual(4, len(out["entries"]))
        only_layout = self.repo.app_knowledge("TPS62840", knowledge_type="layout-rule")
        self.assertEqual(1, len(only_layout["entries"]))

    def test_unknown_component_absent(self):
        self.assertEqual("absent", self.repo.app_knowledge("UNKNOWN-1")["status"])

    def test_unknown_type_rejected(self):
        with self.assertRaises(VaultRepositoryError) as ctx:
            self.repo.app_knowledge("AP2112K-3.3", knowledge_type="folk-wisdom")
        self.assertEqual("VAULT-E602", ctx.exception.code)


class CompletenessViewTests(EdaTestCase):
    def test_completeness_reflects_real_eda_asset(self):
        self.repo.upsert_component("AP2112K-3.3", actor=ACTOR)
        before = self.repo.component_completeness("AP2112K-3.3")
        self.assertEqual(0, before["has_eda_asset"])
        self.repo.register_eda_asset(
            "AP2112K-3.3", "kicad-symbol", "Regulator_Linear:AP2112K-3.3", actor=ACTOR
        )
        after = self.repo.component_completeness("AP2112K-3.3")
        self.assertEqual(1, after["has_eda_asset"])
        self.assertEqual(before["extraction_score"] + 1, after["extraction_score"])


class MigrationTests(unittest.TestCase):
    def test_existing_v4_db_migrates_cleanly_to_v5(self):
        with TemporaryDirectory() as temp:
            vault_dir = Path(temp) / "vault"
            saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
            try:
                from bodesign_component_kb import storage as storage_module

                original_migrations = storage_module.MIGRATIONS
                original_version = storage_module.SCHEMA_VERSION
                storage_module.MIGRATIONS = original_migrations[:4]
                storage_module.SCHEMA_VERSION = 4
                try:
                    v4_storage = open_vault(vault_dir)
                    repo = VaultRepository(v4_storage)
                    repo.upsert_component("STM32F405RGT6", actor=ACTOR)
                    self.assertEqual(4, v4_storage.conn.execute("PRAGMA user_version").fetchone()[0])
                    v4_storage.close()
                finally:
                    storage_module.MIGRATIONS = original_migrations
                    storage_module.SCHEMA_VERSION = original_version

                v5_storage = open_vault(vault_dir)
                try:
                    self.assertEqual(
                        SCHEMA_VERSION, v5_storage.conn.execute("PRAGMA user_version").fetchone()[0]
                    )
                    repo = VaultRepository(v5_storage)
                    self.assertEqual("found", repo.resolve("STM32F405RGT6").status)
                    names = {
                        row[0]
                        for row in v5_storage.conn.execute(
                            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                        )
                    }
                    for required in ("eda_assets", "app_knowledge", "component_completeness"):
                        self.assertIn(required, names)
                    # rebuilt view reads real eda_assets
                    repo.register_eda_asset(
                        "STM32F405RGT6", "kicad-symbol", "MCU_ST_STM32F4:STM32F405RGTx", actor=ACTOR
                    )
                    out = repo.component_completeness("STM32F405RGT6")
                    self.assertEqual(1, out["has_eda_asset"])
                finally:
                    v5_storage.close()
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
