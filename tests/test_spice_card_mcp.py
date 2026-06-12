"""P4 (knowledge/datasheet-spice-models) — simulate model_source + MCP tool.

Covers tasks 4.1–4.4 (R4, DD-8/DD-9):
- model_source annotation (vault-grounded / generic-default) — deterministic
  manifest lookup, fail-fast (no manifest -> generic-default, no guessing)
- bodesign_spice_model_card MCP handler: happy path + SPX_* passthrough
- spice ValidationEvidence adapter (smoke/simulate -> envelope findings)
"""

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bodesign_eda_bridge.simulate import (
    _model_source_for,
    _vault_grounded_components,
)

ACTOR = "test-agent"
SHA = "f" * 64


class ModelSourceAnnotationTests(unittest.TestCase):
    def test_tv_r4_1_grounded_when_ref_hits_manifest(self):
        grounded = {"D1", "C2"}
        self.assertEqual(
            "vault-grounded", _model_source_for({"components": ["D1", "X9"]}, grounded)
        )

    def test_tv_r4_2_generic_when_no_hit(self):
        grounded = {"D1"}
        self.assertEqual(
            "generic-default", _model_source_for({"components": ["X9", "R3"]}, grounded)
        )

    def test_empty_components_is_generic(self):
        self.assertEqual("generic-default", _model_source_for({"components": []}, {"D1"}))

    def test_no_manifest_yields_empty_grounded_set(self):
        # fail-fast: missing manifest -> no grounded refs (everything generic)
        with TemporaryDirectory() as d:
            sch = Path(d) / "x.kicad_sch"
            sch.write_text("(kicad_sch)")
            analysis = Path(d) / "analysis.json"
            analysis.write_text("{}")
            self.assertEqual(set(), _vault_grounded_components(sch, analysis))

    def test_grounded_refs_mapped_from_analysis(self):
        with TemporaryDirectory() as d:
            proj = Path(d)
            sch = proj / "x.kicad_sch"
            sch.write_text("(kicad_sch)")
            models = proj / "spice" / "models"
            models.mkdir(parents=True)
            (models / "manifest.json").write_text(json.dumps({
                "1N4148W": {"file": "1N4148W.sub", "mpn": "1N4148W", "source": "vault-grounded"},
                "GENERIC": {"file": "g.sub", "mpn": "GENERIC", "source": "lookup"},
            }))
            analysis = proj / "analysis.json"
            analysis.write_text(json.dumps({"components": [
                {"reference": "D1", "value": "1N4148W"},
                {"reference": "D2", "value": "GENERIC"},
                {"reference": "R1", "value": "10k"},
            ]}))
            grounded = _vault_grounded_components(sch, analysis)
            self.assertEqual({"D1"}, grounded)  # only the vault-grounded MPN's ref


class McpHandlerTests(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self._saved_env = os.environ.pop("BODESIGN_VAULT_DIR", None)
        self.addCleanup(self._restore_env)
        self.vault_dir = str(Path(self._temp.name) / "vault")
        # import server lazily (needs services/mcp on path)
        mcp_dir = str(Path(__file__).resolve().parent.parent / "services" / "mcp")
        if mcp_dir not in sys.path:
            sys.path.insert(0, mcp_dir)
        import server  # noqa
        self.server = server
        self._seed_diode()

    def _restore_env(self):
        if self._saved_env is not None:
            os.environ["BODESIGN_VAULT_DIR"] = self._saved_env

    def _seed_diode(self, mpn="1N4148W", *, full=True):
        from bodesign_component_kb.storage import open_vault
        from bodesign_component_kb.repository import VaultRepository
        from bodesign_component_kb.spice_card import ingest_spice_extraction
        st = open_vault(Path(self.vault_dir))
        repo = VaultRepository(st)
        rows = [{"field_path": "spice_model.diode.is_a", "status": "found",
                 "value_num": 2.5e-9, "value_kind": "typ",
                 "evidence": {"document_sha256": SHA, "page": 3}}]
        if full:
            rows.append({"field_path": "spice_model.diode.n", "status": "found",
                         "value_num": 1.8, "value_kind": "typ",
                         "evidence": {"document_sha256": SHA, "page": 3}})
        ingest_spice_extraction(repo, mpn, rows, actor=ACTOR)
        st.close()

    def test_tv_r4_3_happy_path(self):
        out = self.server._h_spice_model_card(
            {"mpn": "1N4148W", "category": "diode", "vault_dir": self.vault_dir}
        )
        self.assertEqual("ok", out["status"])
        self.assertEqual("D_1N4148W", out["card"]["card_name"])
        self.assertIn(".model D_1N4148W", out["card"]["card_text"])

    def test_tv_r4_4_spx_params_missing_passthrough(self):
        self._seed_diode("BADDIODE", full=False)  # missing required 'n'
        out = self.server._h_spice_model_card(
            {"mpn": "BADDIODE", "category": "diode", "vault_dir": self.vault_dir}
        )
        self.assertEqual("error", out["status"])
        self.assertEqual("SPX_PARAMS_MISSING", out["error_code"])
        self.assertIn("payload", out)

    def test_unsupported_category_passthrough(self):
        out = self.server._h_spice_model_card(
            {"mpn": "1N4148W", "category": "transistor", "vault_dir": self.vault_dir}
        )
        self.assertEqual("error", out["status"])
        self.assertEqual("SPX_CATEGORY_UNSUPPORTED", out["error_code"])

    def test_materialize_path(self):
        proj = str(Path(self._temp.name) / "proj")
        out = self.server._h_spice_model_card({
            "mpn": "1N4148W", "category": "diode", "vault_dir": self.vault_dir,
            "materialize": True, "project_dir": proj,
        })
        self.assertEqual("ok", out["status"])
        self.assertIn("materialize", out)
        # 1N4148W either written (smoke pass/skipped) or excluded (fail)
        mat = out["materialize"]
        self.assertEqual(
            1,
            len(mat["written"]) + len(mat["excluded"]),
        )


class SpiceEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        # workflow-core __init__ pulls reverse-core; ensure path present
        root = Path(__file__).resolve().parent.parent / "packages"
        for pkg in ("workflow-core", "reverse-core", "design-ir", "component-kb", "shared"):
            p = str(root / pkg)
            if p not in sys.path:
                sys.path.insert(0, p)

    def test_simulate_fail_becomes_finding(self):
        from bodesign_workflow_core import wrap_validation_evidence
        raw = {"results": [
            {"type": "rc_filter", "status": "fail", "model_source": "generic-default"},
            {"type": "divider", "status": "pass", "model_source": "vault-grounded"},
        ]}
        ev = wrap_validation_evidence("spice", raw).to_dict()
        self.assertEqual("spice", ev["tool"])
        self.assertEqual(1, len(ev["findings"]))
        self.assertIn("model_source=generic-default", ev["findings"][0]["message"])

    def test_smoke_fail_becomes_finding(self):
        from bodesign_workflow_core import wrap_validation_evidence
        ev = wrap_validation_evidence(
            "spice", {"smoke": "fail", "stderr_excerpt": "singular matrix"}
        ).to_dict()
        self.assertEqual(1, len(ev["findings"]))
        self.assertEqual("major", ev["severity"])

    def test_all_pass_no_findings(self):
        from bodesign_workflow_core import wrap_validation_evidence
        raw = {"results": [{"type": "divider", "status": "pass", "model_source": "vault-grounded"}]}
        ev = wrap_validation_evidence("spice", raw).to_dict()
        self.assertEqual(0, len(ev["findings"]))
        self.assertEqual("info", ev["severity"])


if __name__ == "__main__":
    unittest.main()
