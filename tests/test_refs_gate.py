import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core.refs_gate import (
    REFS_SSOT_MISSING,
    RefsGateError,
    ingest_refs,
    require_refs,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_BASELINE = (
    "# Reference Baseline\n\n"
    "authority order: formal deck > X01/BOM > OpenMV heritage > concept sketches\n\n"
    "1. formal deck wins on conflict.\n"
)


class RefsGateTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-refs-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _seed_refs(self, *, with_baseline=True, with_sources=True):
        """Seed C04's per-stage ``01_refs/`` and return the STAGE dir.

        Note the two callers want different roots: ``ingest_refs`` takes a stage
        dir (or a direct ``01_refs`` path), while ``require_refs`` takes the
        PRODUCT ROOT and derives the stage from its ``layer`` argument.
        """
        refs = self.work / "C04-Layout" / "01_refs"
        refs.mkdir(parents=True, exist_ok=True)
        if with_baseline:
            (refs / "Reference_Baseline.md").write_text(_BASELINE, encoding="utf-8")
        if with_sources:
            (refs / "01_正式需求書").mkdir(exist_ok=True)
            (refs / "01_正式需求書" / "N6需求說明_優化版v3.pptx").write_bytes(b"PK\x03\x04stub")
            (refs / "C03_元件與腳位SSOT.md").write_text("# 元件清單\n", encoding="utf-8")
            # English-named source that DOES match an authority-order token,
            # proving the ranking mechanism works when tokens are matchable.
            (refs / "formal_deck_requirement.pdf").write_bytes(b"%PDF-1.4 stub")
        return self.work / "C04-Layout"

    # ── require_refs: fail-fast on missing SSOT ─────────────────────────────
    def test_missing_refs_root_raises_typed_error(self):
        # require_refs takes the PRODUCT ROOT; it derives <root>/C04-Layout/01_refs
        # from layer="C04" (the caller never pre-joins the stage folder).
        with self.assertRaises(RefsGateError) as ctx:
            require_refs(self.work, layer="C04")
        self.assertEqual(ctx.exception.code, REFS_SSOT_MISSING)
        self.assertEqual(ctx.exception.detail["layer"], "C04")
        self.assertEqual(ctx.exception.detail["reason"], "root_not_visible")

    def test_empty_refs_root_raises_typed_error(self):
        self._seed_refs(with_sources=False)  # 01_refs exists but empty
        with self.assertRaises(RefsGateError) as ctx:
            require_refs(self.work, layer="C04")
        self.assertEqual(ctx.exception.code, REFS_SSOT_MISSING)
        self.assertEqual(ctx.exception.detail["reason"], "no_sources")

    # ── require_refs: pass on populated SSOT ────────────────────────────────
    def test_populated_refs_passes_and_returns_manifest(self):
        self._seed_refs()
        manifest = require_refs(self.work, layer="C04")
        self.assertTrue(manifest.complete)
        self.assertEqual(manifest.schema, "bodesign.refs.manifest.v1")
        self.assertEqual(len(manifest.sources), 3)

    # ── ingest_refs: classification + authority ranking + adjudication ──────
    def test_ingest_classifies_and_ranks(self):
        stage = self._seed_refs()
        m = ingest_refs(stage).to_dict()
        self.assertEqual(m["authority_order"][0], "formal deck")
        by_path = {s["path"]: s for s in m["sources"]}
        pptx = next(s for p, s in by_path.items() if p.endswith(".pptx"))
        # PPTX = formal requirement, rich media → not yet adjudicated.
        self.assertEqual(pptx["category"], "formal_requirement")
        self.assertEqual(pptx["media_type"], "pptx")
        self.assertFalse(pptx["adjudicated"])
        # Chinese filename does NOT substring-match the English authority token
        # 'formal deck' → rank 0 (honest: no fabricated cross-language match).
        self.assertEqual(pptx["authority_rank"], 0)
        # markdown SSOT = machine-readable → adjudicated.
        md = next(s for p, s in by_path.items() if p.endswith(".md"))
        self.assertTrue(md["adjudicated"])
        # English-named source matching 'formal'/'deck' → authority rank 1.
        pdf = next(s for p, s in by_path.items() if p.endswith(".pdf"))
        self.assertEqual(pdf["authority_rank"], 1)

    def test_ingest_invisible_root_is_loud_not_empty(self):
        stage = self.work / "nonexistent-stage"
        m = ingest_refs(stage)
        self.assertFalse(m.root_visible)
        self.assertFalse(m.complete)
        self.assertTrue(m.warnings)

    def test_ingest_accepts_direct_01refs_path(self):
        self._seed_refs()
        direct = self.work / "C04-Layout" / "01_refs"
        m = ingest_refs(direct)
        self.assertTrue(m.complete)


if __name__ == "__main__":
    unittest.main()
