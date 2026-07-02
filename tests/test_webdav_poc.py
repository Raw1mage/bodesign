"""WebDAV deliverable-cache PoC tests (plan mcp_r13-landing-webdav-cache,
group 5: DD-4/DD-5/DD-6, AC-4).

Two layers:

* **Pure-protocol tests** (no starlette required): the `_webdav` composer,
  the `_auth_provider` credential store/provider, and the cache lifecycle
  logic in `server.py` driven directly against the token store. These run
  under the bare host python3.
* **HTTP-integration tests** (skipUnless starlette+httpx importable): the
  REAL routes from ``server.build_cache_dav_routes()`` through a Starlette
  TestClient — the same code uvicorn serves. Ported from docxmcp
  tests/test_webdav_poc.py.
"""
from __future__ import annotations

import base64
import importlib
import json
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

try:
    from starlette.applications import Starlette  # noqa: F401
    from starlette.testclient import TestClient
    HAVE_STARLETTE = True
    _STARLETTE_SKIP = ""
except ImportError as _exc:  # host venv without starlette/httpx (expected per AGENTS)
    HAVE_STARLETTE = False
    _STARLETTE_SKIP = f"starlette/httpx not importable in this interpreter: {_exc}"

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _basic(owner: str, password: str = "x") -> dict:
    tok = base64.b64encode(f"{owner}:{password}".encode()).decode()
    return {"Authorization": f"Basic {tok}"}


class CacheEnvBase(unittest.TestCase):
    """Fresh sessions root + credential file + provider singleton per test."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-dav-", dir=PRIVATE_BASE))
        os.environ["BODESIGN_SESSIONS_ROOT"] = str(self.work / "sessions")
        os.environ["BODESIGN_WEBDAV_CRED_PATH"] = str(self.work / ".webdav-creds.json")
        self.ts = importlib.import_module("token_store")
        self.ap = importlib.import_module("_auth_provider")
        self.dav = importlib.import_module("_webdav")
        self.server = importlib.import_module("server")
        self.ap.reset_default_provider_for_testing()
        self.store = self.ts.default_store()

    def tearDown(self):
        self.ap.reset_default_provider_for_testing()
        shutil.rmtree(self.work, ignore_errors=True)
        for key in ("BODESIGN_SESSIONS_ROOT", "BODESIGN_WEBDAV_CRED_PATH",
                    "BODESIGN_CACHE_SOFT_CAP_COUNT", "BODESIGN_CACHE_SOFT_CAP_BYTES",
                    "BODESIGN_DAV_MAX_PUT_BYTES"):
            os.environ.pop(key, None)


# ── pure protocol: _webdav composer (task 5.1) ───────────────────────────

class WebdavComposerTests(unittest.TestCase):
    def setUp(self):
        self.dav = importlib.import_module("_webdav")
        self.dir = Path(tempfile.mkdtemp(prefix="dav-composer-"))
        (self.dir / "a.md").write_text("A")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "b.md").write_text("B")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_options_headers_class2(self):
        h = self.dav.options_headers()
        self.assertEqual(h["DAV"], "1, 2")
        for m in ("PROPFIND", "LOCK", "MKCOL", "MOVE", "COPY"):
            self.assertIn(m, h["Allow"])

    def test_propfind_depth1_not_recursive(self):
        res = self.dav.build_propfind("/dav/tok_x", self.dir, "", "1")
        hrefs = [r.href for r in res]
        self.assertIn("/dav/tok_x/", hrefs)          # self (collection, trailing /)
        self.assertIn("/dav/tok_x/a.md", hrefs)      # immediate file
        self.assertIn("/dav/tok_x/sub/", hrefs)      # immediate subdir
        self.assertNotIn("/dav/tok_x/sub/b.md", hrefs)  # depth 1 is not recursive

    def test_propfind_depth0_self_only(self):
        res = self.dav.build_propfind("/dav/tok_x", self.dir, "", "0")
        self.assertEqual(len(res), 1)
        self.assertTrue(res[0].is_collection)

    def test_propfind_file_target_and_404(self):
        res = self.dav.build_propfind("/dav/tok_x", self.dir, "a.md", "1")
        self.assertEqual(len(res), 1)
        self.assertFalse(res[0].is_collection)
        self.assertEqual(res[0].size, 1)
        with self.assertRaises(self.dav.PropfindNotFound):
            self.dav.build_propfind("/dav/tok_x", self.dir, "nope.md", "0")

    def test_multistatus_xml_well_formed(self):
        from xml.dom import minidom
        res = self.dav.build_propfind("/dav/tok_x", self.dir, "", "1")
        xml = self.dav.multistatus_xml(res)
        minidom.parseString(xml)
        self.assertIn("D:multistatus", xml)
        self.assertIn("a.md", xml)

    def test_normalise_depth(self):
        self.assertEqual(self.dav.normalise_depth(None), "1")
        self.assertEqual(self.dav.normalise_depth("0"), "0")
        self.assertEqual(self.dav.normalise_depth("infinity"), "1")

    def test_parse_timeout_header(self):
        d = self.dav.DEFAULT_LOCK_TTL_SECONDS
        self.assertEqual(self.dav.parse_timeout_header(None), d)
        self.assertEqual(self.dav.parse_timeout_header("Second-600"), 600)
        self.assertEqual(self.dav.parse_timeout_header("Infinite"), d)
        self.assertEqual(self.dav.parse_timeout_header("Second-99999999"),
                         self.dav.MAX_LOCK_TTL_SECONDS)
        self.assertEqual(self.dav.parse_timeout_header("Second-bogus"), d)

    def test_lock_table_exclusive_and_release(self):
        lt = self.dav.LockTable()
        lock = lt.acquire("tok_x", "f.md", "alice", ttl=60)
        self.assertIsNotNone(lock)
        # other identity is refused
        self.assertIsNone(lt.acquire("tok_x", "f.md", "bob", ttl=60))
        self.assertIsNotNone(lt.check("tok_x", "f.md", "bob"))   # blocking for bob
        self.assertIsNone(lt.check("tok_x", "f.md", "alice"))    # never blocks holder
        # release requires the matching locktoken
        self.assertFalse(lt.release("tok_x", "f.md", "opaquelocktoken:wrong"))
        self.assertTrue(lt.release("tok_x", "f.md", lock.token))
        self.assertIsNone(lt.check("tok_x", "f.md", "bob"))

    def test_lock_expiry_is_lazy_swept(self):
        lt = self.dav.LockTable()
        lock = lt.acquire("tok_x", "f.md", "alice", ttl=60)
        lock.expires_at = time.time() - 1
        self.assertIsNone(lt.check("tok_x", "f.md", "bob"))  # expired == absent


# ── pure protocol: _auth_provider (task 5.2) ─────────────────────────────

class AuthProviderTests(CacheEnvBase):
    def test_issue_verify_rotate_revoke(self):
        creds = self.ap.WebDavCredentialStore()
        pw1 = creds.issue("alice")
        self.assertTrue(creds.verify("alice", pw1))
        self.assertFalse(creds.verify("alice", "wrong"))
        self.assertFalse(creds.verify("ghost", pw1))
        # rotate: old password stops working, new one is returned plaintext once
        pw2 = creds.issue("alice")
        self.assertNotEqual(pw1, pw2)
        self.assertFalse(creds.verify("alice", pw1))
        self.assertTrue(creds.verify("alice", pw2))
        # plaintext never stored
        raw = Path(os.environ["BODESIGN_WEBDAV_CRED_PATH"]).read_text()
        self.assertNotIn(pw2, raw)
        self.assertTrue(creds.revoke("alice"))
        self.assertFalse(creds.verify("alice", pw2))
        self.assertFalse(creds.revoke("alice"))

    def test_credentials_persist_across_reload(self):
        pw = self.ap.WebDavCredentialStore().issue("alice")
        again = self.ap.WebDavCredentialStore()
        self.assertTrue(again.verify("alice", pw))

    def test_resolve_identity_typed_failures_no_fallback(self):
        provider = self.ap.BuiltinAuthProvider()
        with self.assertRaises(self.ap.AuthError) as cm:
            provider.resolve_identity(auth_header=None, cookies={})
        self.assertEqual(cm.exception.code, "AUTH_REQUIRED")
        with self.assertRaises(self.ap.AuthError) as cm:
            provider.resolve_identity(auth_header="Basic !!notb64!!", cookies={})
        self.assertEqual(cm.exception.code, "AUTH_BASIC_MALFORMED")
        pw = provider.credentials.issue("alice")
        with self.assertRaises(self.ap.AuthError) as cm:
            provider.resolve_identity(
                auth_header=_basic("alice", "wrong")["Authorization"], cookies={})
        self.assertEqual(cm.exception.code, "AUTH_BASIC_REJECTED")
        ident = provider.resolve_identity(
            auth_header=_basic("alice", pw)["Authorization"], cookies={})
        self.assertEqual(ident.owner_identity, "alice")
        self.assertEqual(ident.method, "basic")

    def test_owns_is_strict_equality(self):
        provider = self.ap.BuiltinAuthProvider()
        ident = self.ap.Identity(owner_identity="alice", method="basic")
        self.assertTrue(provider.owns(ident, "alice"))
        self.assertFalse(provider.owns(ident, "bob"))
        self.assertFalse(provider.owns(self.ap.Identity("", "basic"), ""))


# ── pure logic: cache lifecycle against the store (tasks 5.3/5.5) ────────

class CacheLifecycleLogicTests(CacheEnvBase):
    def _seed(self, owner="alice", subject="s"):
        meta = self.store.provision_cache(owner, subject)
        root = self.work / "sessions" / meta.token
        (root / "a.md").write_text("A")
        return meta

    def test_export_copies_tree_and_marks(self):
        meta = self._seed()
        target = self.work / "land"
        result = self.server._cache_export_tree(self.store, meta.token, target)
        self.assertEqual(result["count"], 1)
        self.assertEqual((target / "a.md").read_text(), "A")
        self.assertIsNotNone(self.store.cache_meta(meta.token).last_export_at)

    def test_export_target_parent_missing_is_typed(self):
        meta = self._seed()
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.server._cache_export_tree(
                self.store, meta.token, self.work / "no" / "such" / "dir")
        self.assertEqual(cm.exception.code, "EXPORT_TARGET_UNREACHABLE")

    def test_export_relative_target_rejected(self):
        meta = self._seed()
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.server._cache_export_tree(self.store, meta.token, Path("relative/dir"))
        self.assertEqual(cm.exception.code, "EXPORT_TARGET_UNREACHABLE")

    def test_close_dirty_gate_and_force(self):
        meta = self._seed()
        with self.assertRaises(self.ts.StoreOpError) as cm:
            self.server._cache_close(self.store, meta.token)
        self.assertEqual(cm.exception.code, "WORKSPACE_CLOSE_DIRTY")
        self.assertIn("a.md", cm.exception.unexported)
        result = self.server._cache_close(self.store, meta.token, force=True)
        self.assertTrue(result["closed"] and result["forced"])
        with self.assertRaises(self.ts.TokenNotFoundError):
            self.store.cache_meta(meta.token)

    def test_close_clean_after_export(self):
        meta = self._seed()
        self.server._cache_export_tree(self.store, meta.token, self.work / "land")
        result = self.server._cache_close(self.store, meta.token)
        self.assertTrue(result["closed"])
        self.assertFalse(result["forced"])

    def test_soft_cap_warn_first_signal(self):
        os.environ["BODESIGN_CACHE_SOFT_CAP_COUNT"] = "2"
        for i in range(3):
            self.store.provision_cache("alice", f"s{i}")
        sc = self.server._cache_soft_cap_status(self.store, "alice")
        self.assertTrue(sc["over"] and sc["over_count"])
        self.assertEqual((sc["count"], sc["count_cap"]), (3, 2))
        # per-owner boundary: bob is unaffected
        self.store.provision_cache("bob", "s0")
        self.assertFalse(self.server._cache_soft_cap_status(self.store, "bob")["over"])

    def test_mcp_tool_handlers_provision_export_close(self):
        r = self.server._h_cache_provision({"owner_identity": "alice", "subject_id": "s"})
        self.assertIn("token", r)
        self.assertEqual(r["webdav_username"], "alice")
        self.assertTrue(r["webdav_password"])
        self.assertIn("/dav/" + r["token"], r["mount_url"])
        # password is real: the provider verifies it
        self.assertTrue(self.ap.default_provider().credentials.verify(
            "alice", r["webdav_password"]))
        token = r["token"]
        (self.work / "sessions" / token / "x.md").write_text("X")
        # cross-owner tool access is typed CACHE_FORBIDDEN
        r = self.server._h_cache_export(
            {"cache_token": token, "owner_identity": "bob", "target": str(self.work / "l")})
        self.assertEqual(r["error"], "CACHE_FORBIDDEN")
        r = self.server._h_cache_close({"cache_token": token, "owner_identity": "bob"})
        self.assertEqual(r["error"], "CACHE_FORBIDDEN")
        # owner path: export then dirty-close then clean close
        r = self.server._h_cache_close({"cache_token": token, "owner_identity": "alice"})
        self.assertEqual(r["error"], "WORKSPACE_CLOSE_DIRTY")
        self.assertIn("x.md", r["unexported"])
        r = self.server._h_cache_export(
            {"cache_token": token, "owner_identity": "alice", "target": str(self.work / "l")})
        self.assertTrue(r["exported"])
        r = self.server._h_cache_close({"cache_token": token, "owner_identity": "alice"})
        self.assertTrue(r["closed"])

    def test_cache_tools_registered_additively(self):
        names = {t["name"] for t in self.server.TOOLS}
        for n in ("bodesign_cache_provision", "bodesign_cache_export", "bodesign_cache_close"):
            self.assertIn(n, names)
        # additive only: the compute-plane surface is still there (v0.2.0:
        # ingest_project landed — it is a gate.py verb now, not an MCP tool)
        for n in ("bodesign_stage_dir", "bodesign_emit_fab"):
            self.assertIn(n, names)


# ── HTTP integration: the real route factory over TestClient (AC-4) ──────

@unittest.skipUnless(HAVE_STARLETTE, _STARLETTE_SKIP)
class WebdavHttpBase(CacheEnvBase):
    def setUp(self):
        super().setUp()
        from starlette.applications import Starlette
        # Real provider (Basic-only), pre-seeded credentials per owner.
        self.provider = self.ap.BuiltinAuthProvider()
        self.ap._default_provider = self.provider
        self.passwords = {o: self.provider.credentials.issue(o)
                          for o in ("alice", "bob")}
        app = Starlette(routes=self.server.build_cache_dav_routes())
        self.client = TestClient(app)

    def auth(self, owner: str) -> dict:
        return _basic(owner, self.passwords[owner])

    def provision(self, owner: str, subject: str) -> dict:
        r = self.client.post("/caches", json={"subject_id": subject},
                             headers=self.auth(owner))
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        # provision rotates the credential; adopt the returned password
        self.passwords[owner] = body["webdav_password"]
        return body


@unittest.skipUnless(HAVE_STARLETTE, _STARLETTE_SKIP)
class WebdavPocRoundtripTests(WebdavHttpBase):
    def test_full_lifecycle_over_the_wire(self):
        """AC-4: provision → OPTIONS → PUT×2 → PROPFIND → GET → MOVE →
        dirty-close 409 → export → close 200."""
        body = self.provision("alice", "boardX-fab")
        token = body["token"]
        self.assertEqual(body["owner"], "alice")
        self.assertEqual(body["webdav_username"], "alice")
        self.assertIn(f"/dav/{token}", body["mount_url"])
        self.assertIn("soft_cap", body)
        A = self.auth("alice")
        base = f"/dav/{token}"

        # OPTIONS advertises class-2 (identity-free probe)
        r = self.client.request("OPTIONS", base)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["DAV"], "1, 2")
        self.assertIn("PROPFIND", r.headers["Allow"])
        self.assertIn("LOCK", r.headers["Allow"])

        # PUT ×2
        r = self.client.request("PUT", f"{base}/body.md", content=b"# Fab\n", headers=A)
        self.assertEqual(r.status_code, 201, r.text)
        r = self.client.request("PUT", f"{base}/gerbers/top.gbr", content=b"G04*", headers=A)
        self.assertEqual(r.status_code, 201)

        # PROPFIND depth 1: immediate members only (RFC 4918 §9.1)
        r = self.client.request("PROPFIND", base, headers={**A, "Depth": "1"})
        self.assertEqual(r.status_code, 207, r.text)
        self.assertIn("body.md", r.text)
        self.assertIn("gerbers/", r.text)
        self.assertNotIn("top.gbr", r.text)  # depth 1 is not recursive
        from xml.dom import minidom
        minidom.parseString(r.text)
        # PROPFIND into the subdir surfaces the file; missing rel is 404
        r = self.client.request("PROPFIND", f"{base}/gerbers", headers={**A, "Depth": "1"})
        self.assertEqual(r.status_code, 207)
        self.assertIn("top.gbr", r.text)
        r = self.client.request("PROPFIND", f"{base}/nope.md", headers={**A, "Depth": "0"})
        self.assertEqual(r.status_code, 404)

        # GET
        r = self.client.request("GET", f"{base}/body.md", headers=A)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"# Fab\n")

        # MKCOL
        r = self.client.request("MKCOL", f"{base}/media", headers=A)
        self.assertEqual(r.status_code, 201)

        # MOVE (rename) — new destination → 201
        r = self.client.request(
            "MOVE", f"{base}/body.md",
            headers={**A, "Destination": f"http://testserver{base}/body-final.md"})
        self.assertEqual(r.status_code, 201, r.text)
        r = self.client.request("GET", f"{base}/body-final.md", headers=A)
        self.assertEqual(r.content, b"# Fab\n")
        r = self.client.request("GET", f"{base}/body.md", headers=A)
        self.assertEqual(r.status_code, 404)

        # dirty close → 409 with unexported list
        r = self.client.post(f"/caches/{token}/close", json={}, headers=A)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "WORKSPACE_CLOSE_DIRTY")
        self.assertIn("body-final.md", r.json()["unexported"])

        # export → clean close 200
        land = self.work / "landing"
        r = self.client.post(f"/caches/{token}/export",
                             json={"target": str(land)}, headers=A)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((land / "body-final.md").read_bytes(), b"# Fab\n")
        self.assertEqual((land / "gerbers/top.gbr").read_bytes(), b"G04*")
        r = self.client.post(f"/caches/{token}/close", json={}, headers=A)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["closed"])

    def test_provision_idempotent_per_owner_subject(self):
        t1 = self.provision("alice", "subjX")["token"]
        t2 = self.provision("alice", "subjX")["token"]
        self.assertEqual(t1, t2)
        t3 = self.provision("alice", "subjY")["token"]
        self.assertNotEqual(t1, t3)

    def test_copy_preserves_source(self):
        token = self.provision("alice", "cp")["token"]
        A = self.auth("alice")
        base = f"/dav/{token}"
        self.client.request("PUT", f"{base}/orig.md", content=b"hello copy", headers=A)

        # COPY to NEW dest → 201; both exist
        r = self.client.request(
            "COPY", f"{base}/orig.md",
            headers={**A, "Destination": f"http://x{base}/dup.md"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(self.client.request("GET", f"{base}/orig.md", headers=A).content,
                         b"hello copy")
        self.assertEqual(self.client.request("GET", f"{base}/dup.md", headers=A).content,
                         b"hello copy")

        # COPY over EXISTING dest → 204 (RFC 4918)
        self.client.request("PUT", f"{base}/other.md", content=b"was here", headers=A)
        r = self.client.request(
            "COPY", f"{base}/orig.md",
            headers={**A, "Destination": f"http://x{base}/other.md"})
        self.assertEqual(r.status_code, 204, r.text)

        # Overwrite:F on existing dest → 412
        r = self.client.request(
            "COPY", f"{base}/orig.md",
            headers={**A, "Destination": f"http://x{base}/dup.md", "Overwrite": "F"})
        self.assertEqual(r.status_code, 412)

        # missing source → 404
        r = self.client.request(
            "COPY", f"{base}/nope.md",
            headers={**A, "Destination": f"http://x{base}/z.md"})
        self.assertEqual(r.status_code, 404)

    def test_move_overwrite_semantics(self):
        token = self.provision("alice", "mv")["token"]
        A = self.auth("alice")
        base = f"/dav/{token}"
        self.client.request("PUT", f"{base}/a.md", content=b"a", headers=A)
        self.client.request("PUT", f"{base}/b.md", content=b"b", headers=A)
        # Overwrite:F onto existing → 412
        r = self.client.request(
            "MOVE", f"{base}/a.md",
            headers={**A, "Destination": f"http://x{base}/b.md", "Overwrite": "F"})
        self.assertEqual(r.status_code, 412)
        # default overwrite onto existing → 204
        r = self.client.request(
            "MOVE", f"{base}/a.md", headers={**A, "Destination": f"http://x{base}/b.md"})
        self.assertEqual(r.status_code, 204)
        # missing source → 404
        r = self.client.request(
            "MOVE", f"{base}/a.md", headers={**A, "Destination": f"http://x{base}/c.md"})
        self.assertEqual(r.status_code, 404)

    def test_cross_token_destination_403(self):
        tokA = self.provision("alice", "sA")["token"]
        tokB = self.provision("alice", "sB")["token"]
        A = self.auth("alice")
        self.client.request("PUT", f"/dav/{tokA}/f.md", content=b"x", headers=A)
        for method in ("MOVE", "COPY"):
            r = self.client.request(
                method, f"/dav/{tokA}/f.md",
                headers={**A, "Destination": f"http://x/dav/{tokB}/f.md"})
            self.assertEqual(r.status_code, 403, (method, r.status_code))
            self.assertEqual(r.json()["error"], "CACHE_FORBIDDEN")

    def test_lock_unlock_and_lock_guard(self):
        token = self.provision("alice", "lk")["token"]
        A = self.auth("alice")
        base = f"/dav/{token}"
        self.client.request("PUT", f"{base}/f.md", content=b"v1", headers=A)
        r = self.client.request("LOCK", f"{base}/f.md",
                                headers={**A, "Timeout": "Second-120"})
        self.assertEqual(r.status_code, 200, r.text)
        locktoken = r.headers["Lock-Token"].strip("<>")
        self.assertIn("lockdiscovery", r.text)
        # holder may still write
        r = self.client.request("PUT", f"{base}/f.md", content=b"v2", headers=A)
        self.assertEqual(r.status_code, 201)
        r = self.client.request("UNLOCK", f"{base}/f.md",
                                headers={**A, "Lock-Token": f"<{locktoken}>"})
        self.assertEqual(r.status_code, 204)

    def test_put_size_cap_413(self):
        os.environ["BODESIGN_DAV_MAX_PUT_BYTES"] = "16"
        token = self.provision("alice", "cap")["token"]
        A = self.auth("alice")
        r = self.client.request("PUT", f"/dav/{token}/big.bin",
                                content=b"x" * 64, headers=A)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json()["error"], "PAYLOAD_TOO_LARGE")

    def test_traversal_defence_over_the_wire(self):
        token = self.provision("alice", "tr")["token"]
        A = self.auth("alice")
        r = self.client.request("PUT", f"/dav/{token}/..%2f..%2fescape.md",
                                content=b"evil", headers=A)
        self.assertIn(r.status_code, (403, 404))
        outside = (self.work / "sessions").parent / "escape.md"
        self.assertFalse(outside.exists())


@unittest.skipUnless(HAVE_STARLETTE, _STARLETTE_SKIP)
class WebdavIsolationTests(WebdavHttpBase):
    def test_wrong_credential_401_typed(self):
        token = self.provision("alice", "s")["token"]
        # no credential at all → 401 + WWW-Authenticate
        r = self.client.request("PROPFIND", f"/dav/{token}", headers={"Depth": "0"})
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.headers.get("WWW-Authenticate", "").startswith("Basic"))
        # lifecycle route: typed AUTH code in the body
        r = self.client.get("/caches")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"], "AUTH_REQUIRED")
        # wrong password → 401 (constant-time verify)
        r = self.client.request("PROPFIND", f"/dav/{token}",
                                headers={**_basic("alice", "wrong"), "Depth": "0"})
        self.assertEqual(r.status_code, 401)

    def test_valid_b_against_a_token_403(self):
        token = self.provision("alice", "s")["token"]
        base = f"/dav/{token}"
        B = self.auth("bob")
        for method, kwargs in (
            ("PROPFIND", {"headers": {**B, "Depth": "1"}}),
            ("GET", {"headers": B}),
            ("PUT", {"headers": B, "content": b"hijack"}),
            ("DELETE", {"headers": B}),
        ):
            r = self.client.request(method, f"{base}/x.md", **kwargs)
            self.assertEqual(r.status_code, 403, (method, r.status_code))
        # lifecycle: export/close by B are 403 too
        r = self.client.post(f"/caches/{token}/export",
                             json={"target": str(self.work / "l")}, headers=B)
        self.assertEqual(r.status_code, 403)
        r = self.client.post(f"/caches/{token}/close", json={}, headers=B)
        self.assertEqual(r.status_code, 403)
        # B's listing never leaks alice's cache
        r = self.client.get("/caches", headers=B)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 0)
        # alice's listing shows exactly her one cache
        r = self.client.get("/caches", headers=self.auth("alice"))
        self.assertEqual(r.json()["count"], 1)
        self.assertEqual(r.json()["caches"][0]["token"], token)

    def test_unknown_token_404(self):
        r = self.client.request("PROPFIND", "/dav/tok_deadbeef00000000",
                                headers={**self.auth("alice"), "Depth": "0"})
        self.assertEqual(r.status_code, 404)
        r = self.client.post("/caches/tok_deadbeef00000000/close",
                             json={}, headers=self.auth("alice"))
        self.assertEqual(r.status_code, 404)

    def test_export_target_unreachable_typed(self):
        token = self.provision("alice", "s")["token"]
        A = self.auth("alice")
        self.client.request("PUT", f"/dav/{token}/f.md", content=b"x", headers=A)
        r = self.client.post(
            f"/caches/{token}/export",
            json={"target": str(self.work / "no" / "such" / "dir")}, headers=A)
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json()["error"], "EXPORT_TARGET_UNREACHABLE")

    def test_soft_cap_warn_first_over_http(self):
        os.environ["BODESIGN_CACHE_SOFT_CAP_COUNT"] = "2"
        for i in range(2):
            sc = self.provision("alice", f"s{i}")["soft_cap"]
            self.assertFalse(sc["over"], sc)
        # third subject crosses the ceiling: STILL 201, but over=True
        sc = self.provision("alice", "s2")["soft_cap"]
        self.assertTrue(sc["over"] and sc["over_count"], sc)
        self.assertEqual((sc["count"], sc["count_cap"]), (3, 2))
        # a different owner is unaffected
        self.assertFalse(self.provision("bob", "s0")["soft_cap"]["over"])


if __name__ == "__main__":
    unittest.main()
