import importlib
import io
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class TokenStoreTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-tok-", dir=PRIVATE_BASE))
        os.environ["BODESIGN_SESSIONS_ROOT"] = str(self.work)
        self.ts = importlib.import_module("token_store")
        importlib.reload(self.ts)
        self.store = self.ts.TokenStore(root=self.work)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        os.environ.pop("BODESIGN_SESSIONS_ROOT", None)

    def test_stage_files_and_resolve(self):
        r = self.store.stage_files({"a.txt": {"content": "hi"}, "sub/b.md": {"content": "# x"}})
        self.assertTrue(r["token"].startswith("tok_"))
        self.assertEqual(sorted(r["files"]), ["a.txt", "sub/b.md"])
        doc_dir = self.store.resolve(r["token"])
        self.assertEqual((doc_dir / "a.txt").read_text(), "hi")

    def test_stage_tarball(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, data in [("proj/x.kicad_sch", b"sch"), ("proj/bom.csv", b"a,b")]:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        r = self.store.stage_tarball(buf.getvalue())
        self.assertIn("proj/x.kicad_sch", r["files"])
        self.assertIn("proj/bom.csv", r["files"])

    def test_tarball_traversal_rejected(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            data = b"evil"
            info = tarfile.TarInfo("../escape.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with self.assertRaises(self.ts.TokenError):
            self.store.stage_tarball(buf.getvalue())

    def test_safe_join_rejects_escape(self):
        _, doc_dir = self.store.new_token()
        with self.assertRaises(ValueError):
            self.store.safe_join(doc_dir, "../../etc/passwd")

    def test_resolve_unknown_token(self):
        with self.assertRaises(self.ts.TokenNotFoundError):
            self.store.resolve("tok_doesnotexist")


class TokenAwareDispatchTests(unittest.TestCase):
    """G11b: a tool call with `token` operates inside the token doc_dir and
    surfaces produced files. Uses emit_symbol (pure-python, no external deps)."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-tokdisp-", dir=PRIVATE_BASE))
        os.environ["BODESIGN_SESSIONS_ROOT"] = str(self.work)
        import token_store
        importlib.reload(token_store)
        self.server = importlib.import_module("services.mcp.server")
        self.store = token_store.TokenStore(root=self.work)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        os.environ.pop("BODESIGN_SESSIONS_ROOT", None)

    def test_token_call_resolves_paths_and_surfaces_produced(self):
        token, _ = self.store.new_token()
        result = self.server.run_tool("bodesign_emit_symbol", {
            "token": token,
            "symbol_name": "PART",
            "pins": [{"number": "1", "name": "VIN", "type": "S"}, {"number": "2", "name": "GND", "type": "S"}],
            "output_path": "gen/part.kicad_sym",
        })
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["token"], token)
        rels = [p["rel"] for p in result["produced"]]
        self.assertIn("gen/part.kicad_sym", rels)
        url = next(p["url"] for p in result["produced"] if p["rel"] == "gen/part.kicad_sym")
        self.assertEqual(url, f"/files/{token}/blob/gen/part.kicad_sym")
        # file actually written inside the token tree
        doc_dir = self.store.resolve(token)
        self.assertTrue((doc_dir / "gen" / "part.kicad_sym").is_file())

    def test_bad_token_is_error_data(self):
        result = self.server.run_tool("bodesign_emit_symbol", {"token": "tok_nope", "symbol_name": "X",
                                      "pins": [{"number": "1", "name": "A"}], "output_path": "x.kicad_sym"})
        self.assertFalse(result["ok"])
        self.assertIn("token", result["error"])


if __name__ == "__main__":
    unittest.main()
