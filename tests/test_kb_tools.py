"""Domain KB serving tools (plan mcp_r16-domain-kb) — TV-1..TV-5, TV-7.

Unit-level: calls the _h_kb_query/_h_kb_get handlers (and run_tool for the
typed-error surface) directly against the real repo KB at
.specbase/ragbase.sqlite, with BODESIGN_KB_DB patched per test. TV-6 (two-door
consistency vs specbase gate.ts) is a live check run by the orchestrator.
"""
import importlib
import json
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DB = REPO_ROOT / ".specbase" / "ragbase.sqlite"
KNOWN_ID = "control.pcb.emc-decoupling-placement"


class KbToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = importlib.import_module("services.mcp.server")

    def _env(self, db_path):
        return patch.dict(os.environ, {"BODESIGN_KB_DB": str(db_path)})

    # TV-1: FTS happy path — existing distilled object reachable in-band.
    def test_tv1_fts_hits_known_object(self):
        with self._env(KB_DB):
            result = self.server._h_kb_query({"q": "EMC decoupling"})
        # A1 (BR_A Fix1): multi-word default recall is OR-ranked, self-describing
        # matchMode -> "fts-or" (was bare "fts" before the OR-ranked fix).
        self.assertEqual(result["matchMode"], "fts-or")
        ids = [h["id"] for h in result["hits"]]
        self.assertIn(KNOWN_ID, ids)
        self.assertGreater(result["total"], 0)
        hit = next(h for h in result["hits"] if h["id"] == KNOWN_ID)
        for field in ("id", "type", "title", "score", "confidence", "source_weight"):
            self.assertIn(field, hit)

    # TV-2: short CJK tokens degrade to LIKE scan, self-described.
    def test_tv2_short_tokens_like_scan(self):
        with self._env(KB_DB):
            result = self.server._h_kb_query({"q": "佈線"})
        self.assertEqual(result["matchMode"], "like-scan")
        for h in result["hits"]:
            self.assertEqual(h["score"], 0)

    def test_tv2b_mixed_tokens_hybrid(self):
        with self._env(KB_DB):
            result = self.server._h_kb_query({"q": "EMC 佈線"})
        # A1: mixed long+short tokens, OR-ranked default -> "hybrid-or".
        self.assertEqual(result["matchMode"], "hybrid-or")

    # TV-3: KB file missing → typed fail-fast with remedy (run_tool surface).
    def test_tv3_kb_missing_unavailable(self):
        with self._env("/nonexistent/kb.sqlite"):
            out = self.server.run_tool("bodesign_kb_query", {"q": "anything"})
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("isError"))
        self.assertTrue(out["error"].startswith("KB_UNAVAILABLE"))
        self.assertIn("remedy:", out["error"])

    def test_tv3b_env_unset_unavailable(self):
        env = {k: v for k, v in os.environ.items() if k != "BODESIGN_KB_DB"}
        with patch.dict(os.environ, env, clear=True):
            out = self.server.run_tool("bodesign_kb_query", {"q": "anything"})
        self.assertFalse(out["ok"])
        self.assertTrue(out["error"].startswith("KB_UNAVAILABLE"))
        self.assertIn("remedy:", out["error"])

    # TV-4: kb_get returns full body + provenance grading.
    def test_tv4_kb_get_full_object(self):
        with self._env(KB_DB):
            result = self.server._h_kb_get({"id": KNOWN_ID})
        for field in ("body_md", "confidence", "source_weight", "provenance"):
            self.assertIn(field, result)
        self.assertTrue(result["body_md"].strip())
        self.assertEqual(result["id"], KNOWN_ID)

    def test_tv4b_kb_get_unknown_id(self):
        with self._env(KB_DB):
            out = self.server.run_tool("bodesign_kb_get", {"id": "no.such.object"})
        self.assertFalse(out["ok"])
        self.assertTrue(out["error"].startswith("KB_OBJECT_NOT_FOUND: no.such.object"))
        self.assertIn("consider: bodesign_kb_query", out["error"])

    # TV-5: read-only enforced — write attempt on the serving connection fails.
    def test_tv5_query_only_blocks_writes(self):
        with self._env(KB_DB):
            conn = self.server._kb_connect()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute(
                    "INSERT INTO ragbase_objects (id, type, title, updated_at) "
                    "VALUES ('test.write.attempt', 'concept', 'x', 0)")
        finally:
            conn.close()

    # TV-7: empty query rejected.
    def test_tv7_empty_query_rejected(self):
        with self._env(KB_DB):
            out = self.server.run_tool("bodesign_kb_query", {"q": "  "})
        self.assertFalse(out["ok"])
        self.assertTrue(out["error"].startswith("KB_BAD_QUERY"))

    # Contract guards: schema registration + read-only declarations.
    def test_tools_registered_core_readonly(self):
        for name in ("bodesign_kb_query", "bodesign_kb_get"):
            spec = self.server.TOOLS_BY_NAME[name]
            self.assertEqual(spec["group"], "core")
            self.assertTrue(spec["description"].startswith("READ-ONLY"))
            self.assertTrue(spec["annotations"]["readOnlyHint"])
        q_schema = self.server.TOOLS_BY_NAME["bodesign_kb_query"]["schema"]
        self.assertEqual(q_schema["required"], ["q"])
        self.assertIn("type", q_schema["properties"])
        self.assertIn("limit", q_schema["properties"])

    def test_type_filter_and_limit(self):
        with self._env(KB_DB):
            result = self.server._h_kb_query({"q": "EMC", "type": "control", "limit": 3})
        self.assertLessEqual(len(result["hits"]), 3)
        for h in result["hits"]:
            self.assertEqual(h["type"], "control")

    # --- A1 (BR_A Fix1): multi-word discoverability — OR-ranked recall ---
    # Baseline crash (implicit-AND): an in-store object reachable by a single
    # word drops to total=0 as soon as a co-occurring word is added, because
    # `_kb_match_plan` joins FTS tokens with AND. After the OR-ranked fix these
    # multi-word situational queries MUST recall the object again.

    def _ids(self, q, **kw):
        with self._env(KB_DB):
            r = self.server._h_kb_query({"q": q, **kw})
        return [h["id"] for h in r["hits"]], r

    def test_a1_multiword_recalls_crystal_object(self):
        ids, r = self._ids("crystal oscillator load capacitor")
        self.assertIn("control.si.crystal-oscillator-layout", ids)
        self.assertGreater(r["total"], 0)

    def test_a1_multiword_recalls_decoupling_object(self):
        ids, r = self._ids("regulator LDO buck decoupling")
        self.assertIn("control.power.decoupling-pdn-strategy", ids)
        self.assertGreater(r["total"], 0)

    def test_a1_matchmode_self_describes_or(self):
        # multi-word default recall reports an OR-flavoured matchMode, not bare "fts"
        _, r = self._ids("crystal oscillator load capacitor")
        self.assertIn(r["matchMode"], ("fts-or", "fts"))
        self.assertIn("or", r["matchMode"].lower())

    def test_a1_single_word_recall_not_regressed(self):
        # the single-word hit sets that already worked must not shrink
        crystal_ids, cr = self._ids("crystal")
        self.assertIn("control.si.crystal-oscillator-layout", crystal_ids)
        self.assertGreaterEqual(cr["total"], 10)
        dec_ids, dr = self._ids("decoupling")
        self.assertIn("control.power.decoupling-pdn-strategy", dec_ids)
        self.assertGreaterEqual(dr["total"], 19)

    def test_a1_mode_all_preserves_exact_and(self):
        # opt-in exact AND: the multi-word query that OR-recalls stays 0 under AND,
        # proving mode=all still enforces conjunction (no silent widening).
        _, r_or = self._ids("crystal oscillator load capacitor")
        _, r_and = self._ids("crystal oscillator load capacitor", mode="all")
        self.assertGreater(r_or["total"], 0)
        self.assertEqual(r_and["total"], 0)
        self.assertIn(r_and["matchMode"], ("fts-and", "fts"))

    def test_a1_or_ranks_target_near_top(self):
        # bm25 ordering: the intended object should rank in the top results,
        # not be buried under OR noise.
        ids, _ = self._ids("crystal oscillator load capacitor", limit=10)
        self.assertIn("control.si.crystal-oscillator-layout", ids[:5])


if __name__ == "__main__":
    unittest.main()
