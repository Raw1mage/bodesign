"""aiguard P0 acceptance cases for the refs-first gate (EPIC refs-derived-design).

Maps plan test-vectors.json TV-1 / TV-2 (切面 1 refs-gate MVP) onto a realistic
multi-layer aiguard project skeleton:

  <project>/C01-ID/01_refs/       — ID face-layout SSOT (deck-derived)
  <project>/C03-EE/01_refs/       — component + pin SSOT
  <project>/C04-Layout/01_refs/   — physical-constraint SSOT (board/face)

The gate is per-layer: a downstream C04 generation verb must find C04's own
01_refs/ SSOT before it may generate. TV-1 proves a missing SSOT hard-blocks
with REFS_SSOT_MISSING + a non-empty offending detail; TV-2 proves a populated,
traceable SSOT passes and yields a manifest the downstream can consume.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import REFS_SSOT_MISSING, RefsGateError, require_refs

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_BASELINE = (
    "# Reference Baseline\n\n"
    "authority order: formal deck > X01 BOM > OpenMV heritage > concept\n\n"
    "1. 01_正式需求書/N6核心郵票模組_訊倢需求說明_優化版v3.pptx — V1 scope AUTHORITY\n"
    "2. 02_第一代板_N6_X01參考/N6_X01 說明文件.pdf — gen-1 stamp board\n"
)


class AiguardRefsGateAcceptanceTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.proj = Path(tempfile.mkdtemp(prefix="aiguard-refs-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.proj, ignore_errors=True)

    def _seed_layer(self, layer: str, *, baseline=True, docs=()):
        refs = self.proj / layer / "01_refs"
        refs.mkdir(parents=True, exist_ok=True)
        if baseline:
            (refs / "Reference_Baseline.md").write_text(_BASELINE, encoding="utf-8")
        for rel, body in docs:
            p = refs / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                p.write_bytes(body)
            else:
                p.write_text(body, encoding="utf-8")
        return self.proj / layer

    # ── TV-1: 缺 SSOT → fail-fast typed error + 缺項清單 ─────────────────────
    def test_tv1_c04_missing_refs_hard_blocks(self):
        # C01/C03 SSOT exist, but the C04 layer the generation verb targets has
        # no 01_refs/ at all → downstream C04 generation must refuse.
        self._seed_layer("C01-ID", docs=[("C01_物理配置SSOT.md", "# 面向配置\nUSB-C=BOTTOM\n")])
        self._seed_layer("C03-EE", docs=[("C03_元件與腳位SSOT.md", "# 元件清單\nMCU, LBEE5KL1YN\n")])
        # (no C04-Layout/01_refs)
        with self.assertRaises(RefsGateError) as ctx:
            require_refs(self.proj / "C04-Layout", layer="C04")
        err = ctx.exception
        self.assertEqual(err.code, REFS_SSOT_MISSING)
        self.assertEqual(err.detail["layer"], "C04")
        # offending detail (缺項清單) non-empty and names the layer + reason.
        self.assertTrue(err.detail.get("refs_root"))
        self.assertEqual(err.detail["reason"], "root_not_visible")

    # ── TV-2: SSOT 齊備且可追溯 → 放行 ──────────────────────────────────────
    def test_tv2_c04_populated_refs_passes(self):
        self._seed_layer(
            "C04-Layout",
            docs=[
                ("C04_物理約束SSOT.md", "# 板框/面向\nboard 40x40, USB-C=BOTTOM\n"),
                ("01_正式需求書/N6需求說明_優化版v3.pptx", b"PK\x03\x04stub-deck"),
            ],
        )
        # require_refs takes the PRODUCT ROOT and derives <root>/C04-Layout/01_refs
        # from layer="C04"; the caller never pre-joins the stage folder.
        manifest = require_refs(self.proj, layer="C04")
        self.assertTrue(manifest.complete)
        self.assertTrue(manifest.root_visible)
        # authority order parsed from the deck-derived baseline.
        self.assertEqual(manifest.authority_order[0], "formal deck")
        # the rich-media deck is flagged unadjudicated (a reader must interpret
        # it before its content may be asserted); the .md SSOT is machine-read.
        d = manifest.to_dict()
        self.assertIn("01_正式需求書/N6需求說明_優化版v3.pptx", d["unadjudicated"])
        self.assertEqual(d["source_count"], 2)

    # ── cross-check: each layer gates independently ─────────────────────────
    def test_each_layer_gates_independently(self):
        self._seed_layer("C01-ID", docs=[("C01_物理配置SSOT.md", "x")])
        # C01 passes, C03 (unseeded) blocks — proves per-layer isolation.
        self.assertTrue(require_refs(self.proj, layer="C01").complete)
        with self.assertRaises(RefsGateError):
            require_refs(self.proj, layer="C03")


if __name__ == "__main__":
    unittest.main()
