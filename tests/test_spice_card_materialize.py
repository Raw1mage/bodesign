"""P3 (knowledge/datasheet-spice-models) — smoke validation + materialization.

Covers tasks 3.1–3.4 (R5 first half, DD-2/DD-7):
- smoke three states (pass / fail / skipped-no-simulator)
- materialize writes card + manifest entry (source=vault-grounded)
- fail cards excluded from manifest
- manifest round-trip: vault format hits the spice skill cascade tier 0
"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bodesign_component_kb.repository import VaultRepository
from bodesign_component_kb.spice_card import (
    MaterializeResult,
    SmokeResult,
    generate_model_card,
    ingest_spice_extraction,
    materialize_model_cards,
    run_smoke,
)
from bodesign_component_kb import spice_card as sc
from bodesign_component_kb.storage import open_vault

ACTOR = "test-agent"
SHA = "d" * 64


def _row(field_path, value_num, *, value_kind="typ"):
    return {
        "field_path": field_path,
        "status": "found",
        "value_num": value_num,
        "value_kind": value_kind,
        "evidence": {"document_sha256": SHA, "page": 3},
    }


class P3TestCase(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self._saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
        self.addCleanup(self._restore_env)
        self.storage = open_vault(Path(self._temp.name) / "vault")
        self.addCleanup(self.storage.close)
        self.repo = VaultRepository(self.storage)
        self.proj = Path(self._temp.name) / "proj"
        self.proj.mkdir()

    def _restore_env(self):
        if self._saved_env is not None:
            os.environ["BODESIGN_VAULT_DIR"] = self._saved_env

    def _ingest_diode(self, mpn="1N4148W"):
        ingest_spice_extraction(self.repo, mpn, [
            _row("spice_model.diode.is_a", 2.5e-9),
            _row("spice_model.diode.n", 1.8),
        ], actor=ACTOR)
        return mpn


class SmokeStateTests(P3TestCase):
    def test_tv_r5_1_skipped_when_no_simulator(self):
        mpn = self._ingest_diode()
        card = generate_model_card(self.repo, mpn, "diode")
        with mock.patch.object(sc, "_ngspice_available", return_value=False):
            result = run_smoke(card)
        self.assertEqual("skipped-no-simulator", result.status)

    def test_tv_r5_2_pass_on_valid_card(self):
        # only runs the real ngspice path when present; otherwise asserts skip
        mpn = self._ingest_diode()
        card = generate_model_card(self.repo, mpn, "diode")
        result = run_smoke(card)
        self.assertIn(result.status, ("pass", "skipped-no-simulator"))
        if not sc._ngspice_available():
            self.assertEqual("skipped-no-simulator", result.status)

    def test_tv_r5_3_fail_carries_stderr_excerpt(self):
        mpn = self._ingest_diode()
        card = generate_model_card(self.repo, mpn, "diode")
        # force a fail by mocking subprocess to return an error
        fake = mock.Mock(returncode=1, stderr="Error: singular matrix\n", stdout="")
        with mock.patch.object(sc, "_ngspice_available", return_value=True), \
             mock.patch.object(sc.subprocess, "run", return_value=fake):
            result = run_smoke(card)
        self.assertEqual("fail", result.status)
        self.assertIn("singular matrix", result.stderr_excerpt)


class MaterializeTests(P3TestCase):
    def test_tv_r5_4_materialize_writes_card_and_manifest(self):
        mpn = self._ingest_diode()
        with mock.patch.object(sc, "run_smoke", return_value=SmokeResult("skipped-no-simulator")):
            res = materialize_model_cards(
                self.proj, [mpn], self.repo, category_of={mpn: "diode"}
            )
        self.assertIsInstance(res, MaterializeResult)
        self.assertEqual((mpn,), res.written)
        self.assertEqual((), res.excluded)

        models = self.proj / "spice" / "models"
        self.assertTrue((models / "1N4148W.sub").exists())
        manifest = json.loads((models / "manifest.json").read_text())
        entry = manifest["1N4148W"]
        self.assertEqual("vault-grounded", entry["source"])
        self.assertEqual("1N4148W.sub", entry["file"])
        self.assertEqual("skipped-no-simulator", entry["smoke"])
        self.assertIn("trust=unverified", entry["provenance_summary"])

    def test_tv_r5_5_fail_card_excluded_from_manifest(self):
        mpn = self._ingest_diode()
        with mock.patch.object(sc, "run_smoke", return_value=SmokeResult("fail", "boom")):
            res = materialize_model_cards(
                self.proj, [mpn], self.repo, category_of={mpn: "diode"}
            )
        self.assertEqual((), res.written)
        self.assertEqual((mpn,), res.excluded)
        manifest = json.loads((self.proj / "spice" / "models" / "manifest.json").read_text())
        self.assertNotIn("1N4148W", manifest)

    def test_manifest_is_deterministic_sorted(self):
        mpn = self._ingest_diode()
        with mock.patch.object(sc, "run_smoke", return_value=SmokeResult("skipped-no-simulator")):
            materialize_model_cards(self.proj, [mpn], self.repo, category_of={mpn: "diode"})
        raw = (self.proj / "spice" / "models" / "manifest.json").read_text()
        # sort_keys=True -> entry keys alphabetical
        entry = json.loads(raw)["1N4148W"]
        self.assertEqual(sorted(entry.keys()), list(json.loads(raw)["1N4148W"].keys()))


class CascadeRoundTripTests(P3TestCase):
    """TV-R5-* / task 3.3: vault manifest must hit the spice skill cascade."""

    def test_vault_manifest_hits_skill_cascade_tier0(self):
        skill_scripts = Path.home() / ".config/opencode/skills/spice/scripts"
        if not (skill_scripts / "spice_model_cache.py").exists():
            self.skipTest("spice skill not installed on this host")
        import sys
        sys.path.insert(0, str(skill_scripts))
        try:
            import spice_model_cache as smc
        finally:
            pass

        mpn = self._ingest_diode()
        with mock.patch.object(sc, "run_smoke", return_value=SmokeResult("skipped-no-simulator")):
            materialize_model_cards(self.proj, [mpn], self.repo, category_of={mpn: "diode"})

        models = self.proj / "spice" / "models"
        subckt, specs = smc.get_cached_model(models, mpn)
        self.assertIsNotNone(subckt)
        self.assertIn(".model D_1N4148W", subckt)


if __name__ == "__main__":
    unittest.main()
