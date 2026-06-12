"""P2 (knowledge/datasheet-spice-models) — deterministic model-card generation.

Covers tasks 2.1–2.4 (R3):
- typ-selection rule (typ -> single -> ambiguous SPX_PARAMS_AMBIGUOUS)
- three category templates (diode .model / ldo .subckt / passive RLC)
- byte-identical determinism (no timestamps)
- missing-required SPX_PARAMS_MISSING, SPX_CATEGORY_UNSUPPORTED
"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_component_kb.repository import VaultRepository
from bodesign_component_kb.spice_card import (
    ModelCard,
    SpiceCardError,
    generate_model_card,
    ingest_spice_extraction,
)
from bodesign_component_kb.storage import open_vault

ACTOR = "test-agent"
SHA = "b" * 64


def _row(field_path, value_num, *, value_kind="typ", unit=None, page=3):
    return {
        "field_path": field_path,
        "status": "found",
        "value_num": value_num,
        "value_kind": value_kind,
        "unit": unit,
        "evidence": {"document_sha256": SHA, "page": page},
    }


class CardTestCase(unittest.TestCase):
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

    def _ingest_diode(self, mpn="1N4148W"):
        ingest_spice_extraction(self.repo, mpn, [
            _row("spice_model.diode.is_a", 2.5e-9, unit="A"),
            _row("spice_model.diode.n", 1.8),
            _row("spice_model.diode.rs_ohm", 0.6),
        ], actor=ACTOR)
        return mpn

    def _ingest_ldo(self, mpn="AMS1117-3.3"):
        ingest_spice_extraction(self.repo, mpn, [
            _row("spice_model.ldo.vout_v", 3.3, unit="V"),
            _row("spice_model.ldo.dropout_v", 1.1, unit="V"),
            _row("spice_model.ldo.iout_max_a", 1.0, unit="A"),
        ], actor=ACTOR)
        return mpn

    def _ingest_passive(self, mpn="GRM188R71C104KA01"):
        ingest_spice_extraction(self.repo, mpn, [
            _row("spice_model.passive.c_f", 1e-7, unit="F"),
            _row("spice_model.passive.esr_ohm", 0.05),
            _row("spice_model.passive.esl_h", 5e-10),
        ], actor=ACTOR)
        return mpn


class CategoryTemplateTests(CardTestCase):
    def test_tv_r3_1_diode_card(self):
        mpn = self._ingest_diode()
        card = generate_model_card(self.repo, mpn, "diode")
        self.assertIsInstance(card, ModelCard)
        self.assertEqual("D_1N4148W", card.card_name)
        self.assertIn(".model D_1N4148W D(", card.card_text)
        self.assertIn("IS=2.5e-09", card.card_text)
        self.assertIn("N=1.8", card.card_text)
        self.assertIn("RS=0.6", card.card_text)
        # provenance header present, no timestamp
        self.assertIn("trust=unverified", card.card_text)
        self.assertNotIn("202", card.card_text)  # crude no-year/timestamp check

    def test_tv_r3_2_ldo_card_with_limitations(self):
        mpn = self._ingest_ldo()
        card = generate_model_card(self.repo, mpn, "ldo")
        self.assertEqual("LDO_AMS1117_3_3", card.card_name)
        self.assertIn(".subckt LDO_AMS1117_3_3", card.card_text)
        self.assertTrue(card.limitations)
        self.assertIn("first-order", card.limitations[0])

    def test_tv_r3_3_passive_card(self):
        mpn = self._ingest_passive()
        card = generate_model_card(self.repo, mpn, "passive")
        self.assertIn(".subckt", card.card_text)
        self.assertIn("Cmain", card.card_text)
        self.assertIn("Resr", card.card_text)
        self.assertIn("Lesl", card.card_text)


class DeterminismTests(CardTestCase):
    def test_tv_r3_4_byte_identical_for_identical_state(self):
        mpn = self._ingest_diode()
        a = generate_model_card(self.repo, mpn, "diode").card_text
        b = generate_model_card(self.repo, mpn, "diode").card_text
        self.assertEqual(a, b)

    def test_provenance_order_is_stable(self):
        mpn = self._ingest_diode()
        card = generate_model_card(self.repo, mpn, "diode")
        leaves = [p.leaf for p in card.provenance]
        self.assertEqual(sorted(leaves), leaves)


class FailFastTests(CardTestCase):
    def test_tv_r3_5_missing_required_param(self):
        # ingest only n + rs, omit required is_a
        ingest_spice_extraction(self.repo, "BADDIODE", [
            _row("spice_model.diode.n", 1.8),
            _row("spice_model.diode.rs_ohm", 0.6),
        ], actor=ACTOR)
        with self.assertRaises(SpiceCardError) as ctx:
            generate_model_card(self.repo, "BADDIODE", "diode")
        self.assertEqual("SPX_PARAMS_MISSING", ctx.exception.code)
        self.assertIn("spice_model.diode.is_a", ctx.exception.payload["missing"])
        self.assertIn("repair", ctx.exception.payload)

    def test_tv_r3_6_unsupported_category(self):
        with self.assertRaises(SpiceCardError) as ctx:
            generate_model_card(self.repo, "WHATEVER", "transistor")
        self.assertEqual("SPX_CATEGORY_UNSUPPORTED", ctx.exception.code)

    def test_ambiguous_multi_value_no_typ(self):
        # two rows for is_a, neither typ -> ambiguous
        ingest_spice_extraction(self.repo, "AMBIG", [
            _row("spice_model.diode.is_a", 1e-9, value_kind="min"),
            _row("spice_model.diode.is_a", 5e-9, value_kind="max"),
            _row("spice_model.diode.n", 1.8),
        ], actor=ACTOR)
        with self.assertRaises(SpiceCardError) as ctx:
            generate_model_card(self.repo, "AMBIG", "diode")
        self.assertEqual("SPX_PARAMS_AMBIGUOUS", ctx.exception.code)
        self.assertIn("candidates", ctx.exception.payload)

    def test_typ_wins_over_min_max(self):
        ingest_spice_extraction(self.repo, "TYPWINS", [
            _row("spice_model.diode.is_a", 1e-9, value_kind="min"),
            _row("spice_model.diode.is_a", 3e-9, value_kind="typ"),
            _row("spice_model.diode.is_a", 5e-9, value_kind="max"),
            _row("spice_model.diode.n", 1.8),
        ], actor=ACTOR)
        card = generate_model_card(self.repo, "TYPWINS", "diode")
        self.assertIn("IS=3e-09", card.card_text)

    def test_passive_missing_primary_value(self):
        # only esr/esl, no c_f/l_h/r_ohm
        ingest_spice_extraction(self.repo, "BADPASSIVE", [
            _row("spice_model.passive.esr_ohm", 0.05),
        ], actor=ACTOR)
        with self.assertRaises(SpiceCardError) as ctx:
            generate_model_card(self.repo, "BADPASSIVE", "passive")
        self.assertEqual("SPX_PARAMS_MISSING", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
