"""Unit tests for the deliverable-cache extension of the token store
(plan mcp_r13-landing-webdav-cache, group 4: DD-5 / DD-7).

Reaper tests are fast-forward: last_used_at (sidecar) and the token dir mtime
are rewound directly so the class-aware reap / safety-net paths observe an
"aged" entry immediately — no sleeping (docxmcp test_webdav_cache_reaper.py
pattern).
"""
import importlib
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = str(REPO_ROOT / "services" / "mcp")
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class CacheStoreBase(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-cache-", dir=PRIVATE_BASE))
        os.environ["BODESIGN_SESSIONS_ROOT"] = str(self.work)
        self.ts = importlib.import_module("token_store")
        importlib.reload(self.ts)
        self.store = self.ts.TokenStore(root=self.work)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        for key in ("BODESIGN_SESSIONS_ROOT", "BODESIGN_TOKEN_TTL_SECONDS",
                    "BODESIGN_CACHE_SAFETY_TTL_SECONDS", "BODESIGN_CACHE_SAFETY_WARN_SECONDS"):
            os.environ.pop(key, None)

    # helpers ------------------------------------------------------------
    def _age(self, token: str, seconds: float) -> None:
        """Rewind BOTH clocks the reaper reads: dir mtime and (if a cache)
        the sidecar last_used_at."""
        past = time.time() - seconds
        os.utime(self.work / token, (past, past))
        meta_path = self.work / (token + self.ts._META_SUFFIX)
        if meta_path.exists():
            meta = self.ts.TokenStore._parse_meta(meta_path)
            meta.last_used_at = past
            self.store._write_meta(meta)

    def _write(self, token: str, rel: str, text: str = "x") -> Path:
        doc_dir = self.work / token
        target = self.store.safe_join(doc_dir, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target


class CacheMetadataTests(CacheStoreBase):
    """4.1: sidecar metadata roundtrip, idempotent provision, dirty/clean."""

    def test_provision_mints_and_persists_sidecar(self):
        meta = self.store.provision_cache("alice", "subj-1")
        self.assertTrue(meta.token.startswith("tok_"))
        self.assertEqual(meta.kind, "deliverable-cache")
        self.assertEqual(meta.owner_identity, "alice")
        self.assertEqual(meta.subject_id, "subj-1")
        self.assertIsNone(meta.last_export_at)
        self.assertTrue((self.work / (meta.token + ".meta.json")).is_file())

    def test_metadata_survives_restart(self):
        meta = self.store.provision_cache("alice", "subj-1")
        self.store.mark_exported(meta.token)
        # a "restart": brand-new store instance over the same root
        fresh = self.ts.TokenStore(root=self.work)
        loaded = fresh.cache_meta(meta.token)
        self.assertEqual(loaded.owner_identity, "alice")
        self.assertEqual(loaded.subject_id, "subj-1")
        self.assertIsNotNone(loaded.last_export_at)

    def test_provision_is_idempotent_per_owner_subject(self):
        a = self.store.provision_cache("alice", "subj-1")
        b = self.store.provision_cache("alice", "subj-1")
        self.assertEqual(a.token, b.token)
        # different subject or owner → different cache
        self.assertNotEqual(a.token, self.store.provision_cache("alice", "subj-2").token)
        self.assertNotEqual(a.token, self.store.provision_cache("bob", "subj-1").token)

    def test_provision_rejects_empty_identity(self):
        with self.assertRaises(self.ts.StoreOpError):
            self.store.provision_cache("", "subj")
        with self.assertRaises(self.ts.StoreOpError):
            self.store.provision_cache("alice", "")

    def test_dirty_clean_mark_exported_transitions(self):
        meta = self.store.provision_cache("alice", "s")
        # never exported + empty tree → clean (no files exist)
        self.assertTrue(self.store.is_cache_clean(meta.token))
        # never exported + a file → dirty
        self._write(meta.token, "a/out.txt")
        self.assertFalse(self.store.is_cache_clean(meta.token))
        self.assertEqual(self.store.cache_dirty_files(meta.token), ["a/out.txt"])
        # export stamps last_export_at → clean
        self.store.mark_exported(meta.token)
        self.assertTrue(self.store.is_cache_clean(meta.token))
        # touch a file newer than the export stamp → dirty again
        target = self._write(meta.token, "a/out.txt", "v2")
        future = time.time() + 5
        os.utime(target, (future, future))
        self.assertFalse(self.store.is_cache_clean(meta.token))

    def test_cache_meta_unknown_token(self):
        with self.assertRaises(self.ts.TokenNotFoundError):
            self.store.cache_meta("tok_doesnotexist")

    def test_cache_meta_on_plain_token_is_not_found(self):
        token, _ = self.store.new_token()
        with self.assertRaises(self.ts.TokenNotFoundError):
            self.store.cache_meta(token)


class StructureHelperTests(CacheStoreBase):
    """4.2: mkdir / move / copy with traversal defence + overwrite semantics."""

    def setUp(self):
        super().setUp()
        self.token, _ = self.store.new_token()

    def test_mkdir_creates_and_is_idempotent(self):
        p = self.store.mkdir(self.token, "a/b/c")
        self.assertTrue(p.is_dir())
        self.assertEqual(p, self.store.mkdir(self.token, "a/b/c"))

    def test_mkdir_over_file_rejected(self):
        self._write(self.token, "f.txt")
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.store.mkdir(self.token, "f.txt")
        self.assertEqual(cm.exception.code, "MKCOL_NOT_DIR")

    def test_traversal_rejected_same_typed_error(self):
        self._write(self.token, "f.txt")
        for fn in (lambda: self.store.mkdir(self.token, "../esc"),
                   lambda: self.store.move(self.token, "f.txt", "../esc"),
                   lambda: self.store.move(self.token, "../esc", "f2"),
                   lambda: self.store.copy(self.token, "f.txt", "../../etc/x")):
            with self.assertRaises(ValueError):
                fn()

    def test_move_new_dest_reports_created(self):
        self._write(self.token, "src.txt", "data")
        path, created = self.store.move(self.token, "src.txt", "sub/dst.txt")
        self.assertTrue(created)  # DAV → 201
        self.assertEqual(path.read_text(), "data")
        self.assertFalse((self.work / self.token / "src.txt").exists())

    def test_move_overwrite_reports_not_created(self):
        self._write(self.token, "src.txt", "new")
        self._write(self.token, "dst.txt", "old")
        path, created = self.store.move(self.token, "src.txt", "dst.txt")
        self.assertFalse(created)  # DAV → 204
        self.assertEqual(path.read_text(), "new")

    def test_move_no_overwrite_rejected(self):
        self._write(self.token, "src.txt")
        self._write(self.token, "dst.txt")
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.store.move(self.token, "src.txt", "dst.txt", overwrite=False)
        self.assertEqual(cm.exception.code, "MOVE_DEST_EXISTS")

    def test_move_missing_src(self):
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.store.move(self.token, "nope.txt", "d.txt")
        self.assertEqual(cm.exception.code, "MOVE_SRC_MISSING")

    def test_copy_preserves_source_file(self):
        self._write(self.token, "src.txt", "data")
        path, created = self.store.copy(self.token, "src.txt", "cp.txt")
        self.assertTrue(created)
        self.assertEqual(path.read_text(), "data")
        self.assertTrue((self.work / self.token / "src.txt").exists())

    def test_copy_directory_tree(self):
        self._write(self.token, "d/a.txt", "1")
        self._write(self.token, "d/sub/b.txt", "2")
        path, created = self.store.copy(self.token, "d", "d2")
        self.assertTrue(created)
        self.assertEqual((path / "a.txt").read_text(), "1")
        self.assertEqual((path / "sub" / "b.txt").read_text(), "2")
        self.assertTrue((self.work / self.token / "d" / "a.txt").exists())

    def test_copy_overwrite_semantics(self):
        self._write(self.token, "src.txt", "new")
        self._write(self.token, "dst.txt", "old")
        _, created = self.store.copy(self.token, "src.txt", "dst.txt")
        self.assertFalse(created)
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.store.copy(self.token, "src.txt", "dst.txt", overwrite=False)
        self.assertEqual(cm.exception.code, "COPY_DEST_EXISTS")

    def test_copy_missing_src(self):
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.store.copy(self.token, "nope", "d")
        self.assertEqual(cm.exception.code, "COPY_SRC_MISSING")

    def test_helpers_unknown_token(self):
        with self.assertRaises(self.ts.TokenNotFoundError):
            self.store.mkdir("tok_nope", "a")


class ReaperClassAwareTests(CacheStoreBase):
    """4.3/4.4: class-aware reaper state machine, fast-forward."""

    def test_idle_reap_is_class_aware(self):
        os.environ["BODESIGN_TOKEN_TTL_SECONDS"] = "3600"
        os.environ["BODESIGN_CACHE_SAFETY_TTL_SECONDS"] = "604800"
        eph, _ = self.store.new_token()
        cache = self.store.provision_cache("alice", "s")
        self._age(eph, 7200)     # past 1h idle TTL
        self._age(cache.token, 7200)
        removed = self.store.reap()
        self.assertEqual(removed, 1)
        self.assertFalse((self.work / eph).exists())          # ephemeral reaped
        self.assertTrue((self.work / cache.token).is_dir())   # deliverable retained
        self.assertTrue((self.work / (cache.token + ".meta.json")).exists())

    def test_safety_net_warn_first_does_not_reclaim(self):
        os.environ["BODESIGN_CACHE_SAFETY_TTL_SECONDS"] = "100"
        os.environ["BODESIGN_CACHE_SAFETY_WARN_SECONDS"] = "40"
        cache = self.store.provision_cache("alice", "s")
        self._age(cache.token, 80)  # warn zone: (60, 100)
        with self.assertLogs("bodesign.token_store", level="WARNING") as logs:
            reclaimed = self.store.reap_safety_net()
        self.assertEqual(reclaimed, 0)
        self.assertTrue((self.work / cache.token).is_dir())
        self.assertTrue(any("reaper_safety_net_warn" in m for m in logs.output))

    def test_safety_net_reclaims_past_full_ttl(self):
        os.environ["BODESIGN_CACHE_SAFETY_TTL_SECONDS"] = "100"
        os.environ["BODESIGN_CACHE_SAFETY_WARN_SECONDS"] = "40"
        cache = self.store.provision_cache("alice", "s")
        self._age(cache.token, 120)  # past the 100s floor
        self.assertEqual(self.store.reap_safety_net(), 1)
        self.assertFalse((self.work / cache.token).exists())
        self.assertFalse((self.work / (cache.token + ".meta.json")).exists())
        with self.assertRaises(self.ts.TokenNotFoundError):
            self.store.resolve(cache.token)

    def test_safety_net_reactivation_resets_clock(self):
        os.environ["BODESIGN_CACHE_SAFETY_TTL_SECONDS"] = "100"
        os.environ["BODESIGN_CACHE_SAFETY_WARN_SECONDS"] = "40"
        cache = self.store.provision_cache("alice", "s")
        self._age(cache.token, 90)  # warn zone
        self.assertEqual(self.store.reap_safety_net(), 0)  # warned, not reaped
        self.store.touch_cache(cache.token)                # user comes back
        self.assertEqual(self.store.reap_safety_net(), 0)  # fresh again
        self.assertTrue((self.work / cache.token).is_dir())

    def test_safety_net_ignores_ephemeral(self):
        os.environ["BODESIGN_TOKEN_TTL_SECONDS"] = "100000"  # idle reaper out of the way
        os.environ["BODESIGN_CACHE_SAFETY_TTL_SECONDS"] = "100"
        eph, _ = self.store.new_token()
        self._age(eph, 200)
        self.assertEqual(self.store.reap_safety_net(), 0)
        self.assertTrue((self.work / eph).is_dir())

    def test_safety_net_disabled_when_ttl_nonpositive(self):
        os.environ["BODESIGN_CACHE_SAFETY_TTL_SECONDS"] = "0"
        cache = self.store.provision_cache("alice", "s")
        self._age(cache.token, 10**9)
        self.assertEqual(self.store.reap_safety_net(), 0)
        self.assertTrue((self.work / cache.token).is_dir())


if __name__ == "__main__":
    unittest.main()
